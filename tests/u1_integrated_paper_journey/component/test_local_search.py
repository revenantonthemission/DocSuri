"""Rank/cursor policy isolation; PostgreSQL and BGE checks are separate real boundaries."""

from copy import deepcopy
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from backend.modules.discovery.local_search import POLICY, VOCABULARY, SearchPageBuilder
from docsuri_ops.local_models import ModelUnavailable

pytestmark = pytest.mark.u1_component


def example():
    query = {
        "query": "sequence transduction",
        "modeId": "lexical",
        "orderId": "relevance",
        "filters": [],
        "vocabularyRevision": VOCABULARY,
        "policyRef": POLICY,
    }
    rows = []
    for index, score in enumerate([0.9, 0.5, 0.2]):
        rows.append(
            {
                "version_id": f"v{index}",
                "paper_id": f"p{index}",
                "ordinal": 0,
                "eligibility_revision": uuid4(),
                "title": f"Paper {index}",
                "authors": ["Alpha" if index == 0 else "Beta"],
                "published_on": date(2020 + index, 1, 1),
                "text_content": "source excerpt",
                "source_url": "https://example.org/paper",
                "lexical_score": score,
            }
        )
    snapshot = {
        "candidates": rows,
        "publication": {
            "revision": uuid4(),
            "generation_id": uuid4(),
            "manifest_hash": "a" * 64,
            "published_at": datetime.now(timezone.utc),
        },
    }
    return dict(snapshot=snapshot, query=query, execution=str(uuid4()), owner="owner-A")


def test_rank_deduplicates_versions_and_exposes_no_scores_or_vectors():
    args = example()
    args["snapshot"]["candidates"].append(dict(args["snapshot"]["candidates"][0], ordinal=1))
    page = SearchPageBuilder(b"x" * 32).build(**args)
    assert [hit["paper"]["versionId"] for hit in page["hits"]] == ["v0", "v1", "v2"]
    assert all("lexical_score" not in hit and "embedding" not in hit for hit in page["hits"])
    assert page["query"] == args["query"]


def test_filters_and_newest_order_are_applied_before_pagination():
    args = example()
    args["query"].update(
        orderId="newest",
        filters=[
            {"filterId": "author", "operatorId": "contains", "values": ["beta"]},
            {"filterId": "year", "operatorId": "between", "values": [2020, 2022]},
        ],
    )
    page = SearchPageBuilder(b"x" * 32).build(**args, limit=1)
    assert page["hits"][0]["paper"]["versionId"] == "v2"
    assert page["page"]["nextCursor"]


def test_cursor_binds_owner_query_snapshot_and_page_size():
    builder = SearchPageBuilder(b"x" * 32)
    args = example()
    cursor = builder.build(**args, limit=1)["page"]["nextCursor"]
    page = builder.build(**args, limit=1, cursor=cursor)
    assert page["hits"][0]["paper"]["versionId"] == "v1"
    for key in ("owner", "query", "snapshot", "limit"):
        altered = deepcopy(dict(args, limit=1))
        if key == "query":
            altered[key]["query"] = "another query"
        elif key == "snapshot":
            altered[key]["publication"]["revision"] = uuid4()
        else:
            altered[key] = 2 if key == "limit" else "owner-B"
        with pytest.raises(ValueError, match="cursor"):
            builder.build(**altered, cursor=cursor)


def test_cursor_tamper_expiry_and_oversize_are_rejected():
    now = [1000.0]
    builder = SearchPageBuilder(b"x" * 32, clock=lambda: now[0])
    args = example()
    cursor = builder.build(**args, limit=1)["page"]["nextCursor"]
    for invalid in (cursor[:-8] + "xxxxxxxx", "not base64!", "x" * 2049):
        with pytest.raises(ValueError, match="cursor"):
            builder.build(**args, limit=1, cursor=invalid)
    now[0] += 301
    with pytest.raises(ValueError, match="cursor"):
        builder.build(**args, limit=1, cursor=cursor)


def test_semantic_dependency_failure_cannot_be_a_successful_empty_result():
    args = example()
    args["query"]["modeId"] = "semantic"
    with pytest.raises(ModelUnavailable, match="unavailable"):
        SearchPageBuilder(b"x" * 32).build(**args)
    for row in args["snapshot"]["candidates"]:
        row.update(embedding=[1.0] + [0.0] * 1023, vector_policy="wrong-policy")
    with pytest.raises(ModelUnavailable, match="compatibility"):
        SearchPageBuilder(b"x" * 32).build(**args, query_vector=[1.0] + [0.0] * 1023)


def test_unknown_policy_filters_and_unbounded_inputs_are_rejected():
    for changes in (
        {"query": "가" * 1000},
        {"query": "\n"},
        {"modeId": "invented"},
        {"filters": [{"filterId": "year", "operatorId": "between", "values": [True, 2022]}]},
        {"filters": [{"filterId": "sql", "operatorId": "execute", "values": ["x"]}]},
    ):
        args = example()
        args["query"].update(changes)
        with pytest.raises(ValueError):
            SearchPageBuilder(b"x" * 32).build(**args)
    with pytest.raises(ValueError, match="page size"):
        SearchPageBuilder(b"x" * 32).build(**example(), limit=101)


def test_valid_empty_lexical_search_is_distinct_from_missing_scoring():
    args = example()
    for row in args["snapshot"]["candidates"]:
        row["lexical_score"] = 0
    page = SearchPageBuilder(b"x" * 32).build(**args)
    assert page["hits"] == [] and page["outcome"] == "complete"
    del args["snapshot"]["candidates"][0]["lexical_score"]
    with pytest.raises(ValueError, match="scores"):
        SearchPageBuilder(b"x" * 32).build(**args)
