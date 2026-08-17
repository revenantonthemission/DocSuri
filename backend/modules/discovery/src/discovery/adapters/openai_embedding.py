"""OpenAICompatQueryEmbedder — local ``EmbeddingAdapter`` (full-local serving, 2026-08-17).

The reader-side mirror of U1's ``OpenAICompatEmbeddingPort``: SAME model/space (bge-m3,
1024-dim, vector-spec §4), served by any OpenAI-compatible endpoint — Ollama's ``/v1``
routes today, rapid-mlx or another MLX server tomorrow, with no code change (the endpoint
is env-driven, ``DOCSURI_EMBEDDING_API_BASE``). Unlike Cohere, bge-m3 is symmetric — no
search_query/search_document input-type asymmetry, so reader and writer issue identical
requests. The failure contract is inherited from the Bedrock adapter: a transient failure
raises ``EmbeddingUnavailable`` so the orchestrator degrades to lexical-only (Q1/BR-16);
a dimension mismatch is NOT transient — it means the query was embedded in a different
space than the index (full re-embed required, vector-spec §4) — so it fails loud rather
than silently degrading.
"""

from __future__ import annotations

import json
import urllib.request

from docsuri_shared.vector_spec import DIMENSIONS

from ..ports.search_ports import EmbeddingUnavailable

# Local single-query embeds on Apple Silicon are subsecond once the model is resident; the
# first call after a server restart pays model load (~2-4s). 10s covers the cold load while
# still failing inside the BFF's 30s search hop (same budget reasoning as the Bedrock adapter).
_TIMEOUT_S = 10.0


class OpenAICompatQueryEmbedder:
    """Query embedding via a local OpenAI-compatible server (bge-m3, 1024-dim, symmetric)."""

    def __init__(self, *, api_base: str, model: str) -> None:
        self._embed_url = api_base.rstrip("/") + "/embeddings"
        self._model = model

    def embed_query(self, text: str) -> list[float]:
        body = json.dumps({"model": self._model, "input": text}).encode("utf-8")
        request = urllib.request.Request(
            self._embed_url, data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 — any local-server/transport error → degrade
            raise EmbeddingUnavailable("local embedding server failed") from exc

        data = payload.get("data") or []
        if not data or "embedding" not in data[0]:
            raise EmbeddingUnavailable("local embedding server returned no embedding")
        vector = data[0]["embedding"]
        if len(vector) != DIMENSIONS:
            # Space mismatch is a configuration error, not a transient outage (vector-spec §4).
            raise ValueError(
                f"local embedding server returned vector dimension {len(vector)}, expected "
                f"{DIMENSIONS} — query/index embedding spaces differ (vector-spec §4)"
            )
        return [float(x) for x in vector]
