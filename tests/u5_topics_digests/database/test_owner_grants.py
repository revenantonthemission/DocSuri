"""Step 17 (a)-(c): who may read and write what, read from the realm's own catalog.

U5's chain gives the topics login (`docsuri_topics`) exactly these grants outside its
own schema (NFR1.2, NFR2.2). The runner's base install grants USAGE on `public`,
`accounts` and `corpus`, SELECT on the realm identity row and EXECUTE on
`accounts.guard_session` and `corpus.guard_version`. `u5_lifecycle_guard.sql` adds the
coordinator's two ticket functions, `u5_digest_read.sql` SELECT on `corpus.paper` and
`corpus.version`, `u5_digest_recipient.sql` the one recipient fact, and
`u5_digest_preferences.sql` USAGE on `personalization` with its one narrow read. No U3
or U4 file in the chain grants the topics login anything. Each expectation is checked
in the catalog and then exercised with the statement itself under the owner login.
"""

import re

import psycopg
import pytest
from psycopg import sql

from scripts import verify_docsuri_u5 as runner
from tests.u5_topics_digests.realm_catalog import (
    admin_connection,
    callable_functions,
    relation_privileges,
    relations,
    schema_privileges,
)

TOPICS = "docsuri_topics"
TOPICS_OWNER = "docsuri_topics_owner"
# The design's six owned entities (functional-design/entities.md) and the two tables
# built after it: the lifecycle participant's evidence (u5_schema.sql) and the
# one-click unsubscribe capability (u5_unsubscribe_capability.sql).
DESIGN_ENTITIES = frozenset(
    {
        "followed_topic",
        "digest_settings",
        "digest_run",
        "delivery_outcome",
        "send_log_entry",
        "topic_delivery_watermark",
    }
)
TOPICS_TABLES = DESIGN_ENTITIES | {"lifecycle_evidence", "email_unsubscribe"}
INTENDED_READS = {
    "corpus.paper": "the corpus eligibility read: withdrawal and publication date",
    "corpus.version": "the corpus eligibility read: eligibility, purpose and paper",
    "public.docsuri_local_identity": "the realm identity row every runtime login reads",
}
INTENDED_FUNCTIONS = {
    "personalization.digest_preferences(uuid)": "the narrow preference read",
    "corpus.guard_version(text,text)": "the corpus eligibility guard",
    "accounts.digest_recipient(uuid)": "the one recipient fact per account",
    "accounts.guard_session(uuid,uuid,text)": "the owner session guard",
    "accounts.guard_lifecycle_effect(uuid,uuid,text,text,bigint,jsonb,text)": (
        "the coordinator's ticket guard"
    ),
    "accounts.lifecycle_effect_action(uuid,uuid,text,text,bigint,jsonb,text)": (
        "the coordinator's ticket action"
    ),
}
INTENDED_SCHEMAS = frozenset({"accounts", "corpus", "personalization", "public", "topics"})
# A function body changes rows only through one of these statements (or dynamic SQL).
DATA_CHANGE = re.compile(
    r"\b(INSERT\s+INTO|UPDATE\s+[\w.\"]+(?:\s+\w+)?\s+SET|DELETE\s+FROM|TRUNCATE|"
    r"MERGE\s+INTO|COPY|EXECUTE)\b",
    re.IGNORECASE,
)
CALL = re.compile(r"\b([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\s*\(")
COMMENTS_AND_LITERALS = re.compile(r"--[^\n]*|/\*.*?\*/|'(?:[^']|'')*'", re.DOTALL)


def write_statements(table: dict) -> list[sql.Composed]:
    name = sql.Identifier(table["schema"], table["name"])
    column = sql.Identifier(table["first_column"])
    return [
        sql.SQL("INSERT INTO {} DEFAULT VALUES").format(name),
        sql.SQL("UPDATE {} SET {}={} WHERE false").format(name, column, column),
        sql.SQL("DELETE FROM {} WHERE false").format(name),
    ]


