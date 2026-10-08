"""Immutable final pipeline output and safe C7 outcome inspection.

Capture the actual returned payload (including rendered translation overlays), not
SummaryResultDTO's cached translation base. There is deliberately no cache, current
preferences, generation or storage URL resolver in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Protocol

from docsuri_shared._generated.dtos.docmodel_schema import SourceMode, SourceTier, Type
from docsuri_shared.dtos import DocModel
from pydantic import ValidationError

from .job import JobError, JobState
from .job_protocol import (
    JobInput,
    JobProtocolError,
    JobTask,
    JsonValue,
    identifier,
    instant,
    json_object,
    rfc3339_instant,
)
from .models import Persona
from .result_storage_codec import (
    CANONICAL_VERSION,
    CONTENT_ENCODING,
    canonical_content,
    decode_canonical_content,
    decode_prepared_content,
    prepared_content_digest,
)

_SUMMARY_TEXT = ("tldr", "method", "results", "limitations")
_ABSTAIN_REASONS = frozenset({"input_too_long", "generation_unavailable",
                             "insufficient_grounding", "empty_translation"})
_ERRORS = {
    "cost_degraded": ("AI 요약을 일시적으로 이용할 수 없습니다.", True),
    "source_unavailable": ("이 요청의 원문을 이용할 수 없습니다.", True),
    "generation_protocol_error": ("처리 결과를 확인할 수 없습니다.", False),
    "generation_failed": ("처리 중 문제가 발생했습니다.", False),
    "generation_outcome_uncertain": (
        "처리 결과를 확인할 수 없습니다. 작업을 다시 실행하지 않습니다.", False,
    ),
    "dispatch_outcome_uncertain": ("요청 전달 결과를 확인할 수 없습니다.", False),
    "dispatch_unavailable": (
        "요청을 전달할 수 없습니다. 같은 요청을 명시적으로 복구할 수 있습니다.", True,
    ),
}


def safe_job_error(category: str) -> JobError:
    message, retryable = _ERRORS.get(category, _ERRORS["generation_failed"])
    code = category if category in _ERRORS else "generation_failed"
    return JobError(code, message, retryable)


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise JobProtocolError("content_invalid")
    return value


def _strings(value: object) -> list[JsonValue]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise JobProtocolError("content_invalid")
    return list(value)


def _summary(value: object) -> dict[str, JsonValue]:
    body = json_object(value)
    out: dict[str, JsonValue] = {name: _text(body.get(name)) for name in _SUMMARY_TEXT}
    out["contributions"] = _strings(body.get("contributions"))
    reproduction = body.get("reproducibility")
    if not isinstance(reproduction, dict) or reproduction.keys() != {"code", "data"}:
        raise JobProtocolError("content_invalid")
    out["reproducibility"] = {name: _text(reproduction[name]) for name in ("code", "data")}
    anchors = body.get("anchors")
    if not isinstance(anchors, list):
        raise JobProtocolError("content_invalid")
    safe_anchors: list[JsonValue] = []
    for raw in anchors:
        anchor = json_object(raw)
        if (not isinstance(anchor.get("target"), str)
                or anchor["target"] not in {"section", "table", "figure"}):
            raise JobProtocolError("content_invalid")
        safe_anchors.append({
            name: _text(anchor.get(name)) for name in ("field", "target", "span", "label")
        })
    out["anchors"] = safe_anchors
    return out


def _document_validation_value(value: JsonValue, context: str = "") -> object:
    """Strict shared model validation shadow; never serialize its normalized output.

    Python-mode validation retains arbitrary JSON strings (including NUL/lone
    surrogates). Convert ONLY the shared enum/date fields for strict Pydantic
    validation; original document strings, optional presence and arrays survive.
    JSON Schema permits no null fields in the bare document.
    """
    if value is None:
        raise JobProtocolError("content_invalid")
    if isinstance(value, list):
        return [_document_validation_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    out = {key: _document_validation_value(item, key) for key, item in value.items()}
    try:
        if context == "provenance":
            out["sourceTier"] = SourceTier(value.get("sourceTier"))
            out["generatedAt"] = rfc3339_instant(value.get("generatedAt"))
        if context == "assetRef":
            out["type"] = Type(value.get("type"))
            if "sourceMode" in value:
                out["sourceMode"] = SourceMode(value["sourceMode"])
    except (ValueError, TypeError) as exc:
        raise JobProtocolError("content_invalid") from exc
    return out


def _translation(value: object, input: JobInput) -> dict[str, JsonValue]:
    body = json_object(value)
    doc = json_object(body.get("docModel"))
    # Bare shared DocModel only: no wrappers, integer/bool coercion or defaults
    # applied to the stored output. Validate; retain the original detached doc.
    try:
        validated = DocModel.model_validate(_document_validation_value(doc), strict=True)
    except ValidationError as exc:
        raise JobProtocolError("content_invalid") from exc
    meta = validated.meta
    if meta.paperId != input.paper_id and meta.paperId != input.paper_id.rsplit("v", 1)[0]:
        raise JobProtocolError("content_identity_invalid")
    if meta.version != input.version:
        raise JobProtocolError("content_identity_invalid")
    out: dict[str, JsonValue] = {"docModel": doc, "keptTerms": _strings(body.get("keptTerms"))}
    if "standardGlossary" in body:
        glossary = body["standardGlossary"]
        if not isinstance(glossary, list):
            raise JobProtocolError("content_invalid")
        safe_glossary: list[JsonValue] = []
        for raw in glossary:
            term = json_object(raw)
            item: dict[str, JsonValue] = {"term": _text(term.get("term"))}
            if "translated" in term:
                item["translated"] = _text(term["translated"])
            safe_glossary.append(item)
        out["standardGlossary"] = safe_glossary
    return out


def final_content(task: JobTask, input: JobInput, raw: object) -> dict[str, JsonValue]:
    body = json_object(raw)
    expected_task = task.pipeline_task.value
    if body.get("status") != "ok" or body.get("task") != expected_task:
        raise JobProtocolError("content_invalid")
    if (task is JobTask.SUMMARIZE and "translation" in body
            or task is JobTask.TRANSLATE and "summary" in body):
        raise JobProtocolError("content_invalid")
    out: dict[str, JsonValue] = {"status": "ok", "task": expected_task}
    if task is JobTask.SUMMARIZE:
        out["summary"] = _summary(body.get("summary"))
    else:
        out["translation"] = _translation(body.get("translation"), input)
    if "cached" in body:
        if type(body["cached"]) is not bool:
            raise JobProtocolError("content_invalid")
        out["cached"] = body["cached"]
    metadata = body.get("meta")
    if isinstance(metadata, dict):
        safe_meta: dict[str, JsonValue] = {}
        if (isinstance(metadata.get("source"), str)
                and metadata["source"] in {"full_text", "abstract"}):
            safe_meta["source"] = metadata["source"]
        if metadata.get("fallback") == "full_text_unavailable":
            safe_meta["fallback"] = metadata["fallback"]
        out["meta"] = safe_meta
    canonical_content(out)
    return out


@dataclass(frozen=True, slots=True)
class PreparationIdentity:
    """Captured private provenance; unavailable means unavailable, not current defaults."""

    input: JobInput = field(repr=False)
    generation: tuple[tuple[str, str], ...] = ()
    personalization: tuple[tuple[str, str], ...] = ()
    source: tuple[tuple[str, str], ...] = ()

    def to_dict(self, digest: str) -> dict[str, JsonValue]:
        out: dict[str, JsonValue] = {"canonicalVersion": CANONICAL_VERSION,
                                   "contentEncoding": CONTENT_ENCODING, "contentDigest": digest,
                                   "input": self.input.to_dict()}
        for name, fields, allowed in (
            ("generation", self.generation, {"modelVersion", "promptVersion"}),
            ("personalization", self.personalization, {"glossaryIdentity", "seedIdentity"}),
            ("source", self.source, {"sourceTier", "parserVersion", "sourceIdentity"}),
        ):
            if len(dict(fields)) != len(fields) or not all(key in allowed for key, _ in fields):
                raise JobProtocolError("provenance_invalid")
            values: dict[str, JsonValue] = {key: identifier(value) for key, value in fields}
            values["status"] = "captured" if fields else "unavailable"
            out[name] = values
        return out


@dataclass(frozen=True, slots=True)
class PreparedJobResult:
    prepared_result_id: str
    job_id: str
    owner_id: str
    task: JobTask
    content_digest: str
    serialized_content: str | None = field(repr=False)
    serialized_identity: str = field(repr=False)
    prepared_at: float
    expires_at: float | None = None
    purged_at: float | None = None
    submitted_level: Persona | None = None
    asset_id: str | None = None
    schema_version: int = 1
    content_encoding: str | None = None
    canonical_version: int | None = None

    def __post_init__(self) -> None:
        for value in (self.prepared_result_id, self.job_id, self.owner_id):
            identifier(value, maximum=64)
        instant(self.prepared_at)
        if self.schema_version != 1 or type(self.schema_version) is not int:
            raise JobProtocolError("result_version_unsupported")
        if (self.content_encoding != CONTENT_ENCODING
                or type(self.canonical_version) is not int
                or self.canonical_version != CANONICAL_VERSION):
            raise JobProtocolError("result_unavailable")
        if not isinstance(self.task, JobTask):
            raise JobProtocolError("result_task_invalid")
        if self.submitted_level is not None and not isinstance(self.submitted_level, Persona):
            raise JobProtocolError("result_metadata_invalid")
        if self.asset_id is not None:
            identifier(self.asset_id)
        if self.expires_at is not None and instant(self.expires_at) <= self.prepared_at:
            raise JobProtocolError("expiry_invalid")
        if (self.purged_at is not None) != (self.serialized_content is None):
            raise JobProtocolError("purge_invalid")
        if self.purged_at is not None:
            if self.expires_at is None or instant(self.purged_at) < self.expires_at:
                raise JobProtocolError("purge_invalid")
        else:
            self.content()

    @classmethod
    def capture(cls, job_id: str, owner_id: str, task: JobTask, raw: object, *,
                result_id: str, prepared_at: float, identity: PreparationIdentity,
                asset_id: str | None = None) -> PreparedJobResult:
        safe = final_content(task, identity.input, raw)
        digest = prepared_content_digest(safe)
        if asset_id is not None:
            identifier(asset_id)
        prepared_at = instant(prepared_at)
        binding = {**identity.to_dict(digest), "jobId": job_id, "ownerId": owner_id,
                   "taskType": task.value, "preparedResultId": result_id, "preparedAt": prepared_at}
        return cls(result_id, job_id, owner_id, task, digest, canonical_content(safe),
                   canonical_content(binding), prepared_at,
                   submitted_level=identity.input.persona, asset_id=asset_id,
                   content_encoding=CONTENT_ENCODING, canonical_version=CANONICAL_VERSION)

    def initialize_expiry(self, expires_at: float) -> PreparedJobResult:
        if self.expires_at is not None and self.expires_at != expires_at:
            raise JobProtocolError("expiry_immutable")
        return replace(self, expires_at=instant(expires_at))

    def purge(self, now: float) -> PreparedJobResult:
        if self.expires_at is None or instant(now) < self.expires_at:
            raise JobProtocolError("purge_not_due")
        if self.purged_at is not None:
            return self
        # No content-derived provenance survives physical payload cleanup.
        return replace(self, serialized_content=None, serialized_identity="{}", purged_at=now)

    def content(self) -> dict[str, JsonValue]:
        """Validate persisted bytes again; a stored wrapper/digest cannot bypass C2."""
        if self.serialized_content is None:
            raise JobProtocolError("result_unavailable")
        try:
            identity = json_object(decode_canonical_content(self.serialized_identity))
            input = JobInput.parse(identity.get("input"), self.task)
            raw = decode_prepared_content(self.serialized_content,
                                          content_encoding=self.content_encoding,
                                          canonical_version=self.canonical_version,
                                          digest=self.content_digest)
            payload = final_content(self.task, input, raw)
            expected = self._preparation_identity(identity, input)
            if (canonical_content(payload) != self.serialized_content or identity != expected
                    or (self.submitted_level is not None
                        and self.submitted_level is not input.persona)):
                raise JobProtocolError("result_unavailable")
            return payload
        except (ValueError, TypeError, RecursionError, JobProtocolError) as exc:
            raise JobProtocolError("result_unavailable") from exc

    def _preparation_identity(self, identity: dict[str, JsonValue], input: JobInput) -> dict:
        groups = []
        for name in ("generation", "personalization", "source"):
            group = json_object(identity.get(name))
            groups.append(tuple((key, value) for key, value in group.items() if key != "status"))
        captured = PreparationIdentity(input, *groups).to_dict(self.content_digest)
        return {**captured, "jobId": self.job_id, "ownerId": self.owner_id,
                "taskType": self.task.value, "preparedResultId": self.prepared_result_id,
                "preparedAt": self.prepared_at}

    def envelope(self, now: float) -> dict[str, JsonValue]:
        if self.expires_at is None:
            raise JobProtocolError("result_not_ready")
        if instant(now) >= self.expires_at:
            raise JobProtocolError("result_expired")
        if self.serialized_content is None:
            raise JobProtocolError("result_unavailable")
        payload = self.content()
        prepared_at = datetime.fromtimestamp(self.prepared_at, UTC).isoformat()
        expires_at = datetime.fromtimestamp(self.expires_at, UTC).isoformat()
        rfc3339_instant(prepared_at)
        rfc3339_instant(expires_at)
        body: dict[str, JsonValue] = {
            "schemaVersion": 1, "jobId": self.job_id, "taskType": self.task.value,
            "preparedAt": prepared_at,
            "expiresAt": expires_at,
            "content": payload,
        }
        if self.submitted_level is not None:
            body["submittedLevel"] = self.submitted_level.value
        if self.asset_id is not None:
            body["assetId"] = self.asset_id
        return {"resultRef": self.prepared_result_id, "preparedResult": body}


class PipelineResponse(Protocol):
    def to_dict(self) -> object: ...


@dataclass(frozen=True, slots=True)
class InspectedOutcome:
    state: JobState
    serialized_content: str | None = field(default=None, repr=False)
    error: JobError | None = None
    abstain_reason: str | None = None


def inspect_outcome(task: JobTask, input: JobInput, response: PipelineResponse) -> InspectedOutcome:
    """Returned DTO alone never means successful content; failures use safe categories."""
    try:
        body = json_object(response.to_dict())
        status = body.get("status")
        if not isinstance(status, str):
            raise JobProtocolError("content_invalid")
        if status == "abstain":
            reason = body.get("reason")
            safe_reason = (
                reason if isinstance(reason, str) and reason in _ABSTAIN_REASONS
                else "generation_abstained"
            )
            return InspectedOutcome(JobState.ABSTAINED, abstain_reason=safe_reason)
        if status in {"cost_degraded", "source_unavailable"}:
            return InspectedOutcome(JobState.FAILED, error=safe_job_error(str(status)))
        payload = final_content(task, input, body)
        return InspectedOutcome(JobState.COMPLETED, serialized_content=canonical_content(payload))
    except JobProtocolError:
        return InspectedOutcome(JobState.FAILED, error=safe_job_error("generation_protocol_error"))
    except Exception:  # Integration boundary: serialization failure must not leak raw output.
        return InspectedOutcome(JobState.FAILED, error=safe_job_error("generation_failed"))
