"""Actual PG source-revocation ordering; clock/identity provisioning remains an operator gate."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from urllib.parse import urlsplit

import psycopg
import pytest

from docsuri_platform_integrity.adapters.authority import MutationUnavailable
from docsuri_platform_integrity.adapters.clock import ClockUnavailable, unavailable_clock
from docsuri_platform_integrity.adapters.operator_authority import (
    PostgresOperatorAuthority,
    revoke_operator_grant,
)
from docsuri_platform_integrity.contracts.codec import digest
from docsuri_platform_integrity.contracts.models import (
    ApprovalBinding,
    TargetFence,
    TargetRef,
    ValidityWindow,
)

DSN = os.environ.get("REM1_TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="isolated REM1_TEST_PG_DSN required")
D = digest(b"registered-step")
TARGET = TargetRef(target_id="fixture", namespace="public", incarnation="i1")
WINDOW = ValidityWindow(valid_from="0", valid_until="10000000")


@pytest.fixture
def authority():
    parsed = urlsplit(DSN)
    assert parsed.hostname == "127.0.0.1" and parsed.port == 15439 and parsed.path == "/rem1_test"
    root = Path(__file__).resolve().parents[1] / "migrations"
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS r1_control CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS r1_audit CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS r1_target CASCADE")
        for name in (
            "001_control.sql", "002_run_protocol.sql", "003_verification_protocol.sql",
            "004_operator_authority.sql",
            "005_reader_access.sql", "006_target_effects.sql", "007_command_roles.sql",
            "008_target_reconciliation.sql", "009_operator_role_binding.sql",
        ):
            conn.execute((root / name).read_text())
        conn.execute("DROP TABLE IF EXISTS public.rem1_effect_fixture")
        conn.execute("CREATE TABLE public.rem1_effect_fixture(id integer PRIMARY KEY)")
        conn.execute("INSERT INTO r1_control.target_identity VALUES ('fixture','public','i1',1)")
        epoch = datetime(1970, 1, 1, tzinfo=UTC)
        conn.execute(
            "INSERT INTO r1_control.authority(binding_id,actor,purpose,target,incarnation,"
            "plan_digest,revision,valid_until,revoked,artifact_digest,policy_digest,namespace,"
            "valid_from) "
            "VALUES ('approval','operator','apply','fixture','i1',%s,1,%s,false,%s,%s,'public',%s)",
            (D, epoch + timedelta(seconds=10), D, D, epoch),
        )
        conn.execute(
            "INSERT INTO r1_control.operator_role_bindings "
            "SELECT a.binding_id,a.revision,a.actor,session_user,p.oid "
            "FROM r1_control.authority a,pg_roles p WHERE p.rolname=session_user"
        )
    binding = ApprovalBinding(approval_id="approval", actor="operator", purpose="apply",
                              target=TARGET, plan=D, artifact=D, policy=D, validity=WINDOW,
                              authority_revision="1")
    fence = TargetFence(target=TARGET, epoch="1", holder="attempt", validity=WINDOW)
    return PostgresOperatorAuthority(
        binding, fence, actor_role="rem1_test", definitions={"step": D},
        clock=lambda: (100, 100), deadline=time.monotonic() + 30,
    )


def count_effects():
    with psycopg.connect(DSN) as conn:
        return conn.execute("SELECT count(*) FROM public.rem1_effect_fixture").fetchone()[0]


def test_revocation_during_work_aborts_before_finalization(authority):
    with psycopg.connect(DSN, autocommit=True) as worker:
        with pytest.raises(PermissionError):
            with authority.guard(worker, "step", D) as guard:
                with worker.transaction():
                    worker.execute("INSERT INTO public.rem1_effect_fixture VALUES (1)")
                    with psycopg.connect(DSN, autocommit=True) as revoker:
                        revoke_operator_grant(revoker, "approval")
                    guard.before_commit()
    assert count_effects() == 0


def test_finalization_winner_commits_before_revocation_completes(authority):
    started = Event()

    def revoke():
        with psycopg.connect(DSN, autocommit=True) as conn:
            started.set()
            revoke_operator_grant(conn, "approval")

    with ThreadPoolExecutor(max_workers=1) as pool:
        with psycopg.connect(DSN, autocommit=True) as worker:
            with authority.guard(worker, "step", D) as guard:
                with worker.transaction():
                    worker.execute("INSERT INTO public.rem1_effect_fixture VALUES (1)")
                    guard.before_commit()
                    pending = pool.submit(revoke)
                    assert started.wait(3)
                    assert not pending.done()
            pending.result(timeout=5)
    assert count_effects() == 1


def test_restored_target_epoch_refuses_old_fence(authority):
    with psycopg.connect(DSN) as conn:
        conn.execute("UPDATE r1_control.target_identity SET epoch=2")
    with psycopg.connect(DSN, autocommit=True) as worker:
        with pytest.raises(MutationUnavailable):
            with authority.guard(worker, "step", D):
                pytest.fail("old fence was accepted")


def test_missing_authenticated_clock_never_uses_database_time(authority):
    authority.clock = unavailable_clock
    with psycopg.connect(DSN, autocommit=True) as worker:
        with pytest.raises(ClockUnavailable):
            with authority.guard(worker, "step", D):
                pytest.fail("unavailable clock was accepted")


@pytest.mark.parametrize("purpose", ["read", "verify", "backup", "adopt"])
def test_matching_grant_for_another_purpose_cannot_apply(authority, purpose):
    authority.binding = authority.binding.model_copy(update={"purpose": purpose})
    with psycopg.connect(DSN, autocommit=True) as worker:
        worker.execute("UPDATE r1_control.authority SET purpose=%s", (purpose,))
        with pytest.raises(PermissionError):
            with authority.guard(worker, "step", D) as guard:
                with worker.transaction():
                    worker.execute("INSERT INTO public.rem1_effect_fixture VALUES (1)")
                    guard.before_commit()
    assert count_effects() == 0


def test_adoption_requires_its_own_purpose(authority):
    authority.definitions = {"registry:adopt": D}
    with psycopg.connect(DSN, autocommit=True) as worker:
        with pytest.raises(PermissionError):
            with authority.guard(worker, "registry:adopt", D):
                pytest.fail("apply grant was accepted for adoption")
        worker.execute("UPDATE r1_control.authority SET purpose='adopt'")
        authority.binding = authority.binding.model_copy(update={"purpose": "adopt"})
        with authority.guard(worker, "registry:adopt", D) as guard:
            with worker.transaction():
                worker.execute("INSERT INTO public.rem1_effect_fixture VALUES (1)")
                guard.before_commit()
    assert count_effects() == 1
