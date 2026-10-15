"""U3 PaperAssistance repository behavior: acceptance, claims, results, glossary."""

from uuid import uuid4

import pytest

from backend.modules.corpus.repository import CorpusRepository
from backend.modules.summarization.u3_glossary import (
    GlossaryConflict,
    GlossaryInvalid,
    GlossaryService,
    virtual_revision,
)
from backend.modules.summarization.u3_provider import SyntheticAssistanceExecutor

pytestmark = pytest.mark.u3_repository


def test_acceptance_replay_and_changed_input_conflict(
    accepted_job, assistance, authority
):
    key = uuid4()
    job, _, _ = accepted_job(key=key)
    request = job["payload"]["request"]
    replay = assistance["repository"].replay_request(authority, key, request)
    assert replay is not None and replay["intent"]["versionId"] == job["version_id"]
    with pytest.raises(ValueError):
        assistance["repository"].replay_request(
            authority, key, dict(request, optionId="different-option")
        )


def test_claim_fence_ordering_and_replaced_worker(
    accepted_job, assistance, authority, maintenance
):
    job, _, _ = accepted_job()
    claims = assistance["claims"]
    binding = claims.binding(job)
    worker = uuid4()
    first = claims.acquire(binding, worker)
    claim = first["claim"]
    # A second claimant cannot steal a live lease.
    with pytest.raises(ValueError):
        claims.acquire(binding, uuid4())
    # Renewal honours the expected lease revision.
    renewed = claims.renew(claim, expected_lease_revision=claim["leaseRevision"])
    claim.update(renewed["claim"])
    with pytest.raises(ValueError):
        claims.renew(claim, expected_lease_revision=str(uuid4()))
    # A stale expected job revision cannot commit a completion.
    stale = claims.proposal(
        claim, input_hash=binding["inputHash"], expected_job_revision=str(uuid4())
    )
    payload = _canonical_payload(claims, claim, maintenance, worker)
    output = SyntheticAssistanceExecutor().run(payload, 0)
    with pytest.raises(ValueError):
        assistance["repository"].complete(
            stale,
            uuid4(),
            output.content,
            coverage=output.coverage,
            provenance=output.provenance,
        )
    assert assistance["repository"].snapshot(authority, job["id"])["state"] == "running"


def _canonical_payload(claims, claim, maintenance, worker):
    """The real guarded payload assembly, exactly as the worker reads it."""
    from backend.modules.summarization.payload import ExecutionPayloads

    payloads = ExecutionPayloads(
        claims, CorpusRepository(maintenance.transactions, files=None)
    )
    return payloads.read(claim, trusted_worker=worker)


def test_result_reads_never_regenerate_work(
    accepted_job, assistance, maintenance, authority, connect
):
    job, _, _ = accepted_job()
    repository = assistance["repository"]
    binding = assistance["claims"].binding(job)
    claim = assistance["claims"].acquire(binding, uuid4())["claim"]
    with connect("assistance") as conn:
        before = conn.execute(
            "SELECT count(*) AS results FROM assistance.result"
        ).fetchone()["results"]
    # Unknown identities read as contract-safe absent, never as another owner's data.
    assert repository.result_metadata(authority, uuid4()) is None
    with pytest.raises(PermissionError):
        repository.snapshot(authority, uuid4())
    snapshot = repository.snapshot(authority, job["id"])
    assert snapshot["state"] in ("accepted", "running")
    assert repository.result_reference(authority, job["id"]) is None
    with connect("assistance") as conn:
        after = conn.execute(
            "SELECT count(*) AS results FROM assistance.result"
        ).fetchone()["results"]
    assert before == after == 0
    assert claim["fence"] == 1


def test_synthetic_executor_completes_through_the_real_claim_path(
    accepted_job, assistance, authority, maintenance, connect
):
    job, _, _ = accepted_job()
    repository = assistance["repository"]
    claims = assistance["claims"]
    binding = claims.binding(job)
    worker = uuid4()
    claim = claims.acquire(binding, worker)["claim"]
    payload = _canonical_payload(claims, claim, maintenance, worker)
    output = SyntheticAssistanceExecutor().run(payload, 0)
    assert output.provenance["synthetic"] is True
    bound = claims.read_input(claim)
    proposal = claims.proposal(
        claim,
        input_hash=binding["inputHash"],
        expected_job_revision=str(bound["jobRevision"]),
    )
    fact = uuid4()
    receipt = repository.complete(
        proposal, fact, output.content, coverage=output.coverage, provenance=output.provenance
    )
    assert receipt["jobId"] == str(job["id"])
    snapshot = repository.snapshot(authority, job["id"])
    assert snapshot["state"] == "succeeded"
    # The durable completion fact replays the original outcome.
    replay = repository.complete(
        proposal, fact, output.content, coverage=output.coverage, provenance=output.provenance
    )
    assert replay == receipt


def test_glossary_cas_and_virtual_empty(transactions, authority, fixture_discard):
    fixture_discard()
    service = GlossaryService(transactions)
    empty = service.read(authority)
    assert empty["terms"] == []
    assert empty["revision"] == virtual_revision(authority.account_id)
    written = service.replace(
        authority,
        {
            "expectedRevision": empty["revision"],
            "normalizationPolicy": {"policyId": "u3-owner-glossary", "revision": "1"},
            "terms": [
                {"termId": None, "source": "attention", "preferred": "어텐션", "languageId": "ko"}
            ],
        },
    )
    assert written["revision"] != empty["revision"]
    # A stale revision conflicts and preserves the committed glossary.
    with pytest.raises(GlossaryConflict):
        service.replace(
            authority,
            {
                "expectedRevision": empty["revision"],
                "normalizationPolicy": {"policyId": "u3-owner-glossary", "revision": "1"},
                "terms": [],
            },
        )
    assert service.read(authority)["terms"] == written["terms"]
    # Duplicate/empty/oversized inputs are refused with the committed values intact.
    for bad in (
        [
            {"termId": None, "source": "same", "preferred": "same", "languageId": "ko"},
        ],
        [{"termId": None, "source": "  ", "preferred": "x", "languageId": "ko"}],
        [{"termId": None, "source": "x" * 200, "preferred": "y", "languageId": "ko"}],
        [
            {"termId": None, "source": "a", "preferred": "b", "languageId": "ko"},
            {"termId": None, "source": "Ａ", "preferred": "c", "languageId": "ko"},
            {"termId": None, "source": "a", "preferred": "d", "languageId": "ko"},
        ],
    ):
        with pytest.raises(GlossaryInvalid):
            service.replace(
                authority,
                {
                    "expectedRevision": written["revision"],
                    "normalizationPolicy": {"policyId": "u3-owner-glossary", "revision": "1"},
                    "terms": bad,
                },
            )
    assert service.read(authority)["terms"] == written["terms"]


def test_progress_events_are_ordered_and_bounded(
    accepted_job, assistance, authority, connect
):
    job, _, _ = accepted_job()
    repository = assistance["repository"]
    claims = assistance["claims"]
    claims.acquire(claims.binding(job), uuid4())
    events = repository.events(authority, job["id"], 0)
    assert [event["sequence"] for event in events] == sorted(
        event["sequence"] for event in events
    )
    assert events and events[-1]["sequence"] >= 1
    again = repository.events(authority, job["id"], events[-1]["sequence"])
    assert again == []
