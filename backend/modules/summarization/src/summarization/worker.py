"""Summarization worker — long-input background jobs (BR-S6/BR-S8/BR-S18, #135).

Consumes the jobs the API enqueues on the LengthRouter MAP_REDUCE band and runs them **inline**
(``allow_enqueue=False``) — here there is no request/gateway timeout, so the long-input work can
complete: summary map-reduce (3-5 LLM calls) or translate map-only (section-by-section).

Deployment note: this is its own deploy unit (separate from the API). It MUST run with
``DOCSURI_MAP_REDUCE_ENABLED`` on (so the orchestrator has the map-reduce summarizer) and
``DOCSURI_SUMMARY_JOB_QUEUE_URL`` pointing at the same queue the API enqueues to. Build/synth
only — actual deploy is handled separately.
"""

from __future__ import annotations

import json
import logging
import signal
import sys
import threading
from collections.abc import Callable, Iterable
from typing import Any, Protocol

from .domain.models import (
    AuthSession,
    Persona,
    RequestContext,
    Scope,
    SummaryRequest,
    TargetLang,
    Task,
)
from .service.job_service import ContentJobService
from .service.orchestrator import SummarizationOrchestrationService

log = logging.getLogger("docsuri.summarization.worker")


class _Message(Protocol):
    body: dict


def request_from_payload(payload: dict) -> tuple[SummaryRequest, str]:
    """Reconstruct the ``SummaryRequest`` + owner ``user_id`` a SqsSummaryJobQueue message
    carries. Unknown enum values raise (poison message → not acked → DLQ via redrive)."""
    request = SummaryRequest(
        paper_id=str(payload["paperId"]),
        version=int(payload.get("version", 1)),
        task=Task(str(payload["task"])),
        target_lang=TargetLang(str(payload.get("targetLang", TargetLang.KO.value))),
        persona=Persona(str(payload.get("persona", Persona.EXPERT.value))),
        scope=Scope(str(payload.get("scope", Scope.ABSTRACT.value))),
        abstract=str(payload["abstract"]) if payload.get("abstract") else None,
    )
    return request, str(payload["userId"])


def process_job(
    orchestrator: SummarizationOrchestrationService,
    job_service: ContentJobService,
    payload: dict,
) -> None:
    """Run one long-summary job inline with durable state transitions.

    The worker:
    1. Marks the job QUEUED → RUNNING
    2. Claims the effect budget for this attempt
    3. Runs the actual generation via orchestrator
    4. On success: marks COMPLETED with result_ref
    5. On failure: marks FAILED, releases effect budget for retry
    """
    request, user_id = request_from_payload(payload)
    job_id = payload["jobId"]
    ctx = RequestContext(auth_session=AuthSession(user_id=user_id), request_id="")

    # 1. QUEUED → RUNNING
    job_service.mark_queued(ctx, job_id)
    job_service.mark_running(ctx, job_id)

    # 2. Claim effect budget (prevents double-payment on redelivery)
    if not job_service.claim_effect(job_id, 1, "generate"):
        log.warning("effect already claimed for %s — skipping duplicate", job_id)
        return

    try:
        # 3. Run the actual generation
        orchestrator.run(request, ctx, allow_enqueue=False)

        # 4. Success — the orchestrator write-throughs the result to the store.
        # Construct a predictable result_ref for the delivery layer to look up.
        if request.task == Task.TRANSLATE:
            result_ref = (
                f"translate/{request.paper_id}/v{request.version}/{request.target_lang.value}"
            )
        else:
            result_ref = f"summary/{request.paper_id}/v{request.version}"
        job_service.mark_completed(ctx, job_id, result_ref=result_ref)

    except Exception as exc:  # noqa: BLE001
        # 5. Failure — mark FAILED and release effect budget so a retry can re-attempt
        log.exception("summary job %s failed", job_id)
        from .domain.job import JobError

        job_service.mark_failed(
            ctx,
            job_id,
            error=JobError("generation_failed", str(exc), retryable=True, retry_after_seconds=30),
        )
        job_service.release_effect(job_id, 1)
        raise


