"""Search candidates by meaning and by words (Step 8; P1, NFR8.4).

One fixture corpus, written as CorpusContent's login for this module and removed after:

- 60 ineligible versions of 10 chunks each, nearer the query than anything else, so an
  index scan that only filtered its first `ef_search` neighbours would find no
  eligible chunk at all;
- 30 eligible versions of 10 chunks each, farther from the query;
- one withdrawn paper whose chunks are nearest and match the words;
- one eligible version whose two chunks each hold one of two query terms;
- 210 eligible single-chunk versions sharing one word, without vectors;
- 10 eligible single-chunk versions without vectors whose text holds that word three
  times (`quorumword quorumword quorumword rank <i>`), ids `u8s-<token>-zrank-<i>`, which
  sort after the 210 `word` versions, so a words read ordered by id alone would drop them
  (Step 50(a)/(b)).
"""

from __future__ import annotations

import json
import random
import secrets

import psycopg
import pytest
from psycopg.rows import dict_row

from backend.local_profile import private_bytes
from backend.modules.discovery.u8_search import (
    CANDIDATE_LIMIT,
    MEANING_LIMIT,
    MEANING_SQL,
    WORDS_LIMIT,
    WORDS_SQL,
    SearchCandidates,
    meaning_parameters,
)

DIMENSIONS = 1024
FAR_VERSIONS, NEAR_VERSIONS, CHUNKS = 30, 60, 10
WORD_VERSIONS = 210
RANKED_VERSIONS = 10


def unit(index: int) -> list[float]:
    vector = [0.0] * DIMENSIONS
    vector[index] = 1.0
    return vector


def near(rng: random.Random, scale: float) -> list[float]:
    """The query direction plus noise of the given size."""
    vector = [rng.uniform(-scale, scale) for _ in range(DIMENSIONS)]
    vector[0] += 1.0
    return vector


QUERY = unit(0)


def _connect(realm, owner: str):
    roles = json.loads(private_bytes(realm.root / "owner-credentials.json"))["roles"]
    return psycopg.connect(
        host="127.0.0.1", port=realm.database_port, dbname=realm.database_name,
        user=f"docsuri_{owner}", password=roles[owner], connect_timeout=3,
        row_factory=dict_row,
    )


def _version(conn, version: str, paper: str, *, eligible: bool, withdrawn: bool = False):
    conn.execute(
        "INSERT INTO corpus.paper(id,title,authors,metadata,withdrawn) "
        "VALUES(%s,%s,'[]','{}',%s)", (paper, "synthetic " + paper, withdrawn))
    conn.execute(
        "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
        "private_path,eligible,purpose,provenance,content) VALUES(%s,%s,"
        "'https://example.invalid/p',%s,'v1','synthetic',%s,'local-research','{}','{}')",
        (version, paper, secrets.token_hex(32), eligible))


def _chunks(conn, version: str, rows: list[tuple[str, list[float] | None]]):
    with conn.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO corpus.projection(version_id,ordinal,content_hash,anchor,section,"
            "text_content,embedding) VALUES(%s,%s,%s,%s,'body',%s,%s)",
            [(version, ordinal, "c" * 64, f"a{ordinal}", text, vector)
             for ordinal, (text, vector) in enumerate(rows)])


@pytest.fixture(scope="module")
def corpus(realm):
    token = secrets.token_hex(4)
    rng = random.Random(20261022)
    made = {"far": [], "near": [], "word": [], "zrank": [], "withdrawn": None,
            "spread": None}
    conn = _connect(realm, "corpus")
    conn.execute("SET statement_timeout = '60s'")
    try:
        for index in range(NEAR_VERSIONS):
            name = f"u8s-{token}-near-{index}"
            _version(conn, name, name + "-paper", eligible=False)
            _chunks(conn, name, [(f"noise {index}", near(rng, 0.01)) for _ in range(CHUNKS)])
            made["near"].append(name)
        for index in range(FAR_VERSIONS):
            name = f"u8s-{token}-far-{index}"
            _version(conn, name, name + "-paper", eligible=True)
            _chunks(conn, name, [(f"meadow {index}", near(rng, 0.2)) for _ in range(CHUNKS)])
            made["far"].append(name)
        withdrawn = f"u8s-{token}-withdrawn"
        _version(conn, withdrawn, withdrawn + "-paper", eligible=True, withdrawn=True)
        _chunks(conn, withdrawn, [("harbor lantern meadow", QUERY)])
        made["withdrawn"] = withdrawn
        spread = f"u8s-{token}-spread"
        _version(conn, spread, spread + "-paper", eligible=True)
        _chunks(conn, spread, [("alpha harbor", None), ("lantern beta", None)])
        made["spread"] = spread
        for index in range(WORD_VERSIONS):
            name = f"u8s-{token}-word-{index}"
            _version(conn, name, name + "-paper", eligible=True)
            _chunks(conn, name, [(f"quorumword item {index}", None)])
            made["word"].append(name)
        for index in range(RANKED_VERSIONS):
            name = f"u8s-{token}-zrank-{index}"
            _version(conn, name, name + "-paper", eligible=True)
            _chunks(conn, name, [(f"quorumword quorumword quorumword rank {index}", None)])
            made["zrank"].append(name)
        conn.commit()
        yield made
    finally:
        conn.rollback()
        prefix = f"u8s-{token}-%"
        conn.execute("DELETE FROM corpus.projection WHERE version_id LIKE %s", (prefix,))
        conn.execute("DELETE FROM corpus.version WHERE id LIKE %s", (prefix,))
        conn.execute("DELETE FROM corpus.paper WHERE id LIKE %s", (prefix,))
        conn.commit()
        conn.close()


