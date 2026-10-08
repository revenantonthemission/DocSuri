"""InMemoryJobStore — a complete ``JobStorePort`` with no external dependency.

Used by the mock/preview wiring and by the tests that assert the *contract* (state machine,
idempotency, ledger, event replay) without a database in the way. The contract lives here, not in
the SQL adapter: ``RdsJobStore`` is a persistence translation of these rules, so a divergence
between the two shows up as a contract test failing against the SQL adapter rather than as a
production-only bug.

Thread safety is real rather than decorative — the worker consumer threads and the API thread share
one instance, and an unlocked check-then-act is exactly how two submissions become two jobs.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any

from ..domain.job import (
    ContentJob,
    JobError,
    JobEvent,
    JobState,
    can_transition,
)


class InMemoryJobStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._jobs: dict[str, ContentJob] = {}
        # (owner_id, idempotency_key) -> job_id. The uniqueness that makes a retry idempotent.
        self._by_idempotency: dict[tuple[str, str], str] = {}
        self._seq: dict[str, int] = defaultdict(int)
        self._events: dict[str, list[JobEvent]] = defaultdict(list)
        self._claimed: dict[tuple[str, int], str] = {}

    # --- acceptance (RJ-AC01 / RJ-AC06) ---------------------------------------------------

    def accept(
        self,
        *,
        job_id: str,
        owner_id: str,
        task_type: str,
        input: dict[str, Any],
        idempotency_key: str | None,
        now: float,
    ) -> tuple[ContentJob, bool]:
        with self._lock:
            if idempotency_key is not None:
                existing_id = self._by_idempotency.get((owner_id, idempotency_key))
                if existing_id is not None:
                    existing = self._jobs.get(existing_id)
                    if existing is not None:
                        # The retry of a submission whose response was lost (RJ-AC06): report the
                        # job that already exists instead of accepting the work twice.
                        return existing, False
            job = ContentJob(
                job_id=job_id,
                owner_id=owner_id,
                task_type=task_type,
                state=JobState.SUBMITTED,
                input=input,
                idempotency_key=idempotency_key,
                created_at=now,
                updated_at=now,
            )
            self._jobs[job_id] = job
            if idempotency_key is not None:
                self._by_idempotency[(owner_id, idempotency_key)] = job_id
            return job, True

    def release_idempotency(self, owner_id: str, key: str | None, job_id: str) -> None:
        with self._lock:
            if key is None:
                return
            # Only unbind the key if it still names *this* job: a late failure from a job that has
            # already been superseded must not free a key that now belongs to newer work.
            if self._by_idempotency.get((owner_id, key)) == job_id:
                del self._by_idempotency[(owner_id, key)]

    def get(self, job_id: str) -> ContentJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def transition(
        self,
        job_id: str,
        target: JobState,
        *,
        expect_from: frozenset[JobState],
        now: float,
        result_ref: str | None = None,
        result_expires_at: float | None = None,
        error: JobError | None = None,
        abstain_reason: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> ContentJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.state not in expect_from:
                # Compare-and-set guard: a duplicate delivery that arrives after the job finished
                # finds no legal source state and is dropped instead of re-running the effect.
                return None
            if not can_transition(job.state, target):
                return None
            updated = job.transitioned(
                target,
                now=now,
                result_ref=result_ref if result_ref is not None else job.result_ref,
                result_expires_at=(
                    result_expires_at if result_expires_at is not None else job.result_expires_at
                ),
                error=error if error is not None else job.error,
                abstain_reason=(
                    abstain_reason if abstain_reason is not None else job.abstain_reason
                ),
            )
            self._jobs[job_id] = updated
            # Exactly one event per transition — the payload belongs to this edge, so appending
            # again from the service would double-count it in a replayed stream.
            self.append_event(job_id, job.owner_id, target, payload or {}, now)
            return updated

    # --- effect ledger (ND-Q8) ------------------------------------------------------------

    def claim_effect(self, job_id: str, attempt: int, effect: str) -> bool:
        """Spend this attempt's single effect budget, labelled with ``effect`` (plan item 25).

        The key is ``(job_id, attempt)``, not the effect name: one attempt buys one externally
        observable effect, so a redelivery relabelled "write_through" cannot buy a second one.
        Steps after the first are guarded by the transition compare-and-set instead.
        """
        with self._lock:
            key = (job_id, attempt)
            if key in self._claimed:
                return False
            self._claimed[key] = effect
            return True

    def release_effect(self, job_id: str, attempt: int) -> None:
        """Give the budget back after a *failed* effect, so the retry can re-attempt it.

        Only ever call this on failure: releasing after a success is how one piece of work gets
        paid for twice.
        """
        with self._lock:
            self._claimed.pop((job_id, attempt), None)

    # --- events (RJ-AC04) -----------------------------------------------------------------

    def append_event(
        self, job_id: str, owner_id: str, state: JobState, payload: dict[str, Any], now: float
    ) -> JobEvent:
        with self._lock:
            self._seq[job_id] += 1
            seq = self._seq[job_id]
            event = JobEvent(
                seq=seq,
                event_id=f"{job_id}:{seq}",
                job_id=job_id,
                owner_id=owner_id,
                state=state,
                payload=dict(payload),
                created_at=now,
            )
            self._events[job_id].append(event)
            return event

    def list_events(
        self, job_id: str, *, after_seq: int = 0, limit: int = 500
    ) -> list[JobEvent]:
        with self._lock:
            return [e for e in self._events.get(job_id, []) if e.seq > after_seq][:limit]

    # --- lifecycle ------------------------------------------------------------------------

    def purge_owner(self, owner_id: str) -> None:
        with self._lock:
            job_ids = [j.job_id for j in self._jobs.values() if j.owner_id == owner_id]
            for job_id in job_ids:
                self._jobs.pop(job_id, None)
                self._events.pop(job_id, None)
                self._seq.pop(job_id, None)
                self._claimed = {k: v for k, v in self._claimed.items() if k[0] != job_id}
            self._by_idempotency = {
                k: v for k, v in self._by_idempotency.items() if k[0] != owner_id
            }