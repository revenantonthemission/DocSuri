"""The one composed migration chain applies, refuses drift and reads back one definition.

BR1.4, BR1.5: every owner's files apply once, in order, under the owner's own role; the
four conflicting pairs each end in one definition; nothing migrates at start.
"""

from __future__ import annotations

import re
from pathlib import Path

import psycopg
import pytest

from backend import u8_migrations
from backend.u8_migrations import (
    BASE,
    GUARD_PURPOSES,
    LIFECYCLE_PARTICIPANT_ROLES,
    RECEIPT_KINDS,
    REPLACED,
    SESSION_PURPOSES,
    applied_difference,
    file_digest,
)

ROOT = Path(__file__).resolve().parents[3]
OWNERS = (
    "accounts", "assistance", "corpus", "discovery", "export", "library", "operations",
    "personalization", "research", "topics", "usage",
)
# U2's lifecycle definition, which U5's mirrored file gave its callers verbatim, with
# U8's own additive columns: the origin request identifier (u8_accounts.sql) and the date
# a part retained by policy is gone (u8_lifecycle_retention.sql, BR2.5).
LIFECYCLE_COLUMNS = {
    "lifecycle_request": {
        "id", "account_id", "revision", "action", "policy_ref", "manifest_revision",
        "manifest", "accepted_at", "disposition", "reason_key", "status_generation",
        "origin_request_id",
    },
    "lifecycle_scope": {
        "request_id", "participant", "scope", "generation", "lease_until", "attempts",
        "disposition", "evidence_ref", "reason_key", "updated_at", "retained_until",
    },
}
GUARD_CALLERS = (
    "docsuri_library", "docsuri_personalization", "docsuri_discovery", "docsuri_usage",
    "docsuri_assistance", "docsuri_corpus", "docsuri_research", "docsuri_topics",
    "docsuri_export",
)


@pytest.fixture
def applied(connect) -> dict:
    with connect("operations") as conn:
        return conn.execute(
            "SELECT schema_hashes FROM public.docsuri_local_identity"
        ).fetchone()["schema_hashes"]


def check_values(definition: str) -> set[str]:
    """The quoted values of a `CHECK (x IN (...))` or `= ANY (ARRAY[...])` definition."""
    return set(re.findall(r"'([^']+)'", definition))


# 1. The chain applies, owner by owner, under each owner's role --------------------------


def test_every_chain_file_applied_once_with_its_digest(applied):
    for owner, file in BASE:
        assert applied[owner] == file_digest(file), owner
    for _, file in u8_migrations.migrations():
        assert applied.get(file) == file_digest(file), file
    assert not set(REPLACED) & set(applied), "a left-out file was applied"
    assert len(u8_migrations.chain_files()) == len(set(u8_migrations.chain_files()))


def test_every_owned_object_belongs_to_its_owner_role(connect):
    with connect("operations") as conn:
        relations = conn.execute(
            "SELECT n.nspname AS schema, c.relname AS name, pg_get_userbyid(c.relowner) AS owner "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname = ANY(%s) AND c.relkind IN ('r','p','i','S','v','m')",
            (list(OWNERS),),
        ).fetchall()
        functions = conn.execute(
            "SELECT n.nspname AS schema, p.proname AS name, pg_get_userbyid(p.proowner) AS owner "
            "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname = ANY(%s)",
            (list(OWNERS),),
        ).fetchall()
        schemas = conn.execute(
            "SELECT nspname AS schema, pg_get_userbyid(nspowner) AS owner FROM pg_namespace "
            "WHERE nspname = ANY(%s)", (list(OWNERS),),
        ).fetchall()
    assert {row["schema"] for row in schemas} == set(OWNERS)
    assert relations and functions
    for row in [*schemas, *relations, *functions]:
        assert row["owner"] == f"docsuri_{row['schema']}_owner", row


# 2. migrate refuses drift before any change ----------------------------------------------


class RecordingConnection:
    """Records every statement; a refusal must come before the first one."""

    def __init__(self):
        self.statements = []

    def execute(self, statement, *args, **kwargs):
        self.statements.append(statement)


