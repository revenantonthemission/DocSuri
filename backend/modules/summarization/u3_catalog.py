"""U3 source-selection policy over every eligible published version.

Each option names the exact bounded anchors it will process; the synthetic
executor label is disclosed in the option limitations. A source without usable
bounded chunks receives no runnable option rather than a guessed whole-paper
scope.
"""

from __future__ import annotations

from backend.modules.summarization.guarded_repository import intent_digest
from backend.modules.summarization.requests import (
    PROCESSING_POLICY,
    AssistanceCatalog,
)
from docsuri_shared.workspace import wire

SUMMARY_ANCHORS = 8
TRANSLATION_ANCHORS = 1
LABELS = {
    "summary": "핵심 구간 요약",
    "translation": "핵심 구간 한국어 번역",
}
SYNTHETIC_NOTE = (
    "이 환경은 합성(synthetic) 실행기를 사용합니다. 실제 모델 결과가 아니며 "
    "품질 검증된 출력이 아닙니다."
)


class U3AssistanceCatalog(AssistanceCatalog):
    """Adds the synthetic-provider disclosure to the offered options."""

    def options(self) -> dict:
        value = super().options()
        value["limitations"] = [*value["limitations"], SYNTHETIC_NOTE]
        return wire.AssistanceOptions.model_validate(value).model_dump(mode="json")


def definitions_for(source: dict) -> list[dict] | None:
    content = source.get("content") or {}
    chunks = content.get("chunks")
    if not isinstance(chunks, list) or not 1 <= len(chunks) <= 256:
        return None
    by_anchor = {chunk["anchor"]: chunk for chunk in chunks}
    if len(by_anchor) != len(chunks):
        return None

    def selection(anchors: list[str]) -> list[dict]:
        return [
            {
                "anchor": anchor,
                "heading": by_anchor[anchor]["section"],
                "textHash": by_anchor[anchor]["textHash"],
            }
            for anchor in anchors
            if anchor in by_anchor
        ]

    summary = selection([chunk["anchor"] for chunk in chunks[:SUMMARY_ANCHORS]])
    translation = selection([chunk["anchor"] for chunk in chunks[:TRANSLATION_ANCHORS]])
    definitions = []
    if summary:
        definitions.append(
            {
                "option": {
                    "optionId": "u3-key-sections-summary",
                    "operation": "summary",
                    "sourceLanguageId": "en",
                    "targetLanguageId": "en",
                    "presentationLevelId": "selected-source",
                    "labelKey": LABELS["summary"],
                },
                "selectedSections": summary,
            }
        )
    if translation:
        definitions.append(
            {
                "option": {
                    "optionId": "u3-key-sections-translation",
                    "operation": "translation",
                    "sourceLanguageId": "en",
                    "targetLanguageId": "ko",
                    "presentationLevelId": "selected-source",
                    "labelKey": LABELS["translation"],
                },
                "selectedSections": translation,
            }
        )
    return definitions or None


def catalog_for(source: dict, *, provider_ready: bool) -> AssistanceCatalog | None:
    definitions = definitions_for(source)
    if definitions is None:
        return None
    if not provider_ready:
        raise ValueError("synthetic provider unavailable")
    return U3AssistanceCatalog(source, definitions, quality_ready=True)


def unavailable_options(source: dict) -> dict:
    """Truthful empty catalogue for a source without a usable selection policy."""
    return wire.AssistanceOptions.model_validate(
        {
            "revision": intent_digest(
                {"paper": source["id"], "policy": "no-usable-selection", "options": []}
            ),
            "options": [],
            "policy": PROCESSING_POLICY,
            "limitations": ["이 자료에는 아직 승인된 선택 정책이 없습니다."],
        }
    ).model_dump(mode="json")
