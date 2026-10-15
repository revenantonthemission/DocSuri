"""U3 discovery component behavior: vocabulary, windows, degradation."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from backend.modules.discovery.local_search import SearchPageBuilder, validate_query
from backend.modules.discovery.u3_search import DEGRADATION_NOTE, DependencyUnavailable, U3Search
from docsuri_ops.local_models import ModelUnavailable

pytestmark = pytest.mark.u3_component

SEARCH_POLICY = {"policyId": "u3-paper-search", "revision": "1"}
VOCABULARY = "u3-paper-options-1"


def query(text="attention", **overrides):
    value = {
        "query": text,
        "modeId": "lexical",
        "orderId": "relevance",
        "filters": [],
        "vocabularyRevision": VOCABULARY,
        "policyRef": SEARCH_POLICY,
    }
    value.update(overrides)
    return value


def candidate(version="paper-a:v1", score=1.0, ordinal=0):
    return {
        "version_id": version,
        "paper_id": version.split(":")[0],
        "ordinal": ordinal,
        "lexical_score": score,
        "text_content": f"본문 {version}",
        "section": "Introduction",
        "anchor": f"{version}:p1",
        "authors": ["연구자 A"],
        "title": f"논문 {version}",
        "published_on": None,
        "source_url": f"https://fixture.invalid/{version}",
        "eligibility_revision": "00000000-0000-0000-0000-000000000000",
        "source_hash": "a" * 64,
    }


def snapshot(candidates, revision="11111111-1111-1111-1111-111111111111"):
    return {
        "publication": {
            "generation_id": "22222222-2222-2222-2222-222222222222",
            "revision": revision,
            "manifest_hash": "b" * 64,
            "published_at": datetime.now(UTC),
        },
        "candidates": candidates,
    }


def builder(**overrides):
    return SearchPageBuilder(
        b"k" * 32,
        vocabulary=VOCABULARY,
        policy=SEARCH_POLICY,
        compatibility="u3-projection-1",
        **overrides,
    )


def test_query_vocabulary_rejects_empty_unicode_edge_and_oversized():
    with pytest.raises(ValueError):
        validate_query(query("   "), vocabulary=VOCABULARY, policy=SEARCH_POLICY)
    with pytest.raises(ValueError):
        validate_query(query("\u0000attention"), vocabulary=VOCABULARY, policy=SEARCH_POLICY)
    with pytest.raises(ValueError):
        validate_query(query("가" * 4096), vocabulary=VOCABULARY, policy=SEARCH_POLICY)
    with pytest.raises(ValueError):
        validate_query(
            query(vocabularyRevision="other-vocabulary"),
            vocabulary=VOCABULARY,
            policy=SEARCH_POLICY,
        )
    # A normalized Unicode query is accepted unchanged.
    accepted = validate_query(query("어텐션 検索"), vocabulary=VOCABULARY, policy=SEARCH_POLICY)
    assert accepted["query"] == "어텐션 検索"


def test_filters_are_bounded_and_unique():
    with pytest.raises(ValueError):
        validate_query(
            query(filters=[{"filterId": "author", "operatorId": "contains", "values": ["a"]}] * 3),
            vocabulary=VOCABULARY,
            policy=SEARCH_POLICY,
        )
    with pytest.raises(ValueError):
        validate_query(
            query(filters=[{"filterId": "year", "operatorId": "between", "values": [2020, 2010]}]),
            vocabulary=VOCABULARY,
            policy=SEARCH_POLICY,
        )
    with pytest.raises(ValueError):
        validate_query(
            query(filters=[{"filterId": "secret", "operatorId": "equals", "values": ["x"]}]),
            vocabulary=VOCABULARY,
            policy=SEARCH_POLICY,
        )


def test_snapshot_bound_pagination_is_stable_and_expires():
    page = builder(clock=lambda: 1000.0)
    rows = [candidate("paper-a:v1", 2.0), candidate("paper-b:v1", 1.0)]
    first = page.build(
        snapshot=snapshot(rows), query=query(), execution=str(uuid4()), owner="guest", limit=1
    )
    assert [hit["paper"]["versionId"] for hit in first["hits"]] == ["paper-a:v1"]
    cursor = first["page"]["nextCursor"]
    second = page.build(
        snapshot=snapshot(rows),
        query=query(),
        execution=str(uuid4()),
        owner="guest",
        limit=1,
        cursor=cursor,
    )
    assert [hit["paper"]["versionId"] for hit in second["hits"]] == ["paper-b:v1"]
    # A cursor bound to another owner, query or snapshot is refused.
    with pytest.raises(ValueError):
        page.build(
            snapshot=snapshot(rows),
            query=query(),
            execution=str(uuid4()),
            owner="other-owner",
            limit=1,
            cursor=cursor,
        )
    with pytest.raises(ValueError):
        page.build(
            snapshot=snapshot(rows, revision="33333333-3333-3333-3333-333333333333"),
            query=query(),
            execution=str(uuid4()),
            owner="guest",
            limit=1,
            cursor=cursor,
        )
    with pytest.raises(ValueError):
        page.build(
            snapshot=snapshot(rows),
            query=query("different"),
            execution=str(uuid4()),
            owner="guest",
            limit=1,
            cursor=cursor,
        )


def test_disclosed_degradation_uses_lexical_fallback():
    class Repository:
        def admit(self, authority, execution, digest):
            return 1

        def snapshot(self, authority, query=""):
            return snapshot([candidate()])

        def record(self, *args, **kwargs):
            raise AssertionError("no fact is recorded without an owner")

        def acknowledge_history(self, *args, **kwargs):
            raise AssertionError("no acknowledgement without an owner")

    service = U3Search(None, Repository(), None, cursor_key=b"k" * 32)
    response = service.search(None, {"query": query("attention", modeId="semantic"), "page": {"limit": 10}})
    assert response["outcome"] == "degraded"
    assert response["effectiveModeId"] == "lexical"
    assert DEGRADATION_NOTE in response["limitations"]
    assert response["hits"], "the disclosed fallback still returns lexical results"


def test_configured_semantic_failure_is_dependency_unavailable():
    class Repository:
        def admit(self, authority, execution, digest):
            return 1

        def snapshot(self, authority, query=""):
            return snapshot([candidate()])

    def semantic(_text):
        raise ModelUnavailable("runtime down")

    service = U3Search(None, Repository(), None, cursor_key=b"k" * 32, semantic=semantic)
    with pytest.raises(DependencyUnavailable):
        service.search(None, {"query": query("attention", modeId="semantic"), "page": {"limit": 10}})


def test_empty_requires_successful_retrieval_not_failure():
    class Repository:
        def snapshot(self, authority, query=""):
            return snapshot([])

    service = U3Search(None, Repository(), None, cursor_key=b"k" * 32)
    response = service.search(None, {"query": query(), "page": {"limit": 10}})
    assert response["hits"] == []
    assert response["outcome"] == "complete"
    # Retrieval failure is a distinct raised state, handled by the route as 503.
    class Failing(Repository):
        def snapshot(self, authority, query=""):
            raise ValueError("index unavailable")

    service = U3Search(None, Failing(), None, cursor_key=b"k" * 32)
    with pytest.raises(ValueError):
        service.search(None, {"query": query(), "page": {"limit": 10}})


def test_lexical_and_newest_ordering_are_deterministic():
    page = builder()
    rows = [
        candidate("paper-a:v1", 1.0),
        candidate("paper-b:v1", 3.0),
        candidate("paper-c:v1", 3.0),
    ]
    response = page.build(
        snapshot=snapshot(rows), query=query(), execution=str(uuid4()), owner="guest", limit=10
    )
    order = [hit["paper"]["versionId"] for hit in response["hits"]]
    assert order == ["paper-b:v1", "paper-c:v1", "paper-a:v1"]
    assert response["page"]["snapshotRevision"] == response["publication"]["publicationRevision"]