@pytest.fixture
def runner():
    from scripts import verify_docsuri_u8

    return verify_docsuri_u8


# The composed chain against the earlier Units' own lists (U8 plan Step 160, L4-10) -------
#
# `test_every_chain_file_applied_once_with_its_digest` compares the realm with the same
# list that built it, so a file an earlier Unit added and the chain lacks would show
# only in a journey. These two compare the chain with the lists the earlier runners
# apply. `backend/u8_migrations.py` is read, never edited.

NEWEST_U5_FILE = "backend/modules/topics/u5_scheduled_instant.sql"


def earlier_units_lists() -> dict[str, tuple]:
    """Each earlier runner's own `MIGRATIONS`, as it applies them."""
    from scripts import (
        verify_docsuri_u2,
        verify_docsuri_u3,
        verify_docsuri_u4,
        verify_docsuri_u5,
        verify_docsuri_u6,
    )

    return {"U2": tuple(verify_docsuri_u2.MIGRATIONS), "U3": tuple(verify_docsuri_u3.MIGRATIONS),
            "U4": tuple(verify_docsuri_u4.MIGRATIONS), "U5": tuple(verify_docsuri_u5.MIGRATIONS),
            "U6": tuple(verify_docsuri_u6.MIGRATIONS)}


def chain_place(chain: tuple, replaced: dict, owner: str, file: str) -> int | None:
    """Where the chain holds a file under its owner: its own place, or its reconciling
    file's when the chain leaves it out; None when it holds neither."""
    for candidate in (file, replaced.get(file)):
        if (owner, candidate) in chain:
            return chain.index((owner, candidate))
    return None


def chain_comparison(chain, replaced: dict, lists: dict, ordered) -> list[str]:
    """What the chain lacks of the earlier Units' lists: every file it holds neither
    under the same owner nor through a reconciling file, by name, and every file of
    `ordered` that it holds at or before the file listed ahead of it."""
    chain = tuple(chain)
    report: list[str] = []
    for entries in lists.values():
        for owner, file in entries:
            if chain_place(chain, replaced, owner, file) is None and file not in report:
                report.append(file)
    places = [(chain_place(chain, replaced, owner, file), file) for owner, file in ordered]
    held = [(place, file) for place, file in places if place is not None]
    report += [f"out of order: {file}"
               for (ahead, _), (place, file) in zip(held, held[1:], strict=False)
               if place <= ahead]
    return report


def own_tail(lists: dict) -> tuple[list, list]:
    """U5's and U6's own files (their lists past U4's), split into the files U2's chain
    does not already hold, in their listed order, and the files it does."""
    assert lists["U5"][:len(lists["U4"])] == lists["U4"]
    assert lists["U6"][:len(lists["U5"])] == lists["U5"]
    tail = lists["U6"][len(lists["U4"]):]
    return ([entry for entry in tail if entry not in lists["U2"]],
            [entry for entry in tail if entry in lists["U2"]])


def test_the_composed_chain_holds_every_file_of_the_earlier_units_chains(runner):
    """Every owner and file of U2's, U3's, U4's, U5's and U6's own lists is in the
    composed chain under the same owner, or is left out for a reconciling file that is.
    U5's and U6's own files keep their listed order in it, but for the two U2 files
    U5's list names again, which the chain holds once, in U2's part."""
    lists = earlier_units_lists()
    assert set(lists["U3"]) | set(lists["U4"]) | set(lists["U5"]) <= set(lists["U6"])
    ordered, held_by_u2 = own_tail(lists)
    assert len(ordered) + len(held_by_u2) == 20
    assert [file for _, file in held_by_u2] == [
        "backend/modules/accounts/u2_lifecycle_effect.sql",
        "backend/modules/accounts/u2_lifecycle_action.sql"]
    assert ("topics", NEWEST_U5_FILE) in ordered
    assert chain_comparison(u8_migrations.CHAIN, REPLACED, lists, ordered) == []
    # The files the chain leaves out are each one of the earlier lists' files.
    listed = {file for entries in lists.values() for _, file in entries}
    assert set(REPLACED) <= listed


