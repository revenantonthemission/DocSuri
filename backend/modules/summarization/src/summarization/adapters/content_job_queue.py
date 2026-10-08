"""ContentJobQueue — the durable enqueue path bridging the API handover to SQS.

REM-2 Phase 5/6. The old ``SqsSummaryJobQueue`` was a best-effort fire-and-forget that only
deduplicated in-process. The new contract requires a *durable receipt* before the message ever
hits the queue, so this adapter:

1. Calls ``ContentJobService.submit()`` to atomically create the job row (or return the existing
   one via idempotency key).
2. Enqueues to SQS with the *job_id* so the worker can look it up and transition states.

The idempotency key is derived from the same logical submission the API uses (owner + paper +
task + params), so a retry of the same over-budget request hits the same job rather than spawning
a second one.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..domain.models import SummaryRequest
from ..service.job_service import ContentJobService

log = logging.getLogger(__name__)


class ContentJobQueue:
    """Enqueues content jobs durably, then hands them to SQS for worker consumption.

    The queue URL is expected to point to a queue that has a DLQ configured with a redrive policy
    (maxReceiveCount=3). The worker acks on success; on failure the message is returned to the
    queue and after 3 receives it lands in the DLQ. A recovery sweeper (Phase 6) handles orphaned
    ACCEPTED jobs that were never dispatched.
    """

    def __init__(
        self,
        *,
        job_service: ContentJobService,
        queue_url: str,
        dlq_url: str | None = None,
        region_name: str | None = None,
        client: Any | None = None,
    ) -> None:
        self._job_service = job_service
        self._queue_url = queue_url
        self._dlq_url = dlq_url
        if client is None:
            import boto3  # lazy

            client = boto3.client("sqs", region_name=region_name)
        self._sqs = client

    def enqueue(self, request: SummaryRequest, user_id: str) -> bool:
        """Create/look up the job, then enqueue it to SQS.

        Returns ``True`` if the job was created and enqueued, ``False`` if the work was already
        accepted (idempotency collision) or the request shape isn't supported.
        """
        from ..domain.models import AuthSession, RequestContext
        ctx = RequestContext(auth_session=AuthSession(user_id=user_id), request_id="")

        # Map SummaryRequest to our job task_type + input
        task_type, input_data = self._map_request(request)

        # Submit to the job service — this is the durable acceptance point
        outcome = self._job_service.submit(
            ctx, task_type, input_data, idempotency_key=self._idempotency_key(request, user_id)
        )

        # If the job wasn't accepted (e.g. duplicate that's already dispatched), don't enqueue
        if outcome.state.value != "ACCEPTED":
            return False

        # Enqueue to SQS with the job_id so the worker can find it
        payload = self._sqs_payload(request, user_id, outcome.job_id)
        try:
            self._sqs.send_message(QueueUrl=self._queue_url, MessageBody=json.dumps(payload))
            return True
        except Exception:  # noqa: BLE001 — enqueue is best-effort
            log.warning("content job enqueue failed for %s", outcome.job_id)
            return False

    def _map_request(self, request: SummaryRequest) -> tuple[str, dict]:
        """Map SummaryRequest to (task_type, input) for the job service."""
        from ..domain.models import Task

        if request.task == Task.SUMMARY:
            return "summarize", {
                "paperId": request.paper_id,
                "version": request.version,
                "persona": request.persona.value,
                "scope": request.scope.value,
            }
        if request.task == Task.TRANSLATE:
            return "translate", {
                "paperId": request.paper_id,
                "version": request.version,
                "targetLang": request.target_lang.value,
                "persona": request.persona.value,
                "scope": request.scope.value,
            }
        # Novelty/evidence/ingest_userdoc not yet supported via this path
        return "unknown", {}

    def _idempotency_key(self, request: SummaryRequest, user_id: str) -> str:
        """Same logical key as the API uses — owner + paper + task + params."""
        return (
            f"{user_id}|{request.paper_id}|v{request.version}|{request.task.value}|"
            f"{request.persona.value}|{request.scope.value}|{request.target_lang.value}"
        )

    def _sqs_payload(self, request: SummaryRequest, user_id: str, job_id: str) -> dict:
        return {
            "jobId": job_id,
            "userId": user_id,
            "paperId": request.paper_id,
            "version": request.version,
            "task": request.task.value,
            "targetLang": request.target_lang.value,
            "persona": request.persona.value,
            "scope": request.scope.value,
            "abstract": request.abstract,
        }