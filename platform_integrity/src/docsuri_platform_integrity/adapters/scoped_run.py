"""Command-only control store for the co-located PostgreSQL execution profile.

Native commands derive transitions and evidence; this process has no table-write privilege.
A preparation secret is released only after the control transaction acknowledgement.
"""

import math
import time
from contextlib import contextmanager
from types import MappingProxyType

from ..contracts.codec import canonical, digest
from ..contracts.models import (
    ApprovalBinding,
    CheckpointReceipt,
    CommandContext,
    EffectObservation,
    ExecutionPlan,
    RunAttempt,
    RunIntent,
    RunRecord,
    TargetFence,
)
from ..domain.run import make_intent
from .authority import MutationUnavailable
from .operator_authority import check_source, read_source
from .postgres import ControlUnavailable


class ScopedPostgresRunStore:
    def __init__(
        self, connection_factory, bindings: dict[str, ApprovalBinding], *, actor_role: str,
        clock, deadline: float,
    ):
        if (
            set(bindings) != {"plan", "run", "reconcile"}
            or any(value.purpose != key for key, value in bindings.items())
            or not actor_role or not math.isfinite(deadline)
        ):
            raise ValueError("scoped plan, run and reconcile authorities required")
        self._connect = connection_factory
        self.bindings = MappingProxyType(dict(bindings))
        self.actor_role, self.clock, self.deadline = actor_role, clock, deadline

    @contextmanager
    def _transaction(self, binding: ApprovalBinding, *, readonly=False):
        import psycopg
        from psycopg.pq import TransactionStatus

        remaining = int((self.deadline - time.monotonic()) * 1000)
        if remaining <= 0:
            raise MutationUnavailable("control attempt deadline expired")
        connection = None
        try:
            connection = self._connect()
            if (
                not connection.autocommit
                or connection.info.transaction_status != TransactionStatus.IDLE
                or connection.execute("SELECT session_user").fetchone()[0] != self.actor_role
            ):
                raise MutationUnavailable("dedicated mapped control session required")
            connection.execute(
                "SELECT set_config('statement_timeout',%s,false),"
                "set_config('lock_timeout',%s,false),"
                "set_config('idle_in_transaction_session_timeout','3000',false)",
                (str(min(2000, remaining)), str(min(1000, remaining))),
            )
            with connection.transaction():
                if readonly:
                    connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                row = read_source(connection, binding.approval_id)
                check_source(binding, row, self.clock, purpose=binding.purpose)
                yield connection
                row = read_source(connection, binding.approval_id, finalizing=not readonly)
                check_source(binding, row, self.clock, purpose=binding.purpose)
                if not readonly and connection.execute(
                    "SELECT current_setting('fsync'),current_setting('synchronous_commit'),"
                    "pg_is_in_recovery()"
                ).fetchone() != ("on", "on", False):
                    raise ControlUnavailable("control durability unavailable")
                if time.monotonic() >= self.deadline:
                    raise MutationUnavailable("control finalization deadline expired")
            # Leaving transaction() is the acknowledgement, not receiving the function's row.
        except psycopg.Error as error:
            if error.sqlstate == "R1C01":
                raise ValueError("native control transition rejected") from None
            if error.sqlstate == "R1T02":
                raise MutationUnavailable("native control scope rejected") from None
            raise ControlUnavailable("native control command outcome unconfirmed") from None
        finally:
            if connection is not None:
                connection.close()

    def _command(self, action: str, data: dict, context: CommandContext, purpose: str):
        from psycopg.types.json import Jsonb

        if context.purpose != purpose or context.actor != self.bindings[purpose].actor:
            raise MutationUnavailable("control command purpose or actor mismatch")
        binding = self.bindings[purpose]
        with self._transaction(binding) as conn:
            payload = conn.execute(
                "SELECT r1_control.run_command(%s,%s,%s,%s)",
                (action, Jsonb(data), binding.approval_id, Jsonb(context.model_dump(mode="json"))),
            ).fetchone()[0]
        return payload

    def _read(self, run_id: str, part: str, item: str | None = None):
        binding = self.bindings["reconcile"]
        with self._transaction(binding, readonly=True) as conn:
            return conn.execute("SELECT r1_control.run_read(%s,%s,%s,%s)",
                                (run_id, binding.approval_id, part, item)).fetchone()[0]

    @staticmethod
    def _receipt(payload, *, prepared=False):
        receipt = CheckpointReceipt.model_validate_json(canonical(payload))
        record = receipt.record
        if (
            receipt.record_digest != digest(canonical(record.model_dump(mode="json")))
            or receipt.event_id != digest(canonical([
                "checkpoint", record.binding.run_id, record.checkpoint.sequence,
            ]))
            or bool(receipt.dispatch_token) != prepared
        ):
            raise ControlUnavailable("native checkpoint receipt integrity unproven")
        return receipt

    def read(self, run_id: str) -> RunRecord:
        run = RunRecord.model_validate_json(canonical(self._read(run_id, "run")))
        if run.intent != make_intent(run.plan, run_id):
            raise ValueError("native run identity mismatch")
        return run

    def latest(self, run_id: str, step: str):
        value = self._read(run_id, "latest", step)
        return self._receipt(value).record if value is not None else None

    def attempt(self, run_id: str, attempt_id: str) -> RunAttempt:
        value = self._read(run_id, "attempt", attempt_id)
        if value is None:
            raise ValueError("attempt not found")
        return RunAttempt.model_validate_json(canonical(value))

    def register(
        self, plan: ExecutionPlan, *, run_id: str, submission_key: str, context: CommandContext,
    ) -> RunIntent:
        value = self._command("register", {
            "run_id": run_id, "submission_key": submission_key,
            "plan": plan.model_dump(mode="json"),
        }, context, "plan")
        intent = RunIntent.model_validate_json(canonical(value))
        if intent != make_intent(plan, intent.run_id):
            raise ValueError("native registration identity mismatch")
        return intent

    def begin_attempt(
        self, run_id: str, *, attempt_id: str, approval: str, invocation: str,
        context: CommandContext,
    ) -> RunAttempt:
        value = self._command("begin", {
            "run_id": run_id, "attempt_id": attempt_id,
            "approval": approval, "invocation": invocation,
        }, context, "run")
        return RunAttempt.model_validate_json(canonical(value))

    def prepare(
        self, run_id: str, *, attempt_id: str, step: str, fence: TargetFence,
        expected_revision: str, context: CommandContext,
    ) -> CheckpointReceipt:
        if not fence.validity.contains(*self.clock()):
            raise MutationUnavailable("preparation fence validity rejected")
        value = self._command("prepare", {
            "run_id": run_id, "attempt_id": attempt_id, "step": step,
            "fence": fence.model_dump(mode="json"), "expected_revision": expected_revision,
        }, context, "run")
        return self._receipt(value, prepared=True)

    def reconcile(
        self, run_id: str, *, step: str, observation: EffectObservation,
        expected_revision: str, context: CommandContext,
    ) -> CheckpointReceipt:
        # Observation is an advisory port value. Native evidence decides the persisted result.
        value = self._command("reconcile", {
            "run_id": run_id, "step": step, "expected_revision": expected_revision,
        }, context, "reconcile")
        return self._receipt(value)
