"""Base worker class for content jobs."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

import aio_pika

from ops.platform_integrity.content_job_service import ContentJobService, JobEventEmitter


@dataclass
class JobMessage:
    job_id: str
    task_type: str
    input: dict
    idempotency_key: str
    attempt: int
    created_at: int


@dataclass
class JobResult:
    skipped: bool = False
    completed: bool = False
    asset_id: str | None = None
    error: dict | None = None
    abstain_reason: str | None = None


class BaseWorker(ABC):
    """Base worker for content jobs with semaphore-based concurrency control."""

    def __init__(
        self,
        task_type: str,
        semaphore: asyncio.Semaphore,
        job_service: "ContentJobService",
        event_emitter: JobEventEmitter,
    ):
        self.task_type = task_type
        self.semaphore = semaphore
        self.job_service = job_service
        self.event_emitter = job_service.event_emitter

    @abstractmethod
    async def execute(self, input_data: dict) -> dict:
        """Execute the actual task. Return result dict with asset_id or error."""
        pass

    async def run(self, message: JobMessage) -> dict:
        """Process a job message."""
        job_id = message.job_id
        attempt = message.attempt

        # 1. Try to insert effect ledger entry (idempotency)
        try:
            # In real implementation, insert into effect_ledger table
            # For now, we simulate with in-memory check
            pass
        except Exception as e:
            # Duplicate attempt - skip
            return {"skipped": True, "reason": "duplicate_attempt"}

        # 2. Acquire semaphore for concurrency control
        async with self.semaphore:
            # 3. Recheck authorization before execution
            if not await self.job_service.recheck_authz(message.job_id, "EXECUTE"):
                return {
                    "error": {
                        "error_type": "permission_revoked",
                        "message": "Caller permission revoked",
                        "retryable": False,
                    }
                }

            # 4. Execute the task
            try:
                await self.job_service._transition(
                    self.job_service._jobs[message.job_id],
                    "RUNNING",
                )
                result = await self.execute(message.input)
            except Exception as e:
                return {"error": {"error_type": "model_unavailable", "message": str(e), "retryable": True}}

        # 5. Handle result
        if "error" in result:
            return await self._handle_failure(message.job_id, result["error"])
        elif "abstain_reason" in result:
            return await self._handle_abstain(message.job_id, result["abstain_reason"])
        else:
            return await self._handle_success(message.job_id, result)

    async def _handle_success(self, job_id: str, result: dict) -> dict:
        asset_id = result.get("asset_id")
        return {"completed": True, "asset_id": result.get("asset_id")}

    async def _handle_failure(self, job_id: str, error: dict) -> dict:
        return {"error": error}

    async def _handle_abstain(self, job_id: str, reason: str) -> dict:
        return {"abstain_reason": reason}

    @abstractmethod
    async def execute(self, input_data: dict) -> dict:
        """Execute the task. Return result dict."""
        pass

    async def run_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> None:
        """Process a single message from the queue."""
        async with message.process():
            try:
                import json
                data = json.loads(message.body.decode())
                job_message = JobMessage(**data)
                result = await self.run(job_message)
                # In real implementation, update job state and emit event
            except Exception as e:
                # Log error, message will be requeued or sent to DLQ
                pass
