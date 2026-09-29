"""Actual login authentication and least-privilege target execution in the disposable realm."""

import os
import secrets
import time
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import psycopg
import pytest
from test_dispatch_postgres import context
from test_dispatch_postgres import (
    pipeline as pipeline,
)
from test_target_effects import (
    AFTER,
    APPLY,
    BEFORE,
    DSN,
    INSTANT,
    STEP,
    effect,
    ledger_rows,
    target_state,
)
from test_target_effects import (
    realm as realm,
)

from docsuri_platform_integrity.adapters.authority import MutationUnavailable
from docsuri_platform_integrity.adapters.clock import ClockUnavailable
from docsuri_platform_integrity.adapters.nts import (
    NativeTime,
    NTSFrame,
    ProtectedClock,
    publish_frame,
)
from docsuri_platform_integrity.adapters.target_effect import PostgresTargetExecutor
from docsuri_platform_integrity.contracts.codec import canonical, digest
from docsuri_platform_integrity.deployment.operator_helper import build_operator_dispatcher

pytestmark = [pytest.mark.integration, pytest.mark.skipif(not DSN, reason="isolated DB required")]


@pytest.fixture
def native(pipeline, tmp_path):
    store, auth = pipeline
    groups = {"helper": "r1_target_operator", "other": "r1_target_operator",
              "supervisor": "r1_operator_authority_reader", "admin": "r1_operator_grant_admin"}
    names = {key: f"r1_test_{key}_{secrets.token_hex(4)}" for key in groups}
    password = secrets.token_urlsafe(32)
    created = []
    with psycopg.connect(DSN, autocommit=True) as owner:
        try:
            for key, name in names.items():
                owner.execute(psycopg.sql.SQL(
                    "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOREPLICATION NOBYPASSRLS PASSWORD {}"
                ).format(psycopg.sql.Identifier(name), psycopg.sql.Literal(password)))
                created.append(name)
                owner.execute(psycopg.sql.SQL("GRANT {} TO {}").format(
                    psycopg.sql.Identifier(groups[key]), psycopg.sql.Identifier(name)))

            def connect(key="helper"):
                # Authenticate as the actual login, rather than SET ROLE from a superuser session.
                return psycopg.connect(DSN, user=names[key], password=password, autocommit=True)

            auth.actor_role = names["helper"]
            # Replace the synthetic owner mapping made by the shared fixture, before the test
            # realm is handed to a login. Real mappings are immutable and never reassigned.
            owner.execute("ALTER TABLE r1_control.operator_role_bindings "
                          "DISABLE TRIGGER immutable_operator_binding")
            owner.execute("DELETE FROM r1_control.operator_role_bindings")
            owner.execute("ALTER TABLE r1_control.operator_role_bindings "
                          "ENABLE TRIGGER immutable_operator_binding")
            with connect("admin") as admin:
                admin.execute("SELECT r1_control.bind_operator_role('approval-1',1,%s)",
                              (names["helper"],))
                for purpose in ("run", "reconcile"):
                    owner.execute(
                        "INSERT INTO r1_control.authority(binding_id,actor,purpose,target,"
                        "incarnation,plan_digest,revision,valid_until,revoked,artifact_digest,"
                        "policy_digest,namespace,valid_from) SELECT %s,actor,%s,target,incarnation,"
                        "plan_digest,revision,valid_until,revoked,artifact_digest,policy_digest,"
                        "namespace,valid_from FROM r1_control.authority "
                        "WHERE binding_id='approval-1'",
                        (f"approval-{purpose}", purpose),
                    )
                    admin.execute("SELECT r1_control.bind_operator_role(%s,1,%s)",
                                  (f"approval-{purpose}", names["supervisor"]))
            grants = {purpose: auth.binding.model_copy(update={
                "purpose": purpose, "approval_id": f"approval-{purpose}",
            }) for purpose in ("run", "reconcile")}
            frame = NTSFrame(
                utc_us=str(INSTANT), continuous_ns="1000000000", uncertainty_us=100,
                drift_ppm=0.0, boot_id="test-boot", resume_id="test-wake", authenticated=True,
                source="time.cloudflare.com", address="192.0.2.1", config_digest=STEP,
            )
            frame_path = tmp_path / "clock.json"
            publish_frame(frame_path, frame)
            now = NativeTime(1_000_000_000, INSTANT, "test-boot", "test-wake")
            clock = ProtectedClock(frame_path, writer_uid=os.getuid(), config_digest=STEP,
                                   context=lambda: now, trusted_root=tmp_path)

            def transport(key):
                def open_connection(*, readonly, autocommit):
                    assert autocommit is True
                    conn = connect(key)
                    if readonly:
                        conn.execute("SET default_transaction_read_only=on")
                    return conn

                # Test transport authenticates real PG logins. Actual mTLS is covered separately;
                # the production composition uses PostgresTLS.open and Keychain materialization.
                return SimpleNamespace(
                    target=SimpleNamespace(user=names[key], database="rem1_test", port=15439),
                    open=open_connection,
                )

            def recreate_helper():
                owner.execute(psycopg.sql.SQL("DROP ROLE {}").format(
                    psycopg.sql.Identifier(names["helper"])))
                owner.execute(psycopg.sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    psycopg.sql.Identifier(names["helper"]), psycopg.sql.Literal(password)))
                owner.execute(psycopg.sql.SQL("GRANT r1_target_operator TO {}").format(
                    psycopg.sql.Identifier(names["helper"])))

            target = PostgresTargetExecutor(DSN, auth, identity=APPLY, connection_factory=connect)
            binding = effect().model_copy(update={"plan": auth.binding.plan})
            yield SimpleNamespace(store=store, auth=auth, target=target, binding=binding,
                                  connect=connect, names=names, grants=grants, clock=clock,
                                  now=now, transport=transport, recreate_helper=recreate_helper)
        finally:
            for name in reversed(created):
                owner.execute(psycopg.sql.SQL("DROP ROLE {}").format(psycopg.sql.Identifier(name)))


