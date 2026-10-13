from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from docsuri_ops.platform_control.errors import ControlError
from docsuri_ops.platform_control.reconciler import reconcile_unknown

pytestmark = pytest.mark.u7_repository


def key() -> str:
    return uuid4().hex


def settled_unknown(harness, *, reference: str):
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
    harness.runtime.mark_executing(binding["operationId"])
    harness.runtime.settle_operation(
        operation_id=binding["operationId"],
        outcome="unknown",
        disposition="unknown",
        effect_refs=[],
    )
    return target, authority, binding["operationId"]


def reconcile(harness, authority, operation_id):
    return reconcile_unknown(
        harness.runtime, harness.profile.target_root, operation_id, harness.actor, authority
    )


def test_unknown_with_a_present_effect_reconciles_applied(harness):
    reference = f"recon-{uuid4().hex[:8]}/effect-0123456789abcdef.json"
    target, authority, operation_id = settled_unknown(harness, reference=reference)
    path = Path(harness.profile.target_root) / reference
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("applied")
    reconciled = reconcile(harness, authority, operation_id)
    assert reconciled["reconciliationState"] == "reconciled-applied"
    # reconciliation never changes the operation's own outcome
    assert reconciled["operationState"] == "unknown"


def test_unknown_with_an_absent_effect_reconciles_not_applied(harness):
    reference = f"absent-{uuid4().hex[:8]}/effect-0123456789abcdef.json"
    target, authority, operation_id = settled_unknown(harness, reference=reference)
    reconciled = reconcile(harness, authority, operation_id)
    assert reconciled["reconciliationState"] == "reconciled-not-applied"


def test_escaping_reference_stays_unresolved(harness):
    target, authority, operation_id = settled_unknown(harness, reference="../../etc/passwd")
    reconciled = reconcile(harness, authority, operation_id)
    assert reconciled["reconciliationState"] == "unresolved"


def test_reconciliation_of_a_settled_receipt_is_refused(harness):
    target = harness.target()
    authority = harness.grant(target=target)
    digest = "b" * 64
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
        effect_reference=f"{target}/effect-0123456789abcdef.json",
    )
    harness.runtime.settle_operation(
        operation_id=binding["operationId"],
        outcome="completed",
        disposition="applied",
        effect_refs=[f"{target}/effect-0123456789abcdef.json"],
    )
    with pytest.raises(ControlError) as excinfo:
        harness.runtime.reconcile_receipt(
            operation_id=binding["operationId"], applied=True, evidence=["x"]
        )
    assert excinfo.value.code == "CONFLICT"


def test_reconciliation_does_not_execute_a_second_effect(harness):
    reference = f"no-dup-{uuid4().hex[:8]}/effect-0123456789abcdef.json"
    target, authority, operation_id = settled_unknown(harness, reference=reference)
    before = harness.counts(authority)
    reconcile(harness, authority, operation_id)
    reconcile(harness, authority, operation_id)  # idempotent read
    after = harness.counts(authority)
    assert after["completed"] == before["completed"]
    assert after["executing"] == 0
