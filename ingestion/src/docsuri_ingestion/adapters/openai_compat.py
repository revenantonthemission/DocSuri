"""OpenAICompatEmbeddingPort — local writer-side embedding (full-local serving, 2026-08-17).

The writer-side mirror of U2's ``OpenAICompatQueryEmbedder``: SAME model/space (bge-m3,
1024-dim, vector-spec §4), served by any OpenAI-compatible endpoint — Ollama's ``/v1``
routes today, rapid-mlx tomorrow (``DOCSURI_EMBEDDING_API_BASE`` swap, no code change).
bge-m3 is symmetric, so the Cohere search_document/search_query asymmetry disappears;
both sides issue identical requests. Dimension validation mirrors the Bedrock port:
a wrong-width vector raises ``ValidationViolationError(stage="embed")`` — a space
mismatch must never reach the index (vector-spec §4).
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Sequence

from docsuri_shared.vector_spec import EMBEDDING_SPEC

from docsuri_ingestion.domain.errors import ValidationViolationError

# Document batches embed in bulk; keep sub-batches modest so one request stays well under
# local-server limits and a failure retries a small unit. Order is concatenated IN ORDER —
# the assembler zips chunk_ids↔vectors with strict=True (same contract as the Bedrock port).
_EMBED_BATCH_LIMIT = 64
# Bulk embeds of 64 chunks on Apple Silicon run a few seconds warm; first call after a
# server restart pays model load. Generous read timeout — the ingest worker is async.
_TIMEOUT_S = 120.0


class OpenAICompatEmbeddingPort:
    def __init__(
        self,
        *,
        api_base: str,
        model: str,
        output_dimension: int | None = None,
    ) -> None:
        self._embed_url = api_base.rstrip("/") + "/embeddings"
        self._model = model
        # Defaults to the frozen spec width (1024); a re-embed to a different space overrides.
        self._output_dimension = output_dimension or EMBEDDING_SPEC.dimensions

    def embed_documents(
        self,
        texts: list[str] | tuple[str, ...],
        *,
        correlation_id: str | None = None,
    ) -> list[list[float]]:
        del correlation_id
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _EMBED_BATCH_LIMIT):
            vectors.extend(self._embed_batch(texts[start : start + _EMBED_BATCH_LIMIT]))
        return vectors

    def _embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        body = json.dumps({"model": self._model, "input": list(texts)}).encode("utf-8")
        request = urllib.request.Request(
            self._embed_url, data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
            payload = json.loads(response.read().decode("utf-8"))
        data = payload.get("data") or []
        if len(data) != len(texts):
            raise ValidationViolationError(
                f"local embedding server returned {len(data)} vectors for {len(texts)} texts",
                stage="embed",
            )
        # OpenAI-compatible servers echo the input order via the `index` field; sort defensively
        # so a permuted response cannot mis-pair chunk_ids↔vectors downstream (strict zip).
        ordered = sorted(data, key=lambda item: item.get("index", 0))
        vectors = [item["embedding"] for item in ordered]
        for vector in vectors:
            if len(vector) != self._output_dimension:
                raise ValidationViolationError(
                    f"local embedding server returned vector dimension {len(vector)}, "
                    f"expected {self._output_dimension}",
                    stage="embed",
                )
        return [[float(x) for x in vector] for vector in vectors]
