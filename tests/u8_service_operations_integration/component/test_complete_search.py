"""The complete assembly's search (U8 plan Step 24; P1, BR7.2, NFR8.4).

`CompleteSearch` takes Step 7's candidates, at most 400, into the built ranking. One
fixture corpus, written as CorpusContent's login for this module and removed after:
seven eligible versions that hold this run's own word (the first one, `top`, also
carries the stand-in embedder's vector for the query, so it is nearest by meaning), and
one withdrawn paper that matches both ways.
"""

from __future__ import annotations

import json
import secrets

import psycopg
import pytest
from psycopg.rows import dict_row

from backend.local_profile import private_bytes
from backend.modules.discovery.guarded_repository import GuardedDiscoveryRepository
from backend.modules.discovery.local_embedding import EmbeddingTimeout
from backend.modules.discovery.local_search import SearchPageBuilder
from backend.modules.discovery.u8_search import (
    CANDIDATE_LIMIT,
    VECTOR_POLICY,
    CompleteSearch,
    SearchCandidates,
    StandinEmbeddings,
)
from backend.modules.library.u3_history import U3HistoryConsumer
from backend.u3_policy import PROJECTION_COMPATIBILITY, QUERY_VOCABULARY, SEARCH_POLICY

# The search cursor's HMAC key, generated per run (L1-36): no test compares a cursor
# against a fixed value.
KEY = secrets.token_bytes(32)
EMBEDDER = StandinEmbeddings()


def _connect(realm, owner: str):
    roles = json.loads(private_bytes(realm.root / "owner-credentials.json"))["roles"]
    return psycopg.connect(
        host="127.0.0.1", port=realm.database_port, dbname=realm.database_name,
        user=f"docsuri_{owner}", password=roles[owner], connect_timeout=3,
        row_factory=dict_row)


@pytest.fixture(scope="module")
def corpus(realm):
    token = secrets.token_hex(4)
    word = f"zq{token}"
    query_vector = EMBEDDER.embed_query(word)
    far = EMBEDDER.embed_query("unrelated " + token)
    made = {"word": word, "versions": [], "withdrawn": f"u8cs-{token}-withdrawn"}
    conn = _connect(realm, "corpus")
    try:
        def add(name, *, withdrawn=False, text, vector):
            conn.execute("INSERT INTO corpus.paper(id,title,authors,metadata,withdrawn) "
                         "VALUES(%s,%s,'[\"A\"]','{}',%s)", (name + "-paper", name, withdrawn))
            conn.execute(
                "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
                "private_path,eligible,purpose,provenance,content) VALUES(%s,%s,"
                "'https://example.invalid/p',%s,'v1','synthetic',true,'local-research',"
                "'{}','{}')", (name, name + "-paper", secrets.token_hex(32)))
            conn.execute(
                "INSERT INTO corpus.projection(version_id,ordinal,content_hash,anchor,section,"
                "text_content,embedding,vector_policy) VALUES(%s,0,%s,'a0','body',%s,%s,%s)",
                (name, "c" * 64, text, vector, VECTOR_POLICY))

        for index in range(7):
            name = f"u8cs-{token}-v{index}"
            # More occurrences of the word rank a version higher by words.
            add(name, text=" ".join([word] * (7 - index) + ["filler"] * 5),
                vector=query_vector if index == 0 else far)
            made["versions"].append(name)
        add(made["withdrawn"], withdrawn=True, text=" ".join([word] * 20), vector=query_vector)
        conn.commit()
        yield made
    finally:
        conn.rollback()
        prefix = f"u8cs-{token}-%"
        conn.execute("DELETE FROM corpus.projection WHERE version_id LIKE %s", (prefix,))
        conn.execute("DELETE FROM corpus.version WHERE id LIKE %s", (prefix,))
        conn.execute("DELETE FROM corpus.paper WHERE id LIKE %s", (prefix,))
        conn.commit()
        conn.close()


def search_of(transactions, embedder=EMBEDDER) -> CompleteSearch:
    return CompleteSearch(
        transactions, GuardedDiscoveryRepository(transactions), U3HistoryConsumer(transactions),
        cursor_key=KEY, embedder=embedder)


def request(text: str, mode: str = "lexical", **page) -> dict:
    return {"query": {"query": text, "modeId": mode, "orderId": "relevance", "filters": [],
                      "vocabularyRevision": QUERY_VOCABULARY, "policyRef": SEARCH_POLICY},
            "page": page or {"limit": 20}}


def versions(answer) -> list[str]:
    return [hit["paper"]["versionId"] for hit in answer["hits"]]


# 1. Results match the built ranking -------------------------------------------------------------


def test_results_match_the_built_ranking_on_the_fixture_corpus(corpus, transactions):
    search = search_of(transactions)
    answer = search.search(None, request(corpus["word"]))
    assert versions(answer) == corpus["versions"]  # by words, most occurrences first
    query = answer["query"]
    built = SearchPageBuilder(
        KEY, vocabulary=QUERY_VOCABULARY, policy=SEARCH_POLICY,
        compatibility=PROJECTION_COMPATIBILITY, max_candidates=CANDIDATE_LIMIT,
    ).build(snapshot=search.snapshot(None, query, None), query=query, execution="e",
            owner="guest")
    assert versions(built) == versions(answer)
    by_meaning = search.search(None, request(corpus["word"], "semantic"))
    assert by_meaning["effectiveModeId"] == "semantic" and by_meaning["outcome"] == "complete"
    assert versions(by_meaning)[0] == corpus["versions"][0]  # its vector is the query's


