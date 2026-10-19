"""U3 diagnostics operations: seeded defect repair, readiness and redaction."""

import json
from pathlib import Path

import pytest

from backend import local_observation
from backend.transactions import OWNERS, OwnerTransactions

pytestmark = pytest.mark.u3_operations


def test_readiness_distinguishes_observed_unknown_and_stale(
    realm, connect, fixture_discard
):
    fixture_discard()
    transactions = OwnerTransactions(realm[0], process="observation")
    try:
        observations = local_observation.observe_all(transactions)
        assert set(observations) == set(OWNERS)
        assert "research" not in observations
        for owner, row in observations.items():
            assert row["disposition"] in ("available", "unavailable")
            assert isinstance(row["evidence"], dict)
        # A missing relation is observed as unavailable with a bounded reason.
        from backend.local_observation import OwnerProbe, probe_owner

        broken = OwnerProbe("SELECT count(*) AS count FROM corpus.no_such_table")
        local_observation.PROBES["__probe__"] = broken
        try:
            observed = probe_owner(transactions, "__probe__")
        finally:
            del local_observation.PROBES["__probe__"]
        assert observed["disposition"] == "unavailable"
        assert observed["evidence"]["reasonKey"] in (
            "observation.storeDenied",
            "observation.storeUnavailable",
        )
        assert "no_such_table" not in str(observed)
    finally:
        transactions.close()


def test_seeded_defect_is_visible_and_repairable(
    maintenance, run_fixture, authority, maintenance_authority, fixture_discard,
    sources, realm, connect,
):
    """A seeded provider defect is reproduced, repaired and rechecked."""
    fixture_discard()

    original = dict(sources.records["fixture-alpha"])
    sources.records["fixture-alpha"] = {**original, "content": {"document": {"sections": []}}}
    try:
        accepted = maintenance.accept(
            authority, uuid4_body(), _ingest_body()
        )
        outcome = maintenance.execute(accepted["runId"])
        assert outcome["state"] == "failed"
        run = maintenance.read_run(authority, accepted["runId"])
        assert any(effect["error"] == "parsed-document-model-missing" for effect in run["effects"])
    finally:
        sources.records["fixture-alpha"] = original
    # Repair: the same authoritative inputs now complete without residue.
    repaired = run_fixture(["fixture-alpha"])
    assert repaired["state"] == "completed"
    with connect("corpus") as conn:
        versions = conn.execute(
            "SELECT count(*) AS count FROM corpus.version WHERE paper_id='paper-alpha'"
        ).fetchone()["count"]
    assert versions == 1


def uuid4_body():
    from uuid import uuid4

    return uuid4()


def _ingest_body():
    from fixtures import request_body

    return request_body("ingest", ["fixture-alpha"])


def test_diagnostics_are_secret_free(realm, fixture_discard):
    """Evidence written to the run root carries no credentials or seeds."""
    fixture_discard()
    run_root = Path(realm[0].root)
    secret_values = []
    credentials = json.loads((run_root / "owner-credentials.json").read_text())
    secret_values.extend(credentials["roles"].values())
    keys = json.loads((run_root / "corpus-keys.json").read_text())
    secret_values.extend(value for key, value in keys.items() if key.endswith("cursor") or key.endswith("provider"))
    admin = json.loads((run_root / "migration-credentials.json").read_text())
    secret_values.append(admin["databaseAdminPassword"])
    # The U3 runner's private phase logs are named u3-phase-*.log; the running
    # phase's own log exists even in a fresh realm that has no prior evidence.
    inspected = (
        list(run_root.glob("*evidence*.json"))
        + list(run_root.glob("browser-*.log"))
        + list(run_root.glob("u3-phase-*.log"))
    )
    for path in inspected:
        text = path.read_text(errors="replace")
        for secret in secret_values:
            assert secret not in text, f"secret material leaked into {path.name}"
    assert inspected, "at least one evidence file must exist for the redaction scan"


def test_unknown_capability_never_reports_ready_without_evidence(
    realm, fixture_discard
):
    """An owner whose store cannot be observed is never reported available."""
    fixture_discard()
    transactions = OwnerTransactions(realm[0], process="observation")
    try:
        assessment = local_observation.readiness(transactions, {"accounts", "corpus"})
        assert assessment["ready"] is True
        statuses = {row["capability"]: row["status"] for row in assessment["observations"]}
        assert statuses["accounts"] == "available"
        assessment = local_observation.readiness(
            transactions, {"accounts", "unobserved-owner"}
        )
        assert assessment["ready"] is False
        assert "unobserved-owner" in assessment["missing"]
    finally:
        transactions.close()