def test_topics_login_holds_only_its_intended_reads_outside_topics(realm):
    with admin_connection(realm) as conn:
        held = relation_privileges(conn, TOPICS)
        schemas = schema_privileges(conn, TOPICS)
        functions = callable_functions(conn, TOPICS)
        role = conn.execute(
            "SELECT rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolreplication,rolbypassrls "
            "FROM pg_roles WHERE rolname=%s",
            (TOPICS,),
        ).fetchone()
        memberships = conn.execute(
            "SELECT count(*) AS n FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member "
            "WHERE r.rolname=%s",
            (TOPICS,),
        ).fetchone()["n"]
        database = conn.execute(
            "SELECT has_database_privilege(%s,current_database(),'CREATE') AS can_create,"
            "has_database_privilege(%s,current_database(),'TEMP') AS can_temp",
            (TOPICS, TOPICS),
        ).fetchone()
    outside = {name: privileges for name, privileges in held.items() if not name.startswith("topics.")}
    assert outside == {name: frozenset({"SELECT"}) for name in INTENDED_READS}
    assert {name for name, privileges in schemas.items() if "USAGE" in privileges} == INTENDED_SCHEMAS
    assert [name for name, privileges in schemas.items() if "CREATE" in privileges] == []
    reachable = {name: row for name, row in functions.items() if row["schema"] != "topics"}
    assert set(reachable) == set(INTENDED_FUNCTIONS)
    assert all(row["definer"] for row in reachable.values())
    assert role == dict.fromkeys(
        ("rolsuper", "rolinherit", "rolcreaterole", "rolcreatedb", "rolreplication", "rolbypassrls"),
        False,
    )
    assert memberships == 0
    assert database == {"can_create": False, "can_temp": False}


def test_functions_the_topics_login_reaches_outside_topics_change_no_rows(realm):
    """Each reachable definer body, and every owner function it calls, only reads."""
    with admin_connection(realm) as conn:
        pending = [
            name for name, row in callable_functions(conn, TOPICS).items() if row["schema"] != "topics"
        ]
        bodies = {}
        while pending:
            signature = pending.pop()
            if signature in bodies:
                continue
            source = conn.execute(
                "SELECT prosrc FROM pg_proc WHERE oid=%s::regprocedure", (signature,)
            ).fetchone()["prosrc"]
            bodies[signature] = COMMENTS_AND_LITERALS.sub(" ", source)
            for schema, name in CALL.findall(bodies[signature]):
                pending.extend(
                    row["signature"]
                    for row in conn.execute(
                        "SELECT p.oid::regprocedure::text AS signature FROM pg_proc p "
                        "JOIN pg_namespace n ON n.oid=p.pronamespace "
                        "WHERE n.nspname=%s AND p.proname=%s",
                        (schema, name),
                    ).fetchall()
                )
    # The guards' own callees were followed, not only the six entry points.
    assert {"corpus.execution_eligibility(text)", *INTENDED_FUNCTIONS} <= set(bodies)
    assert {name: DATA_CHANGE.findall(body) for name, body in bodies.items() if DATA_CHANGE.search(body)} == {}


def test_topics_login_is_refused_every_write_outside_topics(realm, connect):
    with admin_connection(realm) as conn:
        tables = [row for row in relations(conn, exclude=("topics",)) if row["kind"] in ("r", "p")]
    owners = {table["schema"] for table in tables}
    assert owners == (runner.OWNERS - {"topics"}) | {"public"}
    with connect("topics") as conn:
        for table in tables:
            for statement in write_statements(table):
                with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
                    conn.execute(statement)


def test_topics_login_reads_no_accounts_table_and_keeps_its_intended_reads(realm, connect):
    with admin_connection(realm) as conn:
        accounts = [
            row["name"] for row in relations(conn) if row["schema"] == "accounts" and row["kind"] == "r"
        ]
    assert {"account", "consent", "session", "lifecycle_request", "lifecycle_scope"} <= set(accounts)
    with connect("topics") as conn:
        for name in accounts:
            with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
                conn.execute(sql.SQL("SELECT 1 FROM {} LIMIT 1").format(sql.Identifier("accounts", name)))
        for name in INTENDED_READS:
            conn.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(*name.split("."))))


