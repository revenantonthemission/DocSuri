"""The complete assembly's search: candidates (U8 plan Step 7; P1, NFR8.4).

`SearchCandidates` reads, in one transaction as DiscoveryCitations' login (which holds
SELECT on the corpus tables):

- by meaning: up to 200 chunks nearest the query vector through the HNSW index on
  `corpus.projection.embedding_vector`, with `hnsw.ef_search = 200` and pgvector's
  iterative scan, so the eligibility filter still yields 200 while more exist;
- by words: up to 200 paper versions whose per-version `lexical_all` matches every
  query term (`plainto_tsquery('simple', ...)`, ranked by `ts_rank_cd` on the GIN
  index), each with its best chunk from the per-chunk `lexical` index.

Both read only eligible versions of papers that are not withdrawn, and never the whole
corpus: at most 400 rows reach ranking. The ranking half (`CompleteSearch`, Step 23)
feeds them to the built `local_search` ranking. See:
`aidlc/spaces/default/intents/261016-finish-v2-rebuild/construction/u8-service-operations-integration/code-generation/code-generation-plan.md`.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from uuid import uuid4

from backend.modules.discovery.local_embedding import SEMANTIC_UNAVAILABLE
from backend.modules.discovery.local_search import SearchPageBuilder, validate_query
from backend.modules.discovery.u3_search import SnapshotExpired, U3Search, _query_digest
from backend.transactions import Authority, guard
from backend.u3_policy import (
    PROJECTION_COMPATIBILITY,
    QUERY_VOCABULARY,
    SEARCH_POLICY,
    page_size,
)
from docsuri_ops.local_models import ModelUnavailable
from docsuri_shared.workspace import wire

OWNER = "discovery"
DIMENSIONS = 1024
MEANING_LIMIT = 200
WORDS_LIMIT = 200
CANDIDATE_LIMIT = MEANING_LIMIT + WORDS_LIMIT
EF_SEARCH = 200
MAX_QUERY_BYTES = 2048

# The columns every candidate row carries, as the built snapshot read gives them, with
# the chunk's embedding and its policy, which the built ranking scores by meaning.
_COLUMNS = (
    "c.version_id,c.ordinal,c.content_hash,c.anchor,c.section,c.text_content,"
    "c.embedding,c.vector_policy,"
    "v.paper_id,v.source_hash,v.version_label,v.source_url,v.eligibility_revision,"
    "p.title,p.authors,p.published_on"
)
_ELIGIBLE = "v.eligible AND NOT p.withdrawn"

# Eligibility as a per-row filter on the chunk itself, against the eligible versions read
# first in the same transaction (`ELIGIBLE_SQL`, one short read of at most the corpus's
# version count), passed as a value whose size the planner knows: the HNSW scan streams
# the nearest chunks in distance order, the filter keeps the eligible ones, and
# pgvector's iterative scan keeps reading the graph until `limit` of them are found. A
# correlated semi-join on the version and its paper instead let the planner join first
# and sort every chunk (the performance phase found it; U8 plan Step 7's "through the
# HNSW index"); a subquery in its place hides the list's size, so the planner reads the
# eligible chunks by the primary key and sorts them all.
ELIGIBLE_SQL = (
    "SELECT coalesce(array_agg(v.id ORDER BY v.id), '{}') AS eligible FROM corpus.version v "
    f"JOIN corpus.paper p ON p.id=v.paper_id WHERE {_ELIGIBLE}"
)
_ELIGIBLE_CHUNK = "c.version_id = ANY (%(eligible)s)"
_ELIGIBLE_VERSION = (
    "EXISTS (SELECT 1 FROM corpus.paper p WHERE p.id=v.paper_id AND NOT p.withdrawn) "
    "AND v.eligible"
)

MEANING_SQL = (
    "WITH nearest AS MATERIALIZED (SELECT c.version_id, c.ordinal, "
    "c.embedding_vector <=> %(vector)s::public.vector AS distance FROM corpus.projection c "
    f"WHERE c.embedding_vector IS NOT NULL AND {_ELIGIBLE_CHUNK} "
    "ORDER BY c.embedding_vector <=> %(vector)s::public.vector LIMIT %(limit)s) "
    f"SELECT {_COLUMNS}, nearest.distance FROM nearest "
    "JOIN corpus.projection c ON c.version_id=nearest.version_id AND c.ordinal=nearest.ordinal "
    "JOIN corpus.version v ON v.id=c.version_id JOIN corpus.paper p ON p.id=v.paper_id "
    "ORDER BY nearest.distance, c.version_id, c.ordinal"
)

WORDS_SQL = (
    "WITH q AS (SELECT plainto_tsquery('simple', %(text)s) AS every_term, "
    "replace(plainto_tsquery('simple', %(text)s)::text, '&', '|')::tsquery AS any_term), "
    "versions AS MATERIALIZED (SELECT v.id, ts_rank_cd(v.lexical_all, q.every_term) AS rank "
    "FROM corpus.version v, q WHERE v.lexical_all @@ q.every_term "
    f"AND {_ELIGIBLE_VERSION} "
    "ORDER BY rank DESC, v.id LIMIT %(limit)s) "
    f"SELECT DISTINCT ON (c.version_id) {_COLUMNS}, versions.rank AS lexical_score "
    "FROM versions JOIN corpus.projection c ON c.version_id=versions.id "
    "JOIN corpus.version v ON v.id=c.version_id JOIN corpus.paper p ON p.id=v.paper_id, q "
    "ORDER BY c.version_id, (c.lexical @@ q.any_term) DESC, "
    "ts_rank_cd(c.lexical, q.any_term) DESC, c.ordinal"
)


def _vector_literal(vector: Sequence[float]) -> str:
    values = list(vector)
    if len(values) != DIMENSIONS or not all(
        isinstance(value, (int, float)) and math.isfinite(value) for value in values
    ):
        raise ValueError("query vector outside the pinned embedding's shape")
    return "[" + ",".join(repr(float(value)) for value in values) + "]"


def meaning_parameters(conn, vector: str, limit: int) -> dict:
    """The meaning query's parameters: the query vector, its limit and the eligible
    versions, read in the caller's transaction so the list and the scan see one snapshot."""
    eligible = conn.execute(ELIGIBLE_SQL).fetchone()["eligible"]
    return {"vector": vector, "limit": limit, "eligible": list(eligible)}


