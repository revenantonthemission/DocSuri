"""One bounded execution, with lease supervision separate from owned computation.

The executor is an internal trusted adapter. Its stop acknowledgement is part
of the resource boundary, not a model-quality assertion. No normal model
adapter is selected here while the source-rubric prerequisite remains open.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid5

from backend.modules.summarization.admission import AssistanceAdmission
from backend.modules.summarization.execution import ExecutionClaims
from backend.modules.summarization.payload import ExecutionPayloads
from docsuri_shared.workspace import execution as wire


@dataclass(frozen=True)
class PreparedExecution:
    content: bytes
    coverage: dict
    provenance: dict


class OwnedExecutor(Protocol):
    def run(self, bound_input: dict, absolute_monotonic_deadline: float) -> PreparedExecution: ...

    def abort_owned(self) -> None: ...

    def stopped(self) -> bool: ...


class ExecutionRefused(Exception):
    """A conclusive execution failure; uncertainty is never mapped to this type."""

    def __init__(self, reason: str):
        if reason not in {
            "insufficient-result",
            "dependency-unavailable",
            "invalid-source",
            "deadline-exceeded",
        }:
            raise ValueError("unsupported execution failure")
        self.reason = reason
        super().__init__(reason)


class ExecutionInterrupted(RuntimeError):
    """Worker authority or time was lost; owner recovery decides the outcome."""


class WorkerIntervention(RuntimeError):
    """Owned stop was not confirmed; this worker must remain unavailable."""


class PaperWorker:
    HEARTBEAT_SECONDS = 10.0
    STOP_SECONDS = 5.0

    def __init__(
        self,
        worker_id: UUID,
        claims: ExecutionClaims,
        admission: AssistanceAdmission,
        executor: OwnedExecutor,
        *,
        payloads: ExecutionPayloads | None = None,
    ):
        # This identity comes from operator construction, never a submitted claim.
        self.worker_id = UUID(str(worker_id))
        self.claims = claims
        self.admission = admission
        self.executor = executor
        self.payloads = payloads
        self._active = threading.Lock()
        self._unavailable = False

    def run(self, binding: dict, *, previous_fence: int | None = None) -> dict:
        if not self._active.acquire(blocking=False):
            raise WorkerIntervention("worker already has active owned computation")
        try:
            if self._unavailable or not self.executor.stopped():
                raise WorkerIntervention("owned executor stop is not confirmed")
            acquired = self.claims.acquire(binding, self.worker_id, previous_fence=previous_fence)
            claim = acquired["claim"]
            read_started = time.monotonic()
            bound = self.claims.read_input(claim)
            if "acceptedInput" in bound.get("payload", {}) and self.payloads is None:
                raise WorkerIntervention("canonical acceptance requires its guarded payload reader")
            # Conservatively subtract all payload-call time. Renewal never grants
            # a new execution deadline after a restart or a slow database reply.
            deadline = read_started + min(float(bound["remainingSeconds"]), 90.0)
            if deadline <= time.monotonic():
                raise ExecutionInterrupted("original execution deadline exhausted")
            output = self._execute(bound, claim, deadline)
            proposal = self.claims.proposal(
                claim,
                input_hash=binding["inputHash"],
                expected_job_revision=str(bound["jobRevision"]),
            )
            fact = uuid5(
                UUID(binding["operationId"]),
                f"{claim['leaseId']}:{claim['fence']}:terminal",
            )
            if isinstance(output, ExecutionRefused):
                receipt = self.admission.assistance.fail(proposal, fact, output.reason)
            else:
                receipt = self.admission.assistance.complete(
                    proposal,
                    fact,
                    output.content,
                    coverage=output.coverage,
                    provenance=output.provenance,
                )
            # A commit/settlement exception propagates without a compensating
            # failure or release. Durable owner receipts drive later recovery.
            self.admission.settle_terminal(UUID(binding["operationId"]))
            return receipt
        finally:
            self._active.release()

    def _execute(
        self, bound: dict, claim: dict, deadline: float
    ) -> PreparedExecution | ExecutionRefused:
        done = threading.Event()
        interrupted = threading.Event()
        abort_done = threading.Event()
        output: list[PreparedExecution | ExecutionRefused] = []
        errors: list[BaseException] = []
        abort_errors: list[BaseException] = []
        abort_lock = threading.Lock()

        def abort():
            if not abort_lock.acquire(blocking=False):
                return
            interrupted.set()
            try:
                self.executor.abort_owned()
            except BaseException as exc:
                abort_errors.append(exc)
            finally:
                abort_done.set()

        def execute():
            try:
                execution_input = bound
                if self.payloads is not None:
                    execution_input = wire.AssistanceExecutionPayload.model_validate(
                        self.payloads.read(dict(claim), trusted_worker=self.worker_id)
                    ).model_dump(mode="json")
                    if execution_input["binding"] != claim["binding"]:
                        raise ValueError("canonical payload differs from acquired execution")
                # Payload assembly is supervised by the same heartbeat/watchdog
                # as inference, and never receives a fresh execution budget.
                if interrupted.is_set() or time.monotonic() >= deadline:
                    raise ExecutionInterrupted(
                        "payload assembly exhausted original execution budget"
                    )
                result = self.executor.run(execution_input, deadline)
                if not isinstance(result, PreparedExecution):
                    raise TypeError("executor returned no prepared execution")
                output.append(result)
            except ExecutionRefused as exc:
                output.append(exc)
            except BaseException as exc:
                errors.append(exc)
            finally:
                done.set()

        thread = threading.Thread(target=execute, name="docsuri-owned-execution", daemon=True)
        timer = threading.Timer(max(0, deadline - time.monotonic()), abort)
        timer.daemon = True
        thread_started = False
        timer_started = False
        try:
            thread.start()
            thread_started = True
            timer.start()
            timer_started = True
            while not done.wait(min(self.HEARTBEAT_SECONDS, max(0, deadline - time.monotonic()))):
                if interrupted.is_set() or time.monotonic() >= deadline:
                    raise ExecutionInterrupted("original execution deadline reached")
                renewed = self.claims.renew(claim, expected_lease_revision=claim["leaseRevision"])
                claim.update(renewed["claim"])
            if interrupted.is_set() or time.monotonic() >= deadline:
                raise ExecutionInterrupted("execution ended after its allowed deadline")
            if errors:
                raise errors[0]
            return output[0]
        finally:
            timer.cancel()
            if timer_started:
                timer.join(timeout=self.STOP_SECONDS)
            if thread_started and (not done.is_set() or not self.executor.stopped()):
                # Run abort separately: even a broken adapter must not hang the
                # supervisor. A missing stop acknowledgement latches unavailable.
                try:
                    threading.Thread(target=abort, name="docsuri-owned-abort", daemon=True).start()
                except BaseException as exc:
                    self._unavailable = True
                    raise WorkerIntervention("owned abort supervisor could not start") from exc
                abort_done.wait(self.STOP_SECONDS)
            if thread_started:
                thread.join(timeout=self.STOP_SECONDS)
            if (
                (thread_started and thread.is_alive())
                or (timer_started and timer.is_alive())
                or (interrupted.is_set() and not abort_done.is_set())
                or abort_errors
                or not self.executor.stopped()
            ):
                self._unavailable = True
                raise WorkerIntervention("owned computation stop could not be confirmed")
            if interrupted.is_set():
                raise ExecutionInterrupted(
                    "owned computation was interrupted; owner recovery required"
                )
