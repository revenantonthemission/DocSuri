"""PROP-R1-01/06/07/08: frozen intent identity and conservative recovery decisions."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule
from run_support import attempt, fence, plan, plans

from docsuri_platform_integrity.contracts.codec import digest
from docsuri_platform_integrity.contracts.models import (
    BoundCheckpoint,
    EffectAssurance,
    EffectObservation,
    ExecutionPlan,
)
from docsuri_platform_integrity.domain.run import (
    make_intent,
    prepare_checkpoint,
    reconcile_checkpoint,
)


def prepare(value, *, current=None, number=1, sequence="1", step=None):
    return prepare_checkpoint(
        value, make_intent(value, "r1"), attempt(number=number), fence(value, number),
        step or value.steps[0].step, current=current, sequence=sequence, recorded_at="100",
    )


def observation(record, kind):
    return EffectObservation(
        binding=record.binding, authoritative=kind != "exit-zero", receipt="native-receipt",
        committed=kind in {"commit", "conflict"},
        aborted=kind in {"abort", "in-flight", "conflict"},
        quiescent=kind == "abort",
        observed_state=(
            record.binding.expected_after if kind == "commit" else record.binding.expected_before
        ),
    )


@given(plans())
def test_intent_roundtrip_and_attempts_do_not_change_semantics(value):
    assert ExecutionPlan.model_validate_json(value.model_dump_json()) == value
    first = make_intent(value, "first-submission")
    replay = make_intent(value, "second-submission")
    assert first.semantic_key == replay.semantic_key and first.plan == replay.plan
    changed = value.model_copy(update={"artifact_digest": digest(b"different-artifact")})
    assert make_intent(changed, "first-submission").semantic_key != first.semantic_key
    restored = value.model_copy(update={"target": value.target.model_copy(
        update={"incarnation": "restored-install"}
    )})
    assert make_intent(restored, "first-submission").semantic_key != first.semantic_key


def test_plan_rejects_empty_or_duplicate_steps_and_preserves_meaningful_order():
    value = plan()
    with pytest.raises(ValueError):
        ExecutionPlan.model_validate({**value.model_dump(), "steps": ()})
    with pytest.raises(ValueError):
        ExecutionPlan.model_validate({**value.model_dump(), "steps": (value.steps[0],) * 2})
    reversed_plan = value.model_copy(update={"steps": tuple(reversed(value.steps))})
    assert make_intent(value, "r").semantic_key != make_intent(reversed_plan, "r").semantic_key


@pytest.mark.parametrize("kind", ["exit-zero", "in-flight", "conflict"])
def test_insufficient_or_conflicting_observation_keeps_unknown(kind):
    current = prepare(plan())
    result = reconcile_checkpoint(
        current, observation(current, kind), sequence="2", recorded_at="101"
    )
    assert result.checkpoint.assurance == EffectAssurance.UNKNOWN
    assert result.checkpoint.receipt is None
    with pytest.raises(ValueError, match="unresolved"):
        prepare(plan(), current=result, number=2, sequence="3")


@pytest.mark.parametrize("field,value", [
    ("plan", digest(b"other-plan")), ("fence_epoch", "2"), ("attempt_id", "other-attempt"),
    ("definition_digest", digest(b"other-sql")),
])
def test_other_effect_proof_cannot_resolve_unknown(field, value):
    current = prepare(plan())
    proof = observation(current, "commit")
    proof = proof.model_copy(update={"binding": proof.binding.model_copy(update={field: value})})
    result = reconcile_checkpoint(current, proof, sequence="2", recorded_at="101")
    assert result.checkpoint.assurance == EffectAssurance.UNKNOWN


def test_no_effect_requires_fresh_attempt_and_strictly_new_fence():
    value = plan()
    current = prepare(value)
    current = reconcile_checkpoint(
        current, observation(current, "abort"), sequence="2", recorded_at="101"
    )
    with pytest.raises(ValueError, match="fresh attempt"):
        prepare(value, current=current, sequence="3")
    with pytest.raises(ValueError, match="fence"):
        prepare_checkpoint(
            value, make_intent(value, "r1"), attempt(number=2),
            fence(value, 2).model_copy(update={"epoch": "1"}), value.steps[0].step,
            current=current, sequence="3", recorded_at="102",
        )
    retried = prepare(value, current=current, number=2, sequence="3")
    assert retried.checkpoint.assurance == EffectAssurance.UNKNOWN
    assert retried.binding.attempt_id == "a2"


def test_restore_fence_and_foreign_intent_are_rejected_before_dispatch():
    value = plan()
    for wrong_intent, wrong_fence in (
        (make_intent(plan(incarnation="restore-2"), "r1"), fence(value)),
        (make_intent(value, "r1"), fence(plan(incarnation="restore-2"))),
    ):
        with pytest.raises(ValueError):
            prepare_checkpoint(
                value, wrong_intent, attempt(), wrong_fence, value.steps[0].step,
                current=None, sequence="1", recorded_at="100",
            )


def test_commit_is_historical_fact_not_rewritten_by_later_drift():
    current = prepare(plan())
    committed = reconcile_checkpoint(
        current, observation(current, "commit"), sequence="2", recorded_at="101"
    )
    assert committed.checkpoint.assurance == EffectAssurance.COMMITTED
    assert reconcile_checkpoint(
        committed, observation(committed, "abort"), sequence="3", recorded_at="102",
    ) == committed
    with pytest.raises(ValueError):
        prepare(plan(), current=committed, number=2, sequence="3")


def test_contradictory_native_commit_after_confirmed_abort_blocks_retry():
    current = prepare(plan())
    aborted = reconcile_checkpoint(
        current, observation(current, "abort"), sequence="2", recorded_at="101"
    )
    conflicting = reconcile_checkpoint(
        aborted, observation(aborted, "commit"), sequence="3", recorded_at="102"
    )
    assert conflicting.checkpoint.assurance == EffectAssurance.UNKNOWN
    with pytest.raises(ValueError, match="unresolved"):
        prepare(plan(), current=conflicting, number=2, sequence="4")


@pytest.mark.parametrize("sequence", ["0", "01", "+1", "18446744073709551616"])
def test_checkpoint_sequences_are_lossless_canonical_and_nonwrapping(sequence):
    with pytest.raises(ValueError):
        prepare(plan(), sequence=sequence)


def test_paused_attempt_unknown_step_and_changed_retry_plan_cannot_prepare_effect():
    value = plan()
    with pytest.raises(ValueError, match="not running"):
        prepare_checkpoint(
            value, make_intent(value, "r1"), attempt().model_copy(update={"outcome": "PAUSED"}),
            fence(value), value.steps[0].step, current=None, sequence="1", recorded_at="100",
        )
    with pytest.raises(ValueError, match="not in the frozen plan"):
        prepare(value, step="other:unregistered")
    current = prepare(value)
    aborted = reconcile_checkpoint(
        current, observation(current, "abort"), sequence="2", recorded_at="101"
    )
    changed = value.model_copy(update={"policy_digest": digest(b"new-policy")})
    with pytest.raises(ValueError, match="binding changed"):
        prepare(changed, current=aborted, number=2, sequence="3")


class InterruptedEffectModel(RuleBasedStateMachine):
    """Oracle models observable execution facts, not implementation transition exceptions."""

    def __init__(self):
        super().__init__()
        self.value = plan(count=1)
        self.record = None
        self.number = 0
        self.fact = "absent"

    @rule()
    def dispatch(self):
        sequence = str(int(self.record.checkpoint.sequence) + 1) if self.record else "1"
        if self.fact in {"absent", "aborted"}:
            self.number += 1
            self.record = prepare(
                self.value, current=self.record, number=self.number, sequence=sequence,
            )
            self.fact = "unresolved"
        else:
            with pytest.raises(ValueError):
                prepare(self.value, current=self.record, number=self.number + 1, sequence=sequence)

    @rule(kind=st.sampled_from(["exit-zero", "in-flight", "conflict", "commit", "abort"]))
    def inspect(self, kind):
        if self.record is None:
            return
        prior_fact = self.fact
        self.record = reconcile_checkpoint(
            self.record, observation(self.record, kind),
            sequence=str(int(self.record.checkpoint.sequence) + 1), recorded_at="101",
        )
        if prior_fact == "aborted" and kind in {"commit", "conflict"}:
            self.fact = "unresolved"
        elif prior_fact == "unresolved":
            self.fact = {"commit": "committed", "abort": "aborted"}.get(kind, "unresolved")

    @invariant()
    def matches_independent_effect_facts(self):
        if self.record is None:
            assert self.fact == "absent"
        else:
            expected = {
                "unresolved": EffectAssurance.UNKNOWN,
                "committed": EffectAssurance.COMMITTED,
                "aborted": EffectAssurance.NO_EFFECT_CONFIRMED,
            }
            assert self.record.checkpoint.assurance == expected[self.fact]
            assert BoundCheckpoint.model_validate_json(self.record.model_dump_json()) == self.record


TestInterruptedEffectModel = InterruptedEffectModel.TestCase
TestInterruptedEffectModel.settings = settings.get_profile("stateful")