class SearchCandidates:
    def __init__(self, transactions):
        self.transactions = transactions

    def read(
        self,
        query: str,
        vector: Sequence[float] | None,
        *,
        authority: Authority | None = None,
    ) -> dict:
        """Both candidate sets from one transaction: `meaning` (closest first) and
        `words` (best ranked first), with `vector` None answering by words only."""
        if not isinstance(query, str) or len(query.encode()) > MAX_QUERY_BYTES:
            raise ValueError("search query exceeds its bound")
        literal = None if vector is None else _vector_literal(vector)

        def read(conn):
            if authority is not None:
                guard(conn, authority)
            meaning = []
            if literal is not None:
                conn.execute(f"SET LOCAL hnsw.ef_search = {int(EF_SEARCH)}")
                conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
                meaning = conn.execute(MEANING_SQL, meaning_parameters(
                    conn, literal, MEANING_LIMIT)).fetchall()
            words = []
            if query.strip():
                words = conn.execute(
                    WORDS_SQL, {"text": query, "limit": WORDS_LIMIT}
                ).fetchall()
                words.sort(key=lambda row: (-row["lexical_score"], row["version_id"]))
            publication = conn.execute("SELECT * FROM corpus.guard_publication()").fetchone()
            return {"meaning": meaning, "words": words, "publication": publication}

        return self.transactions.run(OWNER, read)

    @staticmethod
    def merged(candidates: dict) -> list[dict]:
        """The distinct chunks that reach ranking, at most 400, meaning first."""
        seen, rows = set(), []
        for row in [*candidates["meaning"], *candidates["words"]]:
            key = (row["version_id"], row["ordinal"])
            if key not in seen:
                seen.add(key)
                rows.append(row)
        if len(rows) > CANDIDATE_LIMIT:
            raise ValueError("search candidates exceed their bound")
        return rows


# --- The ranking half (Step 23) -----------------------------------------------------------

