"""One-shot control/target coordination, with no retry or automatic resume.

Protected composition supplies native target and current control-purpose authority ports. Neither
serialized checkpoints nor caller-supplied CommandContext values are execution capabilities.
"""

from collections.abc import Callable

from ..contracts.models import (
    CheckpointReceipt,
    CommandContext,
    EffectObservation,
    RunRecord,
    TargetFence,
)
from ..contracts.ports import RunControlPort, TargetEffectPort


class RunDispatcher:
    def __init__(
        self, store: RunControlPort, target: TargetEffectPort,
        *, authorize: Callable[[CommandContext, RunRecord], None],
    ):
        self.store = store
        self.target = target
        self.authorize = authorize

    def _current(self, run_id: str, context: CommandContext, purpose: str) -> RunRecord:
        if context.purpose != purpose:
            raise PermissionError("dispatcher command purpose mismatch")
        run = self.store.read(run_id)
        # This port must consult its current source and raise on refusal, not renew a session.
        self.authorize(context, run)
        return run

    def dispatch(
        self, run_id: str, *, attempt_id: str, step: str, fence: TargetFence,
        expected_revision: str, context: CommandContext, result_context: CommandContext,
    ) -> CheckpointReceipt:
        run = self._current(run_id, context, "run")
        if result_context.purpose != "reconcile":
            raise PermissionError("dispatcher result purpose mismatch")
        attempt = self.store.attempt(run_id, attempt_id)
        self.target.validate_attempt(attempt, run.plan, fence)
        prepared = self.store.prepare(
            run_id, attempt_id=attempt_id, step=step, fence=fence,
            expected_revision=expected_revision, context=context,
        )
        # No finally/retry dispatch: an unacknowledged control commit never reaches this line.
        # Any later exception leaves the durable UNKNOWN for explicit reconciliation.
        binding = prepared.record.binding
        receipt = self.target.apply(binding, preparation=prepared)
        observed = self.target.observe(binding)
        if (
            observed.binding == binding and observed.authoritative and observed.committed
            and not observed.aborted and observed.receipt == receipt
        ):
            # Only this acknowledged live guarded invocation supplies historical authorization.
            # Reconciliation after a crash/lost reply has no such proof and must not invent it.
            observed = observed.model_copy(update={"authorization_verified": True})
        else:
            observed = EffectObservation(binding=binding)
        return self._record(
            run_id, step, observed, prepared.record.checkpoint.sequence, result_context,
        )

    def reconcile(
        self, run_id: str, *, step: str, expected_revision: str, context: CommandContext,
    ) -> CheckpointReceipt:
        run = self._current(run_id, context, "reconcile")
        if run.revision != expected_revision:
            raise ValueError("checkpoint revision conflict")
        current = self.store.latest(run_id, step)
        if current is None:
            raise ValueError("effect checkpoint not found")
        observed = self.target.observe(current.binding)
        return self._record(run_id, step, observed, expected_revision, context)

    def _record(
        self, run_id: str, step: str, observed: EffectObservation,
        revision: str, context: CommandContext,
    ) -> CheckpointReceipt:
        # Observation may take time; reacquire current reconcile authority before recording it.
        self._current(run_id, context, "reconcile")
        return self.store.reconcile(
            run_id, step=step, observation=observed, expected_revision=revision, context=context,
        )
