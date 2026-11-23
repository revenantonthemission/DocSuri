"""U8's schema changes: A10's footprint, the one extension, the search indexes, the
sign-in limit tables, origin request identifiers and the disposable-database roles.

D14 and BR4.3/BR9.17: the scheduler's stand-in login drops only databases owned by the
disposable-databases role. The backup agent's stand-in login reads `docsuri_u8` and the
rehearsal-pattern databases, which it backs up, writes or drops none of them, has no
access to PlatformControl's store, and every database it creates is the disposable
role's (Step 6 test 7, the person's decision of 2026-10-22). PostgreSQL cannot limit
which names a login creates, so the agent's fixed command refuses any non-scratch name
(Step 26).
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row, tuple_row

from backend.local_profile import private_bytes
from docsuri_ops.arrangement import runtimes
from docsuri_ops.arrangement.paths import DATABASE_ROLES, REALM_DATABASES

ROOT = Path(__file__).resolve().parents[3]
PLATFORM = REALM_DATABASES.platform
STANDIN_KEYS = {
    DATABASE_ROLES.scheduler: "scheduler",
    DATABASE_ROLES.backup_agent: "backupAgent",
    DATABASE_ROLES.operator: "operator",
    DATABASE_ROLES.restore: "restore",
}
OWNER_LOGINS = (
    "accounts", "assistance", "corpus", "discovery", "export", "library", "operations",
    "personalization", "research", "topics", "usage",
)
ORIGIN_COLUMNS = (
    ("research", "job"), ("assistance", "job"), ("export", "effect"),
    ("accounts", "lifecycle_request"),
)
LIMIT_TABLES = ("entry_address_limit", "entry_email_failure", "entry_shared_limit")
# Creating or dropping a database copies or removes whole files and can pass the
# realm's 3 s statement bound; these sessions set their own, as the agent's command does.
DATABASE_STATEMENT_TIMEOUT = "60s"


@pytest.fixture
def secrets_of(realm):
    def read(name: str) -> dict:
        value = json.loads(private_bytes(realm.root / name))
        if "runId" in value:
            assert value["runId"] == realm.run_id
        return value

    return read


@pytest.fixture
def login(realm, secrets_of):
    """A connection as a stand-in login, the realm's superuser or an owner login."""
    opened = []

    def open_login(role: str, *, dbname: str = "postgres", autocommit: bool = True):
        if role == "postgres":
            password = secrets_of("migration-credentials.json")["databaseAdminPassword"]
        elif role in STANDIN_KEYS:
            password = secrets_of("standin-credentials.json")["roles"][STANDIN_KEYS[role]]
        else:
            password = secrets_of("owner-credentials.json")["roles"][role.removeprefix("docsuri_")]
        conn = psycopg.connect(
            host="127.0.0.1", port=realm.database_port, dbname=dbname, user=role,
            password=password, connect_timeout=3, autocommit=autocommit, row_factory=dict_row,
        )
        opened.append(conn)
        if autocommit:
            conn.execute(sql.SQL("SET statement_timeout = {}").format(
                sql.Literal(DATABASE_STATEMENT_TIMEOUT)))
        return conn

    yield open_login
    for conn in opened:
        conn.close()


@contextmanager
def disposable_database(login, kind: str):
    """A database of one disposable kind, created by the backup agent's stand-in acting
    as the disposable role, as the agent's command creates one, and always removed."""
    name = REALM_DATABASES.new(kind)
    agent = login(DATABASE_ROLES.backup_agent)
    agent.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(DATABASE_ROLES.disposable)))
    agent.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    agent.execute("RESET ROLE")
    try:
        yield name
    finally:
        login("postgres").execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


def database_owner(login, name: str) -> str | None:
    row = login("postgres").execute(
        "SELECT pg_get_userbyid(datdba) AS owner FROM pg_database WHERE datname=%s", (name,)
    ).fetchone()
    return None if row is None else row["owner"]


# 1. A10's footprint ----------------------------------------------------------------------


def test_the_footprint_counts_the_instance_wal_in_the_realm_database(connect, login):
    with connect("operations") as conn:
        footprint = conn.execute("SELECT * FROM operations.capacity_footprint()").fetchone()
    instance_wal = login("postgres", dbname="docsuri_u8").execute(
        "SELECT coalesce(sum(size),0)::bigint AS wal FROM pg_ls_waldir()").fetchone()["wal"]
    assert instance_wal > 0
    assert footprint["wal_bytes"] > 0
    assert abs(footprint["wal_bytes"] - instance_wal) <= 64 * 1024**2
    assert footprint["database_bytes"] > 0


