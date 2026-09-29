"""Real control -> target -> control failure boundaries; source clock/identity are test inputs."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier

import psycopg
import pytest
from test_target_effects import (
    AFTER,
    APPLY,
    BEFORE,
    DSN,
    STEP,
    authority,
    ledger_rows,
    target_state,
)
from test_target_effects import (
    realm as realm,
)

from docsuri_platform_integrity.adapters.postgres import ControlUnavailable, PostgresRunStore
from docsuri_platform_integrity.adapters.target_effect import (
    PostgresTargetExecutor,
    TargetOutcomeUnknown,
)
from docsuri_platform_integrity.application.dispatch import RunDispatcher
from docsuri_platform_integrity.contracts.codec import canonical, digest
from docsuri_platform_integrity.contracts.models import (
    CommandContext,
    EffectAssurance,
    ExecutionPlan,
    PlannedEffect,
)

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not DSN, reason="isolated DB required")]


def context(purpose="run"):
    return CommandContext(actor="operator", purpose=purpose, correlation="dispatch-test",
                          recorded_at="100", time_quality="unknown")


def authorize(ctx, run):
    # Synthetic CURRENT control-source port, separate from the actual native target guard.
    if ctx.actor != "operator" or run.intent.run_id != "r1":
        raise PermissionError("control source denied")


@pytest.fixture
def pipeline(realm):
    auth = authority()
    plan = ExecutionPlan(
        action="migrate", target=auth.binding.target, registry_digest=STEP,
        artifact_digest=STEP, policy_digest=STEP, recovery_digest=STEP,
        steps=(PlannedEffect(step="apply-1", definition_digest=STEP,
                             expected_before=BEFORE, expected_after=AFTER),),
    )
    plan_digest = digest(canonical(plan.model_dump(mode="json")))
    auth.binding = auth.binding.model_copy(update={"plan": plan_digest})
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE r1_control.authority SET plan_digest=%s", (plan_digest,))
    store = PostgresRunStore(DSN)
    store.register(plan, run_id="r1", submission_key="dispatch-request", context=context("plan"))
    store.begin_attempt("r1", attempt_id="attempt-1", approval="approval-1",
                        invocation="dispatch-invocation", context=context())
    return store, auth


def service(
    pipeline, *, target_class=PostgresTargetExecutor, store=None, authorize_source=authorize,
):
    original, auth = pipeline
    return RunDispatcher(store or original, target_class(DSN, auth, identity=APPLY),
                         authorize=authorize_source)


def dispatch(dispatcher, pipeline):
    return dispatcher.dispatch(
        "r1", attempt_id="attempt-1", step="apply-1", fence=pipeline[1].fence,
        expected_revision="0", context=context(), result_context=context("reconcile"),
    )


def reconcile(dispatcher, pipeline):
    return dispatcher.reconcile(
        "r1", step="apply-1", expected_revision=pipeline[0].read("r1").revision,
        context=context("reconcile"),
    )


def test_dispatch_waits_for_durable_unknown_and_records_verified_live_completion(pipeline):
    class InspectDurableIntent(PostgresTargetExecutor):
        def _write(self, connection, binding, before_commit_hook):
            independent = PostgresRunStore(DSN)
            checkpoint = independent.latest("r1", "apply-1")
            assert checkpoint.binding == binding
            assert checkpoint.checkpoint.assurance == EffectAssurance.UNKNOWN
            assert independent.read("r1").state == "RECONCILE_REQUIRED"
            with psycopg.connect(DSN) as other:
                assert other.execute(
                    "SELECT count(*) FROM r1_audit.events JOIN r1_control.outbox USING(event_id)"
                ).fetchone()[0] == 3
            return super()._write(connection, binding, before_commit_hook)

    result = dispatch(service(pipeline, target_class=InspectDurableIntent), pipeline)
    assert result.record.completion_verified
    assert pipeline[0].read("r1").state == "SUCCEEDED"
    assert target_state() == AFTER
    assert len(ledger_rows()) == 1


def test_lost_prepare_ack_never_dispatches_or_blindly_retries(pipeline):
    class LostAck(PostgresRunStore):
        @contextmanager
        def _transaction(self):
            with super()._transaction() as conn:
                yield conn
            raise ControlUnavailable("lost preparation acknowledgement")

    with pytest.raises(ControlUnavailable):
        dispatch(service(pipeline, store=LostAck(DSN)), pipeline)
    assert target_state() == BEFORE and ledger_rows() == []
    assert pipeline[0].latest("r1", "apply-1").checkpoint.assurance == EffectAssurance.UNKNOWN
    with pytest.raises(ValueError):
        dispatch(service(pipeline), pipeline)
    assert ledger_rows() == []


def test_failed_critical_outbox_prevents_any_target_effect(pipeline):
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("ALTER TABLE r1_control.outbox ADD CONSTRAINT reject_insert "
                     "CHECK(false) NOT VALID")
    with pytest.raises(ControlUnavailable):
        dispatch(service(pipeline), pipeline)
    assert pipeline[0].latest("r1", "apply-1") is None
    assert target_state() == BEFORE and ledger_rows() == []


def test_lost_target_reply_requires_explicit_reconcile_without_invented_authorization(pipeline):
    class LostReply(PostgresTargetExecutor):
        @contextmanager
        def _transaction(self, connection):
            with super()._transaction(connection):
                yield connection
            raise psycopg.OperationalError("lost target acknowledgement")

    dispatcher = service(pipeline, target_class=LostReply)
    with pytest.raises(TargetOutcomeUnknown):
        dispatch(dispatcher, pipeline)
    assert pipeline[0].read("r1").state == "RECONCILE_REQUIRED"
    assert target_state() == AFTER
    with pytest.raises(ValueError):
        dispatch(dispatcher, pipeline)
    result = reconcile(dispatcher, pipeline)
    assert result.record.checkpoint.assurance == EffectAssurance.COMMITTED
    assert not result.record.completion_verified
    assert pipeline[0].read("r1").state == "PAUSED"
    assert len(ledger_rows()) == 1


def test_lost_result_record_does_not_replay_the_committed_effect(pipeline):
    class FailControlAfterCommit(PostgresTargetExecutor):
        def apply(self, binding, *, preparation=None):
            receipt = super().apply(binding, preparation=preparation)
            with psycopg.connect(DSN, autocommit=True) as conn:
                conn.execute("ALTER TABLE r1_control.outbox ADD CONSTRAINT reject_result "
                             "CHECK(false) NOT VALID")
            return receipt

    with pytest.raises(ControlUnavailable):
        dispatch(service(pipeline, target_class=FailControlAfterCommit), pipeline)
    assert pipeline[0].read("r1").state == "RECONCILE_REQUIRED"
    assert target_state() == AFTER
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("ALTER TABLE r1_control.outbox DROP CONSTRAINT reject_result")
    result = reconcile(service(pipeline), pipeline)
    assert result.record.checkpoint.assurance == EffectAssurance.COMMITTED
    assert not result.record.completion_verified
    assert len(ledger_rows()) == 1


def test_authorization_denial_before_prepare_has_no_side_effect(pipeline):
    def deny(ctx, run):
        raise PermissionError("source unavailable")

    with pytest.raises(PermissionError):
        dispatch(service(pipeline, authorize_source=deny), pipeline)
    assert pipeline[0].read("r1").revision == "0"
    assert target_state() == BEFORE and ledger_rows() == []


def test_reconciliation_needs_its_own_current_purpose_authorization(pipeline):
    class StopBeforeEffect(PostgresTargetExecutor):
        def apply(self, binding, *, preparation=None):
            raise RuntimeError("simulated process stop after preparation")

    with pytest.raises(RuntimeError):
        dispatch(service(pipeline, target_class=StopBeforeEffect), pipeline)

    def deny_reconcile(ctx, run):
        raise PermissionError("reconcile source denied")

    with pytest.raises(PermissionError):
        reconcile(service(pipeline, authorize_source=deny_reconcile), pipeline)
    assert pipeline[0].read("r1").revision == "1"
    # Even after the writer is gone, absence without a newer fence is not a safe abort.
    unresolved = reconcile(service(pipeline), pipeline)
    assert unresolved.record.checkpoint.assurance == EffectAssurance.UNKNOWN
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE r1_control.target_identity SET epoch=2")
    result = reconcile(service(pipeline), pipeline)
    assert result.record.checkpoint.assurance == EffectAssurance.NO_EFFECT_CONFIRMED
    assert pipeline[0].read("r1").state == "PAUSED"
    assert target_state() == BEFORE and ledger_rows() == []


def test_two_dispatchers_cannot_dispatch_one_preparation_twice(pipeline):
    barrier = Barrier(2)

    def contender():
        barrier.wait(timeout=5)
        try:
            return dispatch(service(pipeline), pipeline)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: contender(), range(2)))
    assert sum(result is not None for result in results) == 1
    assert len(ledger_rows()) == 1 and pipeline[0].read("r1").state == "SUCCEEDED"


def test_fenced_abort_requires_fresh_attempt_and_then_can_resume(pipeline):
    class StopBeforeEffect(PostgresTargetExecutor):
        def apply(self, binding, *, preparation=None):
            raise RuntimeError("crash after durable preparation")

    with pytest.raises(RuntimeError):
        dispatch(service(pipeline, target_class=StopBeforeEffect), pipeline)
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE r1_control.target_identity SET epoch=2")
    reconcile(service(pipeline), pipeline)
    store, old = pipeline
    fresh = authority(epoch="2")
    fresh.binding = old.binding
    fresh.fence = fresh.fence.model_copy(update={"holder": "attempt-2"})
    store.begin_attempt("r1", attempt_id="attempt-2", approval="approval-1",
                        invocation="new-explicit-invocation", context=context())
    dispatcher = service((store, fresh))
    result = dispatcher.dispatch(
        "r1", attempt_id="attempt-2", step="apply-1", fence=fresh.fence,
        expected_revision=store.read("r1").revision,
        context=context(), result_context=context("reconcile"),
    )
    assert result.record.completion_verified
    assert ledger_rows()[0][2] == "attempt-2"
    assert store.read("r1").state == "SUCCEEDED"
    assert store.attempt("r1", "attempt-1").started_at == "100"


def test_wrong_approval_on_configured_target_is_rejected_before_preparation(pipeline):
    pipeline[1].binding = pipeline[1].binding.model_copy(update={"approval_id": "other"})
    with pytest.raises(PermissionError, match="authority binding"):
        dispatch(service(pipeline), pipeline)
    assert pipeline[0].latest("r1", "apply-1") is None
    assert target_state() == BEFORE and ledger_rows() == []


def test_reconcile_authority_is_rechecked_after_target_observation(pipeline):
    live = True

    def current(ctx, run):
        if not live:
            raise PermissionError("reconcile grant revoked")

    class RevokeAfterObservation(PostgresTargetExecutor):
        def observe(self, binding):
            nonlocal live
            observed = super().observe(binding)
            live = False
            return observed

    with pytest.raises(PermissionError, match="revoked"):
        dispatch(service(pipeline, target_class=RevokeAfterObservation, authorize_source=current),
                 pipeline)
    assert target_state() == AFTER
    assert pipeline[0].read("r1").state == "RECONCILE_REQUIRED"


@pytest.mark.parametrize("run_purpose,result_purpose", [("plan", "reconcile"), ("run", "verify")])
def test_dispatch_requires_distinct_run_and_result_purposes(pipeline, run_purpose, result_purpose):
    with pytest.raises(PermissionError, match="purpose"):
        service(pipeline).dispatch(
            "r1", attempt_id="attempt-1", step="apply-1", fence=pipeline[1].fence,
            expected_revision="0", context=context(run_purpose),
            result_context=context(result_purpose),
        )
    assert pipeline[0].read("r1").revision == "0"
    assert ledger_rows() == []


@pytest.mark.parametrize("revision", ["0", "1"])
def test_reconcile_cannot_create_an_effect_from_missing_or_stale_preparation(pipeline, revision):
    with pytest.raises(ValueError, match="not found|revision conflict"):
        service(pipeline).reconcile("r1", step="apply-1", expected_revision=revision,
                                    context=context("reconcile"))
    assert pipeline[0].read("r1").revision == "0"
    assert ledger_rows() == []


def test_success_reply_cannot_promote_a_mismatched_observation(pipeline):
    class WrongObservation(PostgresTargetExecutor):
        def observe(self, binding):
            observation = super().observe(binding)
            return observation.model_copy(update={"receipt": digest(b"unrelated-receipt")})

    result = dispatch(service(pipeline, target_class=WrongObservation), pipeline)
    assert result.record.checkpoint.assurance == EffectAssurance.UNKNOWN
    assert not result.record.completion_verified
    assert pipeline[0].read("r1").state == "RECONCILE_REQUIRED"
    assert len(ledger_rows()) == 1 and target_state() == AFTER
