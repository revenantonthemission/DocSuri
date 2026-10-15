"""U3 corpus maintenance component behavior: staged effects and truthfulness."""

import hashlib
from uuid import uuid4

import pytest

from backend.modules.corpus.maintenance import CorpusMaintenance, SourceUnavailable
from fixtures import MemorySources, request_body, source_record

pytestmark = pytest.mark.u3_component


def _run(maintenance, authority, scope, operation="ingest"):
    accepted = maintenance.accept(authority, uuid4(), request_body(operation, scope))
    outcome = maintenance.execute(accepted["runId"])
    return accepted, outcome


def test_unresolved_permission_yields_explicit_failed_effect(
    transactions, authority, maintenance_authority, fixture_discard, realm
):
    fixture_discard()
    from backend.artifacts import PrivateArtifacts

    sources = MemorySources(
        {
            "fixture-blocked": source_record(
                "fixture-blocked", paper_id="paper-blocked", permission="unresolved"
            )
        }
    )
    files = PrivateArtifacts(realm[0].root / "corpus-files", maximum_bytes=2097152)
    maintenance = CorpusMaintenance(transactions, files, sources)
    accepted = maintenance.accept(authority, uuid4(), request_body("ingest", ["fixture-blocked"]))
    outcome = maintenance.execute(accepted["runId"])
    assert outcome["state"] == "failed"
    run = maintenance.read_run(authority, accepted["runId"])
    assert run["watermark"] is None
    content_effect = next(
        effect for effect in run["effects"] if effect["stage"] == "content"
    )
    assert content_effect["state"] == "failed"
    assert content_effect["error"] == "source-permission-unresolved"
    # No eligible version is visible for the blocked source.
    assert all(
        effect["state"] != "committed" or effect["stage"] == "source"
        for effect in run["effects"]
    )


def test_unavailable_source_records_failed_source_effect(
    transactions, authority, maintenance_authority, fixture_discard, realm
):
    fixture_discard()
    from backend.artifacts import PrivateArtifacts

    maintenance = CorpusMaintenance(
        transactions,
        PrivateArtifacts(realm[0].root / "corpus-files", maximum_bytes=2097152),
        MemorySources({}),
    )
    accepted = maintenance.accept(authority, uuid4(), request_body("ingest", ["fixture-missing"]))
    outcome = maintenance.execute(accepted["runId"])
    assert outcome["state"] == "failed"
    run = maintenance.read_run(authority, accepted["runId"])
    source_effect = next(
        effect for effect in run["effects"] if effect["stage"] == "source"
    )
    assert source_effect["state"] == "failed" and source_effect["error"] == "source-unavailable"
    assert run["watermark"] is None


def test_malformed_source_record_is_classified_not_dropped(
    transactions, authority, maintenance_authority, fixture_discard, realm
):
    fixture_discard()
    from backend.artifacts import PrivateArtifacts

    broken = source_record("fixture-broken", paper_id="paper-broken")
    broken["content"] = {"document": {"sections": []}, "chunks": []}
    maintenance = CorpusMaintenance(
        transactions,
        PrivateArtifacts(realm[0].root / "corpus-files", maximum_bytes=2097152),
        MemorySources({"fixture-broken": broken}),
    )
    accepted = maintenance.accept(authority, uuid4(), request_body("ingest", ["fixture-broken"]))
    outcome = maintenance.execute(accepted["runId"])
    assert outcome["state"] == "failed"
    assert outcome["outstanding"], "outstanding effects must stay inspectable"
    run = maintenance.read_run(authority, accepted["runId"])
    assert any(
        effect["error"] == "parsed-document-model-missing" for effect in run["effects"]
    )


