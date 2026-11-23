"""Dense local embedding adapter with strict dimensional and finite-value checks.

Its built use (U1's owned runtime: `keep_alive: 0`, at most 8 texts a request) is the
default. The production shape (U8 plan Step 21; P2, P3, BR6.11), on the shared runtime:

- `keep_alive=-1`, so the search model stays loaded;
- the model evidence check before every request: the runtime must report the digest the
  release pins (`runtime.verify`), and a model without a pin is refused. A runtime that
  checks each request itself (`verifies_each_request`) is not asked twice;
- a query embedding bounded by `query_seconds` (2 s), past which `embed_query` raises
  `EmbeddingTimeout` and search answers by words only with `semantic-search-unavailable`;
- imports embedded in batches of `batch` chunks (16), one request each.
"""

from __future__ import annotations

import math
import time

from docsuri_ops.local_models import LocalModelRuntime, ModelUnavailable

MODEL = "bge-m3:latest"
DIMENSIONS = 1024
SEMANTIC_UNAVAILABLE = "semantic-search-unavailable"


class EmbeddingTimeout(ModelUnavailable):
    """A query embedding passed its bound; search answers by words only."""

    reason = SEMANTIC_UNAVAILABLE


class LocalEmbeddings:
    def __init__(self, runtime: LocalModelRuntime, *, keep_alive: int = 0,
                 query_seconds: float | None = None, batch: int = 8):
        if keep_alive not in (0, -1) or not 1 <= batch <= 16:
            raise ValueError("embedding residency or batch outside policy")
        if keep_alive == -1 and not callable(getattr(runtime, "verify", None)):
            raise ValueError("a resident embedding model needs the runtime's evidence check")
        if query_seconds is not None and not 0 < query_seconds <= 30:
            raise ValueError("query embedding bound outside policy")
        self.runtime, self.keep_alive = runtime, keep_alive
        self.query_seconds, self.batch = query_seconds, batch

    def embed(self, texts: list[str], *, work_deadline: float | None = None) -> list[list[float]]:
        if not 1 <= len(texts) <= self.batch:
            raise ModelUnavailable("embedding batch outside policy")
        # ModelEvidence, before every request: here, unless the runtime checks each request
        # itself inside the request's own deadline (U8 plan Step 21), so one check is made.
        if self.keep_alive == -1 and not getattr(self.runtime, "verifies_each_request", False):
            self.runtime.verify(MODEL)
        options = {"work_deadline": work_deadline} if work_deadline is not None else {}
        response = self.runtime.infer(
            model=MODEL,
            body={
                "model": MODEL,
                "input": texts,
                "truncate": False,
                "keep_alive": self.keep_alive,
                "options": {"num_ctx": 2048, "num_thread": 2},
            },
            **options,
        )
        vectors = response.get("embeddings", [])
        if len(vectors) != len(texts):
            raise ModelUnavailable("embedding cardinality mismatch")
        for vector in vectors:
            if len(vector) != DIMENSIONS or any(
                not isinstance(x, (float, int)) or isinstance(x, bool) or not math.isfinite(x)
                for x in vector
            ):
                raise ModelUnavailable("embedding dimensions or values invalid")
            if sum(x * x for x in vector) == 0:
                raise ModelUnavailable("embedding has no direction")
        return vectors

    def embed_query(self, text: str) -> list[float]:
        """One query's vector within the query bound, or `EmbeddingTimeout`."""
        if self.query_seconds is None:
            return self.embed([text])[0]
        try:
            return self.embed([text], work_deadline=time.monotonic() + self.query_seconds)[0]
        except TimeoutError as error:
            raise EmbeddingTimeout("query embedding passed its bound") from error

    def embed_batches(self, texts: list[str]) -> list[list[float]]:
        """An import's chunks, `batch` at a time."""
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch):
            vectors.extend(self.embed(texts[start:start + self.batch]))
        return vectors


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != DIMENSIONS or len(right) != DIMENSIONS:
        raise ValueError("embedding dimension mismatch")
    norm = math.sqrt(sum(x * x for x in left) * sum(x * x for x in right))
    if norm == 0 or not math.isfinite(norm):
        raise ValueError("invalid embedding norm")
    return sum(x * y for x, y in zip(left, right, strict=True)) / norm
