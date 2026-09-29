"""Generated failure cuts in the dispatcher; real database boundaries are tested separately."""

from hypothesis import given
from hypothesis import strategies as st
from run_support import attempt, context, fence, plans

from docsuri_platform_integrity.adapters.postgres import PostgresRunStore
from docsuri_platform_integrity.application.dispatch import RunDispatcher
from docsuri_platform_integrity.contracts.models import EffectObservation, RunRecord
from docsuri_platform_integrity.domain.run import (
    make_intent,
    prepare_checkpoint,
    reconcile_checkpoint,
)


class Interrupted(RuntimeError):
    pass


@given(value=plans(), cut=st.sampled_from([
    "none", "prepare_before", "prepare_ack", "effect_before", "effect_ack", "observe", "result",
    "result_ack",
]), retries=st.integers(min_value=1, max_value=5))
def test_failure_cuts_never_replay_an_effect_or_dispatch_before_ack(value, cut, retries):
    """Independent fault model: once preparation is durable, a retry cannot redispatch it.

    Generated plans vary target incarnation, step ordering/count and artifact identity. The
    in-memory port uses the real pure transition rules, with independent native effect counting.
    """
    pending_failure = cut
    preparations_acknowledged = 0
    effects = 0

    def fail_at(point):
        nonlocal pending_failure
        if pending_failure == point:
            pending_failure = "none"
            raise Interrupted(point)

    class Store:
        run = RunRecord(intent=make_intent(value, "r1"), plan=value, state="RUNNING",
                        revision="0", attempt_id="a1")
        checkpoint = None

        def read(self, run_id):
            return self.run

        def attempt(self, run_id, attempt_id):
            return attempt()

        def prepare(self, run_id, *, attempt_id, step, fence, expected_revision, context):
            nonlocal preparations_acknowledged
            if self.checkpoint is not None:
                raise ValueError("effect already prepared; reconcile required")
            fail_at("prepare_before")
            self.checkpoint = prepare_checkpoint(
                value, self.run.intent, attempt(), fence, step, current=None,
                sequence="1", recorded_at=context.recorded_at,
            )
            self.run = self.run.model_copy(update={"revision": "1", "state": "RECONCILE_REQUIRED"})
            fail_at("prepare_ack")
            preparations_acknowledged += 1
            return PostgresRunStore._receipt(self.checkpoint)

        def reconcile(self, run_id, *, step, observation, expected_revision, context):
            fail_at("result")
            self.checkpoint = reconcile_checkpoint(
                self.checkpoint, observation, sequence="2", recorded_at=context.recorded_at,
            )
            self.run = self.run.model_copy(update={"revision": "2"})
            fail_at("result_ack")
            return PostgresRunStore._receipt(self.checkpoint)

    class Target:
        def validate_attempt(self, attempt, plan, fence):
            pass  # Native authority is exercised in test_dispatch_postgres, not this fault model.

        def apply(self, binding, *, preparation=None):
            nonlocal effects
            assert preparations_acknowledged == 1
            fail_at("effect_before")
            effects += 1
            fail_at("effect_ack")
            return "native-receipt"

        def observe(self, binding):
            fail_at("observe")
            return EffectObservation(
                binding=binding, authoritative=True, committed=bool(effects),
                receipt="native-receipt", quiescent=True, observed_state=binding.expected_after,
                durability_verified=True, authorization_verified=False,
            )

    store = Store()
    dispatcher = RunDispatcher(store, Target(), authorize=lambda ctx, run: None)
    for _ in range(retries):
        try:
            result = dispatcher.dispatch(
                "r1", attempt_id="a1", step=value.steps[0].step, fence=fence(value),
                expected_revision=store.run.revision, context=context(),
                result_context=context("reconcile"),
            )
            assert result.record.completion_verified
            assert effects == 1
        except (Interrupted, ValueError):
            pass
        assert effects <= preparations_acknowledged <= 1
    if cut == "prepare_ack":
        assert effects == 0
