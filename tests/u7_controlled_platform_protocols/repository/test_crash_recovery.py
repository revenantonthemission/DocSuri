from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from docsuri_ops.platform_control.reconciler import reconcile_unknown

pytestmark = pytest.mark.u7_repository


def key() -> str:
    return uuid4().hex


def bound(harness, *, reference: str):
    target = harness.target()
    authority = harness.grant(target=target)
    digest = "a" * 64
    recorded = harness.evidence(target=target, input_hash=digest)
    binding = harness.runtime.begin_operation(
        actor=harness.actor,
        authority_id=authority,
        operation="platform.file.write",
        target=target,
        input_hash=digest,
        environment=harness.environment,
        evidence_id=recorded["evidenceId"],
        generation=recorded["generation"],
        idempotency_key=key(),
        effect_reference=reference,
    )
    return target, authority, binding


def reconcile(harness, authority, operation_id):
    return reconcile_unknown(
        harness.runtime, harness.profile.target_root, operation_id, harness.actor, authority
    )


def backdate(harness, migrate, target):
    migrate.execute(
        "UPDATE platform_control.target_lease SET deadline_at = clock_timestamp() - interval '1 hour' WHERE target_id = %s",
        (target,),
    )
    migrate.commit()


def test_crash_before_effect_leaves_no_orphan_effect(harness, migrate):
    reference = f"crash-before-{uuid4().hex[:8]}/effect-0123456789abcdef.json"
    target, authority, binding = bound(harness, reference=reference)
    assert not (Path(harness.profile.target_root) / reference).exists()
    backdate(harness, migrate, target)
    harness.runtime.promote_in_flight()
    receipt = reconcile(harness, authority, binding["operationId"])
    assert receipt["operationState"] == "unknown"
    assert receipt["reconciliationState"] == "reconciled-not-applied"
    assert harness.provisioner.provision_target(target)["appliedCount"] == 0


def test_crash_after_effect_reconciles_applied_without_double_counting(harness, migrate):
    reference = f"crash-after-{uuid4().hex[:8]}/effect-0123456789abcdef.json"
    target, authority, binding = bound(harness, reference=reference)
    path = Path(harness.profile.target_root) / reference
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("applied")
    backdate(harness, migrate, target)
    harness.runtime.promote_in_flight()
    receipt = reconcile(harness, authority, binding["operationId"])
    assert receipt["reconciliationState"] == "reconciled-applied"
    # reconciliation proves truth; it does not re-run the effect or re-count it
    assert harness.provisioner.provision_target(target)["appliedCount"] == 0


def test_promotion_never_reports_success_on_liveness_alone(harness, migrate):
    reference = f"liveness-{uuid4().hex[:8]}/effect-0123456789abcdef.json"
    target, authority, binding = bound(harness, reference=reference)
    harness.runtime.mark_executing(binding["operationId"])
    backdate(harness, migrate, target)
    harness.runtime.promote_in_flight()
    receipt = harness.receipt(binding["operationId"], authority)
    assert receipt["outcome"] == "unknown"
    assert receipt["outcome"] != "completed"


def test_promotion_releases_the_lease_for_a_new_operation(harness, migrate):
    reference = f"reclaim-{uuid4().hex[:8]}/effect-0123456789abcdef.json"
    target, _authority, binding = bound(harness, reference=reference)
    backdate(harness, migrate, target)
    harness.runtime.promote_in_flight()
    authority = harness.grant(target=target)
    digest = "b" * 64
    recorded = harness.evidence(target=target, input_hash=digest)
    fresh = harness.runtime.begin_operation(
        actor=harness.actor,
        authority_id=authority,
        operation="platform.file.write",
        target=target,
        input_hash=digest,
        environment=harness.environment,
        evidence_id=recorded["evidenceId"],
        generation=recorded["generation"],
        idempotency_key=key(),
        effect_reference=f"{target}/effect-fedcba9876543210.json",
    )
    assert fresh["operationState"] == "authorized"
    assert fresh["operationId"] != binding["operationId"]
