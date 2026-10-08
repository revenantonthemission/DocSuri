"""C1/C6/C7 value types, without a queue, database or generation dependency.

These values describe authority; constructing one never grants a send/invocation.
The store must commit and recheck T1–T8 before returning an execution capability.
Legacy records remain unversioned unless accepted through a *new* T1 operation.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from enum import StrEnum

from .job import ContentJob, JobContractError, JobState
from .models import Persona, Scope, SummaryRequest, TargetLang, Task

# Implicit alias retains standalone Python 3.11 compatibility (PEP 695 needs 3.12).
JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
MAX_SAFE_SEQUENCE = 9_007_199_254_740_991
AUTHORITY_VERSION = 1
_INPUT_FIELDS = frozenset({"paperId", "version", "targetLang", "persona", "scope"})
_HEX_DIGEST = re.compile(r"[a-f0-9]{64}\Z")


class JobProtocolError(JobContractError):
    """Safe category only: never interpolate a body, provider error or credential."""


def identifier(value: object, *, maximum: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise JobProtocolError("identifier_invalid")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise JobProtocolError("identifier_invalid")
    if maximum is not None and len(value) > maximum:
        raise JobProtocolError("identifier_invalid")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise JobProtocolError("identifier_invalid") from exc
    return value


def sequence(value: object, *, minimum: int = 0) -> int:
    # bool and numeric strings are not JSON integer identities.
    if type(value) is not int or not minimum <= value <= MAX_SAFE_SEQUENCE:
        raise JobProtocolError("sequence_invalid")
    return value


def instant(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise JobProtocolError("instant_invalid")
    try:
        datetime.fromtimestamp(value, UTC)
    except (ValueError, OverflowError, OSError) as exc:
        raise JobProtocolError("instant_invalid") from exc
    return float(value)


_RFC3339 = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})[Tt]([0-9]{2}):([0-9]{2}):([0-9]{2})"
    r"(?:\.([0-9]+))?([Zz]|[+-][0-9]{2}:[0-9]{2})\Z"
)
_LEAP_DAYS = frozenset({
    "1972-06-30", "1972-12-31", "1973-12-31", "1974-12-31", "1975-12-31",
    "1976-12-31", "1977-12-31", "1978-12-31", "1979-12-31", "1981-06-30",
    "1982-06-30", "1983-06-30", "1985-06-30", "1987-12-31", "1989-12-31",
    "1990-12-31", "1992-06-30", "1993-06-30", "1994-06-30", "1995-12-31",
    "1997-06-30", "1998-12-31", "2005-12-31", "2008-12-31", "2012-06-30",
    "2015-06-30", "2016-12-31",
})


def _parse_rfc3339(value: object) -> datetime:
    if not isinstance(value, str) or not (match := _RFC3339.fullmatch(value)):
        raise ValueError("timestamp_invalid")
    year, month, day, hour, minute, second = map(int, match.groups()[:6])
    fraction, zone = match.groups()[6:]
    offset = 0
    if zone not in {"Z", "z"}:
        hours, minutes = int(zone[1:3]), int(zone[4:6])
        if hours > 23 or minutes > 59:
            raise ValueError("timestamp_invalid")
        offset = (hours * 60 + minutes) * (1 if zone[0] == "+" else -1)
    result = datetime(year, month, day, hour, minute, min(second, 59),
                      int((fraction or "0")[:6].ljust(6, "0")),
                      timezone(timedelta(minutes=offset)))
    if second > 59:
        utc = result.astimezone(UTC)
        if (second != 60 or (utc.hour, utc.minute) != (23, 59)
                or utc.date().isoformat() not in _LEAP_DAYS):
            raise ValueError("timestamp_invalid")
        result += timedelta(seconds=1)
    return result


# An active checker, not a schema annotation or permissive parser. Kept explicit
# so qualification tests can prove that absent/nonchecking support fails closed.
TIMESTAMP_CHECKER: Callable[[object], datetime] | None = _parse_rfc3339


def require_timestamp_checker() -> Callable[[object], datetime]:
    checker = TIMESTAMP_CHECKER
    if not callable(checker):
        raise JobProtocolError("timestamp_checker_unavailable")
    try:
        checked = checker("2024-02-29T00:00:00Z")
        if not isinstance(checked, datetime) or checked.utcoffset() is None:
            raise JobProtocolError("timestamp_checker_unavailable")
        try:
            checker("2026-02-30T00:00:00Z")
        except (ValueError, TypeError, OverflowError):
            return checker
    except (ValueError, TypeError, OverflowError) as exc:
        raise JobProtocolError("timestamp_checker_unavailable") from exc
    raise JobProtocolError("timestamp_checker_unavailable")


def rfc3339_instant(value: object) -> datetime:
    """Validate calendar/time/offset; callers retain the original content string."""
    checker = require_timestamp_checker()
    try:
        result = checker(value)
        if not isinstance(result, datetime) or result.utcoffset() is None:
            raise ValueError("timestamp_invalid")
        return result
    except (ValueError, TypeError, OverflowError) as exc:
        raise JobProtocolError("timestamp_invalid") from exc


def json_value(value: object) -> JsonValue:
    """Detach JSON at a trust boundary; reject coercion and nonfinite numbers."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, list):
        return [json_value(item) for item in value]
    if isinstance(value, dict) and all(type(key) is str for key in value):
        return {key: json_value(item) for key, item in value.items()}
    raise JobProtocolError("payload_invalid")


