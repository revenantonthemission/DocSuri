"""Dense local embedding adapter with strict dimensional and finite-value checks."""

from __future__ import annotations

import math

from docsuri_ops.local_models import LocalModelRuntime, ModelUnavailable


class LocalEmbeddings:
    def __init__(self, runtime: LocalModelRuntime):
        self.runtime = runtime

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.runtime.infer(
            model="bge-m3:latest",
            body={
                "model": "bge-m3:latest",
                "input": texts,
                "truncate": False,
                "keep_alive": 0,
                "options": {"num_ctx": 2048, "num_thread": 2},
            },
        )
        vectors = response.get("embeddings", [])
        if len(vectors) != len(texts):
            raise ModelUnavailable("embedding cardinality mismatch")
        for vector in vectors:
            if len(vector) != 1024 or any(
                not isinstance(x, (float, int)) or isinstance(x, bool) or not math.isfinite(x)
                for x in vector
            ):
                raise ModelUnavailable("embedding dimensions or values invalid")
            if sum(x * x for x in vector) == 0:
                raise ModelUnavailable("embedding has no direction")
        return vectors


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != 1024 or len(right) != 1024:
        raise ValueError("embedding dimension mismatch")
    norm = math.sqrt(sum(x * x for x in left) * sum(x * x for x in right))
    if norm == 0 or not math.isfinite(norm):
        raise ValueError("invalid embedding norm")
    return sum(x * y for x, y in zip(left, right, strict=True)) / norm
