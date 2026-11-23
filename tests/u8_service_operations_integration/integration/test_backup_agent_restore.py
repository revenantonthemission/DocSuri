"""The backup agent restores a set as a non-superuser (U8 plan Step 26; D14, BR4.5,
Workflow 6; security-design § 15 "The extension (D14)" item 2).

On the composed realm's own instance, the agent's stand-in login (not a superuser, no
CREATEDB of its own, the disposable-databases role held with SET but without INHERIT)
dumps the realm's database into a live set on a stand-in volume, and `verify` restores
that set into a new scratch database without error: the copy belongs to the
disposable-databases role, and the agent hands no file to its caller. The scheduler's
stand-in login, a member of that role, then reads the copy and drops it.
"""

from __future__ import annotations

import json
import os

import psycopg
import pytest

from backend.local_profile import private_bytes
from docsuri_ops.arrangement.paths import REALM_DATABASES
from docsuri_ops.backup_agent.config import Login
from tests.u8_service_operations_integration import agent_flows as af


@pytest.fixture
def standins(realm) -> dict:
    return json.loads(private_bytes(realm.root / "standin-credentials.json"))["roles"]


@pytest.fixture
def container(realm) -> str:
    return json.loads(private_bytes(realm.root / "environment.json"))["container"]


def login(realm, role: str, password: str, database: str):
    return psycopg.connect(host="127.0.0.1", port=realm.database_port, dbname=database,
                           user=role, password=password, require_auth="scram-sha-256",
                           connect_timeout=5, autocommit=True)


@pytest.fixture
def rig(tmp_path, clock, realm, standins, container):
    value = af.build(
        tmp_path, clock, real=True, container=container,
        login=Login("127.0.0.1", realm.database_port, "docsuri_backup_agent", "v2-login"),
    )
    password = value.context.folder / "v2-login"
    descriptor = os.open(password, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(standins["backupAgent"])
    return value


def test_the_agents_login_restores_a_set_into_a_scratch_copy_the_disposable_role_owns(
    rig, realm, standins,
):
    with login(realm, "docsuri_backup_agent", standins["backupAgent"], "docsuri_u8") as conn:
        attributes = conn.execute("SELECT rolsuper, rolcreatedb FROM pg_roles "
                                  "WHERE rolname = current_user").fetchone()
    assert attributes == (False, False)
    written = af.backed_up(rig, "docsuri_u8")
    assert written["integrity"] == "passed" and written["incarnation"].startswith("docsuri_u8:")
    scratch = REALM_DATABASES.new("scratch")
    try:
        status, result, payload = af.invoke(rig, "verify", {"scratchDatabase": scratch,
                                                            "setKind": "live-set"},
                                            caller=af.SCHEDULER)
        assert status == 0, result
        # No file leaves the agent: one JSON result, and no bytes beside it.
        assert payload == b"" and result["setPath"] == written["location"]
        assert set(result) == {"ok", "scratchDatabase", "setPath", "setSha256", "setRecordId",
                               "restoredAt", "hnswRebuildSeconds"}
        # The realm's database holds the search projection's HNSW index, so the restore
        # took two passes and timed the second (NFR9.4, U8 plan Step 62(d)).
        seconds = result["hnswRebuildSeconds"]
        assert type(seconds) is int and seconds >= 0
        with login(realm, "docsuri_scheduler", standins["scheduler"], scratch) as conn:
            owner = conn.execute("SELECT pg_get_userbyid(datdba) FROM pg_database "
                                 "WHERE datname = current_database()").fetchone()[0]
            owners = conn.execute(
                "SELECT DISTINCT pg_get_userbyid(c.relowner) FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relkind = 'r' "
                "AND n.nspname NOT IN ('pg_catalog','information_schema')").fetchall()
            tables = conn.execute(
                "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE c.relkind = 'r' AND n.nspname = 'accounts'").fetchone()[0]
            vector = conn.execute("SELECT count(*) FROM pg_extension WHERE extname = 'vector'"
                                  ).fetchone()[0]
            hnsw = conn.execute(
                "SELECT count(*) FROM pg_indexes WHERE schemaname = 'corpus' "
                "AND indexname = 'projection_embedding_hnsw'").fetchone()[0]
        assert hnsw == 1  # the second pass, through the list file `dd` wrote
        assert owner == "docsuri_disposable" and owners == [("docsuri_disposable",)]
        assert tables > 0 and vector == 1  # pgvector came with template1
    finally:
        # The scheduler's login has no CONNECT on the realm's database; it drops the copy
        # from the instance's maintenance database, through the role's ownership.
        with login(realm, "docsuri_scheduler", standins["scheduler"], "postgres") as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{scratch}"')


def test_a_failed_restore_reports_its_scratch_name_and_writes_nothing_else(
    rig, realm, standins,
):
    """A set whose bytes no longer match its catalogue entry is never restored."""
    written = af.backed_up(rig, "docsuri_u8")
    (rig.u8 / written["location"]).write_bytes(b"altered")
    scratch = REALM_DATABASES.new("scratch")
    status, result, _ = af.invoke(rig, "verify", {"scratchDatabase": scratch,
                                                  "setKind": "live-set"}, caller=af.SCHEDULER)
    assert (status, result["reason"]) == (1, "digest-mismatch")
    with login(realm, "docsuri_scheduler", standins["scheduler"], "postgres") as conn:
        assert conn.execute("SELECT count(*) FROM pg_database WHERE datname = %s",
                            (scratch,)).fetchone()[0] == 0


def test_a_restore_running_below_the_critical_floor_ends_its_sessions_and_stops(
    rig, realm, standins,
):
    """NFR7.18, NFR8.14 (U8 plan Step 122(d)): the floor is crossed once the restore has
    started, so the agent ends its own `pg_restore` session inside the container and
    refuses `internal-disk-critical` with the sessions it ended; no session is left on
    the scratch database, and the scheduler's login drops it, as Workflow 6 does."""
    af.backed_up(rig, "docsuri_u8")
    readings = iter([100 * af.GIB])  # the start check, then below the floor
    rig.context.internal_free = lambda: next(readings, 10 * af.GIB - 1)
    rig.context.disk_watch_seconds = 0.01
    scratch = REALM_DATABASES.new("scratch")
    try:
        status, result, _ = af.invoke(rig, "verify", {"scratchDatabase": scratch,
                                                      "setKind": "live-set"},
                                      caller=af.SCHEDULER)
        assert (status, result["reason"]) == (1, "internal-disk-critical"), result
        assert result["sessionsEnded"] >= 1  # the first pass's pg_restore, ended
        with login(realm, "docsuri_scheduler", standins["scheduler"], "postgres") as conn:
            left = conn.execute("SELECT count(*) FROM pg_stat_activity WHERE datname = %s",
                                (scratch,)).fetchone()[0]
        assert left == 0
        lines = (rig.context.folder / "logs" / "backup-agent.log").read_bytes().splitlines()
        assert json.loads(lines[-1])["reason"] == "internal-disk-critical"
    finally:
        with login(realm, "docsuri_scheduler", standins["scheduler"], "postgres") as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{scratch}"')