def json_object(value: object) -> dict[str, JsonValue]:
    try:
        detached = json_value(value)
    except RecursionError as exc:
        raise JobProtocolError("payload_invalid") from exc
    if not isinstance(detached, dict):
        raise JobProtocolError("payload_invalid")
    return detached


def canonical_json(value: object) -> str:
    """Private canonical-json-v1: sorted keys; unchanged arrays, strings and numbers.

    This is NOT the browser's owner-prefixed JSON.stringify request hash. Surrogate
    code points, unsupported values and nonfinite numbers cannot enter UTF-8 storage.
    """
    try:
        encoded = json.dumps(json_value(value), sort_keys=True, ensure_ascii=False,
                             allow_nan=False, separators=(",", ":"))
        encoded.encode("utf-8")
        return encoded
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise JobProtocolError("payload_invalid") from exc


def content_digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class JobTask(StrEnum):
    SUMMARIZE = "summarize"
    TRANSLATE = "translate"

    @property
    def pipeline_task(self) -> Task:
        return Task.SUMMARY if self is JobTask.SUMMARIZE else Task.TRANSLATE


@dataclass(frozen=True, slots=True)
class JobInput:
    paper_id: str
    version: int
    target_lang: TargetLang
    persona: Persona
    scope: Scope

    def __post_init__(self) -> None:
        identifier(self.paper_id)
        sequence(self.version, minimum=1)
        if not (isinstance(self.target_lang, TargetLang) and isinstance(self.persona, Persona)
                and isinstance(self.scope, Scope)):
            raise JobProtocolError("input_invalid")

    def to_dict(self) -> dict[str, JsonValue]:
        return {"paperId": self.paper_id, "version": self.version,
                "targetLang": self.target_lang.value, "persona": self.persona.value,
                "scope": self.scope.value}

    def request(self, task: JobTask) -> SummaryRequest:
        return SummaryRequest(paper_id=self.paper_id, version=self.version,
                              task=task.pipeline_task, target_lang=self.target_lang,
                              persona=self.persona, scope=self.scope, abstract=None)

    @classmethod
    def parse(cls, raw: object, task: JobTask, *, legacy: bool = False) -> JobInput:
        body = json_object(raw)
        allowed = _INPUT_FIELDS | {"abstract"} if legacy else _INPUT_FIELDS
        if not body.keys() <= allowed or (not legacy and body.keys() != _INPUT_FIELDS):
            raise JobProtocolError("input_invalid")
        paper = identifier(body.get("paperId"))
        _, sep, suffix = paper.rpartition("v")
        default_version = int(suffix) if sep and suffix.isdecimal() else 1
        version = sequence(body.get("version", default_version), minimum=1)
        try:
            lang = TargetLang(body.get("targetLang", "ko"))
            persona = Persona(body.get("persona", "expert"))
            scope = Scope(body.get("scope", "abstract" if legacy else "full"))
        except (ValueError, TypeError) as exc:
            raise JobProtocolError("input_invalid") from exc
        if task is JobTask.SUMMARIZE:
            if not legacy and scope is not Scope.FULL:
                raise JobProtocolError("input_invalid")
            scope = Scope.FULL  # The established summary pipeline always uses full scope.
        return cls(paper, version, lang, persona, scope)


