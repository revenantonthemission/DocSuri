"""Recovery sweeper for orphaned content jobs (Phase 6 / ND-Q8).

An orphaned job is one that was accepted durably (job row exists, state=ACCEPTED) but was never
dispatched to the queue — either because the process crashed between accept and enqueue, or the
enqueue itself failed and was logged but not retried.

The sweeper runs periodically (e.g. via a cron job or scheduled Lambda) and:
1. Finds jobs stuck in ACCEPTED/QUEUED beyond a staleness threshold (e.g. 5 minutes).
2. Re-enqueues them to the queue so the worker can pick them up.
3. Updates the job state to QUEUED so the transition is visible.

This is the second layer of the ND-Q8 defense: the effect ledger prevents double-payment for
the *same* attempt; the sweeper ensures a job that fell through the cracks gets another chance.
"""

from __future__ import annotations

import logging
import time

from ..adapters.content_job_queue import ContentJobQueue
from ..adapters.rds_jobs import RdsJobStore
from ..domain.job import JobState
from ..domain.models import Persona, Scope, SummaryRequest, TargetLang, Task
from ..service.job_service import ContentJobService

log = logging.getLogger(__name__)

# A job is "stale" if it's been in ACCEPTED/QUEUED for more than this many seconds without
# progressing to RUNNING. 5 minutes is generous — the normal API→enqueue→worker path is seconds.
STALE_THRESHOLD_SECONDS = 300

# How many jobs to process per sweep run (avoids long-running transactions / memory spikes).
BATCH_SIZE = 100


class OrphanedJobSweeper:
    """Finds ACCEPTED/QUEUED jobs that never made it to RUNNING and re-enqueues them."""

    def __init__(
        self,
        *,
        job_service: ContentJobService,
        queue: ContentJobQueue,
        job_store: RdsJobStore,
        now: callable | None = None,
    ) -> None:
        self._job_service = job_service
        self._queue = queue
        self._job_store = job_store
        self._now = now or time.time

    def sweep(self) -> int:
        """Find stale jobs, re-enqueue them, and return the count handled."""
        now = self._now()
        cutoff = now - STALE_THRESHOLD_SECONDS

        # Use the job store's pending index (state in SUBMITTED, ACCEPTED, QUEUED + updated_at).
        # The index is: CREATE INDEX ix_content_jobs_pending ON content_jobs (state, updated_at)
        # WHERE state IN ('SUBMITTED', 'ACCEPTED', 'QUEUED')
        jobs = self._job_store.find_stale_jobs(cutoff, BATCH_SIZE)

        requeued = 0
        for job in jobs:
            # Only re-enqueue if still in ACCEPTED or QUEUED (a concurrent worker may have
            # already transitioned it to RUNNING).
            if job.state not in (JobState.ACCEPTED, JobState.QUEUED):
                continue

            # Build a minimal SummaryRequest from the job to re-enqueue.
            # The job's input has all the fields we need.
            req = self._build_request(job)
            if req is None:
                log.warning("orphaned sweeper: could not build request for %s", job.job_id)
                continue

            # Re-enqueue through the queue (which will call submit again, but the idempotency
            # key is the same, so it will return the existing job and NOT create a duplicate).
            ok = self._queue.enqueue(req, job.owner_id)
            if ok:
                # The queue.enqueue path will re-submit with the same idempotency key and get
                # the existing job. The job service marks it ACCEPTED again (idempotent).
                # We also explicitly advance to QUEUED so the worker sees progress.
                self._job_service.mark_queued(
                    type(
                        "ctx",
                        (),
                        {
                            "auth_session": type("s", (), {"user_id": job.owner_id})(),
                            "request_id": "",
                        },
                    )(),
                    job.job_id,
                )
                requeued += 1
                log.info("re-queued orphaned job %s (was %s)", job.job_id, job.state.value)

        if requeued:
            log.info("orphaned sweeper: re-queued %d jobs", requeued)
        return requeued

    def _build_request(self, job) -> SummaryRequest | None:
        """Reconstruct a SummaryRequest from the job's input."""
        from ..domain.models import SummaryRequest

        inp = job.input
        task_type = inp.get("taskType") or job.task_type

        try:
            task = Task(task_type)
        except ValueError:
            return None

        # Default values for translate-specific fields
        target_lang = inp.get("targetLang", "ko")
        persona = inp.get("persona", "expert")
        scope = inp.get("scope", "abstract")

        try:
            return SummaryRequest(
                paper_id=inp["paperId"],
                version=inp.get("version", 1),
                task=task,
                target_lang=TargetLang(target_lang),
                persona=Persona(persona),
                scope=Scope(scope),
                abstract=inp.get("abstract"),
            )
        except (KeyError, ValueError) as exc:
            log.warning("orphaned sweeper: invalid input for %s: %s", job.job_id, exc)
            return None


def sweep_orphaned_jobs(
    *,
    dsn: str,
    queue_url: str,
    dlq_url: str | None = None,
    region_name: str | None = None,
    now: callable | None = None,
) -> int:
    """Convenience function to run a one-off sweep (e.g. from a cron/Lambda).

    Creates the necessary adapters, runs the sweep, and returns the count.
    """
    from ..adapters.content_job_queue import ContentJobQueue
    from ..adapters.rds_jobs import RdsJobStore
    from ..service.job_service import ContentJobService

    job_store = RdsJobStore(dsn=dsn)
    job_service = ContentJobService(
        store=job_store,
        enqueue=lambda _j: None,
        result_ttl_seconds=3600.0,
        now=time.time,
    )
    queue = ContentJobQueue(
        job_service=job_service,
        queue_url=queue_url,
        dlq_url=dlq_url,
        region_name=region_name,
    )
    sweeper = OrphanedJobSweeper(
        job_service=job_service,
        queue=queue,
        job_store=job_store,
        now=now,
    )
    return sweeper.sweep()