VECTOR_POLICY = "bge-m3-1024-pinned-1"


class StandinEmbeddings:
    """The composed realm's deterministic stand-in for the query embedder (BR7.1): the
    same text always gives the same unit vector, and no model runtime is called. It has
    the production embedder's interface (`embed_query`, `embed_batches`)."""

    path_kind = "stand-in"

    def embed_query(self, text: str) -> list[float]:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("a query text is required")
        stream = b""
        counter = 0
        while len(stream) < DIMENSIONS * 2:
            stream += hashlib.sha256(f"{counter}:{text}".encode()).digest()
            counter += 1
        values = [
            (int.from_bytes(stream[2 * i:2 * i + 2], "big") / 65535.0) - 0.5
            for i in range(DIMENSIONS)
        ]
        norm = math.sqrt(sum(value * value for value in values))
        return [value / norm for value in values]

    def embed_batches(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class CompleteSearch(U3Search):
    """The complete assembly's search (P1): Step 7's candidates, at most 400, into the
    built ranking (`SearchPageBuilder`: the best chunk per version, the order and the
    signed cursor). A semantic query is embedded by the real embedder (bounded at 2 s)
    or the realm's stand-in; when no vector comes back in time it answers by words only,
    disclosed with `semantic-search-unavailable` (BR7.2). History, checkpoints and
    reruns are U3Search's own. `U3Search` itself stays for U3–U6."""

    def __init__(self, transactions, repository, library, *, cursor_key, embedder):
        super().__init__(transactions, repository, library, cursor_key=cursor_key)
        self.candidates = SearchCandidates(transactions)
        self.embedder = embedder
        self.builder = SearchPageBuilder(
            cursor_key, vocabulary=QUERY_VOCABULARY, policy=SEARCH_POLICY,
            compatibility=PROJECTION_COMPATIBILITY, max_candidates=CANDIDATE_LIMIT,
        )

    def _query_vector(self, text: str) -> list[float] | None:
        try:
            return self.embedder.embed_query(text)
        except (ModelUnavailable, TimeoutError):
            return None

    def snapshot(self, authority: Authority | None, query: dict, vector) -> dict:
        found = self.candidates.read(query["query"], vector, authority=authority)
        rows = self.candidates.merged(found)
        if vector is not None:
            rows = [row for row in rows
                    if row["embedding"] is not None and row["vector_policy"] == VECTOR_POLICY]
        else:
            rows = [row for row in rows if "lexical_score" in row]
        return {"publication": found["publication"], "candidates": rows}

    def search(self, authority: Authority | None, request: dict) -> dict:
        query = validate_query(request["query"], vocabulary=QUERY_VOCABULARY,
                               policy=SEARCH_POLICY)
        limit = page_size((request.get("page") or {}).get("limit"))
        vector = self._query_vector(query["query"]) if query["modeId"] == "semantic" else None
        degraded = query["modeId"] == "semantic" and vector is None
        execution = uuid4()
        admission = None
        if authority is not None:
            admission = self.repository.admit(authority, execution, _query_digest(query))
        snapshot = self.snapshot(authority, query, vector)
        expected = request.get("snapshotRevision")
        revision = snapshot["publication"]["revision"]
        if expected is not None and expected != str(revision):
            raise SnapshotExpired("search snapshot changed")
        response = self.builder.build(
            snapshot=snapshot, query=query, execution=str(execution),
            owner=str(authority.account_id) if authority is not None else "guest",
            limit=limit, cursor=(request.get("page") or {}).get("cursor"),
            query_vector=vector, effective_mode="lexical" if degraded else None,
        )
        if degraded:
            response["outcome"] = "degraded"
            response["limitations"] = [*response["limitations"], SEMANTIC_UNAVAILABLE]
        if authority is not None and not self._relay_fact(
            authority, execution, query, response["hits"], admission,
            snapshot_revision=revision,
            degradation="semantic-unavailable" if degraded else "none",
        ):
            response["limitations"] = [
                *response["limitations"],
                "검색 기록을 저장하지 못했습니다. 다음 검색에서 다시 시도합니다.",
            ]
        return wire.SearchResponse.model_validate(response).model_dump(mode="json")
