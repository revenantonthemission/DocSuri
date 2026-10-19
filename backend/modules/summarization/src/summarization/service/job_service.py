"""ContentJobService — the job contract's behavior, above the store.

REM-2 corrective, Phase 5 (items 20–26). The store decides *what exists*; this decides *what is
allowed*, and it is the layer that keeps three promises the queue-only design could not:

1. **Acceptance is durable and reported honestly** (RJ-AC01). The job row is written first, the
   work is dispatched second, and the state the caller receives reflects what actually happened —
   ``ACCEPTED`` only if the dispatch succeeded, ``FAILED`` (retryable) if it did not.
2. **A retry is a lookup, not a second job** (RJ-AC06). The idempotency key is resolved inside the
   store's atomic ``accept``, so two concurrent retries produce one job. A *failed* job does not
   consume the key, because a caller retrying a dispatch failure must not be permanently poisoned.
3. **Every boundary re-checks the caller** (RJ-AC05). Not-yours and does-not-exist are the same
   ``None``, so the job id is a lookup handle and never an existence oracle for another tenant.
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from ..domain.job import ContentJob, JobError, JobEvent, JobState
from ..domain.models import RequestContext
from ..ports.ports import JobStorePort

log = logging.getLogger(__name__)

#: Every state after ACCEPTED is entered by exactly one worker-side edge, which is what the
#: compare-and-set guards below name. A redelivered message therefore finds no legal source state
#: and returns ``None`` instead of re-running work.
_SUBMITTED_ONLY = frozenset({JobState.SUBMITTED})
_ACCEPTED_ONLY = _SUBMITTED_ONLY
_QUEUED_ONLY = frozenset({JobState.ACCEPTED})
_RUNNING_ONLY = frozenset({JobState.QUEUED})
_NOT_RUNNING = frozenset({JobState.QUEUED, JobState.RUNNING})
_RUNNING_ONLY_STATE = frozenset({JobState.RUNNING})

#: Effect names for the ND-Q8 ledger. One per externally-observable, money-spending step, so a
#: redelivery after a crash re-attempts only what did not happen.
EFFECT_GENERATE = "generate"

#: History page size when resolving a stream cursor; a job's log is short, so usually one read.
_CURSOR_PAGE_LIMIT = 100
#: The seq part of a legacy ``"<job>:<seq>"`` cursor (seq is bounded to 2**53 - 1 in storage).
_LEGACY_SEQ = re.compile(r"[0-9]{1,16}")


def _legacy_seq(job_id: str, cursor: str) -> int | None:
    """The seq of a ``"<job_id>:<seq>"`` cursor for *this* job, or None for any other shape."""
    prefix = f"{job_id}:"
    if not cursor.startswith(prefix):
        return None
    digits = cursor[len(prefix) :]
    return int(digits) if _LEGACY_SEQ.fullmatch(digits) else None


class SubmitOutcome:
    """What the caller is told after submitting — and nothing more.

    ``deduplicated`` is internal bookkeeping for the retry path (it distinguishes "you just created
    this" from "this already existed, here it is"), not a field the API serializes.
    """

    __slots__ = ("job_id", "state", "deduplicated", "error")

    def __init__(
        self,
        job_id: str,
        state: JobState,
        *,
        deduplicated: bool = False,
        error: JobError | None = None,
    ) -> None:
        self.job_id = job_id
        self.state = state
        self.deduplicated = deduplicated
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"jobId": self.job_id, "state": self.state.value}
        if self.error is not None:
            out["error"] = self.error.to_dict()
        return out


class ContentJobService:
    def __init__(
        self,
        *,
        store: JobStorePort,
        enqueue: Callable[[ContentJob], None],
        result_ttl_seconds: float = 3600.0,
        now: Callable[[], float] | None = None,
    ) -> None:
        self._store = store
        self._enqueue = enqueue
        self._result_ttl = result_ttl_seconds
        self._now = now or time.time

    # --- submission (items 20, 21 / RJ-AC01, RJ-AC06) --------------------------------------

    def submit(
        self,
        ctx: RequestContext,
        task_type: str,
        input: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> SubmitOutcome:
        """Accept one unit of work, durably and idempotently.

        Order matters: the row exists *before* the dispatch, so a dispatch that dies leaves a
        record that says so instead of leaving the caller polling a phantom. The state the caller
        receives is the honest one — ``ACCEPTED`` only when the dispatch went out.
        """
        user_id = _principal(ctx)
        if not user_id:
            # SEC-8: refuse before writing anything, so an anonymous request cannot leave a row a
            # later authenticated request could claim or enumerate.
            raise PermissionError("no principal")

        now = self._now()
        job, created = self._store.accept(
            job_id=f"job-{uuid4().hex}",
            owner_id=user_id,
            task_type=task_type,
            input=input,
            idempotency_key=idempotency_key,
            now=now,
        )
        if not created:
            # The retry of a submission whose response was lost. The job already exists; re-enqueue
            # only if it never got dispatched (a dispatch that failed before the caller retried).
            if job.state is JobState.SUBMITTED:
                return self._dispatch(job, retry_of_failed_dispatch=True)
            return SubmitOutcome(job.job_id, job.state, deduplicated=True)

        return self._dispatch(job)

    def _dispatch(
        self, job: ContentJob, *, retry_of_failed_dispatch: bool = False
    ) -> SubmitOutcome:
        now = self._now()
        try:
            self._enqueue(job)
        except Exception as exc:  # noqa: BLE001 — any dispatch failure must be reported, not raised
            # RJ-AC01: do not report ACCEPTED for work that was never handed off. The failure is
            # retryable on purpose, and the idempotency key is deliberately not burned: a caller
            # retrying must be able to get a fresh job rather than being stuck with this failure.
            log.warning("content job dispatch failed (%s): %s", job.job_id, exc)
            # The key bound to work that was never accepted; free it so the caller's retry can
            # proceed instead of being handed this failure forever.
            self._store.release_idempotency(job.owner_id, job.idempotency_key, job.job_id)
            failed = self._store.transition(
                job.job_id,
                JobState.FAILED,
                expect_from=(
                    _ACCEPTED_ONLY if not retry_of_failed_dispatch else _SUBMITTED_ONLY
                ),
                now=now,
                error=JobError(
                    error_type="dispatch_unavailable",
                    message="요청을 처리하기 어렵습니다. 잠시 후 다시 시도해 주세요.",
                    retryable=True,
                    retry_after_seconds=5,
                ),  # noqa: E501
            )
            state = failed.state if failed is not None else job.state
            return SubmitOutcome(job.job_id, state)

        accepted = self._store.transition(
            job.job_id, JobState.ACCEPTED, expect_from=_ACCEPTED_ONLY, now=now
        )
        if accepted is None:
            # Another actor moved the job between accept() and here (a concurrent retry won). The
            # work is queued once; report whatever is durably true rather than assuming success.
            current = self._store.get(job.job_id) or job
            return SubmitOutcome(current.job_id, current.state, deduplicated=True)
        return SubmitOutcome(accepted.job_id, accepted.state)

    # --- authorization (item 23 / RJ-AC05) --------------------------------------------------

    def _owned(self, ctx: RequestContext, job_id: str) -> ContentJob | None:
        """The job if *this* caller owns it, else ``None`` — and ``None`` also for "no such job".

        One return type for both cases is the point: a caller must not be able to tell another
        tenant's job from a job that does not exist.
        """
        user_id = _principal(ctx)
        if not user_id:
            return None
        job = self._store.get(job_id)
        if job is None or job.owner_id != user_id:
            return None
        return job

    def state_of(self, ctx: RequestContext, job_id: str) -> ContentJob | None:
        """The caller's job state. A read — it creates nothing and enqueues nothing (RJ-AC02)."""
        return self._owned(ctx, job_id)

    def events(
        self, ctx: RequestContext, job_id: str, *, after_seq: int = 0, limit: int = 500
    ) -> list[JobEvent]:
        """The caller's job history, resumable from ``after_seq`` (RJ-AC02/RJ-AC04)."""
        if self._owned(ctx, job_id) is None:
            return []
        return self._store.list_events(job_id, after_seq=after_seq, limit=limit)

    def resume_seq(self, ctx: RequestContext, job_id: str, cursor: str | None) -> int:
        """The per-job ``seq`` a stream cursor names, resolved through the caller's own history.

        The cursor is the SSE ``id:`` the stream sent: the store's opaque ``event_id`` (a global
        id in RdsJobStore, ``"<job>:<seq>"`` in the in-memory store), never a value to cast to a
        seq. The legacy ``"<job>:<seq>"`` form still resolves when that seq is in this job's
        history. Anything else (unknown, another job's, malformed) resumes from 0: a full replay,
        which the client de-duplicates by ``eventId``.
        """
        if not cursor:
            return 0
        legacy = _legacy_seq(job_id, cursor)
        after = 0
        while True:
            page = self.events(ctx, job_id, after_seq=after, limit=_CURSOR_PAGE_LIMIT)
            for event in page:
                if event.event_id == cursor or event.seq == legacy:
                    return event.seq
            if len(page) < _CURSOR_PAGE_LIMIT or page[-1].seq <= after:
                return 0
            after = page[-1].seq

    # --- worker-side progression ------------------------------------------------------------

    # The worker-side edges re-check ownership too (item 23): "the worker authenticated" is not the
    # same claim as "this caller may drive this job", and a message replayed with another owner's
    # context must not advance a job it does not own.

    def mark_queued(self, ctx: RequestContext, job_id: str) -> ContentJob | None:
        if self._owned(ctx, job_id) is None:
            return None
        return self._store.transition(
            job_id, JobState.QUEUED, expect_from=_QUEUED_ONLY, now=self._now()
        )

    def mark_running(self, ctx: RequestContext, job_id: str) -> ContentJob | None:
        if self._owned(ctx, job_id) is None:
            return None
        return self._store.transition(
            job_id, JobState.RUNNING, expect_from=_RUNNING_ONLY, now=self._now()
        )

    def mark_completed(
        self, ctx: RequestContext, job_id: str, *, result_ref: str | None = None
    ) -> ContentJob | None:
        """Finish successfully and record where the prepared result lives (item 24).

        The expiry is set here, not read from a config default at delivery time, so the window is
        the one that was true when the work finished.
        """
        if self._owned(ctx, job_id) is None:
            return None
        now = self._now()
        job = self._store.transition(
            job_id,
            JobState.COMPLETED,
            expect_from=_RUNNING_ONLY_STATE,
            now=now,
            result_ref=result_ref,
            result_expires_at=now + self._result_ttl if result_ref is not None else None,
            payload={"resultReady": True} if result_ref is not None else {},
        )
        return job

    def mark_abstained(
        self, ctx: RequestContext, job_id: str, *, reason: str
    ) -> ContentJob | None:
        """A domain abstention: a real answer, not a failure and not a success (RJ-AC03)."""
        if self._owned(ctx, job_id) is None:
            return None
        return self._store.transition(
            job_id,
            JobState.ABSTAINED,
            expect_from=_NOT_RUNNING,
            now=self._now(),
            abstain_reason=reason,
        )

    def mark_failed(
        self, ctx: RequestContext, job_id: str, *, error: JobError
    ) -> ContentJob | None:
        """A terminal failure, reported without internal detail (SEC-15)."""
        if self._owned(ctx, job_id) is None:
            return None
        return self._store.transition(
            job_id,
            JobState.FAILED,
            expect_from=_NOT_RUNNING,
            now=self._now(),
            error=error,
        )

    # --- delivery (items 24, 26 / RJ-AC07, RJ-AC08) -----------------------------------------

    def result_ref(self, ctx: RequestContext, job_id: str) -> str | None:
        """Where this caller's prepared result lives, or ``None``.

        Direct authorized delivery: no new job is created to fetch a job's result, and nothing
        outside this origin is handed back (RJ-AC08). An expired result is not delivered at all —
        the job store must not become an unbounded read path around the result TTL (RJ-AC07).
        """
        job = self._owned(ctx, job_id)
        if job is None or job.state is not JobState.COMPLETED or not job.result_ref:
            return None
        expires_at = job.result_expires_at
        if expires_at is not None and self._now() > expires_at:
            return None
        return job.result_ref

    # --- effects (item 25 / ND-Q8) ------------------------------------------------------------

    def claim_effect(self, job_id: str, attempt: int, effect: str = EFFECT_GENERATE) -> bool:
        """Claim ``(job_id, attempt, effect)`` before doing it. False when already claimed."""
        return self._store.claim_effect(job_id, attempt, effect)

    def release_effect(self, job_id: str, attempt: int) -> None:
        self._store.release_effect(job_id, attempt)


def _principal(ctx: RequestContext) -> str | None:
    """The authenticated caller id, or ``None`` (SEC-8)."""
    return getattr(getattr(ctx, "auth_session", None), "user_id", None)