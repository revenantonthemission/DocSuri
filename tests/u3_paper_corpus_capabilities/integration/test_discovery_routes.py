"""Mounted U3 discovery routes: guest search, citations, snapshot boundaries."""

from uuid import uuid4

import pytest

pytestmark = pytest.mark.u3_integration

SEARCH_POLICY = {"policyId": "u3-paper-search", "revision": "1"}
VOCABULARY = "u3-paper-options-1"
CITATION_POLICY = {"policyId": "u3-citation-traversal", "revision": "1"}


def post(client, path, value, key=None):
    return client.post(
        path, json=value, headers={"Idempotency-Key": str(key or uuid4())}
    )


def query(text="paper-alpha", *, mode="lexical", vocabulary=VOCABULARY):
    return {
        "query": text,
        "modeId": mode,
        "orderId": "relevance",
        "filters": [],
        "vocabularyRevision": vocabulary,
        "policyRef": SEARCH_POLICY,
    }


@pytest.fixture
def published(run_fixture, fixture_discard):
    fixture_discard()
    outcome = run_fixture(["fixture-alpha", "fixture-gamma"])
    assert outcome["state"] == "completed", outcome["effects"]


def test_guest_search_returns_results_without_owner_state(anonymous, published, connect):
    response = post(
        anonymous, "/api/v2/c05/search", {"query": query(), "page": {"limit": 10}}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["hits"], "published eligible content must be retrievable by a guest"
    assert body["outcome"] == "complete"
    assert body["publication"]["complete"] is True
    with connect("discovery") as conn:
        owner_rows = conn.execute(
            "SELECT count(*) AS count FROM discovery.execution WHERE account_id IS NOT NULL"
        ).fetchone()["count"]
    assert owner_rows == 0, "guest search must not write owner history"


def test_semantic_request_discloses_degradation_through_the_route(anonymous, published):
    response = post(
        anonymous,
        "/api/v2/c05/search",
        {"query": query(mode="semantic"), "page": {"limit": 10}},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outcome"] == "degraded"
    assert body["effectiveModeId"] == "lexical"
    assert body["limitations"]


def test_invalid_query_is_refused_before_retrieval(anonymous, published):
    response = post(
        anonymous,
        "/api/v2/c05/search",
        {"query": query("   "), "page": {"limit": 10}},
    )
    assert response.status_code == 422
    response = post(
        anonymous,
        "/api/v2/c05/search",
        {"query": query(vocabulary="other"), "page": {"limit": 10}},
    )
    assert response.status_code == 422


def test_expired_snapshot_returns_the_explicit_boundary(anonymous, published, run_fixture):
    first = post(
        anonymous, "/api/v2/c05/search", {"query": query(), "page": {"limit": 1}}
    )
    snapshot = first.json()["page"]["snapshotRevision"]
    # A later publication replaces the snapshot; the stale revision is explicit.
    assert run_fixture(["fixture-beta"])["state"] == "completed"
    stale = post(
        anonymous,
        "/api/v2/c05/search",
        {"query": query(), "page": {"limit": 1}, "snapshotRevision": snapshot},
    )
    assert stale.status_code == 410
    assert stale.json()["code"] == "SNAPSHOT_EXPIRED"


def test_citation_exploration_is_bounded_labelled_and_saved_through_library(
    browser, published
):
    response = post(
        browser,
        "/api/v2/c05/read-citations",
        {
            "paper": {"paperId": "paper-alpha", "versionId": "paper-alpha:v1",
                      "eligibilityRevision": "x"},
            "direction": "cited",
            "page": {"limit": 20},
            "traversalPolicy": CITATION_POLICY,
            "snapshotRevision": None,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["freshness"] == "current"
    assert body["coverage"] in ("complete", "partial")
    assert body["nodes"] == [] or all(node.get("disposition") for node in body["nodes"])
    # Saving an explored reference runs the Library operation (never Discovery).
    saved = post(
        browser,
        "/api/v2/c03/library-save-paper",
        {
            "paper": {"paperId": "paper-alpha", "versionId": "paper-alpha:v1",
                      "eligibilityRevision": body["root"]["eligibilityRevision"]},
            "policyRef": {"policyId": "synthetic-local-library", "revision": "1"},
        },
    )
    assert saved.status_code == 200, saved.text
    listed = post(
        browser,
        "/api/v2/c03/library-list-saved-papers",
        {"page": {"limit": 20}},
    )
    assert listed.status_code == 200, listed.text
    assert any(
        item["savedPaper"]["paperId"] == "paper-alpha" for item in listed.json()["items"]
    ), listed.text


def test_citation_requests_require_authentication(anonymous, published):
    response = post(
        anonymous,
        "/api/v2/c05/read-citations",
        {
            "paper": {"paperId": "paper-alpha", "versionId": "paper-alpha:v1",
                      "eligibilityRevision": "x"},
            "direction": "cited",
            "page": {"limit": 20},
            "traversalPolicy": CITATION_POLICY,
            "snapshotRevision": None,
        },
    )
    assert response.status_code in (401, 403)
