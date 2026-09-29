"""The native commit guard receipt is issued from a live operator authority.

These run against the isolated REM1_TEST_PG_DSN database. They prove the whole Step 6 chain:
a digest-pinned frozen plan, an operator approval row in the database, a protected clock, and
the real :class:`PostgresOperatorAuthority` refusing an unplanned effect while admitting the
planned one -- with no effect performed.
"""

import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
import pytest

from docsuri_platform_integrity.contracts.codec import canonical, digest
from docsuri_platform_integrity.contracts.models import ValidityWindow
from docsuri_platform_integrity.deployment.capability import (
    ProbeSet,
    probe_native_commit_guard,
    receipt_from,
)
from docsuri_platform_integrity.deployment.operator_plan import read_frozen_plan
from docsuri_platform_integrity.deployment.receipt import (
    Capability,
    host_identity,
    verify_capability,
)

DSN = os.environ.get("REM1_TEST_PG_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="isolated REM1_TEST_PG_DSN required")
RELEASE = "r1-2026.09"
STEP = digest(b"registered-adopt-step")
APPLY = "registry:adopt"
EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
DAY = 86400 * 1_000_000
# A fixed authenticated instant. The database rows and the local binding window must both
# contain it, because check_binding requires them to agree with the clock exactly.
INSTANT = 1_700_000_000_000_000
# check_binding caps the authority window at 1800s, so the local binding window is exactly
# that wide and centred on the instant.
SPAN = 1800 * 1_000_000
HALF = SPAN // 2
MOMENT = datetime.fromtimestamp(INSTANT / 1_000_000, tz=UTC)


@pytest.fixture
def seeded():
    """A live authority row, target identity and frozen plan on the disposable database."""
    parsed = urlsplit(DSN)
    assert parsed.hostname == "127.0.0.1" and parsed.port == 15439
    root = Path(__file__).resolve().parents[1] / "migrations"
    plan = Path(__file__).parent / ".rem1-test-operator-plan.json"
    if plan.exists():
        os.chmod(plan, 0o600)
    plan.write_bytes(canonical({"release": RELEASE, "identities": {APPLY: STEP}}))
    os.chmod(plan, 0o400)
    # The approval names this exact plan, so the digest is computed before the row is written.
    plan_digest = digest(plan.read_bytes())
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS r1_control CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS r1_audit CASCADE")
        conn.execute("DROP SCHEMA IF EXISTS r1_target CASCADE")
        for name in ("001_control.sql", "002_run_protocol.sql", "003_verification_protocol.sql",
                      "004_operator_authority.sql", "005_reader_access.sql",
                      "006_target_effects.sql", "007_command_roles.sql",
                      "008_target_reconciliation.sql", "009_operator_role_binding.sql"):
            conn.execute((root / name).read_text())
        conn.execute("INSERT INTO r1_control.target_identity VALUES ('pg','public','i1',1)")
        conn.execute(
            "INSERT INTO r1_control.authority(binding_id,actor,purpose,target,incarnation,"
            "plan_digest,revision,valid_until,revoked,artifact_digest,policy_digest,namespace,"
            "valid_from) VALUES ('approval-1','operator','adopt','pg','i1',%s,1,%s,false,%s,%s,"
            "'public',%s)",
            (plan_digest, MOMENT + timedelta(minutes=15), STEP, STEP,
             MOMENT - timedelta(minutes=15)))
        conn.execute(
            "INSERT INTO r1_control.operator_role_bindings "
            "SELECT a.binding_id,a.revision,a.actor,session_user,p.oid "
            "FROM r1_control.authority a,pg_roles p WHERE p.rolname=session_user"
        )
    yield plan
    os.chmod(plan, 0o600)
    plan.unlink()


def live_authority(plan_path, *, purpose="adopt", actor_role="rem1_test", incarnation="i1",
                   deadline=30):
    """Build the real adapter from the pinned plan and the live approval row."""
    from docsuri_platform_integrity.adapters.operator_authority import PostgresOperatorAuthority
    from docsuri_platform_integrity.contracts.models import ApprovalBinding, TargetFence, TargetRef

    plan_digest = digest(plan_path.read_bytes())
    pinned = read_frozen_plan(plan_path, plan_digest, release=RELEASE)
    window = ValidityWindow(valid_from=str(INSTANT - HALF), valid_until=str(INSTANT + HALF))
    target = TargetRef(target_id="pg", namespace="public", incarnation=incarnation)
    binding = ApprovalBinding(approval_id="approval-1", actor="operator", purpose=purpose,
                              target=target, plan=plan_digest, artifact=STEP,
                              policy=STEP, validity=window, authority_revision="1")
    fence = TargetFence(target=target, epoch="1", holder="attempt-1", validity=window)
    return PostgresOperatorAuthority(
        binding, fence, actor_role=actor_role, definitions=dict(pinned.identities),
        clock=lambda: (INSTANT, INSTANT), deadline=time.monotonic() + deadline)


def test_live_guard_refuses_unplanned_and_admits_planned_without_any_effect(seeded):
    with psycopg.connect(DSN, autocommit=True) as connection:
        outcome = probe_native_commit_guard(
            live_authority(seeded), connection=connection, identity=APPLY, definition_digest=STEP)
    assert outcome.proven is True, outcome.reason
    assert outcome.artifact and outcome.evidence


def test_live_guard_refuses_when_the_operator_approval_is_revoked(seeded):
    """A revoked grant must not be able to produce a receipt."""
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE r1_control.authority SET revoked=true WHERE binding_id='approval-1'")
    with psycopg.connect(DSN, autocommit=True) as connection:
        outcome = probe_native_commit_guard(
            live_authority(seeded), connection=connection, identity=APPLY, definition_digest=STEP)
    # The plan boundary still refuses first, so the wired observation is what fails. A revoked
    # grant is a legitimate refusal (PermissionError), not an internal error.
    assert (outcome.proven, outcome.reason) == (False, "planned_effect_not_admitted")


def test_live_guard_refuses_when_the_caller_is_not_the_operator_role(seeded):
    with psycopg.connect(DSN, autocommit=True) as connection:
        outcome = probe_native_commit_guard(
            live_authority(seeded, actor_role="someone_else"), connection=connection,
            identity=APPLY, definition_digest=STEP)
    assert (outcome.proven, outcome.reason) == (False, "planned_effect_not_admitted")


def test_live_guard_receipt_verifies_under_the_normal_verifier(seeded):
    """The capability receipt is a normal receipt: same signer, same verifier, same rules."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from docsuri_platform_integrity.deployment.receipt import issue, trust_key

    with psycopg.connect(DSN, autocommit=True) as connection:
        outcome = probe_native_commit_guard(
            live_authority(seeded), connection=connection, identity=APPLY, definition_digest=STEP)
    assert outcome.proven is True
    host = host_identity()
    receipt = receipt_from(outcome, host=host, release=RELEASE, days=1)
    key = Ed25519PrivateKey.generate()
    envelope = issue(receipt, key_id="release-key-1", key=key)
    moment = int(time.time() * 1_000_000)
    trust = {"release-key-1": trust_key(
        "release-key-1", key.public_key(),
        validity=ValidityWindow(valid_from=str(moment - DAY), valid_until=str(moment + 30 * DAY)))}
    proven, reason = verify_capability(
        envelope, capability=Capability.NATIVE_COMMIT_GUARD, host=host, release=RELEASE,
        trust=trust, lower=moment, upper=moment)
    assert (proven, reason) == (True, "verified")
    # The artifact binds the exact identity set the guard was proven against. The plan file's
    # own digest is pinned separately, by planDigest in the issuer's reference document.
    assert receipt.artifact == digest(canonical({"identities": [APPLY]}))


def test_probe_set_reports_the_guard_unproven_without_a_connection(seeded):
    probes = ProbeSet(release=RELEASE, host=host_identity(), authority=live_authority(seeded),
                      guard_identity=APPLY, guard_definition_digest=STEP)
    outcomes = probes.run()
    assert outcomes[Capability.NATIVE_COMMIT_GUARD].reason == "not_configured"
    assert outcomes[Capability.NATIVE_COMMIT_GUARD].proven is False


def test_live_guard_performs_no_effect_and_leaves_no_transaction(seeded):
    """The probe must not leave a lock, an open transaction or a row behind."""
    with psycopg.connect(DSN, autocommit=True) as connection:
        probe_native_commit_guard(live_authority(seeded), connection=connection, identity=APPLY,
                                  definition_digest=STEP)
        from psycopg.pq import TransactionStatus
        assert connection.info.transaction_status == TransactionStatus.IDLE
    # The audit trail and outbox are where an effect would have to appear.
    with psycopg.connect(DSN, autocommit=True) as conn:
        assert conn.execute("SELECT count(*) FROM r1_audit.events").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM r1_control.outbox").fetchone()[0] == 0


def test_live_guard_refuses_when_the_database_names_a_different_plan(seeded):
    """The approval row must agree with the pinned plan, not merely exist."""
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("UPDATE r1_control.authority SET plan_digest=%s WHERE binding_id='approval-1'",
                     (digest(b"a-different-plan"),))
    with psycopg.connect(DSN, autocommit=True) as connection:
        outcome = probe_native_commit_guard(
            live_authority(seeded), connection=connection, identity=APPLY, definition_digest=STEP)
    assert (outcome.proven, outcome.reason) == (False, "planned_effect_not_admitted")


def test_live_guard_refuses_when_the_fence_targets_another_incarnation(seeded):
    """A fence for a different incarnation must not admit the planned effect."""
    with psycopg.connect(DSN, autocommit=True) as connection:
        outcome = probe_native_commit_guard(
            live_authority(seeded, incarnation="i2"), connection=connection, identity=APPLY,
            definition_digest=STEP)
    assert (outcome.proven, outcome.reason) == (False, "planned_effect_not_admitted")


def test_live_guard_refuses_when_the_authority_deadline_has_passed(seeded):
    """An expired decision deadline must refuse rather than admit."""
    with psycopg.connect(DSN, autocommit=True) as connection:
        outcome = probe_native_commit_guard(
            live_authority(seeded, deadline=-1), connection=connection, identity=APPLY,
            definition_digest=STEP)
    assert outcome.proven is False
    assert outcome.reason == "planned_effect_not_admitted"


def test_live_guard_never_issues_a_receipt_on_a_broken_connection(seeded):
    """Any adapter failure fails closed, so no receipt can be produced."""
    connection = psycopg.connect(DSN, autocommit=True)
    connection.close()
    outcome = probe_native_commit_guard(
        live_authority(seeded), connection=connection, identity=APPLY, definition_digest=STEP)
    assert outcome.proven is False
    # The dedicated idle autocommit precondition is checked before the plan boundary, so the
    # guard refuses for the wrong reason: the plan boundary was never exercised at all.
    assert outcome.reason == "guard_refused_for_the_wrong_reason"