def test_the_footprint_counts_wal_in_a_rehearsal_named_database(login):
    definition = (ROOT / "ops/src/docsuri_ops/u8_capacity.sql").read_text()
    with disposable_database(login, "rehearsal") as name:
        assert REALM_DATABASES.kind_of(name) == "rehearsal"
        admin = login("postgres", dbname=name, autocommit=False)
        admin.execute("CREATE SCHEMA operations AUTHORIZATION docsuri_operations_owner")
        admin.execute(
            "GRANT EXECUTE ON FUNCTION pg_catalog.pg_ls_waldir() TO docsuri_operations_owner"
        )
        admin.execute("SET LOCAL ROLE docsuri_operations_owner")
        admin.execute(definition, prepare=False)
        admin.execute("RESET ROLE")
        footprint = admin.execute("SELECT * FROM operations.capacity_footprint()").fetchone()
        admin.rollback()
        admin.close()
    assert footprint["wal_bytes"] > 0 and footprint["database_bytes"] > 0


# 2. The one extension (D14) --------------------------------------------------------------


def test_pgvector_is_in_template1_and_every_later_database(login):
    for name in ("template1", "docsuri_u8"):
        conn = login("postgres", dbname=name)
        version = conn.execute(
            "SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()
        conn.close()  # a session on template1 would block every CREATE DATABASE
        assert version == {"extversion": runtimes.PGVECTOR.version}, name
    with disposable_database(login, "scratch") as name:
        version = login(DATABASE_ROLES.backup_agent, dbname=name).execute(
            "SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()
        assert version == {"extversion": runtimes.PGVECTOR.version}


def test_no_login_but_the_superuser_can_create_another_extension(login):
    available = {row["name"] for row in login("postgres").execute(
        "SELECT name FROM pg_available_extensions").fetchall()}
    assert available == set(runtimes.DATABASE_EXTENSIONS)
    for role in [f"docsuri_{owner}" for owner in OWNER_LOGINS] + list(STANDIN_KEYS):
        # A login that may not even connect (the scheduler) cannot either.
        with pytest.raises(psycopg.Error):
            login(role, dbname="docsuri_u8").execute("CREATE EXTENSION pg_trgm")
    with disposable_database(login, "scratch") as name:
        for role in (DATABASE_ROLES.backup_agent, DATABASE_ROLES.scheduler):
            conn = login(role, dbname=name)
            for extension in ("pg_trgm", "hstore", "pgcrypto"):
                with pytest.raises(psycopg.Error):
                    conn.execute(sql.SQL("CREATE EXTENSION {}").format(sql.Identifier(extension)))
        assert {row["extname"] for row in login("postgres", dbname=name).execute(
            "SELECT extname FROM pg_extension").fetchall()} == set(runtimes.DATABASE_EXTENSIONS)


# 3. The search indexes -------------------------------------------------------------------


def test_the_hnsw_and_gin_indexes_exist_with_their_parameters(connect):
    with connect("corpus") as conn:
        rows = {row["indexname"]: row["indexdef"] for row in conn.execute(
            "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname='corpus'").fetchall()}
        column = conn.execute(
            "SELECT format_type(atttypid, atttypmod) AS kind FROM pg_attribute "
            "WHERE attrelid='corpus.projection'::regclass AND attname='embedding_vector' "
            "AND NOT attisdropped").fetchone()
    assert column == {"kind": "vector(1024)"}
    hnsw = rows["projection_embedding_hnsw"]
    assert "USING hnsw (embedding_vector " in hnsw and "vector_cosine_ops)" in hnsw
    assert "m='16'" in hnsw and "ef_construction='64'" in hnsw
    assert "USING gin (lexical_all)" in rows["version_lexical_all"]
    assert "USING gin (lexical)" in rows["projection_lexical"], "U3's per-chunk index stays"


def test_chunks_write_the_vector_and_the_per_version_words_beside_them(connect):
    with connect("corpus") as conn:
        conn.execute(
            "INSERT INTO corpus.paper(id,title,authors,metadata) VALUES('u8-schema-paper',"
            "'synthetic','[]','{}')")
        conn.execute(
            "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
            "private_path,purpose,provenance,content) VALUES('u8-schema-v1','u8-schema-paper',"
            "'https://example.invalid/p',%s,'v1','synthetic','local-research','{}','{}')",
            ("c" * 64,))
        vector = [0.0] * 1023 + [1.0]
        conn.execute(
            "INSERT INTO corpus.projection(version_id,ordinal,content_hash,anchor,section,"
            "text_content,embedding) VALUES ('u8-schema-v1',0,%s,'a0','body','alpha harbor',%s),"
            "('u8-schema-v1',1,%s,'a1','body','lantern beta',NULL)",
            ("d" * 64, vector, "e" * 64))
        row = conn.execute(
            "SELECT embedding_vector::text AS vector FROM corpus.projection "
            "WHERE version_id='u8-schema-v1' AND ordinal=0").fetchone()
        assert row["vector"].endswith(",1]")
        words = conn.execute(
            "SELECT lexical_all @@ plainto_tsquery('simple','harbor lantern') AS both "
            "FROM corpus.version WHERE id='u8-schema-v1'").fetchone()
        assert words["both"] is True
        conn.execute("DELETE FROM corpus.projection WHERE version_id='u8-schema-v1'")
        emptied = conn.execute(
            "SELECT lexical_all FROM corpus.version WHERE id='u8-schema-v1'").fetchone()
        assert emptied["lexical_all"] is None
        conn.rollback()


# 4. Sign-in limits keep keyed digests only -----------------------------------------------


def test_the_sign_in_limit_tables_hold_no_raw_address_or_email(connect):
    with connect("accounts") as conn:
        for table in LIMIT_TABLES:
            columns = {row["column_name"]: row["data_type"] for row in conn.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema='accounts' AND table_name=%s", (table,)).fetchall()}
            assert columns, table
            text_columns = {name for name, kind in columns.items() if kind == "text"}
            assert all(name.endswith("_digest") for name in text_columns), table
            assert not {"address", "email", "ip", "client_address"} & set(columns), table
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "INSERT INTO accounts.entry_email_failure(email_digest,window_started_at,"
                "failures,last_failure_at) VALUES('person@example.invalid',now(),1,now())")
        conn.rollback()
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "INSERT INTO accounts.entry_address_limit VALUES('203.0.113.7',1,1)")
        conn.rollback()


# 4a. The account-mail outbox and the daily count (Step 53(h)-(i); L1-69, L1-71) -------------

OUTBOX_FILE = "backend/modules/accounts/u8_mail_outbox.sql"
OUTBOX_TABLES = ("mail_outbox", "mail_sender_beat", "mail_account_limit")


def table_columns(conn, table: str) -> dict:
    return {row["column_name"]: (row["data_type"], row["is_nullable"]) for row in conn.execute(
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_schema='accounts' AND table_name=%s", (table,)).fetchall()}


def primary_key(conn, table: str) -> list[str]:
    return [row["attname"] for row in conn.execute(
        "SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid "
        "AND a.attnum=ANY(i.indkey) WHERE i.indrelid=%s::regclass AND i.indisprimary "
        "ORDER BY array_position(i.indkey, a.attnum)", (f"accounts.{table}",)).fetchall()]


def new_account(conn) -> object:
    account = uuid4()
    conn.execute(
        "INSERT INTO accounts.account(id,email,password_hash,display_name) "
        "VALUES(%s,%s,'!test','outbox schema')", (account, f"outbox-{account.hex}@example.test"))
    return account


def new_challenge(conn, account) -> object:
    challenge = uuid4()
    conn.execute(
        "INSERT INTO accounts.challenge(id,account_id,proof_hash,authority_revision,expires_at,"
        "purpose,delivery) VALUES(%s,%s,%s,%s,clock_timestamp()+interval '5 minutes',"
        "'verify-email','acknowledged')", (challenge, account, uuid4().hex * 2, uuid4()))
    return challenge


def new_proof(conn, account, purpose: str = "password-reset") -> object:
    proof = uuid4()
    conn.execute(
        "INSERT INTO accounts.control_proof(id,account_id,purpose,proof_hash,flow_hash,"
        "authority_revision,lifecycle_revision,expires_at) VALUES(%s,%s,%s,%s,%s,%s,%s,"
        "clock_timestamp()+interval '5 minutes')",
        (proof, account, purpose, uuid4().hex * 2, uuid4().hex * 2, uuid4(), uuid4()))
    return proof


def outbox_row(conn, purpose: str, *, challenge=None, proof=None) -> object:
    key = uuid4()
    conn.execute(
        "INSERT INTO accounts.mail_outbox(message_key,purpose,challenge_id,control_proof_id,"
        "protected_payload,key_version,queued_at) VALUES(%s,%s,%s,%s,'\\x00','test',now())",
        (key, purpose, challenge, proof))
    return key


def refused(conn, error, statement: str, params: tuple = ()) -> None:
    with pytest.raises(error), conn.transaction():
        conn.execute(statement, params)


def test_the_account_mail_outbox_tables(login, connect):
    """Step 53(h)-(i)'s three tables, each write in a transaction rolled back at the end,
    U2's own delete statements run as the accounts owner (as Step 48(a) acts as its
    owner), and the grants to `docsuri_accounts` alone."""
    from backend import u8_migrations
    from backend.modules.operations.restore_checks import personal_columns
    from backend.u8_registry import chain_files_of

    conn = login("postgres", dbname="docsuri_u8", autocommit=False)
    try:
        assert table_columns(conn, "mail_outbox") == {
            "message_key": ("uuid", "NO"), "purpose": ("text", "NO"),
            "challenge_id": ("uuid", "YES"), "control_proof_id": ("uuid", "YES"),
            "protected_payload": ("bytea", "NO"), "key_version": ("text", "NO"),
            "queued_at": ("timestamp with time zone", "NO"),
            "attempted_at": ("timestamp with time zone", "YES"),
        }
        assert primary_key(conn, "mail_outbox") == ["message_key"]
        assert table_columns(conn, "mail_sender_beat") == {
            "singleton": ("boolean", "NO"), "beat_at": ("timestamp with time zone", "NO")}
        assert primary_key(conn, "mail_sender_beat") == ["singleton"]
        assert table_columns(conn, "mail_account_limit") == {
            "account_id": ("uuid", "NO"), "day": ("bigint", "NO"),
            "messages": ("integer", "NO")}
        assert primary_key(conn, "mail_account_limit") == ["account_id", "day"]
        cascades = {row["table"]: (row["referenced"], row["action"]) for row in conn.execute(
            "SELECT conrelid::regclass::text || '.' || a.attname AS table, "
            "confrelid::regclass::text AS referenced, confdeltype AS action "
            "FROM pg_constraint c JOIN pg_attribute a ON a.attrelid=c.conrelid "
            "AND a.attnum=c.conkey[1] WHERE c.contype='f' AND c.conrelid = ANY(ARRAY["
            "'accounts.mail_outbox'::regclass,'accounts.mail_account_limit'::regclass])"
        ).fetchall()}
        assert cascades == {
            "accounts.mail_outbox.challenge_id": ("accounts.challenge", "c"),
            "accounts.mail_outbox.control_proof_id": ("accounts.control_proof", "c"),
            "accounts.mail_account_limit.account_id": ("accounts.account", "c"),
        }

        # The beat holds at most one row.
        conn.execute("INSERT INTO accounts.mail_sender_beat(beat_at) VALUES(now())")
        refused(conn, psycopg.errors.UniqueViolation,
                "INSERT INTO accounts.mail_sender_beat(beat_at) VALUES(now())")
        refused(conn, psycopg.errors.CheckViolation,
                "INSERT INTO accounts.mail_sender_beat(singleton,beat_at) VALUES(false,now())")

        # The purpose and the one reference that matches it.
        account = new_account(conn)
        challenge, proof = new_challenge(conn, account), new_proof(conn, account)
        reactivation = new_proof(conn, account, "reactivate")
        refused(conn, psycopg.errors.CheckViolation,
                "INSERT INTO accounts.mail_outbox(message_key,purpose,control_proof_id,"
                "protected_payload,key_version,queued_at) VALUES(%s,'email-change',%s,"
                "'\\x00','test',now())", (uuid4(), proof))
        for purpose, references in (
            ("password-reset", {"challenge": None, "proof": None}),
            ("password-reset", {"challenge": challenge, "proof": proof}),
            ("password-reset", {"challenge": challenge, "proof": None}),
            ("verification", {"challenge": None, "proof": proof}),
            ("reactivation", {"challenge": challenge, "proof": None}),
        ):
            with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
                outbox_row(conn, purpose, **references)
        by_challenge = outbox_row(conn, "verification", challenge=challenge)
        by_proof = outbox_row(conn, "password-reset", proof=proof)
        by_reactivation = outbox_row(conn, "reactivation", proof=reactivation)

        # The count's checks.
        conn.execute("INSERT INTO accounts.mail_account_limit VALUES(%s,1,90)", (account,))
        for day, messages in ((-1, 1), (2, 0), (3, 91)):
            refused(conn, psycopg.errors.CheckViolation,
                    "INSERT INTO accounts.mail_account_limit VALUES(%s,%s,%s)",
                    (account, day, messages))

        # U2's own statements, as the accounts owner, take the rows by the cascade.
        conn.execute("SET LOCAL ROLE docsuri_accounts_owner")
        conn.execute("DELETE FROM accounts.delivery WHERE challenge_id IN (SELECT id FROM "
                     "accounts.challenge WHERE account_id=%s)", (account,))
        conn.execute("DELETE FROM accounts.challenge WHERE account_id=%s", (account,))
        conn.execute("DELETE FROM accounts.control_proof WHERE account_id=%s AND "
                     "purpose<>'reauthenticate'", (account,))
        left = conn.execute(
            "SELECT count(*) AS n FROM accounts.mail_outbox WHERE message_key=ANY(%s)",
            ([by_challenge, by_proof, by_reactivation],)).fetchone()["n"]
        assert left == 0
        # Deleting the account removes its counts by the cascade.
        conn.execute("DELETE FROM accounts.account WHERE id=%s", (account,))
        assert conn.execute("SELECT count(*) AS n FROM accounts.mail_account_limit "
                            "WHERE account_id=%s", (account,)).fetchone()["n"] == 0
        conn.execute("RESET ROLE")

        # Grants: docsuri_accounts holds the four privileges on each table.
        for table in OUTBOX_TABLES:
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                assert conn.execute(
                    "SELECT has_table_privilege('docsuri_accounts', %s, %s) AS held",
                    (f"accounts.{table}", privilege)).fetchone()["held"], (table, privilege)

        # A tombstone replay removes an erased owner's counts. `personal_columns` reads
        # plain rows, as the restore check's own connection gives them.
        conn.row_factory = tuple_row
        assert ("accounts", "mail_account_limit", "account_id") in personal_columns(conn)
        conn.row_factory = dict_row
    finally:
        conn.rollback()
    library = connect("library")
    try:
        for table in OUTBOX_TABLES:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                library.execute(f"SELECT 1 FROM accounts.{table}")
            library.rollback()
    finally:
        library.rollback()

    owned = [file for owner, file in u8_migrations.migrations() if file == OUTBOX_FILE]
    files = u8_migrations.chain_files()
    assert files.count(OUTBOX_FILE) == 1
    assert {file: role for role, file in u8_migrations.migrations()}[OUTBOX_FILE] == "accounts"
    assert owned == [OUTBOX_FILE]
    origins = [file for _, file in u8_migrations.U8_FILES]
    # Only the connection-owner read (your answer of 2026-11-11) follows the outbox.
    assert origins[origins.index(OUTBOX_FILE) + 1:] == [OWNER_READ_FILE]
    assert origins.index("ops/src/docsuri_ops/u8_observation_drops.sql") < origins.index(
        OUTBOX_FILE)
    assert OUTBOX_FILE in chain_files_of("service-operations")


# 4b. The Notion connection's owner read (your answer of 2026-11-11, "Wire the owner read")


OWNER_READ_FILE = "backend/modules/export/u8_export_connection_owner.sql"
OWNER_READ = "export.connection_owner(uuid)"


def test_the_connection_owner_read_answers_one_owner_to_operations_alone(login, connect):
    """ApprovedExport's definer function answers a connection's owning account, a pending
    row's included, to ServiceOperations' login, which holds no privilege on the table;
    every other owner login, the export login among them, and PUBLIC cannot execute it.
    The rows are written as the export login and rolled back at the end."""
    from backend import u8_migrations
    from backend.u8_registry import chain_files_of

    conn = login("postgres", dbname="docsuri_u8", autocommit=False)
    try:
        definition = conn.execute(
            "SELECT p.prosecdef AS definer, p.provolatile AS volatility, "
            "pg_get_userbyid(p.proowner) AS owner, p.proconfig AS config, "
            "pg_get_function_result(p.oid) AS result FROM pg_proc p "
            "WHERE p.oid=%s::regprocedure", (OWNER_READ,)).fetchone()
        assert definition == {"definer": True, "volatility": "s",
                              "owner": "docsuri_export_owner",
                              "config": ["search_path=pg_catalog"], "result": "uuid"}
        executors = {role for role in OWNER_LOGINS if conn.execute(
            "SELECT has_function_privilege(%s, %s, 'EXECUTE') AS held",
            (f"docsuri_{role}", OWNER_READ)).fetchone()["held"]}
        assert executors == {"operations"}
        assert not conn.execute(
            "SELECT bool_or(a.grantee = 0) AS public FROM pg_proc p, "
            "aclexplode(p.proacl) a WHERE p.oid=%s::regprocedure",
            (OWNER_READ,)).fetchone()["public"]
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            assert not conn.execute(
                "SELECT has_table_privilege('docsuri_operations','export.connection',%s) "
                "AS held", (privilege,)).fetchone()["held"], privilege
        pending, connected_owner = uuid4(), uuid4()
        connection = uuid4()
        conn.execute("SET LOCAL ROLE docsuri_export")
        conn.execute(
            "INSERT INTO export.connection(id,account_id,revision,state,pending_holder,"
            "pending_started_at) VALUES(%s,%s,0,'pending',%s,clock_timestamp())",
            (connection, connected_owner, uuid4()))
        conn.execute("RESET ROLE")
        conn.execute("SET LOCAL ROLE docsuri_operations")
        assert conn.execute("SELECT export.connection_owner(%s) AS owner",
                            (connection,)).fetchone()["owner"] == connected_owner
        assert conn.execute("SELECT export.connection_owner(%s) AS owner",
                            (pending,)).fetchone()["owner"] is None  # an unknown id
        refused(conn, psycopg.errors.InsufficientPrivilege,
                "SELECT account_id FROM export.connection WHERE id=%s", (connection,))
        conn.execute("RESET ROLE")
    finally:
        conn.rollback()
    for role in ("export", "accounts", "library"):
        other = connect(role)
        try:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                other.execute("SELECT export.connection_owner(%s)", (uuid4(),))
        finally:
            other.rollback()

    assert u8_migrations.chain_files().count(OWNER_READ_FILE) == 1
    assert {file: role for role, file in u8_migrations.migrations()}[OWNER_READ_FILE] == (
        "export")
    assert [file for _, file in u8_migrations.U8_FILES][-1] == OWNER_READ_FILE
    assert OWNER_READ_FILE in chain_files_of("service-operations")


# 5. Origin request identifiers -----------------------------------------------------------


REQUEST_SETTING = "current_setting('docsuri.request_id'"


def origin_default(conn, schema: str, table: str) -> dict:
    return conn.execute(
        "SELECT a.attnotnull AS not_null, format_type(a.atttypid, a.atttypmod) AS kind, "
        "pg_get_expr(d.adbin, d.adrelid) AS expression FROM pg_attribute a "
        "LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum "
        "WHERE a.attrelid=%s::regclass AND a.attname='origin_request_id' "
        "AND NOT a.attisdropped", (f"{schema}.{table}",)).fetchone()


def evaluate(conn, expression: str):
    return conn.execute(sql.SQL("SELECT {} AS value").format(sql.SQL(expression))).fetchone()[
        "value"]


def plant_request(conn, request) -> None:
    conn.execute("SELECT set_config('docsuri.request_id', %s, true)", (str(request),))


def insert_research_job(conn) -> object:
    """A novelty analysis in a context of its own; it needs no session (u4_schema.sql)."""
    owner, context, job = uuid4(), uuid4(), uuid4()
    conn.execute("INSERT INTO research.context(id,owner_id,purpose) VALUES(%s,%s,'novelty')",
                 (context, owner))
    conn.execute(
        "INSERT INTO research.job(id,owner_id,context_id,authority_session,kind,"
        "operation_key,input_hash,input,scope,policy,usage_id) "
        "VALUES(%s,%s,%s,%s,'novelty-analysis',%s,%s,'{}','{}',%s,%s)",
        (job, owner, context, uuid4(), "origin-" + uuid4().hex, "0" * 64,
         json.dumps({"policyId": "u4-synthetic-research", "revision": "1"}), uuid4()))
    return conn.execute("SELECT origin_request_id FROM research.job WHERE id=%s",
                        (job,)).fetchone()["origin_request_id"]


def test_the_origin_request_columns_default_to_the_transactions_request(login, connect):
    """L1-6: each column is a nullable uuid whose default reads the transaction-local
    request identifier, NULL once that transaction has ended or on a fresh connection.
    Read through the realm's catalogue owner, which may resolve every owner's schema."""
    conn = login("postgres", dbname="docsuri_u8", autocommit=False)
    expressions = set()
    for schema, table in ORIGIN_COLUMNS:
        row = origin_default(conn, schema, table)
        assert row["not_null"] is False and row["kind"] == "uuid", table
        assert REQUEST_SETTING in (row["expression"] or ""), table
        expressions.add(row["expression"])
    planted = uuid4()
    for expression in expressions:
        plant_request(conn, planted)
        assert evaluate(conn, expression) == planted
        conn.commit()
        assert evaluate(conn, expression) is None
        conn.rollback()
        fresh = login("postgres", dbname="docsuri_u8", autocommit=False)
        assert evaluate(fresh, expression) is None
        fresh.rollback()
    research = connect("research")
    plant_request(research, planted)
    assert insert_research_job(research) == planted
    research.rollback()
    assert insert_research_job(research) is None
    research.rollback()


def test_the_observation_record_counts_dropped_observations(connect):
    with connect("operations") as conn:
        column = conn.execute(
            "SELECT format_type(a.atttypid, a.atttypmod) AS kind, a.attnotnull AS not_null, "
            "pg_get_expr(d.adbin, d.adrelid) AS expression FROM pg_attribute a "
            "LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum "
            "WHERE a.attrelid='operations.observation_record'::regclass "
            "AND a.attname='dropped_count' AND NOT a.attisdropped").fetchone()
        assert column == {"kind": "integer", "not_null": True, "expression": "0"}
        record = ("INSERT INTO operations.observation_record(id,capability,producer,outcome,"
                  "revision,observed_at{extra}) VALUES(%s,'search','search','available',1,"
                  "clock_timestamp(){value}) RETURNING dropped_count")
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(record.format(extra=",dropped_count", value=",-1"), (uuid4(),))
        conn.rollback()
        stored = conn.execute(record.format(extra="", value=""), (uuid4(),)).fetchone()
        conn.rollback()
    assert stored == {"dropped_count": 0}


# 6. The scheduler drops only disposable databases ----------------------------------------


def test_the_scheduler_drops_a_disposable_database_and_never_the_realm_or_platform(login):
    with disposable_database(login, "scratch") as name:
        assert database_owner(login, name) == DATABASE_ROLES.disposable
        login(DATABASE_ROLES.scheduler).execute(
            sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
        assert database_owner(login, name) is None
    scheduler = login(DATABASE_ROLES.scheduler)
    for protected in ("docsuri_u8", PLATFORM):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            scheduler.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(protected)))
        assert database_owner(login, protected) == "postgres"


# 7. The backup agent reads what it backs up and changes none of it -----------------------


@contextmanager
def rehearsal_database(login):
    """A rehearsal-pattern database as production's environment tool makes one: created
    by the superuser, owned by the disposable role, holding an owner's table and row."""
    name = REALM_DATABASES.new("rehearsal")
    admin = login("postgres")
    admin.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
        sql.Identifier(name), sql.Identifier(DATABASE_ROLES.disposable)))
    try:
        inside = login("postgres", dbname=name)
        inside.execute("CREATE SCHEMA rehearsed AUTHORIZATION docsuri_operations_owner")
        inside.execute("SET ROLE docsuri_operations_owner")
        inside.execute("CREATE TABLE rehearsed.record (id integer PRIMARY KEY)")
        inside.execute("INSERT INTO rehearsed.record VALUES (1)")
        inside.close()
        yield name
    finally:
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