# 2. The cursor round-trips, and a tampered cursor is refused ---------------------------------


def test_the_cursor_round_trips_and_a_tampered_one_is_refused(corpus, transactions):
    search, seen, cursor = search_of(transactions), [], None
    for _ in range(5):
        page = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        answer = search.search(None, request(corpus["word"], **page))
        seen += versions(answer)
        cursor = answer["page"]["nextCursor"]
        if cursor is None:
            break
    assert seen == corpus["versions"]
    first = search.search(None, request(corpus["word"], limit=2))["page"]["nextCursor"]
    tampered = first[:-4] + ("AAAA" if not first.endswith("AAAA") else "BBBB")
    with pytest.raises(ValueError):
        search.search(None, request(corpus["word"], limit=2, cursor=tampered))
    with pytest.raises(ValueError):  # a cursor is bound to its query
        search.search(None, request("other words", limit=2, cursor=first))


# 3. Past 2 s the search answers by words with its limitation ---------------------------------


class Late:
    def embed_query(self, text):
        raise EmbeddingTimeout("query embedding passed its bound")


def test_past_the_embedding_bound_it_answers_by_words_with_its_limitation(corpus,
                                                                         transactions):
    answer = search_of(transactions, Late()).search(None, request(corpus["word"], "semantic"))
    assert (answer["outcome"], answer["effectiveModeId"]) == ("degraded", "lexical")
    assert answer["limitations"] == ["semantic-search-unavailable"]
    assert versions(answer) == corpus["versions"]


# 4. A withdrawn paper never appears --------------------------------------------------------------


def test_a_withdrawn_paper_never_appears(corpus, transactions):
    search = search_of(transactions)
    for mode in ("lexical", "semantic"):
        assert corpus["withdrawn"] not in versions(search.search(None, request(
            corpus["word"], mode, limit=100)))


def test_publication_writes_the_vector_and_the_words_with_the_chunks(corpus, realm):
    """Step 23's last box: a chunk written as CorpusContent publishes it gets its
    `embedding_vector` and its version's `lexical_all`, with no second write."""
    conn = _connect(realm, "corpus")
    try:
        rows = conn.execute(
            "SELECT c.embedding_vector IS NOT NULL AND c.embedding_vector::float4[] = "
            "c.embedding::float4[] AS vector_written, v.lexical_all @@ "
            "plainto_tsquery('simple', %s) AS words_written FROM corpus.projection c "
            "JOIN corpus.version v ON v.id=c.version_id WHERE c.version_id=ANY(%s)",
            (corpus["word"], corpus["versions"])).fetchall()
    finally:
        conn.close()
    assert len(rows) == 7 and all(r["vector_written"] and r["words_written"] for r in rows)


# 5. At most 400 rows are ranked ------------------------------------------------------------------


def test_at_most_four_hundred_rows_reach_ranking(corpus, transactions):
    search = search_of(transactions)
    query = search.search(None, request(corpus["word"]))["query"]
    snapshot = search.snapshot(None, query, EMBEDDER.embed_query(corpus["word"]))
    assert len(snapshot["candidates"]) <= CANDIDATE_LIMIT == 400
    row = snapshot["candidates"][0]
    with pytest.raises(ValueError):
        search.builder.build(snapshot={**snapshot, "candidates": [row] * 401}, query=query,
                             execution="e", owner="guest")
    with pytest.raises(ValueError):
        SearchPageBuilder(KEY, max_candidates=401)
    assert SearchPageBuilder(KEY).max_candidates == 256  # every earlier realm's bound
    assert SearchCandidates.merged({"meaning": [row], "words": [row]}) == [row]


# 6. Each query takes at most 200 of each (Step 55(c)) ---------------------------------------


class _ObservedConnection:
    """A pass-through observer of the discovery transaction's connection: every call is
    forwarded unchanged; `execute` also notes its statement and parameters (L1-35's
    call-through kind)."""

    def __init__(self, conn, executed: list):
        self._conn, self._executed = conn, executed

    def execute(self, statement, params=None, *args, **kwargs):
        self._executed.append((statement, params))
        return self._conn.execute(statement, params, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._conn, name)


class _ObservedTransactions:
    def __init__(self, transactions):
        self._transactions, self.executed = transactions, []

    def run(self, owner, work, *args, **kwargs):
        return self._transactions.run(
            owner, lambda conn: work(_ObservedConnection(conn, self.executed)), *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._transactions, name)


def test_each_query_takes_at_most_two_hundred_of_each(corpus, transactions):
    from backend.modules.discovery.u8_search import (
        MEANING_LIMIT,
        MEANING_SQL,
        WORDS_LIMIT,
        WORDS_SQL,
    )

    assert (MEANING_LIMIT, WORDS_LIMIT) == (200, 200)
    observed = _ObservedTransactions(transactions)
    candidates = SearchCandidates(observed).read(corpus["word"],
                                                 EMBEDDER.embed_query(corpus["word"]))
    assert candidates["meaning"] and candidates["words"]
    limits = {statement: params["limit"] for statement, params in observed.executed
              if statement in (MEANING_SQL, WORDS_SQL)}
    assert limits == {MEANING_SQL: 200, WORDS_SQL: 200}

    def rows(count: int, start: int = 0) -> list[dict]:
        return [{"version_id": f"v{index}", "ordinal": 0} for index in range(start, start + count)]

    with pytest.raises(ValueError, match="exceed their bound"):
        SearchCandidates.merged({"meaning": rows(200), "words": rows(201, 200)})
    merged = SearchCandidates.merged({"meaning": rows(200), "words": rows(200, 200)})
    assert len(merged) == 400
