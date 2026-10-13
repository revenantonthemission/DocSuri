"""Finite U1 source-selection policy over the two approved local fixtures.

The policy is explicit and partial: each option names the exact source anchors
it will process, and every limitation is disclosed. Unknown sources receive no
runnable option rather than a guessed whole-paper scope.
"""

from __future__ import annotations

from backend.modules.summarization.guarded_repository import intent_digest
from backend.modules.summarization.requests import (
    PROCESSING_POLICY,
    AssistanceCatalog,
)
from docsuri_shared.workspace import wire

# Anchor groups were selected during the parent-reviewed model experiments.
# They are a finite, documented selection, never a whole-paper claim.
KEY_SECTIONS = {
    "1706.03762": {
        "summary": ["s3.2.1.eq1", "s3.2.1.p4", "s3.5.p1", "s3.5.p2", "s3.5.p3", "s3.5.p4"],
        "translation": ["s3.5.p1"],
    },
    "2005.11401": {
        "summary": ["s1.p2", "s1.fig1", "s2.1.1.p1", "s2.1.2.p1", "s2.2.p2", "s2.3.p1"],
        "translation": ["s2.1.1.p1"],
    },
}
LABELS = {
    "summary": "핵심 구간 요약",
    "translation": "핵심 구간 한국어 번역",
}


def definitions_for(source: dict) -> list[dict] | None:
    plan = KEY_SECTIONS.get(source["paper_id"])
    if plan is None:
        return None
    chunks = {chunk["anchor"]: chunk for chunk in source["content"]["chunks"]}
    definitions = []
    for operation, anchors in plan.items():
        selection = [
            {
                "anchor": anchor,
                "heading": chunks[anchor]["section"],
                "textHash": chunks[anchor]["textHash"],
            }
            for anchor in anchors
        ]
        definitions.append(
            {
                "option": {
                    "optionId": "key-sections-" + operation,
                    "operation": operation,
                    "sourceLanguageId": "en",
                    "targetLanguageId": "ko" if operation == "translation" else "en",
                    "presentationLevelId": "selected-source",
                    "labelKey": LABELS[operation],
                },
                "selectedSections": selection,
            }
        )
    return definitions


def catalog_for(source: dict, *, quality_ready: bool) -> AssistanceCatalog | None:
    definitions = definitions_for(source)
    if definitions is None:
        return None
    return AssistanceCatalog(source, definitions, quality_ready=quality_ready)


def unavailable_options(source: dict) -> dict:
    """Truthful empty catalogue for a source without an approved selection policy."""
    return wire.AssistanceOptions.model_validate(
        {
            "revision": intent_digest(
                {"paper": source["id"], "policy": "no-approved-selection", "options": []}
            ),
            "options": [],
            "policy": PROCESSING_POLICY,
            "limitations": ["이 자료에는 아직 승인된 선택 정책이 없습니다."],
        }
    ).model_dump(mode="json")