def test_no_other_owner_login_can_write_a_topics_table(realm, connect):
    others = sorted(runner.OWNERS - {"topics"})
    with admin_connection(realm) as conn:
        grants = conn.execute(
            "SELECT c.relname AS name, pg_get_userbyid(c.relowner) AS owner, "
            "array_agg(DISTINCT CASE WHEN x.grantee=0 THEN 'PUBLIC' "
            "ELSE pg_get_userbyid(x.grantee) END) AS grantees, "
            "coalesce(array_agg(DISTINCT CASE WHEN x.grantee=0 THEN 'PUBLIC' "
            "ELSE pg_get_userbyid(x.grantee) END) FILTER "
            "(WHERE x.privilege_type IN ('INSERT','UPDATE','DELETE','TRUNCATE')),'{}') AS writers "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "CROSS JOIN LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) x "
            "WHERE n.nspname='topics' AND c.relkind IN ('r','p') GROUP BY c.relname,c.relowner",
        ).fetchall()
        column_grants = conn.execute(
            "SELECT count(*) AS n FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='topics' AND a.attacl IS NOT NULL"
        ).fetchone()["n"]
        users = conn.execute(
            "SELECT rolname FROM pg_roles WHERE NOT rolsuper AND rolname !~ '^pg_' "
            "AND has_schema_privilege(rolname,'topics','USAGE') ORDER BY 1"
        ).fetchall()
        owner_logs_in = conn.execute(
            "SELECT rolcanlogin FROM pg_roles WHERE rolname=%s", (TOPICS_OWNER,)
        ).fetchone()["rolcanlogin"]
        tables = {
            row["name"]: row for row in relations(conn) if row["schema"] == "topics" and row["kind"] == "r"
        }
        callers = {
            login: [
                name
                for name, row in callable_functions(conn, f"docsuri_{login}").items()
                if row["schema"] == "topics"
            ]
            for login in others
        }
    # One writer per table: the topics login, beside the NOLOGIN owner role that
    # only migrations act as. No other role and no PUBLIC entry holds any grant.
    assert {row["name"] for row in grants} == TOPICS_TABLES
    for row in grants:
        assert row["owner"] == TOPICS_OWNER, row
        assert set(row["grantees"]) == {TOPICS_OWNER, TOPICS}, row
        assert set(row["writers"]) == {TOPICS_OWNER, TOPICS}, row
    assert column_grants == 0
    assert [row["rolname"] for row in users] == [TOPICS, TOPICS_OWNER]
    assert owner_logs_in is False
    assert callers == {login: [] for login in others}
    for login in others:
        with connect(login) as conn:
            for name in sorted(TOPICS_TABLES):
                for statement in write_statements(tables[name]):
                    with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
                        conn.execute(statement)


def test_topics_schema_holds_its_eight_tables(realm):
    with admin_connection(realm) as conn:
        rows = conn.execute(
            "SELECT c.relname AS name, c.relkind AS kind, pg_get_userbyid(c.relowner) AS owner "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='topics' AND c.relkind IN ('r','p','v','m','f','S')"
        ).fetchall()
        schema_owner = conn.execute(
            "SELECT pg_get_userbyid(nspowner) AS owner FROM pg_namespace WHERE nspname='topics'"
        ).fetchone()["owner"]
    assert len(rows) == 8 and {row["name"] for row in rows} == TOPICS_TABLES
    assert {(row["kind"], row["owner"]) for row in rows} == {("r", TOPICS_OWNER)}
    assert schema_owner == TOPICS_OWNER
    # Six of them are the design's entities; the code summary records the other two.
    assert TOPICS_TABLES - DESIGN_ENTITIES == {"lifecycle_evidence", "email_unsubscribe"}