def agent_memberships(login) -> dict:
    rows = login("postgres").execute(
        "SELECT b.rolname AS role, m.inherit_option AS inherits, m.set_option AS sets "
        "FROM pg_auth_members m JOIN pg_roles b ON b.oid=m.roleid "
        "WHERE m.member=(SELECT oid FROM pg_roles WHERE rolname=%s)",
        (DATABASE_ROLES.backup_agent,)).fetchall()
    return {row["role"]: (row["inherits"], row["sets"]) for row in rows}


def test_the_agent_holds_read_access_and_no_write_privilege(login):
    assert agent_memberships(login) == {
        DATABASE_ROLES.disposable: (False, True),  # create as it, never own through it
        "pg_read_all_data": (True, False),
    }
    flags = {row["rolname"]: row for row in login("postgres").execute(
        "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolbypassrls FROM pg_roles "
        "WHERE rolname IN (%s,%s)",
        (DATABASE_ROLES.backup_agent, DATABASE_ROLES.disposable)).fetchall()}
    assert flags[DATABASE_ROLES.backup_agent] == {
        "rolname": DATABASE_ROLES.backup_agent, "rolsuper": False, "rolcreatedb": False,
        "rolcreaterole": False, "rolbypassrls": False}
    assert flags[DATABASE_ROLES.disposable]["rolcreatedb"] is True
    with rehearsal_database(login) as rehearsal:
        rights = login("postgres").execute(
            "SELECT pg_has_role(%(agent)s,'pg_write_all_data','USAGE') AS writes_all, "
            "pg_has_role(%(agent)s,%(disposable)s,'USAGE') AS owns_disposable, "
            "has_database_privilege(%(agent)s,'docsuri_u8','CREATE') AS creates_realm, "
            "has_database_privilege(%(agent)s,%(rehearsal)s,'CREATE') AS creates_rehearsal",
            {"agent": DATABASE_ROLES.backup_agent, "disposable": DATABASE_ROLES.disposable,
             "rehearsal": rehearsal}).fetchone()
    assert rights == {"writes_all": False, "owns_disposable": False,
                      "creates_realm": False, "creates_rehearsal": False}


