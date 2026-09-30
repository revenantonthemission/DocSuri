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

from docsuri_platform_integrity.contracts.codec import canonical, decode, digest
from docsuri_platform_integrity.deployment.launchd import (
    REALMS,
    kernel_groups,
    protected_chain,
    role_account,
)
from docsuri_platform_integrity.deployment.receipt import Capability
from docsuri_platform_integrity.deployment.receipt_policy import PolicySnapshot, load_policy

SIGN_ROLE = "sign"
LABEL_PREFIX = "org.docsuri"
MINIMAL_ENV = {"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8", "HOME": "/var/empty"}


class SignerUnavailable(PermissionError):
    pass


class ContentJobService:
    """Content job lifecycle management."""

    VALID_TRANSITIONS = {
        "SUBMITTED": {"ACCEPTED", "FAILED"},
        "ACCEPTED": {"QUEUED"},
        "QUEUED": {"RUNNING"},
        "RUNNING": {"COMPLETED", "FAILED", "ABSTAINED"},
    }

    def __init__(
        self,
        rabbitmq_url: str,
        authz_service,
        asset_service,
        registry,
        translation_cache,
    ):
        self.rabbitmq_url = rabbitmq_url
        self.authz = authz_service
        self.asset_service = asset_service
        self.registry = registry
        self.translation_cache = translation_cache
        self._jobs: dict[str, "ContentJob"] = {}
        self.event_emitter = JobEventEmitter()
        self._rabbitmq_connection = None
        self._channel = None
        self._queues = {}

    async def initialize(self):
        self._rabbitmq_connection = await aio_pika.connect_robust(self.rabbitmq_url)
        self._channel = await self._rabbitmq_connection.channel()
        for task_type in ["translate", "summarize", "novelty", "evidence", "ingest_userdoc"]:
            queue = await self._channel.declare_queue(
                f"content-job-{task_type}", durable=True
            )
            self._queues[task_type] = queue
        await self._channel.declare_queue("content-job-dlq", durable=True)

    async def close(self):
        if self._rabbitmq_connection:
            await self._rabbitmq_connection.close()

    def _make_idempotency_key(
        self, canonical_paper_id: str, task_type: str, input_data: bytes, params: dict
    ) -> str:
        input_hash = hashlib.sha256(input_data).hexdigest()[:16]
        params_hash = hashlib.sha256(canonical(params).encode()).hexdigest()[:16]
        return f"content:{canonical_paper_id}:{task_type}:{input_hash}:{params_hash}"

    async def submit(
        self,
        task_type: str,
        input_data: dict,
        owner: str,
        idempotency_key: str | None = None,
    ) -> str:
        task_type_enum = task_type.upper()
        
        # Generate idempotency key if not provided
        if not idempotency_key:
            input_bytes = json.dumps(input_data, sort_keys=True).encode()
            params_hash = hashlib.sha256(json.dumps({}, sort_keys=True).encode()).hexdigest()[:16]
            canonical_id = input_data.get("canonical_paper_id", "unknown")
            idempotency_key = f"content:{canonical_id}:{task_type}:{hashlib.sha256(input_bytes).hexdigest()[:16]}:{params_hash}"

        # Check for existing job
        for job in self._jobs.values():
            if job.idempotency_key == idempotency_key:
                return job.job_id

        # Check revocation before accepting
        if not await self.authz.recheck(owner, "global", "SUBMIT"):
            raise PermissionError("Submit permission revoked")

        # Create new job
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        now_us = int(datetime.now().timestamp() * 1_000_000)

        job = ContentJob(
            job_id=job_id,
            task_type=task_type,
            owner=owner,
            input_data=input_data,
            idempotency_key=idempotency_key,
            state="SUBMITTED",
            created_at=now_us,
        )

        self._jobs[job_id] = job
        self.authz.register_job_owner(job_id, owner)

        # Transition to ACCEPTED
        await self._transition(job, "ACCEPTED")

        # Publish to queue
        await self._publish_to_queue(task_type.lower(), {
            "job_id": job.job_id,
            "task_type": task_type,
            "input": input_data,
            "idempotency_key": idempotency_key,
            "attempt": 1,
            "created_at": now_us,
        })

        return job_id

    async def _transition(self, job: "ContentJob", new_state: str) -> None:
        if new_state not in self.VALID_TRANSITIONS.get(job.state, set()):
            raise ValueError(f"Invalid transition: {job.state} -> {new_state}")

        old_state = job.state
        job.state = new_state
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
            "state": job.state,
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
        job = self._jobs.get(job_id)
        if not job:
            return False
        return await self.authz.recheck(job.owner, job_id, action)


@dataclass
class JobEvent:
    event_id: str
    job_id: str
    state: str
    timestamp_us: int
    payload: dict | None = None


class JobEventEmitter:
    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self.outbox: list = []

    def emit(self, event: JobEvent) -> None:
        for queue in self._subscribers.get(event.job_id, []):
            queue.put_nowait(event)
        self.outbox.append(event)

    async def subscribe(self, job_id: str, last_event_id: str | None) -> AsyncGenerator[dict, None]:
        if last_event_id:
            for event in self.outbox:
                if event.event_id > last_event_id:
                    yield {
                        "eventId": event.event_id,
                        "jobId": event.job_id,
                        "state": event.state,
                        "timestampUs": event.timestamp_us,
                        "payload": event.payload,
                    }
        queue = asyncio.Queue()
        self._subscribers.setdefault(job_id, []).append(queue)
        try:
            while True:
                event = await queue.get()
                yield {
                    "eventId": event.event_id,
                    "jobId": event.job_id,
                    "state": event.state,
                    "timestampUs": event.timestamp_us,
                    "payload": event.payload,
                }
        finally:
            self._subscribers[event.job_id].remove(queue)


@dataclass
class ContentJob:
    job_id: str
    task_type: str
    owner: str
    input_data: dict
    idempotency_key: str
    state: str = "SUBMITTED"
    attempt: int = 1
    asset_id: str | None = None
    error: dict | None = None
    abstain_reason: str | None = None
    created_at: int = 0
    updated_at: int = 0
    accepted_at: int | None = None
    started_at: int | None = None
    completed_at: int | None = None
    authz_token: str | None = None
