"""D13 and R-07 grants: the runtime role never reaches an envelope and deletes nothing."""

from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb

ENVELOPE_COLUMNS = ("sealed_token", "token_key_version")
EXPORT_TABLES = (
    "connection",
    "connection_pace",
    "preview_pair",
    "preview_revision",
    "approval",
    "effect",
    "attempt",
    "reconciliation_check",
    "replay_record",
    "lifecycle_evidence",
    "lifecycle_counts",
    "lane_status",
)
RUNTIME_FUNCTIONS = (
    "export.store_token_envelope(uuid,uuid,integer,uuid,bytea,text,text,text,text,timestamptz)",
    "export.open_token_envelope(uuid,uuid)",
    "export.clear_token_envelope(uuid,uuid,integer,text)",
    "export.token_key_counts()",
    "export.release_pending(uuid,uuid)",
    "export.sweep_stale_pending(timestamptz,integer,integer)",
    "export.purge_unapproved_previews(timestamptz,integer,integer)",
    "export.lifecycle_release_pending(uuid,uuid,text,bigint,jsonb,text)",
    "export.erase_account_records(uuid,uuid,bigint,jsonb,text)",
    "export.status_counts(timestamptz)",
)
OPERATOR_FUNCTIONS = (
    "export.token_envelopes_for_reseal(text,integer)",
    "export.reseal_token(uuid,text,bytea,text)",
)
GUARD = "accounts.guard_lifecycle_effect(uuid,uuid,text,text,bigint,jsonb,text)"


def test_runtime_role_holds_no_privilege_on_the_envelope_columns(connect):
    """R-07: no SELECT, INSERT, UPDATE or REFERENCES on the two envelope columns."""
    with connect("export") as conn:
        columns = [
            row["attname"]
            for row in conn.execute(
                "SELECT attname FROM pg_attribute WHERE attrelid='export.connection'::regclass "
                "AND attnum > 0 AND NOT attisdropped ORDER BY attnum"
            ).fetchall()
        ]
        assert set(ENVELOPE_COLUMNS) < set(columns)
        for column in columns:
            for privilege in ("SELECT", "INSERT", "UPDATE", "REFERENCES"):
                held = conn.execute(
                    "SELECT has_column_privilege('docsuri_export','export.connection',%s,%s) AS held",
                    (column, privilege),
                ).fetchone()["held"]
                if column in ENVELOPE_COLUMNS:
                    assert held is False, (column, privilege)
                elif privilege != "REFERENCES":
                    assert held is True, (column, privilege)
        for statement in (
            "SELECT sealed_token FROM export.connection LIMIT 1",
            "SELECT * FROM export.connection LIMIT 1",
            "UPDATE export.connection SET token_key_version=NULL WHERE false",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
                conn.execute(statement)


def test_operator_functions_belong_to_the_schema_owner_alone(connect):
    with connect("export") as conn:
        for function in RUNTIME_FUNCTIONS:
            assert conn.execute(
                "SELECT has_function_privilege('docsuri_export',%s,'EXECUTE') AS held", (function,)
            ).fetchone()["held"], function
        for function in OPERATOR_FUNCTIONS:
            assert not conn.execute(
                "SELECT has_function_privilege('docsuri_export',%s,'EXECUTE') AS held", (function,)
            ).fetchone()["held"], function
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("SELECT * FROM export.token_envelopes_for_reseal('u6-' || repeat('0',32),1)")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("SELECT export.reseal_token(%s,repeat('0',64),'\\x00','u6-x')", (uuid4(),))


def test_public_can_execute_no_function_in_schema_export(connect):
    with connect("export") as conn:
        functions = conn.execute(
            "SELECT p.oid::regprocedure::text AS name, has_function_privilege('public',p.oid,"
            "'EXECUTE') AS public_execute FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='export'"
        ).fetchall()
        for signature in RUNTIME_FUNCTIONS + OPERATOR_FUNCTIONS:
            assert conn.execute(
                "SELECT to_regprocedure(%s) IS NOT NULL AS present", (signature,)
            ).fetchone()["present"], signature
        assert len(functions) > len(RUNTIME_FUNCTIONS + OPERATOR_FUNCTIONS)  # trigger functions too
        assert [row["name"] for row in functions if row["public_execute"]] == []


def test_runtime_role_has_no_delete_on_any_export_table(connect):
    with connect("export") as conn:
        for table in EXPORT_TABLES:
            assert not conn.execute(
                "SELECT has_table_privilege('docsuri_export',%s,'DELETE') AS held",
                (f"export.{table}",),
            ).fetchone()["held"], table
            with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
                conn.execute(f"DELETE FROM export.{table} WHERE false")


def test_runtime_role_runs_both_account_guards(connect, authority):
    with connect("export") as conn:
        for function in ("accounts.guard_session(uuid,uuid,text)", GUARD):
            assert conn.execute(
                "SELECT has_function_privilege('docsuri_export',%s,'EXECUTE') AS held", (function,)
            ).fetchone()["held"], function
        # The session guard admits this runtime login for a live synthetic session.
        conn.execute(
            "SELECT accounts.guard_session(%s,%s,'local-research')",
            (authority.account_id, authority.session_id),
        )
        # ApprovedExport maps to this login, so a bogus ticket fails on the ticket itself.
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="effect denied"), (
            conn.transaction()
        ):
            conn.execute(
                f"SELECT {GUARD.split('(')[0]}(%s,%s,'ApprovedExport','live_records',1,%s,'m')",
                (uuid4(), authority.account_id, Jsonb({})),
            )


def test_lifecycle_guard_refuses_approved_export_under_another_login(connect):
    with connect("topics") as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="owner denied"), (
            conn.transaction()
        ):
            conn.execute(
                f"SELECT {GUARD.split('(')[0]}(%s,%s,'ApprovedExport','live_records',1,%s,'m')",
                (uuid4(), uuid4(), Jsonb({})),
            )


@pytest.mark.parametrize("owner", ["topics", "research"])
def test_another_owner_login_cannot_read_export_tables(connect, owner):
    with connect(owner) as conn:
        for table in ("effect", "approval", "preview_revision"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
                conn.execute(f"SELECT 1 FROM export.{table} LIMIT 1")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("SELECT * FROM export.token_key_counts()")
