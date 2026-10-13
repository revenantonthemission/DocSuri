"""Canonical private result document for the local PaperAssistance executor.

The worker publishes these bytes; the read adapter decodes them into canonical
sections. Malformed bytes are an explicit failed read, never fabricated text.
"""

from __future__ import annotations

import json

from docsuri_shared.workspace import wire

LIMIT = 131072


def encode_result(*, sections: list[dict], citations: list[str], definitions: list[dict]) -> bytes:
    document = {
        "sections": sections,
        "citations": citations,
        "definitions": definitions,
    }
    encoded = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    if not 0 < len(encoded) <= LIMIT:
        raise ValueError("result document outside finite allocation")
    return encoded


def decode_result(content: bytes) -> dict:
    if not 0 < len(content) <= LIMIT:
        raise ValueError("result document outside finite allocation")
    document = json.loads(content.decode("utf-8", errors="strict"))
    if set(document) != {"sections", "citations", "definitions"}:
        raise ValueError("result document shape changed")
    sections = [wire.CorpusSection.model_validate(item) for item in document["sections"]]
    if not sections or not all(isinstance(value, str) for value in document["citations"]):
        raise ValueError("result document requires sections and citations")
    return {
        "sections": [section.model_dump(mode="json") for section in sections],
        "citations": document["citations"],
        "definitions": document["definitions"],
    }
