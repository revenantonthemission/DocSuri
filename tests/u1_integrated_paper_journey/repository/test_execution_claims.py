from copy import deepcopy
from uuid import uuid4

import pytest
from psycopg.errors import InsufficientPrivilege

from backend.modules.summarization.admission import AssistanceAdmission
from backend.modules.summarization.execution import ExecutionClaims

pytestmark = pytest.mark.u1_repository


def accepted(r):
    payload = {
        "versionId": r["ids"]["version"],
        "sourceHash": "a" * 64,
        "action": "summary",
        "fixtureFamily": "repository-boundary",
    }
    job = AssistanceAdmission(r["pa"], r["usage"]).accept(r["authority"], uuid4(), payload)
    return job, ExecutionClaims(r["pa"])


def test_same_worker_redelivery_recovers_identical_live_claim(repositories):
    job, claims = accepted(repositories)
    binding, worker = claims.binding(job), uuid4()
    first = claims.acquire(binding, worker)
    assert claims.acquire(binding, worker) == first
    assert claims.read_input(first["claim"])["payload"] == job["payload"]
    with pytest.raises(ValueError):
        claims.acquire(binding, uuid4())


@pytest.mark.parametrize(
    "field,value",
    [
        ("inputHash", "b" * 64),
        ("inputRevision", str(uuid4())),
        ("payloadRef", str(uuid4())),
        ("ownerComponent", "ResearchWorkspace"),
    ],
)
def test_changed_binding_is_denied_on_acquire_payload_renew_and_fact(repositories, field, value):
    job, claims = accepted(repositories)
    binding = claims.binding(job)
    changed = dict(binding, **{field: value})
    with pytest.raises(ValueError, match="binding mismatch"):
        claims.acquire(changed, uuid4())
    current = claims.acquire(binding, uuid4())
    bad = deepcopy(current["claim"])
    bad["binding"] = changed
    for call in (
        lambda: claims.read_input(bad),
        lambda: claims.renew(bad, expected_lease_revision=bad["leaseRevision"]),
        lambda: claims.proposal(
            bad, input_hash=changed["inputHash"], expected_job_revision=current["jobRevision"]
        ),
    ):
        with pytest.raises(ValueError, match="binding mismatch"):
            call()
    assert claims.read_input(current["claim"])["binding"] == binding


def test_renew_changes_only_lease_revision_and_preserves_original_work_deadline(repositories):
    job, claims = accepted(repositories)
    first = claims.acquire(claims.binding(job), uuid4())
    old_input = claims.read_input(first["claim"])
    renewed = claims.renew(first["claim"], expected_lease_revision=first["claim"]["leaseRevision"])
    assert renewed["jobRevision"] == first["jobRevision"]
    assert renewed["acceptedAt"] == first["acceptedAt"]
    assert renewed["claim"]["leaseRevision"] != first["claim"]["leaseRevision"]
    assert renewed["claim"]["fence"] == first["claim"]["fence"]
    new_input = claims.read_input(renewed["claim"])
    assert new_input["startedAt"] == old_input["startedAt"]
    assert new_input["remainingSeconds"] <= old_input["remainingSeconds"]


def test_reclaim_requires_exact_previous_fence_and_preserves_acceptance(repositories, connect):
    job, claims = accepted(repositories)
    binding = claims.binding(job)
    first = claims.acquire(binding, uuid4())
    started = claims.read_input(first["claim"])["startedAt"]
    with connect("assistance") as conn:
        conn.execute(
            "UPDATE assistance.job SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE id=%s",
            (job["id"],),
        )
    with pytest.raises(ValueError):
        claims.acquire(binding, uuid4())
    with pytest.raises(ValueError):
        claims.acquire(binding, uuid4(), previous_fence=first["claim"]["fence"] + 1)
    second = claims.acquire(binding, uuid4(), previous_fence=first["claim"]["fence"])
    assert second["claim"]["fence"] == first["claim"]["fence"] + 1
    assert second["acceptedAt"] == first["acceptedAt"]
    assert claims.read_input(second["claim"])["startedAt"] == started
    with pytest.raises(InsufficientPrivilege):
        claims.read_input(first["claim"])


def test_current_authority_precedes_same_worker_claim_replay(repositories, connect):
    r = repositories
    job, claims = accepted(r)
    binding, worker = claims.binding(job), uuid4()
    claims.acquire(binding, worker)
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.account SET active=false WHERE id=%s", (r["ids"]["a"],))
    with pytest.raises(InsufficientPrivilege):
        claims.acquire(binding, worker)
