"""Pure intent and recovery rules. These values are not native finalization capabilities."""

from ..contracts.codec import canonical, digest
from ..contracts.models import (
    BoundCheckpoint,
    EffectAssurance,
    EffectBinding,
    EffectCheckpoint,
    EffectObservation,
    ExecutionPlan,
    RunAttempt,
    RunIntent,
    TargetFence,
)

_NEXT = {
    EffectAssurance.NOT_STARTED: {EffectAssurance.UNKNOWN},
    EffectAssurance.UNKNOWN: {
        EffectAssurance.UNKNOWN, EffectAssurance.COMMITTED, EffectAssurance.NO_EFFECT_CONFIRMED
    },
    EffectAssurance.NO_EFFECT_CONFIRMED: {EffectAssurance.UNKNOWN},
    EffectAssurance.COMMITTED: set(),
}


def transition(
    current: EffectCheckpoint, state: EffectAssurance, *, receipt: str | None = None,
    sequence: str | None = None,
) -> EffectCheckpoint:
    if state not in _NEXT[current.assurance]:
        raise ValueError("invalid effect transition")
    if state != EffectAssurance.UNKNOWN and not receipt:
        raise ValueError("authoritative receipt required")
    if state == EffectAssurance.UNKNOWN and receipt is not None:
        raise ValueError("unknown effect cannot carry a completion receipt")
    next_sequence = int(sequence) if sequence is not None else int(current.sequence) + 1
    if sequence is not None and sequence != str(next_sequence):
        raise ValueError("noncanonical sequence")
    if not int(current.sequence) < next_sequence < 2**64:
        raise ValueError("sequence exhausted or stale")
    return EffectCheckpoint(
        run_id=current.run_id,
        step=current.step,
        sequence=str(next_sequence),
        assurance=state,
        receipt=receipt,
    )


def make_intent(plan: ExecutionPlan, run_id: str) -> RunIntent:
    """Freeze plan semantics, excluding submission ID, attempt, time and approval instance."""
    plan_digest = digest(canonical(plan.model_dump(mode="json")))
    semantic_key = digest(canonical({"kind": "rem1.run-intent.v1", "plan": plan_digest}))
    return RunIntent(
        run_id=run_id, semantic_key=semantic_key, plan=plan_digest, target=plan.target
    )


def prepare_checkpoint(
    plan: ExecutionPlan,
    intent: RunIntent,
    attempt: RunAttempt,
    fence: TargetFence,
    step: str,
    *,
    current: BoundCheckpoint | None,
    sequence: str,
    recorded_at: str,
) -> BoundCheckpoint:
    """Prepare UNKNOWN for durable storage, not a dispatch permit or authority/fence proof.

    The protected executor must additionally verify current authority, clock and native fence.
    A caller may not replay this preparation after an unknown commit acknowledgement.
    """
    if intent != make_intent(plan, intent.run_id) or attempt.run_id != intent.run_id:
        raise ValueError("run intent binding mismatch")
    if attempt.outcome != "RUNNING":
        raise ValueError("attempt is not running")
    if fence.target != plan.target or fence.holder != attempt.attempt_id:
        raise ValueError("target fence binding mismatch")
    effect = next((effect for effect in plan.steps if effect.step == step), None)
    if effect is None:
        raise ValueError("effect is not in the frozen plan")
    binding = EffectBinding(
        run_id=intent.run_id, attempt_id=attempt.attempt_id, target=plan.target,
        plan=intent.plan, step=step, definition_digest=effect.definition_digest,
        expected_before=effect.expected_before, expected_after=effect.expected_after,
        fence_epoch=fence.epoch,
    )
    if current is None:
        checkpoint = EffectCheckpoint(
            run_id=intent.run_id, step=step, sequence="0", assurance=EffectAssurance.NOT_STARTED
        )
    else:
        if current.checkpoint.assurance != EffectAssurance.NO_EFFECT_CONFIRMED:
            raise ValueError("effect is unresolved or already committed")
        identity_fields = {"attempt_id", "fence_epoch"}
        if current.binding.model_dump(exclude=identity_fields) != binding.model_dump(
            exclude=identity_fields
        ):
            raise ValueError("effect binding changed")
        if current.binding.attempt_id == attempt.attempt_id:
            raise ValueError("confirmed abort requires a fresh attempt")
        if int(fence.epoch) <= int(current.binding.fence_epoch):
            raise ValueError("confirmed abort requires a newer fence")
        checkpoint = current.checkpoint
    return BoundCheckpoint(
        binding=binding,
        checkpoint=transition(checkpoint, EffectAssurance.UNKNOWN, sequence=sequence),
        recorded_at=recorded_at,
    )


def reconcile_checkpoint(
    current: BoundCheckpoint, observation: EffectObservation, *, sequence: str, recorded_at: str
) -> BoundCheckpoint:
    """Classify exact native facts; absence, exit status, timeout or lease expiry prove nothing.

    A confirmed effect stays historical fact even after later target drift. That fact is not
    a current readiness/authorization decision. Adapters must authenticate observation sources.
    """
    if current.checkpoint.assurance == EffectAssurance.NO_EFFECT_CONFIRMED:
        if (
            observation.authoritative and observation.committed
            and observation.binding == current.binding
        ):
            # Conflicting native facts invalidate safe retry; preserve the old abort in history.
            return BoundCheckpoint(
                binding=current.binding,
                checkpoint=transition(
                    current.checkpoint, EffectAssurance.UNKNOWN, sequence=sequence
                ),
                recorded_at=recorded_at,
            )
        return current
    if current.checkpoint.assurance != EffectAssurance.UNKNOWN:
        return current
    state = EffectAssurance.UNKNOWN
    if observation.authoritative and observation.receipt and observation.binding == current.binding:
        if (
            observation.committed and not observation.aborted
            and observation.observed_state == current.binding.expected_after
        ):
            state = EffectAssurance.COMMITTED
        elif (
            observation.aborted and not observation.committed and observation.quiescent
            and observation.observed_state == current.binding.expected_before
        ):
            state = EffectAssurance.NO_EFFECT_CONFIRMED
    return BoundCheckpoint(
        binding=current.binding,
        checkpoint=transition(
            current.checkpoint, state, sequence=sequence,
            receipt=observation.receipt if state != EffectAssurance.UNKNOWN else None,
        ),
        recorded_at=recorded_at,
        completion_verified=(
            state == EffectAssurance.COMMITTED
            and observation.authorization_verified and observation.durability_verified
        ),
    )
