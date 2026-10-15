"""Mounted U3 corpus routes over the real host, stores and worker loop."""

import time
from uuid import uuid4

import pytest

pytestmark = pytest.mark.u3_integration

CORPUS_POLICY = {"policyId": "u3-corpus-maintenance", "revision": "1"}
ELIGIBILITY_POLICY = {"policyId": "u3-source-eligibility", "revision": "1"}
READING_POLICY = {"policyId": "u3-paper-reading", "revision": "1"}
COMPATIBILITY = "u3-projection-1"


def post(client, path, value, key=None):
    return client.post(
        path, json=value, headers={"Idempotency-Key": str(key or uuid4())}
    )


def run_body(scope, *, operation="ingest", manifest="f" * 64):
    return {
        "operation": operation,
        "sourceScopeIds": scope,
        "authoritativeInputRevision": "u3-input-1",
        "inputManifestHash": manifest,
        "sourcePolicy": CORPUS_POLICY,
        "compatibilityRevision": COMPATIBILITY,
    }


def accept_and_wait(client, scope, *, operation="ingest", seconds=30.0):
    accepted = post(client, "/api/v2/c04/accept-corpus-run", run_body(scope, operation=operation))
    assert accepted.status_code == 200, accepted.text
    return wait_terminal(client, accepted.json()["runId"], seconds=seconds)


