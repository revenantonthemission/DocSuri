"""Paper assistance at production's corpus limits (U8 plan Step 23; your decision of
2026-10-24, "Fix it in U8").

U3 offers assistance only for a paper of at most 256 chunks with no repeated anchor
(`u3_catalog.definitions_for`), and the worker's payload accepts only the same
(`payload.selected_sections`). Production publishes papers of up to 200 chunks (lowered
by your decision of 2026-11-08, L1-74, and measured again by your answer of 2026-11-09,
L1-81, provisional until the first dry run), and
splits a block over 8 KB into pieces that keep the block's anchor with a piece number
(`corpus/limits.py`). Here, in production only:

- assistance accepts up to 200 chunks per paper;
- the split pieces of one block are one unit (`blocks`): offered, selected and cited as
  that block, with the block's anchor, so each citation leads to the block;
- a selection stays inside the payload's 7,000-byte allocation: units are taken whole in
  document order while they fit, and the first one that does not is selected as a span
  of its own text, cut at whitespace (the selection descriptor's `start`/`end`).

The composed realm, a synthetic realm, passes no rule and keeps U3's built rule (BR7.1).
U3's files hold only the seams (`u3_catalog.catalog_for(rule=)`,
`u3_http.assistance_router(source_rule=)`, `u3_dispatch.AssistanceDispatch(payload_rule=)`).
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from backend.modules.corpus.limits import PRODUCTION_LIMITS
from backend.modules.summarization.payload import SelectionRule
from backend.modules.summarization.requests import AssistanceCatalog

MAX_CHUNKS = PRODUCTION_LIMITS.max_chunks  # 200 (L1-74, L1-81; provisional until the first dry run)
SELECTION_BYTES = 7000  # the payload's context allocation (`payload.selected_sections`)
SUMMARY_UNITS, TRANSLATION_UNITS = 8, 1
MIN_SPAN_BYTES = 200
LABELS = {"summary": "핵심 구간 요약", "translation": "핵심 구간 한국어 번역"}
PIECE_SEPARATOR = " "


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def blocks(chunks: list[dict]) -> list[dict]:
    """The units assistance offers: each chunk, except that the consecutive pieces of one
    split block (the same anchor, `piece` 1, 2, ...) are joined into that block. A
    repeated anchor that is not such a run stays repeated, so the selection refuses it as
    ambiguous."""
    units: list[dict] = []
    last_piece = 0
    for chunk in chunks:
        piece = chunk.get("piece")
        if (
            units and type(piece) is int and piece == last_piece + 1 and piece > 1
            and units[-1]["anchor"] == chunk["anchor"]
            and units[-1]["section"] == chunk["section"]
        ):
            joined = units[-1]["text"] + PIECE_SEPARATOR + chunk["text"]
            units[-1] = {**units[-1], "text": joined, "textHash": _hash(joined)}
            last_piece = piece
            continue
        units.append({"anchor": chunk["anchor"], "section": chunk["section"],
                      "text": chunk["text"], "textHash": _hash(chunk["text"])})
        last_piece = piece if type(piece) is int else 0
    return units


PAYLOAD_RULE = SelectionRule(max_chunks=MAX_CHUNKS, blocks=blocks)


def _span(unit: dict, limit: int) -> dict | None:
    """A unit's first `limit` bytes, cut at whitespace, as a span descriptor."""
    encoded = unit["text"].encode()[:limit].decode(errors="ignore")
    cut = encoded.rfind(" ")
    if cut <= 0:
        return None
    text = encoded[:cut]
    return {"anchor": unit["anchor"], "heading": unit["section"], "textHash": unit["textHash"],
            "start": 0, "end": len(text), "selectedHash": _hash(text)}


def _selection(units: list[dict], count: int) -> list[dict]:
    selection, used = [], 0
    for unit in units[:count]:
        size = len(unit["text"].encode())
        if used + size <= SELECTION_BYTES:
            selection.append({"anchor": unit["anchor"], "heading": unit["section"],
                              "textHash": unit["textHash"]})
            used += size
            continue
        if SELECTION_BYTES - used >= MIN_SPAN_BYTES:
            span = _span(unit, SELECTION_BYTES - used)
            if span is not None:
                selection.append(span)
        break
    return selection


def definitions_for(source: dict) -> list[dict] | None:
    """Production's options for one version, or None when it has no usable units."""
    content = source.get("content") or {}
    chunks = content.get("chunks")
    if not isinstance(chunks, list) or not 1 <= len(chunks) <= MAX_CHUNKS:
        return None
    units = blocks(chunks)
    if len({unit["anchor"] for unit in units}) != len(units):
        return None
    definitions = []
    for operation, option_id, count, target in (
        ("summary", "u8-key-sections-summary", SUMMARY_UNITS, "en"),
        ("translation", "u8-key-sections-translation", TRANSLATION_UNITS, "ko"),
    ):
        selection = _selection(units, count)
        if selection:
            definitions.append({
                "option": {"optionId": option_id, "operation": operation,
                           "sourceLanguageId": "en", "targetLanguageId": target,
                           "presentationLevelId": "selected-source",
                           "labelKey": LABELS[operation]},
                "selectedSections": selection,
            })
    return definitions or None


class ProductionAssistanceRule:
    """The production source rule the complete assembly passes in production only: its
    catalog (`u3_catalog.catalog_for(rule=)`) and its payload rule
    (`u3_dispatch.AssistanceDispatch(payload_rule=)`). New work is offered only while the
    reviewed real-model evidence for assistance is recorded (`ready`, BR7.7)."""

    payload = PAYLOAD_RULE

    def __init__(self, ready: Callable[[], bool]):
        self.ready = ready

    def catalog(self, source: dict) -> AssistanceCatalog | None:
        definitions = definitions_for(source)
        if definitions is None:
            return None
        return AssistanceCatalog(source, definitions, quality_ready=bool(self.ready()),
                                 rule=PAYLOAD_RULE)
