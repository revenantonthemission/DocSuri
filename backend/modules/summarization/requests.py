"""Server-owned option selection and immutable browser-request preparation.

Catalog definitions come from the local assembly, never from browser bodies.
Their revision binds source bytes, scope, language and presentation policy.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from uuid import UUID

from backend.modules.corpus.repository import CorpusRepository, content_revision
from backend.modules.summarization.admission import AssistanceAdmission
from backend.modules.summarization.guarded_repository import intent_digest
from backend.modules.summarization.payload import selected_sections
from backend.transactions import Authority
from docsuri_shared.workspace import wire

PROCESSING_POLICY = {"policyId": "local-research", "revision": "1"}


class AssistanceUnavailable(RuntimeError):
    """Required useful-output evidence or its runtime binding is unavailable."""


class AssistanceCatalog:
    def __init__(self, source: dict, definitions: list[dict], *, quality_ready: bool = False):
        if not 1 <= len(definitions) <= 16:
            raise ValueError("finite option catalogue allocation exceeded")
        self.source = deepcopy(source)
        self.definitions = deepcopy(definitions)
        self.quality_ready = quality_ready
        self.content_revision = content_revision(source)
        seen = set()
        for definition in self.definitions:
            if set(definition) != {"option", "selectedSections"}:
                raise ValueError("invalid trusted option definition")
            option = wire.AssistanceOption.model_validate(definition["option"]).model_dump(
                mode="json"
            )
            if option["optionId"] in seen:
                raise ValueError("duplicate assistance option")
            seen.add(option["optionId"])
            if (
                option["sourceLanguageId"] != "en"
                or option["targetLanguageId"]
                != ("ko" if option["operation"] == "translation" else "en")
                or option["presentationLevelId"] != "selected-source"
            ):
                raise ValueError("unsupported local language or presentation")
            selected_sections(source, definition["selectedSections"])
            definition["option"] = option
        self.revision = intent_digest(
            {
                "contentRevision": self.content_revision,
                "paper": self.paper,
                "policy": PROCESSING_POLICY,
                "definitions": self.definitions,
                "qualityReady": self.quality_ready,
            }
        )

    @property
    def paper(self) -> dict:
        return {
            "paperId": self.source["paper_id"],
            "versionId": self.source["id"],
            "eligibilityRevision": str(self.source["eligibility_revision"]),
        }

    def options(self) -> dict:
        limitations = ["선택한 원문 부분만 처리합니다. 논문 전체에 대한 결과가 아닙니다."]
        if not self.quality_ready:
            limitations.append("AI 응답 품질 검증이 완료되지 않아 새 작업을 시작할 수 없습니다.")
        return wire.AssistanceOptions.model_validate(
            {
                "revision": self.revision,
                "options": [item["option"] for item in self.definitions]
                if self.quality_ready
                else [],
                "policy": PROCESSING_POLICY,
                "limitations": limitations,
            }
        ).model_dump(mode="json")

    def bind(self, request: dict) -> dict:
        if not self.quality_ready:
            raise AssistanceUnavailable("source-bound useful-output readiness is unavailable")
        if (
            request["paper"] != self.paper
            or request["contentRevision"] != self.content_revision
            or request["contentHash"] != self.source["source_hash"]
            or request["optionsRevision"] != self.revision
            or request["processingPolicy"] != PROCESSING_POLICY
        ):
            raise ValueError("source, options or processing revision conflict")
        selected = next(
            (
                item
                for item in self.definitions
                if item["option"]["optionId"] == request["optionId"]
            ),
            None,
        )
        if selected is None or selected["option"]["operation"] != request["operation"]:
            raise ValueError("unsupported assistance option")
        return {
            "versionId": self.source["id"],
            "sourceHash": self.source["source_hash"],
            "action": request["operation"],
            "request": deepcopy(request),
            "selectedSections": deepcopy(selected["selectedSections"]),
        }


class AssistanceRequests:
    def __init__(
        self,
        admission: AssistanceAdmission,
        corpus: CorpusRepository,
        catalog_for: Callable[[dict], AssistanceCatalog],
    ):
        self.admission = admission
        self.corpus = corpus
        self.catalog_for = catalog_for

    def submit(self, authority: Authority, operation: UUID, request: dict) -> dict:
        normalized = wire.AssistanceRequestHttp.model_validate(request).model_dump(mode="json")
        repository = self.admission.assistance
        original = repository.replay_request(authority, operation, normalized)
        if original is not None:
            return self.admission.accept(authority, operation, original["intent"])
        source = self.corpus.read(normalized["paper"]["versionId"])
        proposal = self.catalog_for(source).bind(normalized)
        prepared = repository.prepare_request(authority, operation, proposal)
        return self.admission.accept(authority, operation, prepared["intent"])
