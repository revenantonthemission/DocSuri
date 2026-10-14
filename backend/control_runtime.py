"""Finite U2 admission and a single, supervised owner-work pass.

Route classification grants capacity only. Existing handlers still enforce all
session, owner, CSRF and source checks. Work retains its slot until it returns;
a deadline never creates an overlapping replacement thread.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import re
import time
from contextlib import contextmanager

RECOVERY_REQUEST = contextvars.ContextVar("docsuri_recovery_request", default=False)
WORK_DEADLINE = contextvars.ContextVar("docsuri_control_work_deadline", default=None)

_RECOVERY_POST = frozenset(
    {
        "/api/v2/c02/access-inspect-session",
        "/api/v2/c02/lifecycle-inspect",
        "/api/v2/c03/usage-inspect",
        "/api/v2/c03/usage-list-records",
        "/api/v2/c06/read-assistance-job",
        "/api/v2/c06/read-prepared-assistance",
        "/api/v2/c06/read-assistance-history",
    }
)
_RECOVERY_GET = re.compile(
    r"/api/v2/(?:session|c03/settings-resets(?:/[0-9a-fA-F-]{36})?|"
    r"jobs/[0-9a-fA-F-]{36}(?:/result)?)\Z"
)


def recovery_route(method: str, path: str) -> bool:
    if method == "GET" and path in {"/health/live", "/health/ready"}:
        return True
    return (method == "POST" and path in _RECOVERY_POST) or (
        method == "GET" and bool(_RECOVERY_GET.fullmatch(path))
    )


@contextmanager
def work_budget(seconds: float):
    token = WORK_DEADLINE.set(time.monotonic() + seconds)
    try:
        yield
    finally:
        WORK_DEADLINE.reset(token)


class ControlCapacity:
    """Fail closed until a bounded Ops probe confirms live-store recovery room."""

    def __init__(self, transactions):
        self.transactions = transactions
        self.admitting = False
        self.last_bytes = None
        self.probes = 0

    def refresh(self):
        token = RECOVERY_REQUEST.set(True)
        try:
            row = self.transactions.run(
                "operations",
                lambda conn: conn.execute(
                    "SELECT * FROM operations.capacity_footprint()"
                ).fetchone(),
            )
            values = [row["database_bytes"], row["wal_bytes"]]
            if any(type(value) is not int or value < 0 for value in values):
                raise ValueError("invalid capacity observation")
            self.last_bytes = sum(values)
            self.probes += 1
            # Reserve at least 20% of the live allowance for admitted commits.
            self.admitting = self.last_bytes < (512 * 1024 * 1024 * 4 // 5)
        except Exception:
            self.admitting = False
            raise
        finally:
            RECOVERY_REQUEST.reset(token)


class ControlAdmission:
    """Eight normal and two reserved recovery requests, with no waiting queue.

    All request bodies are bounded before route work. Exhaustion rejects before
    accepting a mutation. Streaming responses retain the admission until the
    producer terminates, including when the caller disconnects.
    """

    def __init__(self, app, *, normal=8, recovery=2, body_limit=65536, capacity=None):
        if (normal, recovery, body_limit) != (8, 2, 65536):
            raise ValueError("explicit u2-synthetic-v1 admission policy required")
        self.app = app
        self.limits = (normal, recovery)
        self.active = [0, 0]
        self.body_limit = body_limit
        self.admitting = True
        self.capacity = capacity

    async def reject(self, send, status, code, message):
        payload = json.dumps(
            {
                "code": code,
                "messageKey": message,
                "requestId": "capacity",
                "retryable": status == 503,
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                    (b"retry-after", b"1"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        recovery = recovery_route(scope["method"], scope["path"])
        lane = int(recovery)
        accepting = self.admitting and (self.capacity is None or self.capacity.admitting)
        if (not accepting and not recovery) or self.active[lane] >= self.limits[lane]:
            return await self.reject(send, 503, "NOT_READY", "capacity.exhausted")
        # No await between comparison and increment on the single serving loop.
        self.active[lane] += 1
        token = RECOVERY_REQUEST.set(recovery)
        try:
            chunks, size = [], 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                if message["type"] != "http.request":
                    raise ValueError("unexpected HTTP receive message")
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > self.body_limit:
                    return await self.reject(send, 413, "INVALID_ARGUMENT", "request.tooLarge")
                chunks.append(chunk)
                if not message.get("more_body", False):
                    break
            body = b"".join(chunks)
            delivered = False

            async def bounded_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()

            return await self.app(scope, bounded_receive, send)
        finally:
            RECOVERY_REQUEST.reset(token)
            self.active[lane] -= 1


class ControlLoop:
    """One background pass at a time, finite attempts owned by durable rows."""

    def __init__(self, worker, *, interval=2.0, deadline=10.0, capacity=None):
        if not 0 < interval <= 4 or not 0 < deadline <= 10:
            raise ValueError("bounded worker cadence required")
        self.worker, self.interval, self.deadline = worker, interval, deadline
        self.capacity = capacity
        self.stopping = asyncio.Event()
        self.task = None
        self.status = {"state": "stopped", "passes": 0, "failures": 0, "timeouts": 0}

    def pass_once(self):
        with work_budget(self.deadline):
            if self.capacity is not None:
                self.capacity.refresh()
            # One responsibility per family is below the policy's batch of five.
            return self.worker.run_once(limit=1)

    async def run(self):
        try:
            while not self.stopping.is_set():
                self.status["state"] = "running"
                execution = asyncio.create_task(asyncio.to_thread(self.pass_once))
                try:
                    try:
                        await asyncio.wait_for(asyncio.shield(execution), self.deadline)
                    except TimeoutError:
                        self.status["state"] = "deadline"
                        self.status["timeouts"] += 1
                        # Keep capacity charged: neither cancellation nor a new
                        # pass may replace an underlying thread still executing.
                        await execution
                    self.status["passes"] += 1
                    self.status["state"] = "idle"
                except Exception:
                    self.status["failures"] += 1
                    self.status["state"] = "degraded"
                try:
                    await asyncio.wait_for(self.stopping.wait(), self.interval)
                except TimeoutError:
                    pass
        finally:
            self.status["state"] = "stopped"

    def start(self):
        if self.task is not None:
            raise ValueError("control loop already started")
        self.task = asyncio.create_task(self.run())

    async def close(self):
        self.stopping.set()
        if self.task is not None:
            # Host supervisor supplies the outer process deadline. Never close
            # pools while an admitted owner action may still be committing.
            await self.task