def test_the_agent_reads_the_realm_and_a_rehearsal_database(login):
    realm = login(DATABASE_ROLES.backup_agent, dbname="docsuri_u8")
    identity = realm.execute(
        "SELECT count(*) AS rows FROM public.docsuri_local_identity"
    ).fetchone()
    assert identity == {"rows": 1}
    with rehearsal_database(login) as rehearsal:
        rows = login(DATABASE_ROLES.backup_agent, dbname=rehearsal).execute(
            "SELECT id FROM rehearsed.record").fetchall()
    assert rows == [{"id": 1}]


@pytest.mark.parametrize("statement", [
    "INSERT INTO {table} SELECT * FROM {table}",
    "DELETE FROM {table}",
    "CREATE TABLE public.agent_written (id integer)",
    "CREATE SCHEMA agent_written",
])
def test_a_write_by_the_agent_is_refused_in_the_realm_and_a_rehearsal_database(
        login, statement):
    realm = login(DATABASE_ROLES.backup_agent, dbname="docsuri_u8")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        realm.execute(statement.format(table="public.docsuri_local_identity"))
    with rehearsal_database(login) as rehearsal:
        inside = login(DATABASE_ROLES.backup_agent, dbname=rehearsal)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            inside.execute(statement.format(table="rehearsed.record"))
        inside.close()
        assert login("postgres", dbname=rehearsal).execute(
            "SELECT count(*) AS rows FROM rehearsed.record").fetchone() == {"rows": 1}