def test_oversized_document_is_refused_with_bounded_evidence(
    transactions, authority, maintenance_authority, fixture_discard, realm
):
    fixture_discard()
    from backend.artifacts import PrivateArtifacts

    record = source_record("fixture-huge", paper_id="paper-huge")
    record["content"]["document"]["sections"][0]["blocks"] = [
        {"type": "paragraph", "id": "huge-block", "text": "x" * 8192}
    ]
    record["content"]["chunks"] = [
        {
            "anchor": "huge-block",
            "section": "Introduction",
            "text": "x" * 8192,
            "kind": "paragraph",
            "textHash": hashlib.sha256(("x" * 8192).encode()).hexdigest(),
        }
    ] * 300
    maintenance = CorpusMaintenance(
        transactions,
        PrivateArtifacts(realm[0].root / "corpus-files", maximum_bytes=2097152),
        MemorySources({"fixture-huge": record}),
    )
    accepted = maintenance.accept(authority, uuid4(), request_body("ingest", ["fixture-huge"]))
    outcome = maintenance.execute(accepted["runId"])
    assert outcome["state"] == "failed"
    run = maintenance.read_run(authority, accepted["runId"])
    assert "content" in {effect["stage"] for effect in run["effects"]}


def test_run_scope_bounds_are_server_validated(
    transactions, authority, maintenance_authority, fixture_discard, realm
):
    fixture_discard()
    from backend.artifacts import PrivateArtifacts

    maintenance = CorpusMaintenance(
        transactions,
        PrivateArtifacts(realm[0].root / "corpus-files", maximum_bytes=2097152),
        MemorySources({}),
    )
    with pytest.raises(ValueError):
        maintenance.accept(authority, uuid4(), request_body("ingest", []))
    with pytest.raises(ValueError):
        maintenance.accept(
            authority,
            uuid4(),
            request_body("ingest", ["a", "a", "b"]),
        )
    with pytest.raises(ValueError):
        maintenance.accept(
            authority,
            uuid4(),
            dict(request_body("ingest", ["a"]), operation="explode"),
        )
    with pytest.raises(ValueError):
        maintenance.accept(
            authority,
            uuid4(),
            dict(request_body("ingest", ["a"]), compatibilityRevision="future-9"),
        )


def test_failed_run_retains_effects_and_retry_reconciles(
    transactions, authority, maintenance_authority, fixture_discard, realm, sources
):
    fixture_discard()
    from backend.artifacts import PrivateArtifacts

    files = PrivateArtifacts(realm[0].root / "corpus-files", maximum_bytes=2097152)
    good = source_record("fixture-alpha", paper_id="paper-alpha")

    class Flaky(MemorySources):
        def read(self, source_id):
            if self.fail_once:
                self.fail_once = False
                raise SourceUnavailable(source_id)
            return super().read(source_id)

    provider = Flaky({"fixture-alpha": good})
    provider.fail_once = True
    maintenance = CorpusMaintenance(transactions, files, provider)
    body = request_body("ingest", ["fixture-alpha"])
    accepted = maintenance.accept(authority, uuid4(), body)
    first = maintenance.execute(accepted["runId"])
    assert first["state"] == "failed"
    preserved = maintenance.read_run(authority, accepted["runId"])
    retry = maintenance.retry(
        authority, uuid4(), {**body, "retryOf": accepted["runId"]}
    )
    second = maintenance.execute(retry["runId"])
    assert second["state"] == "completed"
    # The original run keeps its failed evidence; retry never rewrites it.
    assert maintenance.read_run(authority, accepted["runId"])["state"] == "failed"
    assert preserved["runId"] == accepted["runId"]


def test_rebuild_rederives_everything_from_named_inputs(
    transactions, authority, maintenance_authority, fixture_discard, realm
):
    fixture_discard()
    from backend.artifacts import PrivateArtifacts

    maintenance = CorpusMaintenance(
        transactions,
        PrivateArtifacts(realm[0].root / "corpus-files", maximum_bytes=2097152),
        MemorySources({"fixture-alpha": source_record("fixture-alpha", paper_id="paper-alpha")}),
    )
    first = maintenance.accept(authority, uuid4(), request_body("ingest", ["fixture-alpha"]))
    maintenance.execute(first["runId"])
    rebuild = maintenance.rebuild(
        authority, uuid4(), request_body("rebuild", ["fixture-alpha"])
    )
    outcome = maintenance.execute(rebuild["runId"])
    assert outcome["state"] == "completed"
    run = maintenance.read_run(authority, rebuild["runId"])
    stages = {effect["stage"] for effect in run["effects"]}
    assert {"source", "content", "projection", "publication"} <= stages