@dataclass(frozen=True, slots=True)
class JobSubmission:
    task: JobTask
    input: JobInput = field(repr=False)
    idempotency_key: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.task, JobTask) or not isinstance(self.input, JobInput):
            raise JobProtocolError("input_invalid")
        if self.task is JobTask.SUMMARIZE and self.input.scope is not Scope.FULL:
            raise JobProtocolError("input_invalid")
        if self.idempotency_key is not None:
            identifier(self.idempotency_key, maximum=128)

    @property
    def input_identity(self) -> str:
        # New keyless calls still get independent jobs; this integrity identity
        # is never a synthesized idempotency key or an authentication fact.
        return content_digest({"schemaVersion": 1, "taskType": self.task.value,
                               "input": self.input.to_dict()})

    @classmethod
    def browser(cls, raw: object) -> JobSubmission:
        body = json_object(raw)
        if body.keys() != {"taskType", "input", "idempotencyKey"}:
            raise JobProtocolError("input_invalid")
        key = body["idempotencyKey"]
        if not isinstance(key, str) or not _HEX_DIGEST.fullmatch(key):
            raise JobProtocolError("key_invalid")
        task = _task(body["taskType"])
        return cls(task, JobInput.parse(body["input"], task), key)

    @classmethod
    def legacy(cls, task_type: object, raw: object, key: object = None) -> JobSubmission:
        task = _task("summarize" if task_type == "summary" else task_type)
        normalized_key = None if key is None else identifier(key, maximum=128)
        return cls(task, JobInput.parse(raw, task, legacy=True), normalized_key)


def _task(value: object) -> JobTask:
    try:
        return JobTask(value)
    except (ValueError, TypeError) as exc:
        raise JobProtocolError("task_unsupported") from exc


