"""Complete coordination through real non-owner logins; the owner only provisions the realm."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier

import psycopg
import pytest
from psycopg.types.json import Jsonb
from test_dispatch_postgres import context
from test_dispatch_postgres import (
    pipeline as pipeline,
)
from test_operator_roles_postgres import (
    native as native,
)
from test_target_effects import AFTER, BEFORE, DSN, migration, target_state
from test_target_effects import (
    realm as realm,
)

from docsuri_platform_integrity.adapters.clock import ClockUnavailable
from docsuri_platform_integrity.adapters.postgres import ControlUnavailable
from docsuri_platform_integrity.adapters.scoped_run import ScopedPostgresRunStore
from docsuri_platform_integrity.adapters.target_effect import TargetOutcomeUnknown
from docsuri_platform_integrity.contracts.codec import canonical, digest
from docsuri_platform_integrity.contracts.models import (
    EffectAssurance,
    EffectObservation,
    PlannedEffect,
)
from docsuri_platform_integrity.deployment.operator_helper import build_scoped_operator_dispatcher

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not DSN, reason="isolated DB required")]


@pytest.fixture
def scoped(native):
    plan = native.store.read("r1").plan.model_copy(update={"action": "scoped-migrate"})
    plan_digest = digest(canonical(plan.model_dump(mode="json")))
    with psycopg.connect(DSN, autocommit=True) as owner:
        for name in ("010_control_commands.sql", "011_prepared_target.sql"):
            owner.execute(migration(name))
        owner.execute(psycopg.sql.SQL("GRANT r1_run_operator TO {}").format(
            psycopg.sql.Identifier(native.names["supervisor"])))
        owner.execute("UPDATE r1_control.authority SET plan_digest=%s", (plan_digest,))
        owner.execute(
            "INSERT INTO r1_control.authority(binding_id,actor,purpose,target,incarnation,"
            "plan_digest,revision,valid_until,revoked,artifact_digest,policy_digest,namespace,"
            "valid_from) SELECT 'approval-plan',actor,'plan',target,incarnation,plan_digest,"
            "revision,valid_until,revoked,artifact_digest,policy_digest,namespace,valid_from "
            "FROM r1_control.authority WHERE binding_id='approval-run'"
        )
    with native.connect("admin") as admin:
        admin.execute("SELECT r1_control.bind_operator_role('approval-plan',1,%s)",
                      (native.names["supervisor"],))
    native.auth.binding = native.auth.binding.model_copy(update={"plan": plan_digest})
    native.grants = {purpose: native.auth.binding.model_copy(update={
        "purpose": purpose, "approval_id": f"approval-{purpose}",
    }) for purpose in ("plan", "run", "reconcile")}
    native.plan = plan
    native.scoped_store = ScopedPostgresRunStore(
        lambda: native.connect("supervisor"), native.grants,
        actor_role=native.names["supervisor"], clock=native.clock, deadline=native.auth.deadline,
    )
    native.service = build_scoped_operator_dispatcher(
        plan=plan, step="apply-1", approval=native.auth.binding, fence=native.auth.fence,
        command_grants=native.grants, operator_database=native.transport("helper"),
        control_database=native.transport("supervisor"), clock=native.clock,
        deadline=native.auth.deadline,
    )
    native.scoped_store.register(plan, run_id="scoped-run", submission_key="scoped-request",
                                 context=context("plan"))
    native.scoped_store.begin_attempt("scoped-run", attempt_id="attempt-1", approval="approval-1",
                                      invocation="scoped-invocation", context=context())
    return native


def prepare(scoped, store=None):
    return (store or scoped.scoped_store).prepare(
        "scoped-run", attempt_id="attempt-1", step="apply-1", fence=scoped.auth.fence,
        expected_revision="0", context=context(),
    )


def dispatch(scoped):
    return scoped.service.dispatch(
        "scoped-run", attempt_id="attempt-1", step="apply-1", fence=scoped.auth.fence,
        expected_revision="0", context=context(), result_context=context("reconcile"),
    )


def test_complete_dispatch_uses_scoped_control_and_target_roles(scoped):
    result = dispatch(scoped)
    assert result.record.completion_verified
    assert scoped.scoped_store.read("scoped-run").state == "SUCCEEDED"
    assert target_state() == AFTER


def test_control_login_has_commands_but_no_raw_table_writes(scoped):
    with scoped.connect("supervisor") as conn:
        for sql in (
            "UPDATE r1_control.runs SET state='SUCCEEDED'",
            "DELETE FROM r1_control.checkpoints",
            "INSERT INTO r1_control.outbox(event_id) VALUES ('forged')",
            "SELECT * FROM r1_control.run_preparations",
            "UPDATE r1_target.state SET digest='forged'",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(sql)
    with pytest.raises(PermissionError):
        scoped.scoped_store.read("r1")  # Different, previously provisioned plan.


def test_preparation_secret_is_not_recoverable_from_read_only_history(scoped):
    receipt = prepare(scoped)
    assert receipt.dispatch_token
    assert receipt.dispatch_token not in repr(receipt)
    assert "dispatch_token" not in receipt.model_dump()
    current = scoped.scoped_store.latest("scoped-run", "apply-1")
    assert current == receipt.record
    with scoped.connect("supervisor") as conn:
        value = conn.execute(
            "SELECT r1_control.run_read('scoped-run','approval-reconcile','latest','apply-1')"
        ).fetchone()[0]
    assert receipt.dispatch_token not in str(value)


def test_lost_preparation_ack_cannot_be_replayed_to_obtain_the_secret(scoped):
    class LostAck(ScopedPostgresRunStore):
        @contextmanager
        def _transaction(self, *args, **kwargs):
            with super()._transaction(*args, **kwargs) as conn:
                yield conn
            raise ControlUnavailable("lost native preparation acknowledgement")

    lost = LostAck(lambda: scoped.connect("supervisor"), scoped.grants,
                   actor_role=scoped.names["supervisor"], clock=scoped.clock,
                   deadline=scoped.auth.deadline)
    with pytest.raises(ControlUnavailable):
        prepare(scoped, lost)
    with pytest.raises(ValueError):
        prepare(scoped)
    assert scoped.scoped_store.latest("scoped-run", "apply-1").checkpoint.assurance == (
        EffectAssurance.UNKNOWN
    )
    assert target_state() == BEFORE


def test_missing_or_wrong_preparation_secret_cannot_dispatch(scoped):
    receipt = prepare(scoped)
    with pytest.raises(PermissionError):
        scoped.service.target.apply(receipt.record.binding)
    with pytest.raises(PermissionError):
        scoped.service.target.apply(
            receipt.record.binding,
            preparation=receipt.model_copy(update={"dispatch_token": "wrong"}),
        )
    assert target_state() == BEFORE


def test_coordinator_cannot_invent_commit_or_authorization_evidence(scoped):
    receipt = prepare(scoped)
    fabricated = EffectObservation(
        binding=receipt.record.binding, authoritative=True, committed=True, quiescent=True,
        receipt="forged", observed_state=AFTER,
        authorization_verified=True, durability_verified=True,
    )
    result = scoped.scoped_store.reconcile(
        "scoped-run", step="apply-1", observation=fabricated, expected_revision="1",
        context=context("reconcile"),
    )
    assert not result.record.completion_verified
    assert result.record.checkpoint.assurance == EffectAssurance.UNKNOWN
    assert target_state() == BEFORE


def test_critical_audit_failure_prevents_native_preparation(scoped):
    with psycopg.connect(DSN, autocommit=True) as owner:
        owner.execute("ALTER TABLE r1_control.outbox ADD CONSTRAINT reject_scoped_audit "
                      "CHECK(false) NOT VALID")
    with pytest.raises(ControlUnavailable):
        prepare(scoped)
    assert scoped.scoped_store.read("scoped-run").revision == "0"
    assert target_state() == BEFORE


def test_two_scoped_coordinators_cannot_mint_two_dispatch_secrets(scoped):
    barrier = Barrier(2)

    def contender():
        barrier.wait(timeout=5)
        try:
            return prepare(scoped)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda _: contender(), range(2)))
    assert sum(receipt is not None for receipt in receipts) == 1
    assert scoped.scoped_store.read("scoped-run").revision == "1"


def reconcile(scoped):
    return scoped.service.reconcile(
        "scoped-run", step="apply-1",
        expected_revision=scoped.scoped_store.read("scoped-run").revision,
        context=context("reconcile"),
    )


def native_apply(conn, scoped, receipt):
    b = receipt.record.binding
    return conn.execute(
        "SELECT r1_target.apply_effect(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (b.target.target_id,b.target.namespace,b.target.incarnation,b.run_id,b.step,b.attempt_id,
         b.definition_digest,b.expected_before,b.expected_after,int(b.fence_epoch),"approval-1",
         b.plan,receipt.record_digest,receipt.dispatch_token),
    ).fetchone()[0]


def test_direct_effect_without_guarded_helper_finalization_rolls_back(scoped):
    receipt = prepare(scoped)
    with scoped.connect("helper") as conn:
        with pytest.raises(psycopg.Error) as refused:
            with conn.transaction():
                native_apply(conn, scoped, receipt)
        assert refused.value.sqlstate == "R1T04"
    assert target_state() == BEFORE


def test_old_unprepared_signature_is_unavailable_in_the_scoped_profile(scoped):
    b = scoped.binding
    with scoped.connect("helper") as conn:
        with pytest.raises(psycopg.errors.UndefinedFunction):
            conn.execute(
                "SELECT r1_target.apply_effect(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (b.target.target_id,b.target.namespace,b.target.incarnation,b.run_id,b.step,
                 b.attempt_id,b.definition_digest,b.expected_before,b.expected_after,1,"approval-1",b.plan),
            )


def test_coordinator_cannot_forge_helper_owned_completion(scoped):
    receipt = prepare(scoped)
    with scoped.connect("supervisor") as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "SELECT r1_target.attest_effect('scoped-run','apply-1','attempt-1',%s,'1','2')",
                (receipt.record_digest,),
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("INSERT INTO r1_target.helper_finalizations(run_id) VALUES('forged')")


def test_secret_cannot_be_rebound_to_another_effect_or_executor(scoped):
    receipt = prepare(scoped)
    with scoped.connect("other") as conn:
        with pytest.raises(psycopg.Error) as refused:
            native_apply(conn, scoped, receipt)
        assert refused.value.sqlstate == "R1T04"
    changed = receipt.record.binding.model_copy(update={"attempt_id": "another-attempt"})
    with pytest.raises(PermissionError):
        scoped.service.target.apply(changed, preparation=receipt)
    assert target_state() == BEFORE


def test_committed_secret_cannot_be_reused(scoped):
    receipt = prepare(scoped)
    scoped.service.target.apply(receipt.record.binding, preparation=receipt)
    with pytest.raises(PermissionError):
        scoped.service.target.apply(receipt.record.binding, preparation=receipt)
    assert target_state() == AFTER
    assert reconcile(scoped).record.completion_verified


def test_lost_target_reply_is_resolved_from_durable_helper_evidence(scoped):
    original = scoped.service.target._transaction

    @contextmanager
    def lost_reply(conn):
        with original(conn):
            yield conn
        raise psycopg.OperationalError("injected loss after native target commit")

    scoped.service.target._transaction = lost_reply
    with pytest.raises(TargetOutcomeUnknown):
        dispatch(scoped)
    assert scoped.scoped_store.read("scoped-run").state == "RECONCILE_REQUIRED"
    assert target_state() == AFTER
    result = reconcile(scoped)
    assert result.record.completion_verified
    assert scoped.scoped_store.read("scoped-run").state == "SUCCEEDED"
    with pytest.raises(ValueError):
        dispatch(scoped)


def test_source_admin_fences_a_lost_dispatch_then_a_fresh_attempt_can_resume(scoped):
    receipt = prepare(scoped)
    assert reconcile(scoped).record.checkpoint.assurance == EffectAssurance.UNKNOWN
    with scoped.connect("admin") as admin:
        value = admin.execute(
            "SELECT r1_control.advance_target_epoch('pg','public','1')"
        ).fetchone()
        assert value == (2,)
    aborted = reconcile(scoped)
    assert aborted.record.checkpoint.assurance == EffectAssurance.NO_EFFECT_CONFIRMED
    with pytest.raises(PermissionError):
        scoped.service.target.apply(receipt.record.binding, preparation=receipt)
    scoped.scoped_store.begin_attempt("scoped-run", attempt_id="attempt-2", approval="approval-1",
                                      invocation="explicit-resume", context=context())
    fence = scoped.auth.fence.model_copy(update={"holder": "attempt-2", "epoch": "2"})
    service = build_scoped_operator_dispatcher(
        plan=scoped.plan,step="apply-1",approval=scoped.auth.binding,fence=fence,
        command_grants=scoped.grants,operator_database=scoped.transport("helper"),
        control_database=scoped.transport("supervisor"),clock=scoped.clock,deadline=scoped.auth.deadline,
    )
    result = service.dispatch(
        "scoped-run",attempt_id="attempt-2",step="apply-1",fence=fence,
        expected_revision=scoped.scoped_store.read("scoped-run").revision,
        context=context(),result_context=context("reconcile"),
    )
    assert result.record.completion_verified and target_state() == AFTER


def test_registration_and_attempt_replays_preserve_original_identity_and_time(scoped):
    intent = scoped.scoped_store.register(
        scoped.plan, run_id="another-name", submission_key="scoped-request",
        context=context("plan"),
    )
    assert intent.run_id == "scoped-run"
    attempt = scoped.scoped_store.begin_attempt(
        "scoped-run",attempt_id="attempt-1",approval="approval-1",invocation="scoped-invocation",
        context=context().model_copy(update={"recorded_at": "999"}),
    )
    assert attempt.started_at == "100"
    with pytest.raises(ValueError):
        scoped.scoped_store.begin_attempt("scoped-run",attempt_id="attempt-1",approval="different",
                                          invocation="scoped-invocation",context=context())


def test_weakened_control_durability_never_releases_a_dispatch_secret(scoped):
    def unsafe_connection():
        conn = scoped.connect("supervisor")
        conn.execute("SET synchronous_commit=off")
        return conn

    unsafe = ScopedPostgresRunStore(
        unsafe_connection, scoped.grants, actor_role=scoped.names["supervisor"],
        clock=scoped.clock, deadline=scoped.auth.deadline,
    )
    with pytest.raises((ValueError,ControlUnavailable)):
        prepare(scoped,unsafe)
    assert scoped.scoped_store.read("scoped-run").revision == "0"


def test_source_epoch_advance_has_cas_and_atomic_critical_audit(scoped):
    with psycopg.connect(DSN,autocommit=True) as owner:
        owner.execute("ALTER TABLE r1_control.outbox ADD CONSTRAINT reject_fence "
                      "CHECK(false) NOT VALID")
    with scoped.connect("admin") as admin:
        with pytest.raises(psycopg.Error):
            admin.execute("SELECT r1_control.advance_target_epoch('pg','public','1')")
    with psycopg.connect(DSN,autocommit=True) as owner:
        assert owner.execute("SELECT epoch FROM r1_control.target_identity").fetchone() == (1,)
        owner.execute("ALTER TABLE r1_control.outbox DROP CONSTRAINT reject_fence")
    with scoped.connect("admin") as admin:
        admin.execute("SELECT r1_control.advance_target_epoch('pg','public','1')")
        with pytest.raises(psycopg.Error):
            admin.execute("SELECT r1_control.advance_target_epoch('pg','public','1')")


def test_clock_loss_after_native_prepare_rolls_back_before_secret_release(scoped):
    class LoseClock(ScopedPostgresRunStore):
        @contextmanager
        def _transaction(self, *args, **kwargs):
            with super()._transaction(*args, **kwargs) as conn:
                yield conn
                scoped.clock.path.unlink()

    store = LoseClock(lambda: scoped.connect("supervisor"), scoped.grants,
                      actor_role=scoped.names["supervisor"], clock=scoped.clock,
                      deadline=scoped.auth.deadline)
    with pytest.raises(ClockUnavailable):
        prepare(scoped, store)
    with psycopg.connect(DSN) as owner:
        assert owner.execute("SELECT count(*) FROM r1_control.run_preparations").fetchone() == (0,)
        assert owner.execute("SELECT checkpoint_revision FROM r1_control.runs "
                             "WHERE run_id='scoped-run'").fetchone() == (0,)


@pytest.mark.parametrize("change", [{"run_id": True}, {"expected_revision": "01"},
                                    {"expected_revision": "18446744073709551616"},
                                    {"unexpected": "input"}])
def test_native_command_rejects_coercion_noncanonical_counters_and_extra_fields(scoped, change):
    data = {"run_id": "scoped-run", "attempt_id": "attempt-1", "step": "apply-1",
            "fence": scoped.auth.fence.model_dump(mode="json"), "expected_revision": "0"} | change
    with scoped.connect("supervisor") as conn:
        with pytest.raises(psycopg.Error):
            conn.execute("SELECT r1_control.run_command('prepare',%s,'approval-run',%s)",
                         (Jsonb(data), Jsonb(context().model_dump(mode="json"))))
    assert scoped.scoped_store.read("scoped-run").revision == "0"


def test_successful_control_finalization_serializes_source_revocation(scoped):
    data = {"run_id": "scoped-run", "attempt_id": "attempt-1", "step": "apply-1",
            "fence": scoped.auth.fence.model_dump(mode="json"), "expected_revision": "0"}
    with scoped.connect("supervisor") as conn:
        with conn.transaction():
            conn.execute("SELECT r1_control.run_command('prepare',%s,'approval-run',%s)",
                         (Jsonb(data), Jsonb(context().model_dump(mode="json"))))
            with scoped.connect("admin") as admin:
                admin.execute("SET lock_timeout='100ms'")
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    admin.execute("SELECT r1_control.revoke_operator_grant('approval-run')")
    with scoped.connect("admin") as admin:
        admin.execute("SELECT r1_control.revoke_operator_grant('approval-run')")
    assert scoped.scoped_store.latest("scoped-run", "apply-1").checkpoint.assurance == (
        EffectAssurance.UNKNOWN
    )


def test_complete_multistep_run_obeys_native_predecessor_order(scoped):
    final_state = digest(b"second-state")
    second = PlannedEffect(step="apply-2", definition_digest=digest(b"second-definition"),
                           expected_before=AFTER, expected_after=final_state)
    plan = scoped.plan.model_copy(update={"steps": (*scoped.plan.steps, second)})
    plan_digest = digest(canonical(plan.model_dump(mode="json")))
    with psycopg.connect(DSN, autocommit=True) as owner:
        owner.execute("UPDATE r1_control.authority SET plan_digest=%s", (plan_digest,))
    approval = scoped.auth.binding.model_copy(update={"plan": plan_digest})
    grants = {key: value.model_copy(update={"plan": plan_digest})
              for key, value in scoped.grants.items()}

    def build(step):
        return build_scoped_operator_dispatcher(
            plan=plan, step=step, approval=approval, fence=scoped.auth.fence,
            command_grants=grants, operator_database=scoped.transport("helper"),
            control_database=scoped.transport("supervisor"), clock=scoped.clock,
            deadline=scoped.auth.deadline,
        )

    first, last = build("apply-1"), build("apply-2")
    store = first.store
    store.register(plan, run_id="two-steps", submission_key="two-steps", context=context("plan"))
    store.begin_attempt("two-steps", attempt_id="attempt-1", approval="approval-1",
                        invocation="two-steps", context=context())
    with pytest.raises(ValueError):
        last.dispatch("two-steps", attempt_id="attempt-1", step="apply-2", fence=scoped.auth.fence,
                      expected_revision="0", context=context(), result_context=context("reconcile"))
    first.dispatch("two-steps", attempt_id="attempt-1", step="apply-1", fence=scoped.auth.fence,
                   expected_revision="0", context=context(), result_context=context("reconcile"))
    assert store.read("two-steps").state == "RUNNING"
    last.dispatch("two-steps", attempt_id="attempt-1", step="apply-2", fence=scoped.auth.fence,
                  expected_revision="2", context=context(), result_context=context("reconcile"))
    assert store.read("two-steps").state == "SUCCEEDED"
    assert target_state() == final_state