def test_the_chain_comparison_names_a_missing_file(runner):
    """The same comparison over the chain without U5's newest file names exactly that
    file, and over a chain that holds it out of its listed order names that."""
    lists = earlier_units_lists()
    ordered, _ = own_tail(lists)
    without = [entry for entry in u8_migrations.CHAIN if entry[1] != NEWEST_U5_FILE]
    assert len(without) == len(u8_migrations.CHAIN) - 1
    assert chain_comparison(without, REPLACED, lists, ordered) == [NEWEST_U5_FILE]
    appended = [*without, ("topics", NEWEST_U5_FILE)]
    assert chain_comparison(appended, REPLACED, lists, ordered) == [
        "out of order: backend/modules/accounts/u6_lifecycle_guard.sql"]


def test_migrate_refuses_a_file_listed_twice(runner, applied):
    files, replaced = runner.chain()
    with pytest.raises(runner.Refused, match="twice"):
        runner.validate_chain((*files, files[-1]), replaced, dict(applied))


def test_migrate_refuses_a_chain_that_still_lists_a_left_out_file(runner, applied):
    files, replaced = runner.chain()
    left_out = next(iter(replaced))
    with pytest.raises(runner.Refused, match="left-out"):
        runner.validate_chain((*files, ("accounts", left_out)), replaced, dict(applied))


def test_migrate_refuses_a_changed_digest_before_any_statement(runner, applied, monkeypatch):
    changed = dict(applied)
    victim = u8_migrations.migrations()[3][1]
    changed[victim] = "0" * 64
    conn = RecordingConnection()
    with pytest.raises(runner.Refused, match="changed"):
        runner.apply_migrations(conn, changed)
    assert conn.statements == []


def test_migrate_refuses_a_realm_that_is_not_a_prefix_of_the_chain(runner, applied):
    files, replaced = runner.chain()
    gapped = dict(applied)
    del gapped[files[0][1]]
    with pytest.raises(runner.Refused, match="prefix"):
        runner.validate_chain(files, replaced, gapped)
    held = dict(applied)
    held[next(iter(replaced))] = "1" * 64
    with pytest.raises(runner.Refused, match="leaves out"):
        runner.validate_chain(files, replaced, held)


def test_the_chain_names_no_owner_outside_the_realm(runner, applied):
    files, replaced = runner.chain()
    with pytest.raises(runner.Refused, match="owner outside"):
        runner.validate_chain((*files, ("billing", "nowhere.sql")), replaced, dict(applied))
    runner.validate_chain(files, replaced, dict(applied))


# 3. Each reconciled object reads back with its one definition ----------------------------


def test_the_session_purpose_rule_holds_u2_u3_and_consent_pending(connect):
    with connect("accounts") as conn:
        rows = conn.execute(
            "SELECT conname, pg_get_constraintdef(oid) AS definition FROM pg_constraint "
            "WHERE conrelid='accounts.session'::regclass AND contype='c' "
            "AND pg_get_constraintdef(oid) LIKE '%%purpose%%'"
        ).fetchall()
    assert [row["conname"] for row in rows] == ["session_purpose_check"]
    assert check_values(rows[0]["definition"]) == set(SESSION_PURPOSES)
    assert {"primary_mfa_continuation", "preauthentication", "consent_pending"} <= set(
        SESSION_PURPOSES)


def test_one_guard_session_serves_both_callers(connect):
    with connect("accounts") as conn:
        rows = conn.execute(
            "SELECT p.oid, p.prosrc FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='accounts' AND p.proname='guard_session'"
        ).fetchall()
        assert len(rows) == 1
        source = rows[0]["prosrc"]
        for purpose in GUARD_PURPOSES:
            assert f"'{purpose}'" in source, purpose
        assert "lifecycle_state" in source and "mfa_at" in source
        for role in GUARD_CALLERS:
            permitted = conn.execute(
                "SELECT has_function_privilege(%s,'accounts.guard_session(uuid,uuid,text)',"
                "'EXECUTE') AS ok", (role,),
            ).fetchone()["ok"]
            assert permitted, role
        public = conn.execute(
            "SELECT has_function_privilege('public','accounts.guard_session(uuid,uuid,text)',"
            "'EXECUTE') AS ok"
        ).fetchone()["ok"]
    assert not public