def test_a_drop_by_the_agent_is_refused_for_the_realm_and_a_rehearsal_database(login):
    agent = login(DATABASE_ROLES.backup_agent)
    with rehearsal_database(login) as rehearsal:
        for target in ("docsuri_u8", rehearsal):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                agent.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(target)))
        assert database_owner(login, rehearsal) == DATABASE_ROLES.disposable
    assert database_owner(login, "docsuri_u8") == "postgres"


def test_connecting_to_the_platform_store_is_refused_for_the_agent(login):
    with pytest.raises(psycopg.OperationalError, match="permission denied"):
        login(DATABASE_ROLES.backup_agent, dbname=PLATFORM)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        login(DATABASE_ROLES.backup_agent).execute(
            sql.SQL("DROP DATABASE {}").format(sql.Identifier(PLATFORM)))
    assert database_owner(login, PLATFORM) == "postgres"


def test_every_database_the_agent_creates_is_the_disposable_roles(login):
    agent = login(DATABASE_ROLES.backup_agent)
    refused = REALM_DATABASES.new("scratch")
    # As itself the login may create no database, and it may name no other owner.
    for statement in ("CREATE DATABASE {}", "CREATE DATABASE {} OWNER docsuri_operations_owner",
                      "CREATE DATABASE {} OWNER docsuri_backup_agent"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            agent.execute(sql.SQL(statement).format(sql.Identifier(refused)))
    assert database_owner(login, refused) is None
    with disposable_database(login, "scratch") as name:
        assert database_owner(login, name) == DATABASE_ROLES.disposable
        # Acting as the role, it still names no other owner.
        agent.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(DATABASE_ROLES.disposable)))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            agent.execute(sql.SQL("CREATE DATABASE {} OWNER docsuri_operations_owner").format(
                sql.Identifier(refused)))
        agent.execute("RESET ROLE")
    assert database_owner(login, refused) is None


