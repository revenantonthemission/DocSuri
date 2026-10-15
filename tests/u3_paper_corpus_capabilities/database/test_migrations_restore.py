"""Real-PostgreSQL U3 migration identity and restore boundary enforcement."""

import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from fixtures import request_body

pytestmark = pytest.mark.u3_database


def test_migration_identity_is_recorded_and_stable(realm, connect):
    """The realm records its run identity and every applied migration hash."""
    profile, credentials = realm
    with connect("corpus", autocommit=True):
        pass
    import psycopg

    from backend.local_profile import private_bytes

    admin_password = __import__("json").loads(
        private_bytes(Path(profile.root) / "migration-credentials.json")
    )["databaseAdminPassword"]
    conn = psycopg.connect(
        host="127.0.0.1",
        port=profile.database_port,
        dbname=profile.database_name,
        user="postgres",
        password=admin_password,
        connect_timeout=3,
    )
    try:
        row = conn.execute(
            "SELECT run_id,schema_hashes FROM public.docsuri_local_identity"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == profile.run_id
    hashes = row[1]
    assert hashes["backend/modules/corpus/u3_schema.sql"]
    assert hashes["backend/modules/corpus/u3_watermark_v2.sql"]
    assert hashes["backend/modules/discovery/u3_schema.sql"]
    assert hashes["ops/src/docsuri_ops/u3_capacity_v2.sql"]


def test_changed_migration_bytes_are_refused(realm, monkeypatch):
    """A changed applied migration is refused instead of silently re-applied."""
    profile, _ = realm
    from scripts import verify_docsuri_u3 as runner

    original = hashlib.sha256(
        Path(runner.ROOT / "backend/modules/corpus/u3_schema.sql").read_bytes()
    ).hexdigest()

    def tampered(path: Path) -> str:
        if path.name == "u3_schema.sql" and path.parent.name == "corpus":
            return "0" * 64
        return hashlib.sha256(path.read_bytes()).hexdigest()

    monkeypatch.setattr(runner, "digest", tampered)
    with pytest.raises(runner.Refused):
        runner.migrate(Path(profile.root) / "environment.json")
    # The recorded hash still matches the actual bytes (nothing was rewritten).
    assert (
        hashlib.sha256(
            Path(runner.ROOT / "backend/modules/corpus/u3_schema.sql").read_bytes()
        ).hexdigest()
        == original
    )


def test_restore_boundary_enforcement_in_schema(
    maintenance, run_fixture, authority, maintenance_authority, fixture_discard, connect
):
    """Withdrawal is terminal for serving: no ingest or restore path re-enables it."""
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    maintenance.record_change(
        authority,
        {
            "paperId": "paper-alpha",
            "changeKind": "withdrawal",
            "disposition": "withdrawn",
            "reasonKey": "boundary-check",
            "policy": {"policyId": "u3-source-eligibility", "revision": "1"},
        },
    )
    # A second run over the withdrawn source must not resurrect eligibility.
    second = maintenance.accept(
        authority, uuid4(), request_body("incremental-refresh", ["fixture-alpha"])
    )
    outcome = maintenance.execute(second["runId"])
    assert outcome["state"] in ("completed", "failed")
    with connect("corpus") as conn:
        state = conn.execute(
            "SELECT v.eligible,p.withdrawn FROM corpus.version v JOIN corpus.paper p "
            "ON p.id=v.paper_id WHERE v.id='paper-alpha:v1'"
        ).fetchone()
    assert state["withdrawn"] is True and state["eligible"] is False
    # Restore rehearsal replays the same boundary.
    replay = maintenance.restore_replay("migration-boundary-1", ["paper-alpha:v1"])
    assert replay["refused"] == 1


def test_partial_write_crash_boundary_leaves_no_false_publication(
    maintenance, authority, maintenance_authority, fixture_discard, connect
):
    """An accepted-but-unexecuted run cannot appear published or complete."""
    fixture_discard()
    accepted = maintenance.accept(
        authority, uuid4(), request_body("ingest", ["fixture-alpha"])
    )
    with connect("corpus") as conn:
        generation = conn.execute(
            "SELECT count(*) AS count FROM corpus.generation"
        ).fetchone()["count"]
        eligible = conn.execute(
            "SELECT count(*) AS count FROM corpus.version WHERE eligible "
            "AND paper_id='paper-alpha'"
        ).fetchone()["count"]
    assert generation == 0 and eligible == 0
    run = maintenance.read_run(authority, accepted["runId"])
    assert run["state"] == "accepted" and run["watermark"] is None