def test_the_lifecycle_tables_hold_one_definition_with_u2_and_u5_columns(connect):
    with connect("accounts") as conn:
        for table, expected in LIFECYCLE_COLUMNS.items():
            columns = {row["column_name"] for row in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='accounts' AND table_name=%s", (table,)).fetchall()}
            assert columns == expected, table
        assert conn.execute(
            "SELECT count(*) AS n FROM information_schema.columns WHERE table_schema='accounts' "
            "AND table_name='account' AND column_name='lifecycle_revision'"
        ).fetchone()["n"] == 1
        guard = conn.execute(
            "SELECT prosrc FROM pg_proc WHERE proname='guard_lifecycle_effect'"
        ).fetchall()
    assert len(guard) == 1
    for participant, role in LIFECYCLE_PARTICIPANT_ROLES.items():
        assert f"WHEN '{participant}' THEN '{role}'" in guard[0]["prosrc"], participant


def test_the_entry_receipt_kinds_have_one_rule(connect):
    with connect("accounts") as conn:
        rows = conn.execute(
            "SELECT pg_get_constraintdef(oid) AS definition FROM pg_constraint "
            "WHERE conrelid='accounts.entry_receipt'::regclass AND contype='c'"
        ).fetchall()
        assert len(rows) == 1
        assert check_values(rows[0]["definition"]) == set(RECEIPT_KINDS)
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "INSERT INTO accounts.entry_receipt VALUES(gen_random_uuid(),'mystery',%s,'{}')",
                ("a" * 64,),
            )
        conn.rollback()
        conn.execute(
            "INSERT INTO accounts.entry_receipt VALUES(gen_random_uuid(),'password-reset',%s,'{}')",
            ("a" * 64,),
        )
        conn.rollback()


def test_the_capacity_function_has_one_definition_for_any_database(connect):
    with connect("operations") as conn:
        rows = conn.execute(
            "SELECT pg_get_functiondef(p.oid) AS definition FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='operations' AND p.proname='capacity_footprint'"
        ).fetchall()
        assert len(rows) == 1
        definition = rows[0]["definition"]
        assert "pg_ls_waldir" in definition and "pg_database_size(current_database())" in definition
        assert "docsuri_u" not in definition and "current_database()=" not in definition
        footprint = conn.execute("SELECT * FROM operations.capacity_footprint()").fetchone()
    assert footprint["database_bytes"] > 0 and footprint["wal_bytes"] > 0


def _flow(conn, *, intent="sign_in", account=None, digest=None):
    return conn.execute(
        "INSERT INTO accounts.identity_flow(id,account_id,provider,intent,state_hash,"
        "binding_hash,authority_revision,callback_id,return_route,secret_ciphertext,"
        "key_version,expires_at,client_address_digest) VALUES(gen_random_uuid(),%s,"
        "'google',%s,md5(random()::text)||md5(random()::text),%s,%s,'c','account',"
        "'\\x00','v',clock_timestamp()+interval '5 minutes',%s) RETURNING id",
        (account, intent, "b" * 64, None if account is None else account, digest),
    ).fetchone()["id"]


def test_a_flows_address_digest_is_nullable_and_only_a_keyed_digest_on_any_start(connect):
    """u8_identity_flow_address.sql (the person's decision of 2026-10-25, "Cap per address,
    raise site cap") adds a nullable column that holds only a keyed hex digest;
    u8_identity_flow_starts.sql ("Count every start, free places at once") lets a link's
    start carry it too, and keeps it when the flow leaves 'pending'. Each case is rolled
    back: this test leaves no flow behind."""
    with connect("accounts") as conn:
        column = conn.execute(
            "SELECT is_nullable FROM information_schema.columns WHERE table_schema='accounts' "
            "AND table_name='identity_flow' AND column_name='client_address_digest'"
        ).fetchone()
        assert column == {"is_nullable": "YES"}
        _flow(conn)  # a flow without a digest, as U2's realm writes every flow
        kept = _flow(conn, digest="c" * 64)
        conn.execute("UPDATE accounts.identity_flow SET disposition='complete' WHERE id=%s",
                     (kept,))
        assert conn.execute("SELECT client_address_digest FROM accounts.identity_flow "
                            "WHERE id=%s", (kept,)).fetchone() == {
            "client_address_digest": "c" * 64}  # no trigger clears it any more
        account = conn.execute("SELECT id FROM accounts.account LIMIT 1").fetchone()
        if account is not None:
            _flow(conn, intent="link", account=account["id"], digest="d" * 64)
        conn.rollback()
        for digest in ("198.51.100.1", "C" * 64):
            with pytest.raises(psycopg.errors.CheckViolation):
                _flow(conn, digest=digest)
            conn.rollback()