# 8. Every realm login's privileges equal the pinned inventory (L1-50) --------------------


@pytest.fixture
def runner():
    from scripts import verify_docsuri_u8

    return verify_docsuri_u8


def inventory_difference(current: tuple[str, ...], expected: tuple[str, ...]) -> str:
    added = sorted(set(current) - set(expected))
    removed = sorted(set(expected) - set(current))
    return f"rows added: {added}; rows removed: {removed}"


def test_every_realm_logins_privileges_equal_the_pinned_inventory(login, runner):
    pin = (ROOT / runner.REALM_PRIVILEGES).read_bytes()
    assert hashlib.sha256(pin).hexdigest() == runner.REALM_PRIVILEGES_SHA256
    pinned = tuple(pin.decode().splitlines())
    realm = login("postgres", dbname="docsuri_u8", autocommit=False)
    store = login("postgres", dbname=PLATFORM, autocommit=False)
    current = runner.privilege_inventory(realm, store)
    assert current == pinned, inventory_difference(current, pinned)
    changes = (
        (realm, "GRANT SELECT ON export.connection TO docsuri_library"),
        (store, "GRANT EXECUTE ON FUNCTION platform_control.u8_mark_executing(uuid) "
                "TO docsuri_u8_platform_reader"),
        (realm, "GRANT docsuri_accounts_owner TO platform_control_runtime"),
    )
    for conn, statement in changes:
        with conn.transaction(force_rollback=True):
            conn.execute(statement)
            changed = runner.privilege_inventory(realm, store)
        assert len(set(changed) - set(pinned)) == 1, (statement, inventory_difference(
            changed, pinned))
        assert not set(pinned) - set(changed), (statement, inventory_difference(
            changed, pinned))
    after = runner.privilege_inventory(realm, store)
    realm.rollback()
    store.rollback()
    assert after == pinned, inventory_difference(after, pinned)


