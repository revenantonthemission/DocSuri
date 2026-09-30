"""Content Job Service — submission, idempotency, state machine, event emission."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncGenerator, Optional

import aio_pika
import yaml

from docsuri_platform_integrity.adapters.authz import AuthorizationServiceImpl
from docsuri_platform_integrity.adapters.cache import RedisTranslationCache, CanonicalPaperRegistry
from docsuri_platform_integrity.adapters.assets import AssetService
from docsuri_platform_integrity.contracts.models import Ref


class TaskType(str, Enum):
    TRANSLATE = "TRANSLATE"
    SUMMARIZE = "SUMMARIZE"
    NOVELTY = "NOVELTY"
    EVIDENCE = "EVIDENCE"
    INGEST_USERDOC = "INGEST_USERDOC"


class JobState(str, Enum):
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABSTAINED = "ABSTAINED"


class JobErrorType(str, Enum):
    TIMEOUT = "timeout"
    MODEL_UNAVAILABLE = "model_unavailable"
    VALIDATION_FAILED = "validation_failed"
    PERMISSION_REVOKED = "permission_revoked"
    ABSTAINED = "abstained"


@dataclass
class JobError:
    error_type: str
    message: str
    retryable: bool
    retry_after_seconds: int | None = None


@dataclass
class JobEvent:
    event_id: str
    job_id: str
    state: str
    timestamp_us: int
    payload: dict | None = None


@dataclass
class ContentJob:
    job_id: str
    task_type: str
    owner: str
    input_data: dict
    idempotency_key: str
    state: JobState = JobState.SUBMITTED
    attempt: int = 1
    asset_id: str | None = None
    error: dict | None = None
    abstain_reason: str | None = None
    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1_000_000))
    updated_at: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1_000_000))
    accepted_at: int | None = None
    started_at: int | None = None
    completed_at: int | None = None
    authz_token: str | None = None


class JobEventEmitter:
    """Event emitter with Outbox pattern for SSE and replay."""

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self.outbox: list[JobEvent] = []

    def emit(self, event: JobEvent) -> None:
        # In-memory subscribers
        for queue in self._subscribers.get(event.job_id, []):
            queue.put_nowait(event)
        # Outbox for replay
        self.outbox.append(event)

    async def subscribe(self, job_id: str, last_event_id: str | None) -> AsyncGenerator[JobEvent, None]:
        # Replay missed events
        if last_event_id:
            for event in self.outbox:
                if event.event_id > last_event_id:
                    yield event
        # Live subscription
        queue = asyncio.Queue()
        if event.job_id not in self._subscribers:
            self._subscribers[event.job_id] = []
        self._subscribers[event.job_id].append(queue)
        try:
            while True:
                event = await queue.get()
                yield event
        finally:
            self._subscribers[event.job_id].remove(queue)


class ContentJobService:
    """Content job lifecycle management."""

    VALID_TRANSITIONS = {
        JobState.SUBMITTED: {JobState.ACCEPTED, JobState.FAILED},
        JobState.ACCEPTED: {JobState.QUEUED},
        JobState.QUEUED: {JobState.RUNNING},
        JobState.RUNNING: {JobState.COMPLETED, JobState.FAILED, JobState.ABSTAINED},
        # Terminal states: no transitions
    }

    def __init__(
        self,
        rabbitmq_url: str,
        authz: AuthorizationServiceImpl,
        asset_service: AssetService,
        registry: "CanonicalPaperRegistry",
        translation_cache: "RedisTranslationCache",
    ):
        self.rabbitmq_url = rabbitmq_url
        self.authz = authz
        self.asset_service = asset_service
        self.registry = registry
        self.translation_cache = translation_cache
        self._jobs: dict[str, ContentJob] = {}
        self.event_emitter = JobEventEmitter()
        self._rabbitmq_connection: aio_pika.Connection | None = None
        self._channel: aio_pika.Channel | None = None
        self._queues: dict[str, aio_pika.Queue] = {}

    async def initialize(self) -> None:
        """Initialize RabbitMQ connection and declare queues."""
        self._rabbitmq_connection = await aio_pika.connect_robust(self.rabbitmq_url)
        self._channel = await self._rabbitmq_connection.channel()

        # Declare queues for each task type
        for task_type in ["translate", "summarize", "novelty", "evidence", "ingest_userdoc"]:
            queue = await self._channel.declare_queue(
                f"content-job-{task_type}",
                durable=True,
            )
            self._queues[task_type] = queue

        # DLQ
        await self._channel.declare_queue("content-job-dlq", durable=True)

    async def close(self) -> None:
        if self._rabbitmq_connection:
            await self._rabbitmq_connection.close()

    def _make_idempotency_key(
        self,
        canonical_paper_id: str,
        task_type: str,
        input_data: bytes,
        params: dict,
    ) -> str:
        input_hash = hashlib.sha256(input_data).hexdigest()[:16]
        params_hash = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:16]
        return f"content:{canonical_paper_id}:{task_type}:{input_hash}:{params_hash}"

    async def submit(
        self,
        task_type: str,
        input_data: dict,
        owner: str,
        idempotency_key: str | None = None,
    ) -> str:
        """Submit a new job or return existing job ID if idempotency key matches."""
        task_type_enum = TaskType(task_type.upper())

        # Generate idempotency key if not provided
        if not idempotency_key:
            input_bytes = json.dumps(input_data, sort_keys=True).encode()
            params_hash = hashlib.sha256(json.dumps({}, sort_keys=True).encode()).hexdigest()[:16]
            # Note: canonical_paper_id should come from registry lookup in real usage
            canonical_id = input_data.get("canonical_paper_id", "unknown")
            idempotency_key = f"content:{canonical_id}:{task_type}:{hashlib.sha256(b'dummy').hexdigest()[:16]}:dummy"

        # Check for existing job with same idempotency key
        for job in self._jobs.values():
            if job.idempotency_key == idempotency_key:
                return job.job_id

        # Create new job
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        now_us = int(datetime.now().timestamp() * 1_000_000)

        job = ContentJob(
            job_id=job_id,
            task_type=task_type,
            owner=owner,
            input_data=input_data,
            idempotency_key=idempotency_key,
            state=JobState.SUBMITTED,
        )

        # Transition to ACCEPTED (durable acceptance)
        await self._transition(job, "ACCEPTED")
        self.authz.register_job(job.job_id, owner)

        # Publish to queue
        await self._publish_to_queue(task_type.lower(), {
            "job_id": job.job_id,
            "task_type": task_type,
            "input": input_data,
            "idempotency_key": idempotency_key,
            "attempt": 1,
            "created_at": int(datetime.now().timestamp() * 1_000_000),
        })

        return job.job_id

    async def _transition(self, job: ContentJob, new_state: str) -> None:
        """Transition job state with validation and event emission."""
        current = job.state
        valid_next = self.VALID_TRANSITIONS.get(job.state, set())
        if new_state not in valid_next:
            raise ValueError(f"Invalid transition: {job.state} -> {new_state}")

        old_state = job.state
        job.state = JobState(new_state)
        job.updated_at = int(datetime.now().timestamp() * 1_000_000)

        if new_state == "ACCEPTED":
            job.accepted_at = int(datetime.now().timestamp() * 1_000_000)
        elif new_state == "RUNNING":
            job.started_at = int(datetime.now().timestamp() * 1_000_000)
        elif new_state in ("COMPLETED", "FAILED", "ABSTAINED"):
            job.completed_at = int(datetime.now().timestamp() * 1_000_000)

        # Emit event
        payload = {}
        if new_state == "COMPLETED":
            payload["assetId"] = job.asset_id
        elif new_state == "FAILED":
            payload["error"] = job.error
        elif new_state == "ABSTAINED":
            payload["abstainReason"] = job.abstain_reason

        event = JobEvent(
            event_id=f"evt-{uuid.uuid4().hex[:12]}",
            job_id=job.job_id,
            state=new_state,
            timestamp_us=int(datetime.now().timestamp() * 1_000_000),
            payload=payload or None,
        )
        self.event_emitter.emit(event)

    async def get_state(self, job_id: str) -> dict:
        job = self._jobs.get(job_id)
        if not job:
            return {"error": "Job not found"}
        return {
            "jobId": job.job_id,
            "state": job.state.value,
            "assetId": job.asset_id,
            "error": job.error,
            "abstainReason": job.abstain_reason,
        }

    async def subscribe_events(self, job_id: str, last_event_id: str | None) -> AsyncGenerator[dict, None]:
        async for event in self.event_emitter.subscribe(job_id, last_event_id):
            yield {
                "eventId": event.event_id,
                "jobId": event.job_id,
                "state": event.state,
                "timestampUs": event.timestamp_us,
                "payload": event.payload,
            }

    async def _publish_to_queue(self, task_type: str, message: dict) -> None:
        """Publish message to RabbitMQ queue."""
        if not self._channel:
            raise RuntimeError("Not initialized")

        queue = self._queues.get(task_type)
        if not queue:
            raise ValueError(f"Queue not declared for {task_type}")

        await self._channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=f"content-job-{task_type}",
        )

    async def recheck_authz(self, job_id: str, action: str) -> bool:
        """Recheck authorization for a job."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        return self.authz.recheck(job.owner, job_id, action)


# Load timeouts config
def load_timeouts() -> dict:
    with open("ops/platform-integrity/timeouts.yaml") as f:
        return yaml.safe_load(f)


TIMEOUTS = load_timeouts()