@pytest.fixture
def candidates(transactions):
    return SearchCandidates(transactions)


# Planner settings for this test session only, by the person's decision of 2026-10-22:
# never in production code, and never in `u8_search.py`'s transaction.
MEANING_FORCED = (
    "enable_seqscan", "enable_bitmapscan", "enable_hashjoin",
    # With only the three above off, the planner still reads every eligible chunk
    # through `projection_pkey`, joined by a merge join over a hash aggregate, or by a
    # sorted unique pass, and then sorts them all by distance.
    "enable_mergejoin", "enable_hashagg", "enable_sort",
)
# GIN serves only bitmap scans, so the words check keeps bitmap scans on.
WORDS_FORCED = ("enable_seqscan", "enable_hashjoin")


def index_session(realm, *, forced: tuple[str, ...], iterative: str = "relaxed_order"):
    """A Discovery session with the competing plans turned off for itself alone, plus
    the production query's own `hnsw.ef_search` and iterative-scan settings."""
    conn = _connect(realm, "discovery")
    for setting in forced:
        conn.execute(f"SET {setting} = off")
    conn.execute("SET hnsw.ef_search = 200")
    conn.execute(f"SET hnsw.iterative_scan = {iterative}")
    return conn


def test_two_hundred_by_meaning_while_more_exist_under_the_eligibility_filter(
        corpus, candidates, realm):
    """Proves the meaning query CAN read 200 eligible chunks through the HNSW index's
    iterative scan where the same forced plan without it stops short. That the planner
    DOES choose the index at production size is the performance phase's check (Step 43),
    by the person's decision of 2026-10-22."""
    found = candidates.read("", QUERY)["meaning"]
    assert len(found) == MEANING_LIMIT
    assert {row["version_id"] for row in found} <= set(corpus["far"])
    results, plans = {}, {}
    for mode in ("relaxed_order", "off"):
        conn = index_session(realm, forced=MEANING_FORCED, iterative=mode)
        try:
            params = meaning_parameters(conn, str(QUERY), MEANING_LIMIT)
            plans[mode] = "\n".join(
                row["QUERY PLAN"] for row in conn.execute("EXPLAIN " + MEANING_SQL, params))
            results[mode] = conn.execute(MEANING_SQL, params).fetchall()
        finally:
            conn.close()
    for mode in results:
        assert "projection_embedding_hnsw" in plans[mode], plans[mode]
    # Through the index, the iterative scan still yields 200 eligible chunks; without it
    # the scan stops after its first neighbours, which are the ineligible chunks.
    assert len(results["relaxed_order"]) == MEANING_LIMIT
    assert {row["version_id"] for row in results["relaxed_order"]} <= set(corpus["far"])
    assert len(results["off"]) < MEANING_LIMIT


def test_a_withdrawn_paper_never_appears(corpus, candidates):
    read = candidates.read("harbor lantern meadow", QUERY)
    for row in [*read["meaning"], *read["words"]]:
        assert row["version_id"] != corpus["withdrawn"]


def test_the_eligibility_filter_drops_withdrawn_and_ineligible_chunks_in_its_new_form(
        corpus, candidates, realm):
    """The meaning query's per-row filter (the eligible versions, read once in the same
    transaction): the withdrawn paper's chunk, which is the query itself, and the 600
    ineligible chunks nearer than any eligible one never reach the results, though they
    are the nearest in the index."""
    conn = _connect(realm, "discovery")
    try:
        eligible = set(meaning_parameters(conn, str(QUERY), MEANING_LIMIT)["eligible"])
    finally:
        conn.close()
    assert corpus["withdrawn"] not in eligible
    assert not eligible & set(corpus["near"])
    assert {*corpus["far"], corpus["spread"], *corpus["word"]} <= eligible
    found = candidates.read("", QUERY)["meaning"]
    assert len(found) == MEANING_LIMIT
    versions = {row["version_id"] for row in found}
    assert corpus["withdrawn"] not in versions and not versions & set(corpus["near"])
    # Closest first, as before: the order the ranking and the cursor rely on.
    distances = [row["distance"] for row in found]
    assert distances == sorted(distances)


def test_a_term_spread_across_two_chunks_of_one_version_matches_by_words(corpus, candidates):
    words = candidates.read("harbor lantern", None)["words"]
    spread = [row for row in words if row["version_id"] == corpus["spread"]]
    assert len(spread) == 1
    assert spread[0]["text_content"] in ("alpha harbor", "lantern beta")


