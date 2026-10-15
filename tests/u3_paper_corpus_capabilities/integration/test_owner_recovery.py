"""Mounted U3 recovery and isolation: lost replies, races, forgery, redaction."""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.u3_integration

CORPUS_POLICY = {"policyId": "u3-corpus-maintenance", "revision": "1"}
COMPATIBILITY = "u3-projection-1"
ENTRY_POLICY = {"policyId": "synthetic-local-entry", "revision": "1"}


def post(client, path, value, key=None):
    return client.post(
        path, json=value, headers={"Idempotency-Key": str(key or uuid4())}
    )


def run_body(scope, *, manifest=None):
    return {
        "operation": "ingest",
        "sourceScopeIds": scope,
        "authoritativeInputRevision": "u3-input-1",
        "inputManifestHash": manifest or "9" * 64,
        "sourcePolicy": CORPUS_POLICY,
        "compatibilityRevision": COMPATIBILITY,
    }


def test_lost_reply_before_commit_reconciles_the_same_run(browser, published_state):
    body = run_body(["fixture-gamma"])
    key = uuid4()
    first = post(browser, "/api/v2/c04/accept-corpus-run", body, key=key)
    assert first.status_code == 200
    # A lost reply is retried with the identical original operation key.
    replay = post(browser, "/api/v2/c04/accept-corpus-run", body, key=key)
    assert replay.status_code == 200
    assert replay.json()["runId"] == first.json()["runId"]
    assert replay.json()["revision"] == first.json()["revision"]


def test_changed_intent_under_the_same_key_conflicts(browser, published_state):
    body = run_body(["fixture-gamma"])
    key = uuid4()
    assert post(browser, "/api/v2/c04/accept-corpus-run", body, key=key).status_code == 200
    conflict = post(
        browser,
        "/api/v2/c04/accept-corpus-run",
        dict(body, sourceScopeIds=["fixture-alpha"]),
        key=key,
    )
    assert conflict.status_code in (409, 422)


def test_unknown_outcome_never_becomes_a_success_shape(browser):
    response = post(browser, "/api/v2/c04/read-corpus-run", {"runId": "not-a-uuid"})
    assert response.status_code in (404, 409, 422)
    assert "effects" not in response.json()


def test_forged_owner_field_is_refused_by_the_contract(browser, published_state):
    """Bodies never carry an owner identity; extra fields are rejected."""
    body = run_body(["fixture-gamma"])
    body["accountId"] = str(uuid4())
    response = post(browser, "/api/v2/c04/accept-corpus-run", body)
    assert response.status_code == 422


def test_withdrawal_racing_reads_is_enforced_immediately(
    browser, published_state, maintenance, authority, run_fixture
):
    outcome = run_fixture(["fixture-gamma"])
    assert outcome["state"] == "completed", outcome["effects"]
    resolved = post(
        browser, "/api/v2/c04/resolve-paper", {"identifier": "paper-gamma"}
    )
    assert resolved.status_code == 200
    paper = resolved.json()["paper"]
    first = post(browser, "/api/v2/c04/read-content", {"paper": paper, "purpose": "read"})
    assert first.status_code == 200 and first.json()["availability"] == "ready"
    maintenance.record_change(
        authority,
        {
            "paperId": paper["paperId"],
            "changeKind": "withdrawal",
            "disposition": "withdrawn",
            "reasonKey": "publisher-withdrawal",
            "policy": {"policyId": "u3-source-eligibility", "revision": "1"},
        },
    )
    second = post(browser, "/api/v2/c04/read-content", {"paper": paper, "purpose": "read"})
    assert second.status_code == 200
    assert second.json()["availability"] == "withdrawn"
    # Search no longer returns the withdrawn paper either.
    search = post(
        browser,
        "/api/v2/c05/search",
        {
            "query": {
                "query": "paper-gamma",
                "modeId": "lexical",
                "orderId": "relevance",
                "filters": [],
                "vocabularyRevision": "u3-paper-options-1",
                "policyRef": {"policyId": "u3-paper-search", "revision": "1"},
            },
            "page": {"limit": 10},
        },
    )
    assert search.status_code == 200, search.text
    assert all(
        hit["paper"]["paperId"] != "paper-gamma" for hit in search.json()["hits"]
    )


def test_dependent_owner_outage_yields_an_explicit_error(
    browser, published_state, monkeypatch, mounted
):
    """A dependency failure is a distinct error state, never a success shape."""
    from backend.modules.discovery import guarded_repository as module

    def broken(self, authority, *, query=""):
        raise ValueError("index outage")

    monkeypatch.setattr(module.GuardedDiscoveryRepository, "snapshot", broken)
    response = post(
        browser,
        "/api/v2/c05/search",
        {
            "query": {
                "query": "paper-alpha",
                "modeId": "lexical",
                "orderId": "relevance",
                "filters": [],
                "vocabularyRevision": "u3-paper-options-1",
                "policyRef": {"policyId": "u3-paper-search", "revision": "1"},
            },
            "page": {"limit": 10},
        },
    )
    assert response.status_code in (409, 503), response.text
    assert "hits" not in response.json()
    assert response.json()["code"] in ("CONFLICT", "DEPENDENCY_UNAVAILABLE")


def test_error_envelopes_carry_no_private_material(browser, published_state):
    response = post(browser, "/api/v2/c06/read-assistance-job", {"jobId": str(uuid4())})
    encoded = response.text
    for forbidden in ("password", "token", "private_path", "authority_revision"):
        assert forbidden not in encoded
    assert response.json()["code"] in ("FORBIDDEN", "NOT_FOUND", "UNAUTHENTICATED")


@pytest.fixture
def published_state(run_fixture, fixture_discard):
    fixture_discard()
    outcome = run_fixture(["fixture-alpha"])
    assert outcome["state"] == "completed", outcome["effects"]
