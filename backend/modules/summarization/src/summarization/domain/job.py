"""Content-job domain: the durable job record, its state machine, and its event log.

REM-2 corrective, Phase 5 (job contract RJ-AC01–08, AC12).

Why this exists at all: before it, "submit a long summary" was fire-and-forget. The API enqueued
an SQS message, answered ``pending``, and if the enqueue or the worker died the work was simply
gone — the client was told to poll something that never existed. There was no job id, no state, no
history, and no way to answer "did you actually receive my request?" (RJ-AC01). A retry after a
lost response started a *second* billable job (RJ-AC06).

The invariants encoded here are the ones a caller can feel:

* **Acceptance is durable before it is reported.** A job row exists before the caller is told the
  work was accepted, so a lost response is a duplicate *lookup*, not a duplicate job.
* **A state can only move forward along declared edges** (:data:`TRANSITIONS`). A worker that
  redelivers an old message cannot walk a finished job backwards into ``running`` and re-bill it.
* **Every state change is an event with a monotonic per-job sequence**, which is what makes SSE
  reconnection resumable (RJ-AC04): the client replays ``Last-Event-ID`` and gets the gap, not the
  whole log or a hole.
* **Terminal is terminal.** ``completed``/``failed``/``abstained`` have no outgoing edge, so the
  user's final state cannot be overwritten by a late message.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any


class JobState(StrEnum):
    """The declared lifecycle (plan item 20).

    ``SUBMITTED`` is the durable receipt, ``ACCEPTED`` means the request passed validation and was
    committed to the queue, ``QUEUED`` means a worker holds it, ``RUNNING`` means the effect is
    executing, and the three terminal states are the outcomes a caller can act on. The domain
    abstentions (``abstained``) stay distinct from ``failed`` on purpose (RJ-AC03): "we chose not
    to" and "it broke" are different messages to a user, and a known abstention must never be
    reported as an empty success.
    """

    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABSTAINED = "ABSTAINED"


TERMINAL_STATES: frozenset[JobState] = frozenset(
    {JobState.COMPLETED, JobState.FAILED, JobState.ABSTAINED}
)

#: The only legal forward moves. Anything not listed here is a bug or a stale duplicate delivery,
#: and :func:`can_transition` refuses it. Note there is no edge *out of* a terminal state, and no
#: edge from ``RUNNING`` back to ``QUEUED`` — a redelivered message must not restart finished work.
TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.SUBMITTED: frozenset({JobState.ACCEPTED, JobState.FAILED}),
    JobState.ACCEPTED: frozenset({JobState.QUEUED, JobState.FAILED}),
    JobState.QUEUED: frozenset({JobState.RUNNING, JobState.FAILED}),
    JobState.RUNNING: frozenset(
        {JobState.COMPLETED, JobState.FAILED, JobState.ABSTAINED}
    ),
    JobState.COMPLETED: frozenset(),
    JobState.FAILED: frozenset(),
    JobState.ABSTAINED: frozenset(),
}


class JobContractError(Exception):
    """A job transition or mutation that the contract does not allow.

    Raised rather than silently ignored because a caller-visible no-op here means duplicated LLM
    spend (RJ-AC06) or a finished job being resurrected.
    """


def can_transition(current: JobState, target: JobState) -> bool:
    return target in TRANSITIONS[current]


@dataclass(frozen=True, slots=True)
class JobError:
    """A terminal failure, expressed for a human (RJ-AC03) without leaking internals (SEC-15)."""

    error_type: str
    message: str
    retryable: bool
    retry_after_seconds: int | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "errorType": self.error_type,
            "message": self.message,
            "retryable": self.retryable,
        }
        if self.retry_after_seconds is not None:
            out["retryAfterSeconds"] = self.retry_after_seconds
        return out

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> JobError:
        return cls(
            error_type=str(raw.get("errorType") or raw.get("error_type") or "unknown"),
            message=str(raw.get("message") or "처리 중 문제가 발생했습니다."),
            retryable=bool(raw.get("retryable", False)),
            retry_after_seconds=raw.get("retryAfterSeconds") or raw.get("retry_after_seconds"),
        )


@dataclass(frozen=True, slots=True)
class ContentJob:
    """The durable record of one unit of accepted work.

    ``owner_id`` is the authorization subject (item 23): every read and every state change re-checks
    it, so a job id is a lookup handle and never a capability. ``idempotency_key`` is unique per
    owner, which is how a lost response becomes a lookup instead of a second job (item 21).
    """

    job_id: str
    owner_id: str
    task_type: str
    state: JobState
    input: dict[str, Any] = field(repr=False)
    idempotency_key: str | None = None
    result_ref: str | None = None
    result_expires_at: float | None = None
    attempt: int = 1
    error: JobError | None = None
    abstain_reason: str | None = None
    created_at: float = 0.0
    updated_at: float = 0.0
    #: How many state changes this job has recorded. The durable store owns this number and hands
    #: it back on every transition, so an event written in the same transaction as the state change
    #: can be stamped with the sequence that change consumed.
    seq: int = 0
    # Absent on legacy rows. Absence is NOT evidence of execution eligibility.
    authority_version: int | None = None
    input_identity: str | None = field(default=None, repr=False)
    prepared_result_id: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    def assert_transition(self, target: JobState) -> None:
        if not can_transition(self.state, target):
            raise JobContractError(f"illegal job transition {self.state.value} -> {target.value}")

    def transitioned(
        self,
        target: JobState,
        *,
        now: float,
        **changes: Any,
    ) -> ContentJob:
        """Return the next state of this job, refusing an undeclared move.

        The transition is validated here as well as in the store, so a caller that holds a stale
        in-memory copy cannot write an illegal edge over a fresh one.
        """
        self.assert_transition(target)
        return replace(self, state=target, updated_at=now, **changes)


@dataclass(frozen=True, slots=True)
class JobEvent:
    """One durable entry in a job's history.

    ``seq`` is monotonic per job; ``event_id`` is an opaque job-owned replay cursor.
    Resolve a cursor through authorized history, never by casting it to ``seq``.
    """

    seq: int
    event_id: str
    job_id: str
    owner_id: str
    state: JobState
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "eventId": self.event_id,
            "jobId": self.job_id,
            "seq": self.seq,
            "state": self.state.value,
            "timestampUs": int(self.created_at * 1_000_000),
        }
        if self.payload:
            out["payload"] = self.payload
        return out


def payload_for_state(
    job: ContentJob, *, asset_id: str | None = None, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    """The caller-visible payload for a job state (RJ-AC03: keep the domain meaning).

    Abstention and failure carry their reason so the UI can distinguish "we declined" from "it
    broke" and from "here are zero results" (RJ-AC03) — an empty result set and a known
    degradation must never render as the same successful state.
    """
    payload: dict[str, Any] = {}
    if asset_id:
        payload["assetId"] = asset_id
    if job.error is not None:
        payload["error"] = job.error.to_dict()
    if job.abstain_reason:
        payload["abstainReason"] = job.abstain_reason
    if extra:
        payload.update(extra)
    return payload


def job_state_payload(job: ContentJob) -> dict[str, Any]:
    """The caller-visible state snapshot (``GET /state``).

    Deliberately excludes ``input`` and ``owner_id``: the caller supplied the input, but echoing it
    back on a status read is a needless way to leak one caller's payload into a log or a shared
    screen, and the owner is an authorization fact, not response data.
    """
    out: dict[str, Any] = {"jobId": job.job_id, "state": job.state.value, "seq": job.seq}
    if job.error is not None:
        out["error"] = job.error.to_dict()
    if job.abstain_reason:
        out["abstainReason"] = job.abstain_reason
    if job.result_ref and job.result_expires_at is not None:
        out["resultReady"] = True
    return out