def test_only_accountaccess_definer_function_deletes_a_flow(connect):
    """u8_identity_flow_starts.sql: the runtime login holds no DELETE on the flows; it may
    only call `accounts.expire_identity_flows`, a definer function with a fixed search path,
    granted to it alone, that refuses a limit outside 1 to 10,000. The indexes the counts
    read exist, and the release trigger and its function are gone."""
    with connect("accounts") as conn:
        function = conn.execute(
            "SELECT p.prosecdef,p.proconfig,p.proacl::text AS acl FROM pg_proc p JOIN "
            "pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='accounts' AND "
            "p.proname='expire_identity_flows'").fetchone()
        assert function["prosecdef"] is True
        assert function["proconfig"] == ["search_path=pg_catalog"]
        # Granted to the runtime login, revoked from PUBLIC (an entry with no grantee).
        grantees = {entry.split("=", 1)[0]
                    for entry in function["acl"].strip("{}").split(",")}
        assert "docsuri_accounts" in grantees and "" not in grantees
        for name in ("identity_flow_address_release",):
            assert not conn.execute("SELECT 1 FROM pg_trigger WHERE tgname=%s",
                                    (name,)).fetchone()
            assert not conn.execute("SELECT 1 FROM pg_proc WHERE proname=%s",
                                    (name,)).fetchone()
        indexes = {row["indexname"] for row in conn.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname='accounts' AND "
            "tablename='identity_flow'").fetchall()}
        assert {"identity_flow_expiry", "identity_flow_address_starts",
                "identity_flow_account_starts", "identity_flow_pending_binding"} <= indexes
        assert not {"identity_flow_open_address", "identity_flow_address_expiry"} & indexes
        flow = _flow(conn)
        conn.commit()
        try:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("DELETE FROM accounts.identity_flow WHERE id=%s", (flow,))
            conn.rollback()
            for limit in (0, 10_001, None):
                with pytest.raises(psycopg.errors.InvalidParameterValue):
                    conn.execute("SELECT accounts.expire_identity_flows(%s)", (limit,))
                conn.rollback()
        finally:
            conn.rollback()
            # The flow's one arranged value, its expiry, then AccountAccess's own pass.
            conn.execute("UPDATE accounts.identity_flow SET expires_at=clock_timestamp()-"
                         "interval '2 minutes' WHERE id=%s", (flow,))
            conn.execute("SELECT accounts.expire_identity_flows(10000)")
            conn.commit()
        assert not conn.execute("SELECT 1 FROM accounts.identity_flow WHERE id=%s",
                                (flow,)).fetchone()


# 4. The start's schema check names a difference ------------------------------------------


def test_the_start_schema_check_names_an_applied_digest_that_differs(applied):
    assert applied_difference(applied) == []
    changed_file = u8_migrations.migrations()[10][1]
    changed = {**applied, changed_file: "f" * 64}
    assert applied_difference(changed) == [changed_file]
    missing_file = u8_migrations.migrations()[-1][1]
    missing = {name: value for name, value in applied.items() if name != missing_file}
    assert applied_difference(missing) == [missing_file]
    left_out = next(iter(REPLACED))
    assert applied_difference({**applied, left_out: "e" * 64}) == [left_out]
    base_owner = BASE[0][0]
    assert applied_difference({**applied, base_owner: "d" * 64}) == [base_owner]