class DispatchOutcome(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    SENDING = "SENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class SubmissionBinding:
    binding_id: str
    job_id: str
    owner_id: str
    dispatch_id: str
    input_identity: str
    idempotency_key: str | None = field(default=None, repr=False)
    outcome: DispatchOutcome = DispatchOutcome.NOT_STARTED
    fence: int = 0
    started_at: float | None = None
    released_at: float | None = None
    queue_message_id: str | None = None

    def __post_init__(self) -> None:
        for value in (self.binding_id, self.job_id, self.owner_id, self.dispatch_id):
            identifier(value, maximum=64)
        if (not isinstance(self.input_identity, str)
                or not _HEX_DIGEST.fullmatch(self.input_identity)):
            raise JobProtocolError("identity_invalid")
        sequence(self.fence)
        if not isinstance(self.outcome, DispatchOutcome):
            raise JobProtocolError("dispatch_invalid")
        if self.idempotency_key is not None:
            identifier(self.idempotency_key, maximum=128)
        if self.outcome is DispatchOutcome.NOT_STARTED:
            if self.fence != 0 or self.started_at is not None:
                raise JobProtocolError("dispatch_invalid")
        elif self.outcome is not DispatchOutcome.REJECTED:
            if self.fence == 0 or self.started_at is None:
                raise JobProtocolError("dispatch_invalid")
        elif (self.fence == 0) != (self.started_at is None):
            raise JobProtocolError("dispatch_invalid")
        if self.started_at is not None:
            instant(self.started_at)
        if self.released_at is not None:
            instant(self.released_at)
        if (self.released_at is not None) != (self.outcome is DispatchOutcome.REJECTED):
            raise JobProtocolError("dispatch_release_invalid")
        if self.queue_message_id is not None:
            identifier(self.queue_message_id)

    @property
    def retained(self) -> bool:
        return self.released_at is None


class EffectStatus(StrEnum):
    INTENT = "INTENT"
    PREPARED = "PREPARED"
    TERMINAL = "TERMINAL"


@dataclass(frozen=True, slots=True)
class GenerationEffect:
    job_id: str
    fence: int
    worker_id: str
    lease_until: float
    intent_at: float
    status: EffectStatus = EffectStatus.INTENT
    prepared_result_id: str | None = None
    attempt: int = 1
    effect: str = "generate"

    def __post_init__(self) -> None:
        identifier(self.job_id, maximum=64)
        identifier(self.worker_id)
        sequence(self.fence, minimum=1)
        instant(self.intent_at)
        instant(self.lease_until)
        if self.attempt != 1 or type(self.attempt) is not int or self.effect != "generate":
            raise JobProtocolError("effect_invalid")
        if self.lease_until <= self.intent_at or not isinstance(self.status, EffectStatus):
            raise JobProtocolError("effect_invalid")
        if self.prepared_result_id is not None:
            identifier(self.prepared_result_id, maximum=64)
        if self.status is EffectStatus.PREPARED and self.prepared_result_id is None:
            raise JobProtocolError("prepared_binding_required")


@dataclass(frozen=True, slots=True)
class DispatchMessage:
    job_id: str
    dispatch_id: str

    def __post_init__(self) -> None:
        identifier(self.job_id, maximum=64)
        identifier(self.dispatch_id, maximum=64)

    def to_dict(self) -> dict[str, JsonValue]:
        return {"schemaVersion": 1, "jobId": self.job_id, "dispatchId": self.dispatch_id}

    @classmethod
    def parse(cls, raw: object) -> DispatchMessage:
        body = json_object(raw)
        if type(body.get("schemaVersion")) is not int or body["schemaVersion"] != 1:
            raise JobProtocolError("queue_version_unsupported")
        # Additive fields are not authority: owner/input always come from the job.
        return cls(identifier(body.get("jobId"), maximum=64),
                   identifier(body.get("dispatchId"), maximum=64))


class ClaimDisposition(StrEnum):
    ACTIVE = "active_with_fence"
    DEFER = "defer"
    TERMINAL = "terminal"
    RECONCILE = "reconciliation_required"
    QUARANTINE = "quarantine"


@dataclass(frozen=True, slots=True)
class ExecutionClaim:
    disposition: ClaimDisposition
    job: ContentJob | None = None
    effect: GenerationEffect | None = None

    def __post_init__(self) -> None:
        if self.disposition is not ClaimDisposition.ACTIVE:
            return
        if (self.job is None or self.effect is None or self.job.state is not JobState.RUNNING
                or self.job.authority_version != 1 or self.effect.job_id != self.job.job_id
                or self.effect.status is not EffectStatus.INTENT):
            raise JobProtocolError("execution_grant_invalid")


class MaintenanceClass(StrEnum):
    FIRST_DISPATCH = "first_dispatch"
    AMBIGUOUS_DISPATCH = "ambiguous_dispatch"
    EXPIRED_EXECUTION = "expired_execution"
    CLEANUP = "cleanup"


@dataclass(frozen=True, slots=True)
class MaintenanceProgress:
    environment: str
    eligibility: MaintenanceClass
    cycle_id: str
    cutoff: float
    last_job_id: str | None = None
    last_eligible_at: float | None = None
    processed: int = 0
    last_success_at: float | None = None

    def __post_init__(self) -> None:
        for value in (self.environment, self.cycle_id):
            identifier(value)
        instant(self.cutoff)
        sequence(self.processed)
        if (self.last_job_id is None) != (self.last_eligible_at is None):
            raise JobProtocolError("progress_cursor_invalid")
        if self.last_job_id is not None:
            identifier(self.last_job_id, maximum=64)
            instant(self.last_eligible_at)
        if self.last_success_at is not None:
            instant(self.last_success_at)
