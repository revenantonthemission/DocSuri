"""Actual fault tests for the target effect executor, against the isolated database.

These are the Step 6 fault cases: two writers, revocation serialized against a commit, a
rollback that must leave no trace, and a lost commit reply that may only be resolved by a
read-only observation. No test here asserts success from a mocked adapter; every effect is a
real compare-and-set on a real row.
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
import pytest
from psycopg import OperationalError

from docsuri_platform_integrity.adapters.authority import MutationUnavailable
from docsuri_platform_integrity.adapters.operator_authority import (
    PostgresOperatorAuthority,
    revoke_operator_grant,
)
from docsuri_platform_integrity.adapters.target_effect import (
    PostgresTargetExecutor,
    TargetOutcomeUnknown,
    TargetStateChanged,
    default_session_lock_key,
)
from docsuri_platform_integrity.contracts.codec import canonical, digest
from docsuri_platform_integrity.contracts.models import (
    ApprovalBinding,
    EffectBinding,
    TargetFence,
    TargetRef,
    ValidityWindow,
)

DSN = os.environ.get("REM1_TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="isolated REM1_TEST_PG_DSN required")

RELEASE = "r1-2026.09"
STEP = digest(b"registered-adopt-step")
APPLY = "registry:apply"
INSTANT = 1_700_000_000_000_000
SPAN = 1800 * 1_000_000
HALF = SPAN // 2
MOMENT = datetime.fromtimestamp(INSTANT / 1_000_000, tz=UTC)
BEFORE = digest(b"target-state-before")
AFTER = digest(b"target-state-after")
ACTOR_ROLE = "rem1_test"
LOCK_KEY = int(digest(canonical(["rem1.target-lock.v1", "pg", "public"])).split(":")[1][:15], 16)


def migration(name: str) -> str:
    return (Path(__file__).resolve().parents[1] / "migrations" / name).read_text()


@pytest.fixture
def realm(request):
    """A disposable realm with a live authority row, a fence and a target state row."""
    parsed = urlsplit(DSN)
    assert parsed.hostname == "127.0.0.1" and parsed.port == 15439, "disposable realm only"
    with psycopg.connect(DSN, autocommit=True) as conn:
        for schema in ("r1_control", "r1_audit", "r1_target"):
            conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        for name in (
            "001_control.sql",
            "002_run_protocol.sql",
            "003_verification_protocol.sql",
            "004_operator_authority.sql",
            "005_reader_access.sql",
            "006_target_effects.sql",
            "007_command_roles.sql",
            "008_target_reconciliation.sql",
            "009_operator_role_binding.sql",
        ):
            if name[:3] in {"008", "009"} and getattr(request, "param", True) is False:
                continue
            conn.execute(migration(name))
        conn.execute("INSERT INTO r1_control.target_identity VALUES ('pg','public','i1',1)")
        conn.execute(
            "INSERT INTO r1_control.authority(binding_id,actor,purpose,target,incarnation,"
            "plan_digest,revision,valid_until,revoked,artifact_digest,policy_digest,namespace,"
            "valid_from) VALUES ('approval-1','operator','apply','pg','i1',%s,1,%s,false,%s,%s,"
            "'public',%s)",
            (STEP, MOMENT + timedelta(minutes=15), STEP, STEP, MOMENT - timedelta(minutes=15)),
        )
        if getattr(request, "param", True) is not False:
            # Disposable owner fixture only. Real provisioning rejects privileged logins and is
            # tested through bind_operator_role using actual non-superuser connections.
            conn.execute(
                "INSERT INTO r1_control.operator_role_bindings "
                "SELECT a.binding_id,a.revision,a.actor,session_user,p.oid "
                "FROM r1_control.authority a,pg_roles p WHERE p.rolname=session_user"
            )
        conn.execute("INSERT INTO r1_target.state VALUES ('pg','public','i1',%s)", (BEFORE,))
    return DSN


def authority(*, epoch="1", approval="approval-1", actor_role=ACTOR_ROLE):
    window = ValidityWindow(valid_from=str(INSTANT - HALF), valid_until=str(INSTANT + HALF))
    target = TargetRef(target_id="pg", namespace="public", incarnation="i1")
    binding = ApprovalBinding(
        approval_id=approval,
        actor="operator",
        purpose="apply",
        target=target,
        plan=STEP,
        artifact=STEP,
        policy=STEP,
        validity=window,
        authority_revision="1",
    )
    fence = TargetFence(target=target, epoch=epoch, holder="attempt-1", validity=window)
    return PostgresOperatorAuthority(
        binding,
        fence,
        actor_role=actor_role,
        definitions={APPLY: STEP},
        clock=lambda: (INSTANT, INSTANT),
        deadline=_far_deadline(),
    )


def _far_deadline() -> float:
    import time

    return time.monotonic() + 300


def effect(*, run="r1", step="apply-1", attempt="attempt-1", epoch="1") -> EffectBinding:
    return EffectBinding(
        run_id=run,
        attempt_id=attempt,
        target=TargetRef(target_id="pg", namespace="public", incarnation="i1"),
        plan=STEP,
        step=step,
        definition_digest=STEP,
        expected_before=BEFORE,
        expected_after=AFTER,
        fence_epoch=epoch,
    )


def executor(*, auth=None, factory=None, lock=LOCK_KEY) -> PostgresTargetExecutor:
    return PostgresTargetExecutor(
        DSN, auth or authority(), identity=APPLY, session_lock_key=lock, connection_factory=factory
    )


def ledger_rows() -> list[tuple]:
    with psycopg.connect(DSN, autocommit=True) as conn:
        return conn.execute(
            "SELECT run_id,step,attempt_id,expected_after,actor_role FROM "
            "r1_target.effect_ledger ORDER BY applied_at"
        ).fetchall()


def target_state() -> str:
    with psycopg.connect(DSN, autocommit=True) as conn:
        return conn.execute("SELECT digest FROM r1_target.state").fetchone()[0]


# --- the happy path the fault cases depend on ---------------------------------------------


def test_effect_and_its_ledger_row_commit_in_one_target_transaction(realm):
    binding = effect()
    ledger = executor().apply(binding)
    assert ledger_rows() == [("r1", "apply-1", "attempt-1", AFTER, ACTOR_ROLE)]
    assert target_state() == AFTER
    with psycopg.connect(DSN, autocommit=True) as conn:
        stored = conn.execute("SELECT digest FROM r1_target.effect_ledger").fetchone()[0]
    assert stored == ledger


# --- Step 6 fault case 1: two writers ----------------------------------------------------


def test_two_target_writers_cannot_apply_the_same_effect_twice(realm):
    """The session lock plus the row lock must let exactly one writer through."""
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def contender():
        barrier.wait(timeout=10)
        try:
            executor().apply(effect())
            return "applied"
        except TargetStateChanged:
            return "refused_stale_precondition"
        except MutationUnavailable as error:
            return f"refused:{error}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: contender(), range(2)))
    assert outcomes.count("applied") == 1, outcomes
    # The loser must fail with a classified reason, never a crash or a second effect.
    assert outcomes.count("refused_stale_precondition") == 1, outcomes
    assert len(ledger_rows()) == 1
    assert target_state() == AFTER


def test_a_second_writer_in_a_new_fence_epoch_still_refuses_the_moved_state(realm):
    """A fresh fence and a fresh epoch do not re-arm an effect whose precondition is gone."""
    executor().apply(effect())
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE r1_control.target_identity SET epoch=2")
    with pytest.raises(TargetStateChanged, match="expected_before"):
        executor(auth=authority(epoch="2")).apply(effect(epoch="2"))
    assert len(ledger_rows()) == 1
    assert target_state() == AFTER


def test_a_fence_epoch_the_target_does_not_recognize_is_refused(realm):
    """A fence the target has not adopted is not a valid fence, whatever the caller claims."""
    with pytest.raises(MutationUnavailable, match="scope or target changed"):
        executor(auth=authority(epoch="2")).apply(effect(epoch="2"))
    assert ledger_rows() == []
    assert target_state() == BEFORE


def test_the_database_refuses_a_repeat_even_if_the_precondition_is_forged(realm):
    """Defense in depth: one ledger row per (run, step, fence epoch), enforced by the index."""
    executor().apply(effect())
    with psycopg.connect(DSN, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.UniqueViolation):
            with conn.transaction():
                conn.execute("UPDATE r1_target.state SET digest=%s", (BEFORE,))
                conn.execute(
                    "INSERT INTO r1_target.effect_ledger(run_id,step,attempt_id,"
                    "definition_digest,expected_before,expected_after,fence_epoch,actor_role,"
                    "authorization_revision,applied_at,digest,target_id,namespace,incarnation,"
                    "plan_digest,approval_id) VALUES "
                    "('r1','apply-1','attempt-2',%s,%s,%s,1,session_user,1,now(),'d',"
                    "'pg','public','i1',%s,'approval-1')",
                    (STEP, BEFORE, AFTER, STEP),
                )


# --- Step 6 fault case 2: revocation serialized against the commit ------------------------


def test_a_revoke_committed_before_the_effect_is_seen_and_refused(realm):
    with psycopg.connect(DSN, autocommit=True) as conn:
        revoke_operator_grant(conn, "approval-1")
    with pytest.raises(PermissionError, match="revoked|rejected"):
        executor().apply(effect())
    assert ledger_rows() == []
    assert target_state() == BEFORE


def test_a_revoke_landing_mid_transaction_is_caught_by_the_finalizer(realm):
    """The real race: a revoke commits after the effect write but before before_commit.

    ``before_commit`` re-reads the grant under FOR SHARE, so it must observe the revoke and roll
    the effect back. Without that re-check the effect would commit under an authority that was
    already revoked, which is exactly the privileged-apply hazard Step 6 must not permit.
    """

    def revoke_midflight():
        with psycopg.connect(DSN, autocommit=True) as conn:
            revoke_operator_grant(conn, "approval-1")

    with pytest.raises(PermissionError, match="revoked|rejected"):
        executor().apply(effect(), before_commit_hook=revoke_midflight)
    assert ledger_rows() == []
    assert target_state() == BEFORE


def test_a_revoke_earlier_in_the_same_step_still_blocks_the_next_effect(realm):
    executor().apply(effect())
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute(
            "UPDATE r1_control.authority SET revoked=true,revision=revision+1 "
            "WHERE binding_id='approval-1'"
        )
    with pytest.raises(PermissionError, match="revoked|rejected"):
        executor().apply(effect(step="apply-2"))
    assert [row[1] for row in ledger_rows()] == ["apply-1"]


# --- Step 6 fault case 3: rollback -------------------------------------------------------


def test_a_rollback_after_the_state_write_leaves_neither_state_nor_ledger(realm):
    """The effect and its ledger row are atomic: a failure takes both back."""

    def explode():
        raise RuntimeError("injected failure after the effect write, before commit")

    with pytest.raises(RuntimeError, match="injected failure"):
        executor().apply(effect(), before_commit_hook=explode)
    assert target_state() == BEFORE
    assert ledger_rows() == []


def test_a_rollback_leaves_the_session_lock_releasable(realm):
    def explode():
        raise RuntimeError("injected failure")

    with pytest.raises(RuntimeError):
        executor().apply(effect(), before_commit_hook=explode)
    # A leaked session lock would deadlock every later effect on this key.
    assert executor().apply(effect(step="apply-3")) is not None


# --- Step 6 fault case 4: lost commit reply ----------------------------------------------


def test_a_lost_commit_reply_is_unknown_even_though_the_effect_is_durable(realm):
    """The commit really happened, but the caller cannot prove it, so it must not claim success.

    This is the honest shape of a lost acknowledgement: the effect is durable, the reply is gone,
    and reporting success would be a guess while reporting failure would invite a duplicate
    effect. The only correct answer is UNKNOWN, resolved only by a read-only observation.
    """

    class LoseReply(PostgresTargetExecutor):
        @contextmanager
        def _transaction(self, connection):
            with super()._transaction(connection) as conn:
                yield conn
            raise OperationalError("injected acknowledgement loss after the actual commit")

    with pytest.raises(TargetOutcomeUnknown, match="unproven"):
        LoseReply(DSN, authority(), identity=APPLY, session_lock_key=LOCK_KEY).apply(effect())

    # The effect did commit; the caller simply was not told.
    assert ledger_rows() == [("r1", "apply-1", "attempt-1", AFTER, ACTOR_ROLE)]
    assert target_state() == AFTER
    # And a blind retry must be impossible: the precondition has already moved.
    with pytest.raises(TargetStateChanged):
        executor().apply(effect())


def test_observation_resolves_a_durable_effect_read_only(realm):
    executor().apply(effect())
    binding = effect()
    observation = executor().observe(binding)
    assert observation.authoritative is True
    assert observation.committed is True and observation.aborted is False
    assert observation.receipt is not None
    assert observation.observed_state == AFTER
    # Observing must not write anything.
    assert ledger_rows() == [("r1", "apply-1", "attempt-1", AFTER, ACTOR_ROLE)]
    assert target_state() == AFTER


def test_observation_of_an_unfenced_absent_effect_stays_unknown(realm):
    observation = executor().observe(effect())
    assert observation.committed is False and observation.aborted is False
    assert observation.quiescent is False and observation.receipt is None
    assert observation.observed_state == BEFORE


def test_observation_of_a_drifted_target_stays_unknown(realm):
    """An unexpected digest proves nothing, so it must not resolve either way."""
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE r1_target.state SET digest=%s", (digest(b"something-else"),))
    observation = executor().observe(effect())
    assert observation.committed is False and observation.aborted is False
    assert observation.quiescent is False and observation.receipt is None


def test_observation_uses_a_read_only_transaction(realm):
    executor().apply(effect())

    def readonly_factory():
        conn = psycopg.connect(DSN, autocommit=True)
        conn.execute("SET ROLE r1_target_auditor")
        conn.execute("SET default_transaction_read_only = on")
        return conn

    assert executor(factory=readonly_factory).observe(effect()).committed
    assert len(ledger_rows()) == 1


# --- lock key derivation -----------------------------------------------------------------


def test_the_session_lock_key_is_stable_and_scoped_to_the_target(realm):
    first = default_session_lock_key(effect())
    assert first == default_session_lock_key(effect())
    assert first == default_session_lock_key(effect(step="apply-2", run="another"))
    assert 0 <= first < 2**60


# --- Step 6: append-only enforcement and scoped command roles ----------------------------


def test_the_effect_ledger_is_actually_append_only(realm):
    """006 only claimed this in a comment. It must now be impossible to rewrite history."""
    executor().apply(effect())
    for statement in (
        "UPDATE r1_target.effect_ledger SET expected_after=%s",
        "DELETE FROM r1_target.effect_ledger",
        "TRUNCATE r1_target.effect_ledger",
    ):
        with psycopg.connect(DSN, autocommit=True) as conn:
            with pytest.raises(psycopg.Error, match="append-only"):
                conn.execute(statement, (AFTER,) if "%s" in statement else ())
    assert len(ledger_rows()) == 1
    assert target_state() == AFTER


def test_the_control_outbox_is_append_only_too(realm):
    """The plan requires the outbox to be append-only alongside the critical events."""
    with psycopg.connect(DSN, autocommit=True) as conn:
        # The outbox is keyed to the audit trail, so add the event it relays.
        conn.execute(
            "INSERT INTO r1_audit.events(event_id,payload,digest) "
            "VALUES ('sha256:outbox-1','{}','sha256:outbox-1')"
        )
        conn.execute("INSERT INTO r1_control.outbox(event_id) VALUES ('sha256:outbox-1')")
        for statement in (
            "UPDATE r1_control.outbox SET event_id='sha256:tampered'",
            "DELETE FROM r1_control.outbox",
            "TRUNCATE r1_control.outbox",
        ):
            with pytest.raises(psycopg.Error, match="append-only"):
                conn.execute(statement)
        assert conn.execute("SELECT count(*) FROM r1_control.outbox").fetchone()[0] >= 1


def test_the_operator_role_has_no_table_write_rights_at_all(realm):
    """Scoped means scoped: the process role may not write, delete or truncate any table."""
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("GRANT r1_target_operator TO rem1_test")
        conn.execute("SET ROLE r1_target_operator")
        for statement in (
            "INSERT INTO r1_target.effect_ledger(run_id,step,attempt_id,definition_digest,"
            "expected_before,expected_after,fence_epoch,actor_role,authorization_revision,"
            "applied_at,digest) VALUES ('r','s','a','d','x','y',1,'z',1,now(),'q')",
            "UPDATE r1_target.state SET digest='sha256:forged'",
            "DELETE FROM r1_target.effect_ledger",
            "UPDATE r1_control.authority SET revoked=true",
            "INSERT INTO r1_audit.events(event_id,payload,digest) VALUES ('e','{}','e')",
        ):
            with pytest.raises(psycopg.Error, match="denied|permission"):
                conn.execute(statement)
        conn.execute("RESET ROLE")


def test_the_operator_role_may_invoke_only_the_scoped_effect_command(realm):
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("GRANT r1_target_operator TO rem1_test")
        conn.execute("SET ROLE r1_target_operator")
        digest_value = conn.execute(
            "SELECT r1_target.apply_effect('pg','public','i1','r1','apply-1','attempt-1',%s,%s,%s,"
            "1,'approval-1',%s)",
            (STEP, BEFORE, AFTER, STEP),
        ).fetchone()[0]
        conn.execute("RESET ROLE")
    assert digest_value.startswith("sha256:")
    assert ledger_rows() == [("r1", "apply-1", "attempt-1", AFTER, "rem1_test")]
    assert target_state() == AFTER


def test_the_auditor_role_can_read_the_ledger_and_nothing_else(realm):
    executor().apply(effect())
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("GRANT r1_target_auditor TO rem1_test")
        conn.execute("SET ROLE r1_target_auditor")
        assert conn.execute("SELECT count(*) FROM r1_target.effect_ledger").fetchone()[0] == 1
        for statement in (
            "INSERT INTO r1_target.effect_ledger(run_id,step,attempt_id,definition_digest,"
            "expected_before,expected_after,fence_epoch,actor_role,authorization_revision,"
            "applied_at,digest) VALUES ('r','s','a','d','x','y',1,'z',1,now(),'q')",
            "UPDATE r1_target.state SET digest='sha256:forged'",
            "SELECT r1_target.apply_effect('pg','public','i1','r','s','a','d','x','y',1,'a','p')",
        ):
            with pytest.raises(psycopg.Error, match="denied|permission"):
                conn.execute(statement)
        conn.execute("RESET ROLE")


def test_the_command_rejects_a_forged_or_self_referential_effect(realm):
    """Caller-selected input is validated; nothing caller-shaped reaches SQL."""
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("GRANT r1_target_operator TO rem1_test")
        conn.execute("SET ROLE r1_target_operator")
        for arguments, match in (
            (
                ("pg", "public", "i1", "r1", "s", "a", STEP, BEFORE, BEFORE, 1, "approval-1"),
                "invalid effect command",
            ),
            (
                (
                    "pg",
                    "public",
                    "i1",
                    "r1; DROP TABLE r1_target.state",
                    "s",
                    "a",
                    STEP,
                    BEFORE,
                    AFTER,
                    1,
                    "approval-1",
                ),
                "invalid effect command",
            ),
            (
                (
                    "pg",
                    "public",
                    "i1",
                    "r1",
                    "s",
                    "a",
                    STEP,
                    "not-a-digest",
                    AFTER,
                    1,
                    "approval-1",
                ),
                "invalid effect command",
            ),
            (
                ("pg", "public", "i1", "r1", "s", "a", STEP, BEFORE, AFTER, 0, "approval-1"),
                "invalid effect command",
            ),
            (
                (
                    "pg",
                    "public",
                    "i1",
                    "r1",
                    "s",
                    "a",
                    STEP,
                    digest(b"not-the-current-state"),
                    AFTER,
                    1,
                    "approval-1",
                ),
                "expected_before",
            ),
            (
                ("pg", "public", "i1", "r1", "s", "a", STEP, BEFORE, AFTER, 1, "no-such-approval"),
                "authority is not current",
            ),
        ):
            with pytest.raises(psycopg.Error, match=match):
                conn.execute(
                    "SELECT r1_target.apply_effect(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (*arguments, STEP),
                )
        conn.execute("RESET ROLE")
    assert target_state() == BEFORE
    assert ledger_rows() == []


def test_a_direct_command_call_cannot_bypass_a_revoked_authority(realm):
    """The scoped role can call the command without the Python guard, so the database itself
    must refuse. Otherwise revocation is only a convention the honest adapter follows."""
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("GRANT r1_target_operator TO rem1_test")
        conn.execute("UPDATE r1_control.authority SET revoked=true WHERE binding_id='approval-1'")
        conn.execute("SET ROLE r1_target_operator")
        with pytest.raises(psycopg.Error, match="authority is not current"):
            conn.execute(
                "SELECT r1_target.apply_effect('pg','public','i1','r1','apply-1',"
                "'attempt-1',%s,%s,%s,1,'approval-1',%s)",
                (STEP, BEFORE, AFTER, STEP),
            )
        conn.execute("RESET ROLE")
    assert target_state() == BEFORE
    assert ledger_rows() == []
    # The honest adapter refuses even earlier, in the guard, before any command is issued.
    with pytest.raises(PermissionError):
        executor().apply(effect())
    assert target_state() == BEFORE
    assert ledger_rows() == []


def test_a_revoke_landing_after_the_guard_read_is_caught_by_the_command(realm):
    """Defence in depth: even if a revoke commits after the guard has already validated,
    the scoped command re-reads the authority and refuses, and the adapter says so as a
    refusal rather than an unknown outcome."""

    class RevokeAfterGuardRead(PostgresTargetExecutor):
        def _write(self, connection, binding, before_commit_hook):
            with psycopg.connect(DSN, autocommit=True) as other:
                other.execute(
                    "UPDATE r1_control.authority SET revoked=true WHERE binding_id='approval-1'"
                )
            return super()._write(connection, binding, before_commit_hook)

    with pytest.raises(MutationUnavailable, match="authority is not current"):
        RevokeAfterGuardRead(DSN, authority(), identity=APPLY, session_lock_key=LOCK_KEY).apply(
            effect()
        )
    assert target_state() == BEFORE
    assert ledger_rows() == []


def test_a_direct_command_call_cannot_bypass_a_retargeted_or_stale_epoch(realm):
    """A grant for one target must not authorise another, and a moved epoch must not be reusable."""
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("GRANT r1_target_operator TO rem1_test")
        conn.execute("UPDATE r1_control.target_identity SET epoch=7")
        conn.execute("SET ROLE r1_target_operator")
        with pytest.raises(psycopg.Error, match="identity is not current"):
            conn.execute(
                "SELECT r1_target.apply_effect('pg','public','i1','r1','apply-1',"
                "'attempt-1',%s,%s,%s,1,'approval-1',%s)",
                (STEP, BEFORE, AFTER, STEP),
            )
        conn.execute("RESET ROLE")
    assert target_state() == BEFORE
    assert ledger_rows() == []


def test_a_grant_for_one_target_cannot_authorise_another(realm):
    """A cross-target escape is the failure that matters most here: an approval issued for one
    target must not let the command move a different target, or a different incarnation of it."""
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("GRANT r1_target_operator TO rem1_test")
        # A second, fully provisioned target that nothing in the approval refers to.
        conn.execute("INSERT INTO r1_control.target_identity VALUES ('other','public','i1',1)")
        conn.execute("INSERT INTO r1_target.state VALUES ('other','public','i1',%s)", (BEFORE,))
        # The live incarnation of the approved target is replaced by a newer one.
        conn.execute("INSERT INTO r1_target.state VALUES ('pg','public','i2',%s)", (BEFORE,))
        conn.execute(
            "UPDATE r1_control.target_identity SET incarnation='i2',epoch=2 "
            "WHERE target_id='pg' AND namespace='public'"
        )
        conn.execute("SET ROLE r1_target_operator")
        for target, namespace, incarnation in (
            ("other", "public", "i1"),
            ("pg", "other-ns", "i1"),
            ("pg", "public", "i2"),
        ):
            with pytest.raises(psycopg.Error, match="authority is not current"):
                conn.execute(
                    "SELECT r1_target.apply_effect(%s,%s,%s,'r1','apply-1','attempt-1',%s,%s,%s,"
                    "1,'approval-1',%s)",
                    (target, namespace, incarnation, STEP, BEFORE, AFTER, STEP),
                )
        conn.execute("RESET ROLE")
    for row in (("pg", "public", "i1"), ("other", "public", "i1"), ("pg", "public", "i2")):
        assert conn_row_state(row) == BEFORE
    assert ledger_rows() == []


def conn_row_state(row: tuple[str, str, str]) -> str:
    with psycopg.connect(DSN, autocommit=True) as conn:
        return conn.execute(
            "SELECT digest FROM r1_target.state WHERE target_id=%s "
            "AND namespace=%s AND incarnation=%s",
            row,
        ).fetchone()[0]


def test_a_non_apply_grant_cannot_authorise_an_effect(realm):
    """An 'adopt' approval is scoped to a different operation; it must not permit moving a state."""
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("GRANT r1_target_operator TO rem1_test")
        conn.execute(
            "UPDATE r1_control.authority SET purpose='adopt' WHERE binding_id='approval-1'"
        )
        conn.execute("SET ROLE r1_target_operator")
        with pytest.raises(psycopg.Error, match="authority is not current"):
            conn.execute(
                "SELECT r1_target.apply_effect('pg','public','i1','r1','apply-1',"
                "'attempt-1',%s,%s,%s,1,'approval-1',%s)",
                (STEP, BEFORE, AFTER, STEP),
            )
        conn.execute("RESET ROLE")
    assert target_state() == BEFORE
    assert ledger_rows() == []


def test_the_executor_refuses_a_configuration_that_cannot_scope_its_lock(realm):
    """A zero or absent lock key would silently stop serialising writers on the target."""
    for identity, key in (("", LOCK_KEY), (APPLY, 0), (APPLY, "not-an-int")):
        with pytest.raises(ValueError, match="session lock key"):
            PostgresTargetExecutor(DSN, authority(), identity=identity, session_lock_key=key)


def test_an_unexpected_database_error_is_reported_as_itself(realm):
    """Only two refusals are outcomes this adapter understands. Anything else must not be
    guessed into 'state changed' or 'unknown', because both invite the wrong recovery."""
    import psycopg

    class BrokenWrite(PostgresTargetExecutor):
        def _write(self, connection, binding, before_commit_hook):
            connection.execute("SELECT 1/0")

    with pytest.raises(psycopg.Error) as caught:
        BrokenWrite(DSN, authority(), identity=APPLY, session_lock_key=LOCK_KEY).apply(effect())
    assert not isinstance(caught.value, (TargetOutcomeUnknown, TargetStateChanged))
    assert target_state() == BEFORE
    assert ledger_rows() == []


def test_a_failed_unlock_does_not_mask_the_real_outcome(realm):
    """Losing the session lock on a dead connection must not overwrite a real verdict: a
    success has to stay a success, and the failure must not be reported as an unknown outcome."""

    class DeadUnlock(PostgresTargetExecutor):
        def _unlock(self, connection, key):
            raise psycopg.OperationalError("connection already closed")

    broken = DeadUnlock(DSN, authority(), identity=APPLY, session_lock_key=LOCK_KEY)
    assert broken.apply(effect()) is not None
    assert target_state() == AFTER
    assert ledger_rows() == [("r1", "apply-1", "attempt-1", AFTER, ACTOR_ROLE)]
    # The lock was released when the connection closed, so this is a clean precondition refusal
    # and not a deadlock.
    with pytest.raises(TargetStateChanged):
        executor().apply(effect())


def test_the_operator_role_can_reconcile_read_only(realm):
    """The unknown-outcome path needs the scoped role to read back what the command wrote."""
    executor().apply(effect())
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("GRANT r1_target_operator TO rem1_test")
        conn.execute("SET ROLE r1_target_operator")
        assert conn.execute("SELECT digest FROM r1_target.state").fetchone()[0] == AFTER
        assert conn.execute("SELECT count(*) FROM r1_target.effect_ledger").fetchone()[0] == 1
        conn.execute("RESET ROLE")
    assert executor().observe(effect()) is not None


def test_observer_does_not_report_abort_while_writer_is_uncommitted(realm):
    written, release = threading.Event(), threading.Event()

    def wait_before_commit():
        written.set()
        assert release.wait(5)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(executor().apply, effect(), before_commit_hook=wait_before_commit)
        try:
            assert written.wait(5)
            observation = executor().observe(effect())
            assert not observation.aborted
            assert not observation.quiescent
            assert observation.receipt is None
        finally:
            release.set()
        assert future.result(timeout=5)


@pytest.mark.parametrize("changes", [
    {"plan": digest(b"another-plan")},
    {"definition_digest": digest(b"another-definition")},
    {"fence_epoch": "2"},
    {"expected_before": digest(b"another-precondition")},
    {"expected_after": digest(b"another-postcondition")},
    {"target": TargetRef(target_id="another", namespace="public", incarnation="i1")},
])
def test_ledger_cannot_be_relabelled_as_a_different_effect(realm, changes):
    executor().apply(effect())
    observation = executor().observe(effect().model_copy(update=changes))
    assert not observation.committed
    assert not observation.authorization_verified
    assert observation.receipt is None


def test_direct_command_rechecks_revocation_at_commit(realm):
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("SET ROLE r1_target_operator")
        with pytest.raises(psycopg.Error) as refused:
            with conn.transaction():
                conn.execute(
                    "SELECT r1_target.apply_effect('pg','public','i1','r1','apply-1',"
                    "'attempt-1',%s,%s,%s,1,'approval-1',%s)", (STEP, BEFORE, AFTER, STEP),
                )
                with psycopg.connect(DSN, autocommit=True) as other:
                    revoke_operator_grant(other, "approval-1")
        assert refused.value.sqlstate == "R1T02"
    assert target_state() == BEFORE
    assert ledger_rows() == []


def test_ledger_existence_is_not_historical_authorization_proof(realm):
    executor().apply(effect())
    assert not executor().observe(effect()).authorization_verified


def test_newer_fence_and_exclusion_prove_abort_and_prevent_late_dispatch(realm):
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE r1_control.target_identity SET epoch=2")
    observation = executor().observe(effect())
    assert observation.aborted and observation.quiescent and observation.receipt
    with pytest.raises(MutationUnavailable):
        executor().apply(effect())
    with psycopg.connect(DSN, autocommit=True) as conn:
        with pytest.raises(psycopg.Error, match="epoch must advance"):
            conn.execute("UPDATE r1_control.target_identity SET epoch=1")
    assert ledger_rows() == []


@pytest.mark.parametrize("change", [
    "UPDATE r1_control.target_identity SET epoch=2",
    "UPDATE r1_control.authority SET plan_digest='sha256:changed'",
    "UPDATE r1_control.authority SET revision=2",
])
def test_direct_command_cannot_commit_after_its_native_binding_changes(realm, change):
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("SET ROLE r1_target_operator")
        with pytest.raises(psycopg.Error) as refused:
            with conn.transaction():
                conn.execute(
                    "SELECT r1_target.apply_effect('pg','public','i1','r1','apply-1',"
                    "'attempt-1',%s,%s,%s,1,'approval-1',%s)", (STEP, BEFORE, AFTER, STEP),
                )
                with psycopg.connect(DSN, autocommit=True) as other:
                    other.execute(change)
        assert refused.value.sqlstate == "R1T02"
    assert ledger_rows() == [] and target_state() == BEFORE


def test_native_finalizer_wins_before_later_revoke(realm):
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("SET ROLE r1_target_operator")
        with conn.transaction():
            conn.execute(
                "SELECT r1_target.apply_effect('pg','public','i1','r1','apply-1',"
                "'attempt-1',%s,%s,%s,1,'approval-1',%s)", (STEP, BEFORE, AFTER, STEP),
            )
            # Force the native constraint to finalize now; its SHARE locks persist to commit.
            conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
            with psycopg.connect(DSN, autocommit=True) as other:
                other.execute("SET lock_timeout='100ms'")
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    revoke_operator_grant(other, "approval-1")
    with psycopg.connect(DSN, autocommit=True) as other:
        revoke_operator_grant(other, "approval-1")
    assert target_state() == AFTER and len(ledger_rows()) == 1


def test_direct_command_cannot_weaken_commit_durability(realm):
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("SET ROLE r1_target_operator")
        with pytest.raises(psycopg.Error) as refused:
            with conn.transaction():
                conn.execute(
                    "SELECT r1_target.apply_effect('pg','public','i1','r1','apply-1',"
                    "'attempt-1',%s,%s,%s,1,'approval-1',%s)", (STEP, BEFORE, AFTER, STEP),
                )
                conn.execute("SET LOCAL synchronous_commit=off")
        assert refused.value.sqlstate == "R1T03"
    assert target_state() == BEFORE and ledger_rows() == []


@pytest.mark.parametrize("realm", [False], indirect=True)
def test_migration_keeps_legacy_receipts_without_inventing_binding_proof(realm):
    with psycopg.connect(DSN, autocommit=True) as conn:
        old_digest = conn.execute(
            "SELECT r1_target.apply_effect('pg','public','i1','r1','apply-1',"
            "'attempt-1',%s,%s,%s,1,'approval-1')", (STEP, BEFORE, AFTER),
        ).fetchone()[0]
        conn.execute(migration("008_target_reconciliation.sql"))
        stored = conn.execute("SELECT digest FROM r1_target.effect_ledger").fetchone()[0]
        assert stored == old_digest
    observed = executor().observe(effect())
    assert not observed.committed and observed.receipt is None


def test_direct_writer_and_observer_use_the_same_target_exclusion(realm):
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("SET ROLE r1_target_operator")
        with conn.transaction():
            conn.execute(
                "SELECT r1_target.apply_effect('pg','public','i1','r1','apply-1',"
                "'attempt-1',%s,%s,%s,1,'approval-1',%s)", (STEP, BEFORE, AFTER, STEP),
            )
            assert not executor().observe(effect()).quiescent
    assert executor().observe(effect()).committed


def test_arbitrary_lock_scope_cannot_split_target_exclusion(realm):
    with pytest.raises(ValueError, match="canonical target scope"):
        executor(lock=LOCK_KEY + 1).apply(effect())
    assert target_state() == BEFORE and ledger_rows() == []


def test_receipt_integrity_is_checked_before_promoting_a_commit(realm):
    executor().apply(effect())
    with psycopg.connect(DSN, autocommit=True) as conn:
        # Owner fault injection, not a right granted to the process role.
        conn.execute("ALTER TABLE r1_target.effect_ledger DISABLE TRIGGER immutable_effect_ledger")
        conn.execute("UPDATE r1_target.effect_ledger SET digest=%s", (digest(b"tampered"),))
        conn.execute("ALTER TABLE r1_target.effect_ledger ENABLE TRIGGER immutable_effect_ledger")
    observation = executor().observe(effect())
    assert not observation.committed and observation.receipt is None


def test_critical_audit_cannot_be_truncated(realm):
    with psycopg.connect(DSN, autocommit=True) as conn:
        with pytest.raises(psycopg.Error, match="immutable integrity record"):
            conn.execute("TRUNCATE r1_audit.events CASCADE")


@pytest.mark.parametrize("changes", [
    {"plan": digest(b"unapproved-plan")}, {"attempt_id": "other-attempt"}, {"fence_epoch": "2"},
])
def test_a_guard_cannot_be_reused_for_a_different_effect_binding(realm, changes):
    with pytest.raises(MutationUnavailable, match="authority binding"):
        executor().apply(effect().model_copy(update=changes))
    assert ledger_rows() == [] and target_state() == BEFORE


def test_expired_attempt_never_opens_a_new_target_session(realm):
    auth = authority()
    auth.deadline = time.monotonic() - 1

    def forbidden_connect():
        pytest.fail("expired attempt opened a target session")

    with pytest.raises(MutationUnavailable, match="deadline expired"):
        executor(auth=auth, factory=forbidden_connect).apply(effect())


def test_an_ambient_transaction_is_not_a_dedicated_target_session(realm):
    conn = psycopg.connect(DSN)
    with pytest.raises(MutationUnavailable, match="dedicated idle"):
        executor(factory=lambda: conn).apply(effect())
    assert conn.closed
    assert ledger_rows() == []


def test_target_lock_wait_is_bounded_by_the_original_attempt_deadline(realm):
    with psycopg.connect(DSN, autocommit=True) as holder:
        holder.execute("SELECT pg_advisory_lock(%s)", (LOCK_KEY,))
        auth = authority()
        started = time.monotonic()
        auth.deadline = started + 0.25
        with pytest.raises(psycopg.Error):
            executor(auth=auth).apply(effect())
        assert time.monotonic() - started < 2
    assert ledger_rows() == [] and target_state() == BEFORE