def test_real_non_superuser_can_execute_the_guarded_target_path(native):
    with native.connect() as conn:
        assert conn.execute("SELECT session_user,current_user").fetchone() == (
            native.names["helper"], native.names["helper"],
        )
        row = conn.execute("SELECT rolsuper FROM pg_roles WHERE rolname=session_user").fetchone()
        assert row == (False,)
    receipt = native.target.apply(native.binding)
    assert native.target.observe(native.binding).receipt == receipt
    assert target_state() == AFTER
    assert ledger_rows()[0][-1] == native.names["helper"]


def test_unmapped_login_cannot_use_another_operators_approval_directly(native):
    with native.connect("other") as conn:
        with pytest.raises(psycopg.Error):
            conn.execute(
                "SELECT r1_target.apply_effect('pg','public','i1','r1','apply-1','attempt-1',"
                "%s,%s,%s,1,'approval-1',%s)", (STEP, BEFORE, AFTER, native.auth.binding.plan),
            )
    assert target_state() == BEFORE and ledger_rows() == []


def dispatcher(native, **overrides):
    config = dict(
        plan=native.store.read("r1").plan, step="apply-1", approval=native.auth.binding,
        fence=native.auth.fence, command_grants=native.grants,
        operator_database=native.transport("helper"),
        authority_database=native.transport("supervisor"),
        clock=native.clock, deadline=native.auth.deadline,
    )
    return build_operator_dispatcher(native.store, **(config | overrides))


def dispatch(native, service=None):
    return (service or dispatcher(native)).dispatch(
        "r1", attempt_id="attempt-1", step="apply-1", fence=native.auth.fence,
        expected_revision="0", context=context(), result_context=context("reconcile"),
    )


def test_dispatch_uses_live_source_grants_and_non_superuser_target_login(native):
    result = dispatch(native)
    assert result.record.completion_verified
    assert native.store.read("r1").state == "SUCCEEDED"
    assert ledger_rows()[0][-1] == native.names["helper"]


