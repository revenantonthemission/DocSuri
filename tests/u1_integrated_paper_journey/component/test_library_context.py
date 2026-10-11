import pytest

from backend.modules.library.repository.guarded import query_reference
from backend.modules.discovery.local_search import POLICY, VOCABULARY

pytestmark = pytest.mark.u1_component


def submitted_query():
    return {
        "query": "U1 repository diagnostic submitted query",
        "modeId": "lexical",
        "orderId": "newest",
        "vocabularyRevision": VOCABULARY,
        "policyRef": POLICY,
        "filters": [{"filterId": "year", "operatorId": "between", "values": [2017, 2020]}],
    }


def test_saved_context_preserves_exact_submitted_query_refinements_and_label():
    query = submitted_query()
    result = query_reference(query, "나중에 읽기")
    assert result == {"queryContext": query, "label": "나중에 읽기"}
    query["query"] = "unsent edit"
    assert result["queryContext"]["query"] != "unsent edit"


def test_older_vocabulary_is_preserved_as_reference_without_claiming_rerun_support():
    query = dict(submitted_query(), vocabularyRevision="previous-version")
    assert query_reference(query)["queryContext"] == query


@pytest.mark.parametrize("text", [" ", "x" * 2049])
def test_empty_or_oversize_query_is_not_saved(text):
    with pytest.raises(ValueError):
        query_reference(dict(submitted_query(), query=text))


def test_label_has_finite_nonempty_policy():
    for label in ("", " ", "x" * 101, 1):
        with pytest.raises(ValueError):
            query_reference(submitted_query(), label)


def test_saved_query_rejects_unknown_wire_fields():
    with pytest.raises(ValueError):
        query_reference(dict(submitted_query(), ownerId="untrusted-owner"))