def run_worker(
    orchestrator: SummarizationOrchestrationService,
    job_service: ContentJobService,
    *,
    receive: Callable[[], Iterable[_Message]],
    ack: Callable[[_Message], None],
    should_stop: Callable[[], bool],
    max_concurrent: int = 3,
) -> None:
    """Poll → process → ack loop with bounded concurrency and an injectable transport.

    ``max_concurrent`` limits how many jobs run simultaneously (default 3). Each worker process
    uses a semaphore so that a burst of messages doesn't overwhelm the LLM gateway or the
    database. If the semaphore is full, the loop waits before receiving more messages.
    """
    semaphore = threading.Semaphore(max_concurrent)

    def process_with_semaphore(message: _Message) -> None:
        with semaphore:
            try:
                process_job(orchestrator, job_service, message.body)
            except Exception:  # noqa: BLE001 — leave unacked for redelivery / eventual DLQ.
                log.exception("summary job failed; leaving for redelivery")
                raise
            else:
                ack(message)

    while not should_stop():
        # Wait for a semaphore slot before receiving (avoids piling up messages we can't process).
        acquired = semaphore.acquire(timeout=1.0)
        if not acquired:
            continue
        try:
            messages = receive()
        finally:
            semaphore.release()

        for message in messages:
            if should_stop():
                return
            try:
                process_with_semaphore(message)
            except Exception:  # noqa: S110 — already logged in process_with_semaphore
                pass


# --- production entry ------------------------------------------------------

_shutdown = threading.Event()


def _on_signal(signum, _frame) -> None:
    log.info("received %s — draining then exiting", signal.Signals(signum).name)
    _shutdown.set()


def _build_observability():
    import os

    from docsuri_ops.observability import ObservabilityHub

    namespace = os.getenv("CLOUDWATCH_NAMESPACE")
    if namespace:
        from docsuri_ops.adapters.cloudwatch import CloudWatchEventStore

        store: Any = CloudWatchEventStore(
            namespace=namespace,
            log_group=os.getenv("CLOUDWATCH_LOG_GROUP", "/docsuri/ops"),
            region_name=os.getenv("AWS_REGION", "ap-northeast-2"),
        )
    else:
        from docsuri_ops.adapters.local import InMemoryEventStore

        store = InMemoryEventStore()
    return ObservabilityHub(store)


def main(argv: list[str] | None = None) -> int:
    del argv
    logging.basicConfig(level=logging.INFO)
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    from docsuri_ops.cost_guard import CostGuardCircuitBreaker

    from .adapters.in_memory_jobs import InMemoryJobStore
    from .adapters.rds_jobs import RdsJobStore
    from .adapters.settings import SummarizationSettings
    from .real_wiring import build_real_orchestrator
    from .service.job_service import ContentJobService

    settings = SummarizationSettings.from_env()
    if not settings.summary_job_queue_url:
        log.error("DOCSURI_SUMMARY_JOB_QUEUE_URL not set — nothing to consume")
        return 1
    if not settings.map_reduce_enabled:
        log.error("DOCSURI_MAP_REDUCE_ENABLED not on — worker cannot produce long summaries")
        return 1

    # Build the orchestrator (for running the actual generation)
    bundle = build_real_orchestrator(
        settings,
        cost_guard=CostGuardCircuitBreaker(),
        observability=_build_observability(),
    )

    # Build the job service (for durable state transitions)
    dsn = settings.database_url
    if dsn:
        job_store = RdsJobStore(dsn=dsn)
    else:
        job_store = InMemoryJobStore()
    job_service = ContentJobService(
        store=job_store,
        enqueue=lambda _job: None,  # not used by worker
        result_ttl_seconds=3600.0,
        now=lambda: __import__("time").time(),
    )

    import boto3

    sqs = boto3.client("sqs", region_name=settings.region_name)
    queue_url = settings.summary_job_queue_url

    class _Sqs:
        def __init__(self, raw: dict) -> None:
            self.body = json.loads(raw["Body"])
            self._receipt = raw["ReceiptHandle"]

    def receive() -> list[_Sqs]:
        resp = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=20)
        return [_Sqs(m) for m in resp.get("Messages", [])]

    def ack(message: _Sqs) -> None:
        sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=message._receipt)

    log.info("summarization worker started — polling queue")
    run_worker(
        bundle.orchestrator,
        job_service,
        receive=receive,
        ack=ack,
        should_stop=_shutdown.is_set,
    )
    log.info("summarization worker shut down gracefully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))