@pytest.mark.parametrize("key", ["helper", "other", "supervisor"])
def test_process_roles_cannot_write_source_or_rebind_themselves(native, key):
    with native.connect(key) as conn:
        for statement, args in (
            ("SELECT * FROM r1_control.authority", ()),
            ("UPDATE r1_control.authority SET revoked=false", ()),
            ("DELETE FROM r1_control.operator_role_bindings", ()),
            ("SELECT r1_control.bind_operator_role('approval-1',1,%s)", (native.names[key],)),
            ("SELECT r1_control.revoke_operator_grant('approval-1')", ()),
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(statement, args)


def test_login_mapping_does_not_reveal_other_principals_grants(native):
    with native.connect("supervisor") as conn:
        with pytest.raises(psycopg.Error) as denied:
            conn.execute("SELECT * FROM r1_control.read_operator_authority('approval-1',false)")
        assert denied.value.sqlstate == "R1T02"
        assert conn.execute(
            "SELECT purpose FROM r1_control.read_operator_authority('approval-run',false)"
        ).fetchone() == ("run",)


def test_role_recreation_cannot_reuse_an_existing_approval(native):
    native.recreate_helper()
    with pytest.raises(MutationUnavailable, match="rejected"):
        native.target.apply(native.binding)
    with native.connect("admin") as admin:
        with pytest.raises(psycopg.Error, match="immutable"):
            admin.execute("SELECT r1_control.bind_operator_role('approval-1',1,%s)",
                          (native.names["helper"],))
    assert ledger_rows() == []


def test_binding_is_idempotent_audited_and_cannot_be_reassigned(native):
    with psycopg.connect(DSN, autocommit=True) as owner:
        before = owner.execute("SELECT count(*) FROM r1_audit.events").fetchone()[0]
    with native.connect("admin") as admin:
        admin.execute("SELECT r1_control.bind_operator_role('approval-1',1,%s)",
                      (native.names["helper"],))
        with pytest.raises(psycopg.Error, match="immutable"):
            admin.execute("SELECT r1_control.bind_operator_role('approval-1',1,%s)",
                          (native.names["other"],))
    with psycopg.connect(DSN) as owner:
        assert owner.execute("SELECT count(*) FROM r1_audit.events").fetchone()[0] == before
        rows = owner.execute(
            "SELECT e.payload,e.digest FROM r1_audit.events e JOIN r1_control.outbox o "
            "USING(event_id) WHERE payload->>'code'='operator_role_bound'"
        ).fetchall()
    assert len(rows) == 3
    assert all(digest(canonical(payload)) == value for payload, value in rows)


def test_source_admin_revoke_is_atomic_and_stops_native_finalization(native):
    def revoke():
        with native.connect("admin") as admin:
            assert admin.execute(
                "SELECT r1_control.revoke_operator_grant('approval-1')"
            ).fetchone() == (2,)

    with pytest.raises(MutationUnavailable, match="rejected"):
        native.target.apply(native.binding, before_commit_hook=revoke)
    assert target_state() == BEFORE and ledger_rows() == []
    with psycopg.connect(DSN) as owner:
        payload, value = owner.execute(
            "SELECT e.payload,e.digest FROM r1_audit.events e JOIN r1_control.outbox o "
            "USING(event_id) WHERE payload->>'code'='operator_grant_revoked'"
        ).fetchone()
    assert digest(canonical(payload)) == value
    assert payload["actorRole"] == native.names["admin"]


def test_revoked_run_source_prevents_checkpoint_preparation(native):
    with native.connect("admin") as admin:
        admin.execute("SELECT r1_control.revoke_operator_grant('approval-run')")
    with pytest.raises(MutationUnavailable, match="rejected"):
        dispatch(native)
    assert native.store.read("r1").revision == "0" and ledger_rows() == []


def test_reconcile_source_is_separate_from_expired_mutation_authority(native):
    service = dispatcher(native)
    service.target.apply(native.binding)
    with native.connect("admin") as admin:
        admin.execute("SELECT r1_control.revoke_operator_grant('approval-1')")
    service.authorize(context("reconcile"), native.store.read("r1"))
    assert service.target.observe(native.binding).committed
    with native.connect("admin") as admin:
        admin.execute("SELECT r1_control.revoke_operator_grant('approval-reconcile')")
    with pytest.raises(MutationUnavailable):
        service.authorize(context("reconcile"), native.store.read("r1"))


def test_current_authority_checks_do_not_renew_grants_or_append_audit(native):
    service = dispatcher(native)
    with psycopg.connect(DSN) as owner:
        before = owner.execute("SELECT * FROM r1_control.authority ORDER BY binding_id").fetchall()
        count = owner.execute("SELECT count(*) FROM r1_audit.events").fetchone()[0]
    for _ in range(3):
        service.authorize(context(), native.store.read("r1"))
        service.authorize(context("reconcile"), native.store.read("r1"))
    with psycopg.connect(DSN) as owner:
        after = owner.execute("SELECT * FROM r1_control.authority ORDER BY binding_id").fetchall()
        assert after == before
        assert owner.execute("SELECT count(*) FROM r1_audit.events").fetchone()[0] == count


@pytest.mark.parametrize("change", [
    {"continuous_ns": 31_000_000_000}, {"resume_id": "changed-wake"},
    {"continuous_ns": 999_999_999},
])
def test_native_composition_refuses_stale_or_discontinuous_clock(native, change):
    service = dispatcher(native)
    native.clock.context = lambda: replace(native.now, **change)
    with pytest.raises(ClockUnavailable):
        dispatch(native, service)
    assert native.store.read("r1").revision == "0" and ledger_rows() == []


def test_clock_loss_after_write_rolls_back_the_non_superuser_effect(native):
    service = dispatcher(native)
    with pytest.raises(ClockUnavailable):
        service.target.apply(native.binding, before_commit_hook=native.clock.path.unlink)
    assert ledger_rows() == [] and target_state() == BEFORE


def test_helper_pins_preconditions_as_well_as_definition_digest(native):
    service = dispatcher(native)
    wrong = native.binding.model_copy(update={"expected_after": digest(b"unapproved-state")})
    with pytest.raises(MutationUnavailable, match="frozen helper step"):
        service.target.apply(wrong)
    assert ledger_rows() == []


def test_binding_refuses_unsafe_or_write_capable_logins(native):
    with native.connect("admin") as admin:
        for name in ("rem1_test", "r1_target_owner", native.names["admin"], "r1_absent_login"):
            with pytest.raises(psycopg.Error, match="unsafe operator login"):
                admin.execute("SELECT r1_control.bind_operator_role('approval-1',1,%s)", (name,))
        with psycopg.connect(DSN, autocommit=True) as owner:
            owner.execute(psycopg.sql.SQL("GRANT UPDATE(digest) ON r1_target.state TO {}").format(
                psycopg.sql.Identifier(native.names["other"])))
        try:
            with pytest.raises(psycopg.Error, match="unsafe operator login"):
                admin.execute("SELECT r1_control.bind_operator_role('approval-1',1,%s)",
                              (native.names["other"],))
        finally:
            with psycopg.connect(DSN, autocommit=True) as owner:
                owner.execute(psycopg.sql.SQL(
                    "REVOKE UPDATE(digest) ON r1_target.state FROM {}"
                ).format(psycopg.sql.Identifier(native.names["other"])))


def test_failed_critical_audit_rolls_back_source_revocation(native):
    with psycopg.connect(DSN, autocommit=True) as owner:
        owner.execute("ALTER TABLE r1_control.outbox ADD CONSTRAINT reject_source_audit "
                      "CHECK(false) NOT VALID")
    with native.connect("admin") as admin:
        with pytest.raises(psycopg.Error):
            admin.execute("SELECT r1_control.revoke_operator_grant('approval-1')")
    with psycopg.connect(DSN) as owner:
        assert owner.execute("SELECT revision,revoked FROM r1_control.authority "
                             "WHERE binding_id='approval-1'").fetchone() == (1, False)


def test_source_revision_change_requires_a_new_binding_not_a_refresh(native):
    with psycopg.connect(DSN, autocommit=True) as owner:
        owner.execute("UPDATE r1_control.authority SET revision=2 WHERE binding_id='approval-1'")
    with pytest.raises(MutationUnavailable):
        native.target.apply(native.binding)
    with native.connect("admin") as admin:
        admin.execute("SELECT r1_control.bind_operator_role('approval-1',2,%s)",
                      (native.names["helper"],))
    # The database's new mapping does not rewrite or renew the held approval value.
    with pytest.raises(PermissionError):
        native.target.apply(native.binding)
    assert ledger_rows() == []


def test_source_actor_change_does_not_relabel_an_existing_login_binding(native):
    with psycopg.connect(DSN, autocommit=True) as owner:
        owner.execute("UPDATE r1_control.authority SET actor='another-operator' "
                      "WHERE binding_id='approval-1'")
    with pytest.raises(MutationUnavailable):
        native.target.apply(native.binding)
    assert ledger_rows() == []


def test_reconcile_revocation_after_target_commit_preserves_unknown_control_result(native):
    service = dispatcher(native)
    original = service.target.observe

    def observe_then_revoke(binding):
        observation = original(binding)
        with native.connect("admin") as admin:
            admin.execute("SELECT r1_control.revoke_operator_grant('approval-reconcile')")
        return observation

    service.target.observe = observe_then_revoke
    with pytest.raises(MutationUnavailable):
        dispatch(native, service)
    assert target_state() == AFTER
    assert native.store.read("r1").state == "RECONCILE_REQUIRED"


def test_control_scope_and_role_cannot_be_substituted(native):
    service = dispatcher(native)
    run = native.store.read("r1")
    with pytest.raises(MutationUnavailable, match="approved scope"):
        service.authorize(context().model_copy(update={"actor": "another"}), run)
    with pytest.raises(MutationUnavailable):
        dispatcher(native, authority_database=native.transport("other")).authorize(context(), run)
    service.authorize.actor_role = native.names["other"]
    with pytest.raises(MutationUnavailable, match="caller role mismatch"):
        service.authorize(context(), run)


def test_control_authority_deadline_does_not_reset_between_calls(native):
    service = dispatcher(native)
    service.authorize.deadline = time.monotonic() - 1
    with pytest.raises(MutationUnavailable, match="deadline expired"):
        service.authorize(context(), native.store.read("r1"))
    assert native.store.read("r1").revision == "0"


def test_source_expiry_is_checked_against_the_entire_protected_clock_window(native):
    from test_target_effects import MOMENT

    with psycopg.connect(DSN, autocommit=True) as owner:
        owner.execute("UPDATE r1_control.authority SET valid_until=%s "
                      "WHERE binding_id='approval-run'", (MOMENT + timedelta(microseconds=100),))
    # The protected window's upper endpoint equals expiry; there is no grace period.
    with pytest.raises(MutationUnavailable, match="scope or target changed"):
        dispatch(native)
    assert native.store.read("r1").revision == "0"


@pytest.mark.parametrize("change", ["clock", "deadline", "plan", "fence", "purpose"])
def test_helper_composition_rejects_unbound_or_unprotected_configuration(native, change):
    overrides = {
        "clock": {"clock": lambda: (INSTANT, INSTANT)},
        "deadline": {"deadline": float("inf")},
        "plan": {"step": "missing-step"},
        "fence": {"fence": native.auth.fence.model_copy(update={
            "target": native.binding.target.model_copy(update={"incarnation": "other"}),
        })},
        "purpose": {"command_grants": {"run": native.auth.binding}},
    }
    with pytest.raises(ValueError):
        dispatcher(native, **overrides[change])


def test_failed_binding_audit_does_not_publish_a_mapping(native):
    with psycopg.connect(DSN, autocommit=True) as owner:
        owner.execute("UPDATE r1_control.authority SET revision=2 WHERE binding_id='approval-1'")
        owner.execute("ALTER TABLE r1_control.outbox ADD CONSTRAINT reject_binding_audit "
                      "CHECK(false) NOT VALID")
    with native.connect("admin") as admin:
        with pytest.raises(psycopg.Error):
            admin.execute("SELECT r1_control.bind_operator_role('approval-1',2,%s)",
                          (native.names["helper"],))
    with psycopg.connect(DSN) as owner:
        assert owner.execute("SELECT count(*) FROM r1_control.operator_role_bindings "
                             "WHERE authority_revision=2").fetchone() == (0,)


def test_non_superuser_finalizer_serializes_a_later_source_admin_revoke(native):
    with native.connect() as conn:
        with native.auth.guard(conn, APPLY, STEP) as guard:
            with conn.transaction():
                conn.execute(
                    "SELECT r1_target.apply_effect('pg','public','i1','r1','apply-1','attempt-1',"
                    "%s,%s,%s,1,'approval-1',%s)", (STEP, BEFORE, AFTER, native.auth.binding.plan),
                )
                guard.before_commit()
                with native.connect("admin") as admin:
                    admin.execute("SET lock_timeout='100ms'")
                    with pytest.raises(psycopg.errors.LockNotAvailable):
                        admin.execute("SELECT r1_control.revoke_operator_grant('approval-1')")
    with native.connect("admin") as admin:
        result = admin.execute("SELECT r1_control.revoke_operator_grant('approval-1')").fetchone()
        assert result == (2,)
    assert target_state() == AFTER and len(ledger_rows()) == 1


def test_source_read_failure_never_falls_back_to_a_cached_grant(native):
    service = dispatcher(native)
    service.authorize(context(), native.store.read("r1"))
    with psycopg.connect(DSN, autocommit=True) as owner:
        owner.execute("REVOKE EXECUTE ON FUNCTION r1_control.read_operator_authority(text,boolean) "
                      "FROM r1_operator_authority_reader")
    with pytest.raises(psycopg.Error):
        dispatch(native, service)
    assert native.store.read("r1").revision == "0" and ledger_rows() == []


def test_control_source_rejects_ambient_transactions_and_closes_connection(native):
    service = dispatcher(native)
    conn = native.connect("supervisor")
    conn.autocommit = False
    service.authorize._connect = lambda: conn
    with pytest.raises(MutationUnavailable, match="dedicated idle"):
        service.authorize(context(), native.store.read("r1"))
    assert conn.closed
