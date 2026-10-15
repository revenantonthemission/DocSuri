"""U3 Discovery repository behavior: guest anonymity, facts, snapshots, citations."""

from uuid import uuid4

import pytest

from backend.modules.discovery.u3_search import SnapshotExpired

pytestmark = pytest.mark.u3_repository

SEARCH_POLICY = {"policyId": "u3-paper-search", "revision": "1"}
VOCABULARY = "u3-paper-options-1"


def query(text="paper-alpha", *, mode="lexical", order="relevance"):
    return {
        "query": text,
        "modeId": mode,
        "orderId": order,
        "filters": [],
        "vocabularyRevision": VOCABULARY,
        "policyRef": SEARCH_POLICY,
    }


def test_guest_search_is_anonymous_by_construction(
    maintenance, run_fixture, authority, maintenance_authority, search_service, fixture_discard, connect
):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    response = search_service.search(None, {"query": query(), "page": {"limit": 10}})
    assert response["hits"], "published eligible content must be retrievable"
    assert response["hits"][0]["paper"]["paperId"] == "paper-alpha"
    with connect("discovery") as conn:
        executions = conn.execute(
            "SELECT count(*) AS count FROM discovery.execution WHERE account_id IS NULL"
        ).fetchone()["count"]
        owner_rows = conn.execute(
            "SELECT count(*) AS count FROM discovery.execution WHERE account_id IS NOT NULL"
        ).fetchone()["count"]
    assert executions == 0, "guest search creates no execution fact"
    assert owner_rows == 0


def test_owner_search_records_durable_fact_and_checkpoint(
    maintenance, run_fixture, authority, maintenance_authority, search_service, fixture_discard, connect
):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    first = search_service.search(authority, {"query": query(), "page": {"limit": 10}})
    search_service.search(
        authority, {"query": query("paper-alpha second"), "page": {"limit": 10}}
    )
    assert first["outcome"] == "complete"
    with connect("discovery") as conn:
        rows = conn.execute(
            "SELECT id,relay_state,snapshot_revision,degradation FROM discovery.execution "
            "WHERE account_id=%s ORDER BY completed_at",
            (authority.account_id,),
        ).fetchall()
    assert [row["relay_state"] for row in rows] == ["delivered", "delivered"]
    assert all(row["degradation"] == "none" for row in rows)
    checkpoint = search_service.checkpoint(authority)
    assert checkpoint["admissionSequence"] >= 2
    with connect("library") as conn:
        history = conn.execute(
            "SELECT count(*) AS count FROM library.history WHERE account_id=%s",
            (authority.account_id,),
        ).fetchone()["count"]
    assert history == 2


def test_semantic_request_discloses_lexical_degradation(
    maintenance, run_fixture, authority, maintenance_authority, search_service, fixture_discard
):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    response = search_service.search(
        authority, {"query": query(mode="semantic"), "page": {"limit": 10}}
    )
    assert response["outcome"] == "degraded"
    assert response["effectiveModeId"] == "lexical"
    assert any("의미 검색" in item for item in response["limitations"])
    assert response["hits"], "disclosed fallback still returns real lexical results"


def test_snapshot_window_expires_when_publication_changes(
    maintenance, run_fixture, authority, maintenance_authority, search_service, sources, fixture_discard
):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    first = search_service.search(authority, {"query": query(), "page": {"limit": 1}})
    snapshot = first["page"]["snapshotRevision"]
    assert first["page"]["nextCursor"] is None or first["page"]["nextCursor"]
    # A second publication moves the snapshot; the stale revision is explicit.
    from fixtures import request_body

    accepted = maintenance.accept(
        authority, uuid4(), request_body("ingest", ["fixture-beta"])
    )
    maintenance.execute(accepted["runId"])
    with pytest.raises(SnapshotExpired):
        search_service.search(
            authority,
            {"query": query(), "page": {"limit": 1}, "snapshotRevision": snapshot},
        )
    # Repeating the search without the stale revision succeeds on the new snapshot.
    again = search_service.search(authority, {"query": query(), "page": {"limit": 1}})
    assert again["page"]["snapshotRevision"] != snapshot


