"""Applied migration identity survives restart and applied bytes stay immutable."""
import hashlib
from pathlib import Path

import pytest

pytestmark = pytest.mark.u2_database
ROOT = Path(__file__).resolve().parents[3]


def test_run_identity_and_applied_hashes_survive_restart(connect, realm):
    """A fresh connection observes the same run identity and hash record."""
    from scripts.verify_docsuri_u2 import MIGRATIONS

    profile = realm[0]
    with connect("operations") as first:
        original = first.execute(
            "SELECT run_id,schema_hashes FROM public.docsuri_local_identity"
        ).fetchone()
    assert original["run_id"] == profile.run_id
    with connect("operations") as restarted:
        again = restarted.execute(
            "SELECT run_id,schema_hashes FROM public.docsuri_local_identity"
        ).fetchone()
    assert again == original
    # Restart means new connections to the same realm; it must never reseed.
    assert len(again["schema_hashes"]) >= len(MIGRATIONS)


def test_every_applied_migration_file_matches_its_retained_hash(connect):
    """Editing an applied migration must be refused by construction: hashes differ."""
    from scripts.verify_docsuri_u2 import MIGRATIONS

    with connect("operations") as conn:
        stored = conn.execute(
            "SELECT schema_hashes FROM public.docsuri_local_identity"
        ).fetchone()["schema_hashes"]
    assert stored
    mismatched = []
    for _, relative in MIGRATIONS:
        digest = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        if stored.get(relative) != digest:
            mismatched.append(relative)
    assert not mismatched, "applied migration bytes changed: " + ", ".join(mismatched)


def test_unknown_schema_cannot_be_observed_as_ready(connect, transactions):
    """A capability that has no registered probe is never silently ready."""
    from backend.local_observation import PROBES, observe_all, record

    assert "u2-unknown" not in PROBES
    # Each realm is disposable: a freshly migrated one has never been served, so
    # record one bounded observation pass through the owned writer before reading.
    record(transactions, observe_all(transactions))
    with connect("operations") as conn:
        rows = conn.execute(
            "SELECT capability FROM operations.observation"
        ).fetchall()
    assert rows
    assert all(row["capability"] in PROBES for row in rows)