# 9. A migrated realm holds its search cursor key (L1-4) ----------------------------------


def test_a_migrated_realm_holds_its_cursor_key(realm, runner):
    """Until Step 72(a) moves the search-cursor key, the database phase must run before
    any phase that composes the complete host in a realm: component (component-2 at
    least, whose tests call `compose(realm)`), integration, operations and serve. Every
    composition runs `start_keys` (`backend/u8_host.py`, called from `compose`), which
    creates `search-cursor.key` in the realm root through
    `ensure_key_file(profile.root / CURSOR_KEY)`, and this test's last assertion refuses
    that file."""
    folder = realm.root / "cursor-key"
    folder_info = folder.lstat()
    assert stat.S_ISDIR(folder_info.st_mode) and stat.S_IMODE(folder_info.st_mode) == 0o700
    assert "cursor-key" in runner.KEY_FOLDERS
    key = folder / "search-cursor.key"
    info = key.lstat()
    assert stat.S_ISREG(info.st_mode) and not stat.S_ISLNK(info.st_mode)
    assert info.st_size == 32
    assert stat.S_IMODE(info.st_mode) == 0o600
    assert info.st_nlink == 1
    assert info.st_uid == os.getuid()
    root_key = realm.root / "search-cursor.key"
    assert not (root_key.exists() or root_key.is_symlink())
