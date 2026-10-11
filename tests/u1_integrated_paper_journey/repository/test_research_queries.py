"""Real P1/P2 source projections and cached real BGE vectors; no corpus resets."""

import hashlib
import json
import os
import time
from pathlib import Path
from uuid import uuid4

import pytest

from backend.artifacts import Artifact, PrivateArtifacts
from backend.local_profile import LocalProfile, private_bytes
from backend.modules.discovery.guarded_repository import GuardedDiscoveryRepository
from backend.modules.discovery.local_search import POLICY, VOCABULARY, SearchPageBuilder
from backend.transactions import OwnerTransactions
from scripts.publish_docsuri_u1_papers import QUERIES, publish
from scripts.verify_docsuri_u1 import private_json, source_identity

pytestmark = pytest.mark.u1_repository


@pytest.fixture(scope="module")
def real_corpus():
    profile = LocalProfile.load(Path(os.environ["DOCSURI_U1_ENVIRONMENT_FILE"])).journey()
    publication = json.loads(private_bytes(profile.root / "corpus-publication.json", maximum=65536))
    assert publication["ready"] and publication["identity"]["database"] == profile.database_name
    assert (
        publication["identity"]["queriesHash"] == hashlib.sha256(QUERIES.read_bytes()).hexdigest()
    )
    files = PrivateArtifacts(profile.root / "corpus-files", maximum_bytes=2097152)
    cache = json.loads(files.read(Artifact(**publication["queryArtifact"])))
    assert cache["queries"] == json.loads(QUERIES.read_bytes())
    tx = OwnerTransactions(profile)
    report = {
        "sourceIdentity": source_identity(),
        "publication": publication["publication"],
        "cases": [],
    }
    path = profile.root / f"research-query-evidence-{time.time_ns()}.json"
    try:
        yield GuardedDiscoveryRepository(tx), cache, report, path
    finally:
        tx.close()
        private_json(path, report)


def query_context(text, mode="lexical", filters=None, order="relevance"):
    return {
        "query": text,
        "modeId": mode,
        "orderId": order,
        "filters": filters or [],
        "vocabularyRevision": VOCABULARY,
        "policyRef": POLICY,
    }


def page(
    real_corpus, text, *, mode="lexical", vector=None, filters=None, order="relevance", **kwargs
):
    repository, _, report, path = real_corpus
    started = time.monotonic()
    snapshot = repository.snapshot(None, query=text)
    result = SearchPageBuilder(b"owned-research-query-check-key-0001").build(
        snapshot=snapshot,
        query=query_context(text, mode, filters, order),
        execution=str(uuid4()),
        owner="anonymous",
        query_vector=vector,
        **kwargs,
    )
    report["cases"].append(
        {
            "query": result["query"],
            "papers": [h["paper"] for h in result["hits"]],
            "seconds": time.monotonic() - started,
        }
    )
    private_json(path, report)
    return result


@pytest.mark.parametrize("index", range(4), ids=["P1", "P2", "P1-ko", "P2-ko"])
def test_actual_research_query_dense_ranking(real_corpus, index):
    _, cache, _, _ = real_corpus
    fixture = cache["queries"][index]
    result = page(real_corpus, fixture["query"], mode="semantic", vector=cache["vectors"][index])
    assert result["hits"][0]["paper"]["paperId"] == fixture["expectedPaper"]


@pytest.mark.parametrize("index", [0, 1], ids=["P1", "P2"])
def test_actual_english_research_query_lexical_recall(real_corpus, index):
    fixture = real_corpus[1]["queries"][index]
    result = page(real_corpus, fixture["query"])
    assert fixture["expectedPaper"] in [h["paper"]["paperId"] for h in result["hits"]]


def test_exact_title_identifier_and_version_diagnostics(real_corpus):
    for text, expected in (
        ("Attention Is All You Need", "1706.03762"),
        ("1706.03762", "1706.03762"),
        ("2005.11401v4", "2005.11401"),
    ):
        assert page(real_corpus, text)["hits"][0]["paper"]["paperId"] == expected


def test_lexical_terms_are_not_combined_across_different_papers(real_corpus):
    assert page(real_corpus, "sinusoidal parametric")["hits"] == []


def test_real_author_year_filters_and_empty_match(real_corpus):
    for filters, expected in (
        ([{"filterId": "author", "operatorId": "contains", "values": ["Vaswani"]}], ["1706.03762"]),
        ([{"filterId": "year", "operatorId": "between", "values": [2020, 2020]}], ["2005.11401"]),
        ([{"filterId": "author", "operatorId": "contains", "values": ["no-such-author"]}], []),
    ):
        assert [
            h["paper"]["paperId"] for h in page(real_corpus, "model", filters=filters)["hits"]
        ] == expected


def test_real_newest_cursor_has_no_duplicate_or_missing_paper(real_corpus):
    first = page(real_corpus, "model", order="newest", limit=1)
    second = page(real_corpus, "model", order="newest", limit=1, cursor=first["page"]["nextCursor"])
    assert [first["hits"][0]["paper"]["paperId"], second["hits"][0]["paper"]["paperId"]] == [
        "2005.11401",
        "1706.03762",
    ]
    assert second["page"]["nextCursor"] is None


def test_publication_replay_uses_checked_vectors_without_new_model_work(real_corpus):
    profile = real_corpus[0].transactions.profile
    before = json.loads(private_bytes(profile.root / "corpus-publication.json", maximum=65536))
    assert publish()["ready"]
    after = json.loads(private_bytes(profile.root / "corpus-publication.json", maximum=65536))
    assert after["publication"] == before["publication"]
    assert after["papers"] == before["papers"]
    assert after["attemptCount"] == before["attemptCount"] + 1
    attempt = json.loads(
        private_bytes(profile.root / after["latestAttempt"]["file"], maximum=524288)
    )
    assert not attempt["samples"] and not attempt["runtime"]
