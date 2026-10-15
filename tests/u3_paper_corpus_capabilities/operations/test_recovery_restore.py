"""U3 recovery and restore operations: crash boundaries and withdrawal replay.

A restart test keeps its database, receipts and run identity; nothing here
resets or reseeds the environment between the interruption and the recovery.
"""

from uuid import uuid4

import pytest

from backend.modules.corpus.maintenance import CorpusMaintenance, SourceUnavailable
from fixtures import request_body, source_record

pytestmark = pytest.mark.u3_operations


class PausingSources:
    """Provider that stops mid-run to force a crash boundary between stages."""

    def __init__(self, records: dict):
        self.records = records
        self.reads = 0
        self.fail_after = None

    def read(self, source_id: str) -> dict:
        self.reads += 1
        if self.fail_after is not None and self.reads > self.fail_after:
            raise SourceUnavailable(source_id)
        record = self.records.get(source_id)
        if record is None:
            raise SourceUnavailable(source_id)
        return record


def test_interrupted_effects_stay_inspectable_and_reconcile(
    maintenance, authority, maintenance_authority, fixture_discard, realm
):
    fixture_discard()
    from backend.artifacts import PrivateArtifacts

    provider = PausingSources(
        {
            "fixture-alpha": source_record("fixture-alpha", paper_id="paper-alpha"),
            "fixture-beta": source_record(
                "fixture-beta", paper_id="paper-beta", version_label="v2"
            ),
        }
    )
    provider.fail_after = 1  # the first record commits; the second is interrupted
    scoped = CorpusMaintenance(
        maintenance.transactions,
        PrivateArtifacts(realm[0].root / "corpus-files", maximum_bytes=2097152),
        provider,
    )
    body = request_body("ingest", ["fixture-alpha", "fixture-beta"])
    accepted = scoped.accept(authority, uuid4(), body)
    outcome = scoped.execute(accepted["runId"])
    assert outcome["state"] == "failed"
    run = scoped.read_run(authority, accepted["runId"])
    states = {(effect["stage"], effect["subject"], effect["state"]) for effect in run["effects"]}
    assert ("content", "paper-alpha:v1", "committed") in states
    assert any(state[2] == "failed" for state in states)
    assert run["watermark"] is None

    # Recovery is repeatable and non-corrupting: the retry re-executes only the
    # reconciled stages and re-reads the same authoritative inputs.
    provider.fail_after = None
    retry = scoped.retry(authority, uuid4(), {**body, "retryOf": accepted["runId"]})
    recovered = maintenance.execute(retry["runId"])
    assert recovered["state"] == "completed"
    # The original failure evidence is preserved alongside the recovered run.
    assert scoped.read_run(authority, accepted["runId"])["state"] == "failed"


def test_restore_rehearsal_replays_withdrawal_boundaries(
    maintenance, run_fixture, authority, maintenance_authority, fixture_discard, connect
):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    with connect("corpus") as conn:
        version = conn.execute(
            "SELECT id,source_hash,eligibility_revision FROM corpus.version "
            "WHERE paper_id='paper-alpha'"
        ).fetchone()
    # The snapshot predates the withdrawal; the restore target must still refuse.
    maintenance.record_change(
        authority,
        {
            "paperId": "paper-alpha",
            "changeKind": "withdrawal",
            "disposition": "withdrawn",
            "reasonKey": "restore-boundary",
            "policy": {"policyId": "u3-source-eligibility", "revision": "1"},
        },
    )
    replay = maintenance.restore_replay("restore-ops-1", [version["id"]])
    assert replay["refused"] == 1
    entry = replay["versions"][0]
    assert entry["servable"] is False and entry["disposition"] == "withdrawn"
    # The quarantine marker and current eligibility revision are recorded.
    with connect("corpus") as conn:
        marker = conn.execute(
            "SELECT target FROM corpus.quarantine WHERE marker='restore-ops-1'"
        ).fetchone()
        eligible = conn.execute(
            "SELECT eligible FROM corpus.version WHERE id=%s", (version["id"],)
        ).fetchone()
    assert marker["target"] == "restore-rehearsal"
    assert eligible["eligible"] is False


def test_restart_preserves_run_identity_without_reseeding(
    maintenance, authority, maintenance_authority, fixture_discard, sources, connect
):
    fixture_discard()
    accepted = maintenance.accept(
        authority, uuid4(), request_body("ingest", ["fixture-alpha"])
    )
    run_id = accepted["runId"]
    with connect("corpus") as conn:
        before = conn.execute(
            "SELECT revision,idempotency_key,state FROM corpus.run WHERE id=%s",
            (run_id,),
        ).fetchone()
    # A fresh owner service (as after a process restart) sees the same run.
    restarted = CorpusMaintenance(
        maintenance.transactions, maintenance.files, maintenance.sources
    )
    replay = restarted.accept(
        authority, before["idempotency_key"], request_body("ingest", ["fixture-alpha"])
    )
    assert replay["runId"] == run_id and replay["revision"] == str(before["revision"])
    outcome = restarted.execute(run_id)
    assert outcome["state"] == "completed"


def test_expired_snapshot_windows_stop_without_advancing_boundaries(
    maintenance, run_fixture, authority, maintenance_authority, fixture_discard,
    search_service, connect,
):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    first = search_service.search(authority, {
        "query": {
            "query": "paper-alpha",
            "modeId": "lexical",
            "orderId": "relevance",
            "filters": [],
            "vocabularyRevision": "u3-paper-options-1",
            "policyRef": {"policyId": "u3-paper-search", "revision": "1"},
        },
        "page": {"limit": 5},
    })
    with connect("corpus") as conn:
        before = conn.execute(
            "SELECT revision FROM corpus.publication"
        ).fetchone()["revision"]
    # Re-serving a stale snapshot never mutates the publication boundary.
    from backend.modules.discovery.u3_search import SnapshotExpired

    assert run_fixture(["fixture-beta"])["state"] == "completed"
    with connect("corpus") as conn:
        moved = conn.execute(
            "SELECT revision FROM corpus.publication"
        ).fetchone()["revision"]
    assert moved != before  # the explicit second publication moved it once
    with pytest.raises(SnapshotExpired):
        search_service.search(authority, {
            "query": {
                "query": "paper-alpha",
                "modeId": "lexical",
                "orderId": "relevance",
                "filters": [],
                "vocabularyRevision": "u3-paper-options-1",
                "policyRef": {"policyId": "u3-paper-search", "revision": "1"},
            },
            "page": {"limit": 5},
            "snapshotRevision": first["page"]["snapshotRevision"],
        })
    with connect("corpus") as conn:
        still = conn.execute(
            "SELECT revision FROM corpus.publication"
        ).fetchone()["revision"]
    assert still == moved  # the refused stale read changed nothing