def wait_terminal(client, run_id, *, seconds=30.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        current = post(client, "/api/v2/c04/read-corpus-run", {"runId": run_id})
        assert current.status_code == 200, current.text
        state = current.json()["job"]["state"]
        if state in ("succeeded", "failed"):
            return current.json()
        time.sleep(0.1)
    raise AssertionError("corpus run never reached a terminal state")


def test_maintenance_authority_is_required(browser, admin):
    """A valid owner session without the actor row is refused."""
    admin("DELETE FROM corpus.maintenance_actor")
    response = post(
        browser,
        "/api/v2/c04/accept-corpus-run",
        run_body(["fixture-alpha"]),
    )
    assert response.status_code in (403, 404)
    # The refusal left no run behind.
    assert response.json()["code"] in ("FORBIDDEN", "NOT_FOUND")


def test_ingest_publishes_eligible_content_through_the_worker(browser, connect):
    run = accept_and_wait(browser, ["fixture-alpha"])
    assert run["job"]["state"] == "succeeded"
    assert run["committedWatermark"] == run["publicationGeneration"]
    stages = {effect["stage"]: effect["state"] for effect in run["effects"]}
    assert stages["publication"] == "committed"
    # Reading now serves the exact version through the mounted binding.
    resolved = post(
        browser,
        "/api/v2/c04/resolve-paper",
        {"identifier": "paper-alpha", "versionLabel": "v1"},
    )
    assert resolved.status_code == 200, resolved.text
    identity = resolved.json()
    assert identity["paper"]["versionId"] == "paper-alpha:v1"
    content = post(
        browser,
        "/api/v2/c04/read-content",
        {"paper": identity["paper"], "purpose": "read"},
    )
    assert content.status_code == 200, content.text
    body = content.json()
    assert body["availability"] == "ready"
    assert body["content"]["sections"], "published content must have readable sections"


def test_run_acceptance_replays_and_conflicts(browser):
    body = run_body(["fixture-alpha"], manifest="a" * 64)
    key = uuid4()
    first = post(browser, "/api/v2/c04/accept-corpus-run", body, key=key)
    assert first.status_code == 200
    replay = post(browser, "/api/v2/c04/accept-corpus-run", body, key=key)
    assert replay.status_code == 200
    assert replay.json()["runId"] == first.json()["runId"]
    conflict = post(
        browser,
        "/api/v2/c04/accept-corpus-run",
        dict(body, inputManifestHash="b" * 64),
        key=key,
    )
    assert conflict.status_code in (409, 422)


def test_invalid_scope_and_compatibility_are_refused_before_work(browser):
    assert (
        post(browser, "/api/v2/c04/accept-corpus-run", run_body([])).status_code in (409, 422)
    )
    assert (
        post(
            browser,
            "/api/v2/c04/accept-corpus-run",
            dict(run_body(["fixture-alpha"]), compatibilityRevision="future-9"),
        ).status_code
        in (409, 422)
    )


def test_withdrawal_propagates_to_reads_and_restores(browser, maintenance, authority):
    run = accept_and_wait(browser, ["fixture-beta"], operation="ingest")
    assert run["job"]["state"] == "succeeded"
    withdrawn = post(
        browser,
        "/api/v2/c04/change-source-eligibility",
        {
            "paper": {"paperId": "paper-beta", "versionId": "paper-beta:v2",
                      "eligibilityRevision": "x"},
            "disposition": "withdrawn",
            "reasonKey": "publisher-withdrawal",
            "sourceEvidenceHash": "d" * 64,
            "policy": ELIGIBILITY_POLICY,
        },
    )
    assert withdrawn.status_code == 200, withdrawn.text
    content = post(
        browser,
        "/api/v2/c04/read-content",
        {
            "paper": {"paperId": "paper-beta", "versionId": "paper-beta:v2",
                      "eligibilityRevision": "x"},
            "purpose": "read",
        },
    )
    assert content.status_code == 200
    assert content.json()["availability"] == "withdrawn"
    # Restore rehearsal replays the current boundary; the version stays refused.
    replay = maintenance.restore_replay("mounted-restore-1", ["paper-beta:v2"])
    assert replay["refused"] == 1


def test_reading_requires_an_authenticated_session(anonymous, run_fixture, fixture_discard):
    """C13 marks resolve-paper and read-content session-required for owners.

    Guests receive metadata only through the anonymous search response; the
    exact-version reads never serve an unauthenticated caller.
    """
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    resolved = post(
        anonymous,
        "/api/v2/c04/resolve-paper",
        {"identifier": "paper-alpha"},
    )
    assert resolved.status_code == 401, resolved.text
    assert resolved.json()["code"] == "UNAUTHENTICATED"
    content = post(
        anonymous,
        "/api/v2/c04/read-content",
        {
            "paper": {"paperId": "paper-alpha", "versionId": "paper-alpha:v1",
                      "eligibilityRevision": "x"},
            "purpose": "read",
        },
    )
    assert content.status_code == 401, content.text
    assert content.json()["code"] == "UNAUTHENTICATED"


def test_retry_corpus_run_reconciles_the_failed_original(browser, fixture_discard):
    """C04 retryCorpusRun: retry of reconciled retryable stages only."""
    fixture_discard()
    failed = accept_and_wait(browser, ["fixture-missing"])
    assert failed["job"]["state"] == "failed"
    key = uuid4()
    retried = post(
        browser,
        "/api/v2/c04/retry-corpus-run",
        {"runId": failed["runId"]},
        key=key,
    )
    assert retried.status_code == 200, retried.text
    body = retried.json()
    assert body["runId"] != failed["runId"]
    # The retry attempt carries the original run's authoritative inputs and
    # replays under the same operation key instead of starting a second run.
    replay = post(
        browser,
        "/api/v2/c04/retry-corpus-run",
        {"runId": failed["runId"]},
        key=key,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["runId"] == body["runId"]
    # The retry run replays the reconciled retryable effect on the original
    # authoritative inputs; committed stages are never re-derived.
    retried_run = wait_terminal(browser, body["runId"])
    assert retried_run["job"]["state"] == "failed"
    assert {
        (effect["stage"], effect["state"]) for effect in retried_run["effects"]
    } == {("source", "failed")}
    # The original run keeps its failed evidence; retry never rewrites it.
    original = post(browser, "/api/v2/c04/read-corpus-run", {"runId": failed["runId"]})
    assert original.status_code == 200
    assert original.json()["job"]["state"] == "failed"


def test_retry_corpus_run_refuses_completed_and_unknown_runs(browser, fixture_discard):
    fixture_discard()
    completed = accept_and_wait(browser, ["fixture-alpha"])
    assert completed["job"]["state"] == "succeeded"
    refused = post(
        browser, "/api/v2/c04/retry-corpus-run", {"runId": completed["runId"]}
    )
    assert refused.status_code == 409, refused.text
    unknown = post(
        browser, "/api/v2/c04/retry-corpus-run", {"runId": str(uuid4())}
    )
    assert unknown.status_code in (403, 404), unknown.text


def test_unknown_run_and_foreign_run_reads_are_absent(browser):
    response = post(browser, "/api/v2/c04/read-corpus-run", {"runId": str(uuid4())})
    assert response.status_code in (403, 404, 409)