def test_the_plans_use_the_hnsw_and_gin_indexes(corpus, realm):
    """Proves the production meaning and word queries CAN use the HNSW and GIN indexes,
    with the competing plans off in this session only. That the planner DOES choose them
    at production size is the performance phase's check (Step 43), by the person's
    decision of 2026-10-22."""
    conn = index_session(realm, forced=MEANING_FORCED)
    try:
        meaning = "\n".join(row["QUERY PLAN"] for row in conn.execute(
            "EXPLAIN " + MEANING_SQL, meaning_parameters(conn, str(QUERY), MEANING_LIMIT)))
    finally:
        conn.close()
    conn = index_session(realm, forced=WORDS_FORCED)
    try:
        words = "\n".join(row["QUERY PLAN"] for row in conn.execute(
            "EXPLAIN " + WORDS_SQL, {"text": "harbor lantern", "limit": WORDS_LIMIT}))
    finally:
        conn.close()
    assert "projection_embedding_hnsw" in meaning, meaning
    assert "version_lexical_all" in words, words
    assert "Seq Scan on projection" not in meaning, meaning


def test_two_hundred_by_meaning_two_hundred_by_words_four_hundred_at_most(corpus, candidates):
    """300 eligible chunks with vectors and 220 versions matching `quorumword`: each half
    reads exactly 200, and the two cannot overlap (the meaning rows come from the far
    versions, the words rows from versions without vectors), so exactly 400 reach ranking."""
    read = candidates.read("quorumword", QUERY)
    assert len(read["meaning"]) == 200
    assert len(read["words"]) == 200
    assert {row["version_id"] for row in read["meaning"]} <= set(corpus["far"])
    merged = SearchCandidates.merged(read)
    assert len(merged) == 400 == CANDIDATE_LIMIT
    assert len({(row["version_id"], row["ordinal"]) for row in merged}) == 400


def test_words_read_only_eligible_versions_best_ranked_with_their_best_chunk(
        corpus, candidates):
    # Only the 60 ineligible versions hold `noise`.
    assert candidates.read("noise", None)["words"] == []
    # `WORDS_SQL` keeps 200 by `ORDER BY rank DESC, v.id`: the `zrank` versions rank
    # highest though their ids sort last, so an id-only order would have dropped them.
    words = candidates.read("quorumword", None)["words"]
    assert len(words) == 200
    assert [row["version_id"] for row in words[:10]] == sorted(corpus["zrank"])
    scores = [row["lexical_score"] for row in words]
    assert all(a >= b for a, b in zip(scores, scores[1:], strict=False)), scores
    spread = [row for row in candidates.read("alpha harbor", None)["words"]
              if row["version_id"] == corpus["spread"]]
    assert len(spread) == 1
    assert spread[0]["text_content"] == "alpha harbor"


class _SettingsProxy:
    """A pass-through observer of the `DeadlineConnection` (L1-35, call-through kind): it
    forwards every call unchanged and, just before `MEANING_SQL` runs, adds two
    `current_setting` reads on the same connection, setting nothing."""

    def __init__(self, conn, seen: list):
        self._conn = conn
        self._seen = seen

    def execute(self, query, params=None, **kwargs):
        if query == MEANING_SQL:
            row = self._conn.execute(
                "SELECT current_setting('hnsw.ef_search') AS ef, "
                "current_setting('hnsw.iterative_scan') AS scan").fetchone()
            self._seen.append((row["ef"], row["scan"]))
        return self._conn.execute(query, params, **kwargs)

    def __getattr__(self, name):
        return getattr(self._conn, name)


class _ObservedTransactions:
    """Forwards `run(owner, action)` to the real transactions, handing the action the
    settings proxy over its own connection; it replaces nothing."""

    def __init__(self, transactions, seen: list):
        self._transactions = transactions
        self._seen = seen

    def run(self, owner, action):
        return self._transactions.run(owner, lambda conn: action(_SettingsProxy(conn, self._seen)))


def test_the_production_read_sets_ef_search_and_the_iterative_scan(
        corpus, transactions, realm):
    seen: list = []
    read = SearchCandidates(_ObservedTransactions(transactions, seen)).read("", QUERY)
    assert seen == [("200", "relaxed_order")]
    assert len(read["meaning"]) == 200
    assert {row["version_id"] for row in read["meaning"]} <= set(corpus["far"])
    assert read["words"] == []
    # A fresh session reads the server's defaults once pgvector is loaded: the values
    # came from the search transaction, not from a role or database setting.
    conn = _connect(realm, "discovery")
    try:
        conn.execute("SELECT '[1,0,0]'::public.vector")
        row = conn.execute(
            "SELECT current_setting('hnsw.ef_search') AS ef, "
            "current_setting('hnsw.iterative_scan') AS scan").fetchone()
    finally:
        conn.close()
    assert (row["ef"], row["scan"]) == ("40", "off")


def test_a_query_vector_of_another_shape_is_refused(candidates):
    with pytest.raises(ValueError):
        candidates.read("harbor", [1.0] * 8)
    with pytest.raises(ValueError):
        candidates.read("harbor", [float("nan")] * DIMENSIONS)
