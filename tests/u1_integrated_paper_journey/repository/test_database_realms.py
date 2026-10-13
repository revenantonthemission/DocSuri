"""Real database identity and shared connection allocation, without fixture reset."""

from dataclasses import replace
from pathlib import Path
import subprocess
import sys

import pytest

from backend.transactions import OwnerTransactions

pytestmark = pytest.mark.u1_repository


def test_journey_database_keeps_diagnostic_sources_separate(realm):
    diagnostic = realm[0]
    journey = diagnostic.journey()
    left = OwnerTransactions(diagnostic)
    right = OwnerTransactions(journey)
    try:
        assert left._gate is right._gate
        for tx, expected in ((left, "docsuri_u1"), (right, "docsuri_u1_journey")):
            identity = tx.run(
                "corpus",
                lambda conn: conn.execute(
                    "SELECT current_database() AS database,run_id FROM public.docsuri_local_identity"
                ).fetchone(),
            )
            assert identity == {"database": expected, "run_id": diagnostic.run_id}
        count = right.run(
            "corpus",
            lambda conn: conn.execute(
                "SELECT count(*) AS count FROM corpus.version WHERE id IN "
                "('fixture-v1','repository-fixture-v1')"
            ).fetchone()["count"],
        )
        assert count == 0
        assert (
            left.run(
                "corpus",
                lambda conn: conn.execute(
                    "SELECT count(*) AS count FROM corpus.version WHERE id='fixture-v1'"
                ).fetchone()["count"],
            )
            == 1
        )
    finally:
        left.close()
        right.close()


def test_unknown_database_and_wrong_run_cannot_use_owner_repository(realm):
    with pytest.raises(ValueError, match="database realm"):
        OwnerTransactions(replace(realm[0], database_name="postgres"))
    with pytest.raises(ValueError, match="credential identity"):
        OwnerTransactions(replace(realm[0], run_id="different-owned-run"))


def test_provisioner_refuses_busy_lock_and_replays_without_reset(connect):
    command = [sys.executable, "scripts/bootstrap_docsuri_u1.py", "--journey"]
    root = Path(__file__).resolve().parents[3]
    with connect("corpus") as conn:
        assert conn.execute("SELECT pg_try_advisory_lock(72411011)").fetchone()[0]
        try:
            busy = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=8)
            assert busy.returncode == 2 and "Refused" in busy.stderr
        finally:
            conn.execute("SELECT pg_advisory_unlock(72411011)")
    repeated = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=8)
    assert repeated.returncode == 0, repeated.stderr
    assert "verified-with-explicit-amendments" in repeated.stdout