def test_search_reads_do_not_write(
    maintenance, run_fixture, authority, maintenance_authority, search_service, fixture_discard, connect
):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    with connect("corpus") as conn:
        before = conn.execute(
            "SELECT revision FROM corpus.publication"
        ).fetchone()["revision"]
    for _ in range(3):
        search_service.search(None, {"query": query(), "page": {"limit": 10}})
    with connect("corpus") as conn:
        after = conn.execute(
            "SELECT revision FROM corpus.publication"
        ).fetchone()["revision"]
    assert before == after


def test_citations_are_bounded_labelled_and_persisted(
    maintenance, run_fixture, authority, maintenance_authority, citations, fixture_discard, connect
):
    from fixtures import StaticCitationRecords

    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    records = StaticCitationRecords.chain(
        "paper-alpha:v1",
        links=[
            ("paper-alpha:v1", "paper-cited:v1"),
            ("paper-cited:v1", "paper-deep:v1"),
            ("paper-alpha:v1", "paper-cited:v1"),  # duplicate edge must not duplicate
            ("paper-alpha:v1", "paper-alpha:v1"),  # self-cycle must not loop
        ],
    )
    explorer = citations(records)
    result = explorer.explore(
        authority,
        {
            "paper": {"paperId": "paper-alpha", "versionId": "paper-alpha:v1", "eligibilityRevision": "x"},
            "direction": "cited",
            "page": {"limit": 20},
            "traversalPolicy": {"policyId": "u3-citation-traversal", "revision": "1"},
            "snapshotRevision": None,
        },
    )
    node_ids = [node["nodeId"] for node in result["nodes"]]
    assert node_ids == ["paper-cited:v1", "paper-deep:v1"]
    # Duplicate edges deduplicate; the observed self-edge does not loop traversal.
    edge_keys = [
        (edge["fromNodeId"], edge["toNodeId"]) for edge in result["edges"]
    ]
    assert len(edge_keys) == len(set(edge_keys))
    assert edge_keys.count(("paper-alpha:v1", "paper-cited:v1")) == 1
    assert len(edge_keys) == 3
    assert result["coverage"] in ("complete", "partial")
    assert result["freshness"] == "fresh"
    with connect("discovery") as conn:
        stored = conn.execute(
            "SELECT nodes,edges,coverage FROM discovery.citation_snapshot WHERE id=%s",
            (result["snapshotId"],),
        ).fetchone()
    assert stored is not None and len(stored["nodes"]) == 2
    # Referenced identities outside the corpus are labelled `incomplete`,
    # never fabricated as eligible or silently dropped.
    assert result["nodes"][0]["disposition"] == "incomplete"


def test_citation_provider_failure_is_labelled_not_fabricated(
    maintenance, run_fixture, authority, maintenance_authority, citations, fixture_discard
):
    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    explorer = citations({}, fail=True)
    result = explorer.explore(
        authority,
        {
            "paper": {"paperId": "paper-alpha", "versionId": "paper-alpha:v1", "eligibilityRevision": "x"},
            "direction": "citing",
            "page": {"limit": 20},
            "traversalPolicy": {"policyId": "u3-citation-traversal", "revision": "1"},
            "snapshotRevision": None,
        },
    )
    assert result["coverage"] == "unavailable"
    assert result["freshness"] == "unknown"
    assert len(result["edges"]) == 0
    assert any("인용 제공자" in item for item in result["limitations"])


def test_citation_budget_exhaustion_is_explicit(
    maintenance, run_fixture, authority, maintenance_authority, citations, fixture_discard
):
    from backend.modules.discovery.citations import BudgetExhausted
    from fixtures import StaticCitationRecords

    fixture_discard()
    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    explorer = citations(StaticCitationRecords({}))
    request = {
        "paper": {"paperId": "paper-alpha", "versionId": "paper-alpha:v1", "eligibilityRevision": "x"},
        "direction": "cited",
        "page": {"limit": 20},
        "traversalPolicy": {"policyId": "u3-citation-traversal", "revision": "1"},
        "snapshotRevision": None,
    }
    for _ in range(4):
        explorer.explore(authority, request)
    with pytest.raises(BudgetExhausted):
        explorer.explore(authority, request)
