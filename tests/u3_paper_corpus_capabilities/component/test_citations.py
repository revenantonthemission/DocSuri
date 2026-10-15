"""U3 citation component behavior: bounds, labels and provider failure."""

from uuid import uuid4

import pytest

from backend.modules.discovery.citations import (
    CitationExplorer,
    FixtureCitationProvider,
    _normalize_provider_value,
)
from fixtures import StaticCitationRecords

pytestmark = pytest.mark.u3_component


def records_for(root="paper-a:v1", links=None):
    return StaticCitationRecords.chain(root, links=links or [])


def test_traversal_honours_depth_and_node_bounds():
    records = StaticCitationRecords.chain(
        "paper-a:v1",
        links=[
            ("paper-a:v1", "paper-b:v1"),
            ("paper-b:v1", "paper-c:v1"),
            ("paper-c:v1", "paper-d:v1"),
        ],
    )
    provider = FixtureCitationProvider(records)
    value = provider.read("paper-a:v1", "cited", max_nodes=32, max_depth=2, max_requests=4)
    assert value["truncated"] is True, "depth bound must stop deeper traversal"
    assert {node["versionId"] for node in value["nodes"]} == {"paper-b:v1", "paper-c:v1"}
    assert value["coverage"] == "partial"


def test_cycle_and_duplicate_links_do_not_loop():
    records = StaticCitationRecords.chain(
        "paper-a:v1",
        links=[
            ("paper-a:v1", "paper-b:v1"),
            ("paper-b:v1", "paper-a:v1"),
            ("paper-a:v1", "paper-b:v1"),
            ("paper-b:v1", "paper-b:v1"),
        ],
    )
    provider = FixtureCitationProvider(records)
    value = provider.read("paper-a:v1", "cited", max_nodes=32, max_depth=2, max_requests=8)
    identities = [node["versionId"] for node in value["nodes"]]
    assert identities.count("paper-b:v1") == 1


def test_normalization_labels_unknown_and_partial_provider_data():
    unknown = _normalize_provider_value(
        {"nodes": [], "edges": [], "freshness": "banana", "coverage": "galaxy"},
        "paper-a:v1",
        "cited",
    )
    assert unknown["freshness"] == "unknown"
    assert unknown["coverage"] == "partial"
    truncated = _normalize_provider_value(
        {
            "nodes": [{"versionId": "paper-b:v1", "paperId": "paper-b", "depth": 1}],
            "edges": [],
            "freshness": "fresh",
            "coverage": "complete",
            "truncated": True,
        },
        "paper-a:v1",
        "cited",
    )
    assert truncated["coverage"] == "partial"
    assert any("탐색 한도" in item for item in truncated["limitations"])


def test_fabricated_edges_are_refused():
    normalized = _normalize_provider_value(
        {
            "nodes": [{"versionId": "paper-b:v1", "paperId": "paper-b", "depth": 1}],
            "edges": [
                {"fromNodeId": "paper-a:v1", "toNodeId": "paper-ghost:v1",
                 "sourceUrl": "https://fixture.invalid/ghost"},
                {"fromNodeId": "paper-a:v1", "toNodeId": "paper-b:v1",
                 "sourceUrl": "javascript:alert(1)"},
                {"fromNodeId": "paper-a:v1", "toNodeId": "paper-b:v1",
                 "sourceUrl": "https://fixture.invalid/b"},
            ],
            "freshness": "fresh",
            "coverage": "complete",
        },
        "paper-a:v1",
        "cited",
    )
    assert len(normalized["edges"]) == 1
    assert normalized["edges"][0]["toNodeId"] == "paper-b:v1"


def test_provider_failure_keeps_existing_saves(
    transactions, authority, run_fixture, maintenance, maintenance_authority,
    fixture_discard,
):
    """A provider failure never erases an already saved reference."""
    fixture_discard()
    from backend.modules.library.repository.guarded import GuardedLibraryRepository

    assert run_fixture(["fixture-alpha"])["state"] == "completed"
    library = GuardedLibraryRepository(maintenance.transactions)
    key = uuid4()
    saved = library.save(authority, "paper-alpha", "paper-alpha:v1", key, None)
    assert saved["paperId"] == "paper-alpha"
    explorer = CitationExplorer(
        transactions, FixtureCitationProvider({}, fail=True)
    )
    result = explorer.explore(
        authority,
        {
            "paper": {"paperId": "paper-alpha", "versionId": "paper-alpha:v1",
                      "eligibilityRevision": "x"},
            "direction": "cited",
            "page": {"limit": 10},
            "traversalPolicy": {"policyId": "u3-citation-traversal", "revision": "1"},
            "snapshotRevision": None,
        },
    )
    assert result["coverage"] == "unavailable" and result["edges"] == []
    rows = library.list_saved(authority, limit=10)
    assert [row["paper_id"] for row in rows] == ["paper-alpha"]


def test_ineligible_root_is_explained_without_traversal(
    transactions, authority, fixture_discard
):
    fixture_discard()
    explorer = CitationExplorer(transactions, FixtureCitationProvider(records_for()))
    result = explorer.explore(
        authority,
        {
            "paper": {"paperId": "paper-missing", "versionId": "paper-missing:v1",
                      "eligibilityRevision": "x"},
            "direction": "citing",
            "page": {"limit": 10},
            "traversalPolicy": {"policyId": "u3-citation-traversal", "revision": "1"},
            "snapshotRevision": None,
        },
    )
    assert result["coverage"] == "unavailable"
    assert result["edges"] == []
    assert result["nodes"][0]["disposition"] == "incomplete"


def test_unknown_traversal_policy_is_refused(transactions, authority, fixture_discard):
    fixture_discard()
    explorer = CitationExplorer(transactions, FixtureCitationProvider({}))
    with pytest.raises(ValueError):
        explorer.explore(
            authority,
            {
                "paper": {"paperId": "paper-a", "versionId": "paper-a:v1",
                          "eligibilityRevision": "x"},
                "direction": "sideways",
                "page": {"limit": 10},
                "traversalPolicy": {"policyId": "u3-citation-traversal", "revision": "1"},
                "snapshotRevision": None,
            },
        )
    with pytest.raises(ValueError):
        explorer.explore(
            authority,
            {
                "paper": {"paperId": "paper-a", "versionId": "paper-a:v1",
                          "eligibilityRevision": "x"},
                "direction": "cited",
                "page": {"limit": 10},
                "traversalPolicy": {"policyId": "other-policy", "revision": "1"},
                "snapshotRevision": None,
            },
        )
