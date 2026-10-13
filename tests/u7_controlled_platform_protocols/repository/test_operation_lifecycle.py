from __future__ import annotations

from uuid import uuid4

import pytest

from docsuri_ops.platform_control.errors import ControlError

pytestmark = pytest.mark.u7_repository


def key() -> str:
    return uuid4().hex


def prepare(harness, digest_seed="a"):
    target = harness.target()
    authority = harness.grant(target=target)
    digest = (digest_seed * 64)[:64]
    recorded = harness.evidence(target=target, input_hash=digest)
    return target, authority, digest, recorded


def begin(harness, target, authority, digest, recorded, *, key_=None, reference=None):
    return harness.runtime.begin_operation(
        actor=harness.actor,
        authority_id=authority,
        operation="platform.file.write",
        target=target,
        input_hash=digest,
        environment=harness.environment,
        evidence_id=recorded["evidenceId"],
        generation=recorded["generation"],
        idempotency_key=key_ or key(),
        effect_reference=reference or f"{target}/effect-0123456789abcdef.json",
    )


def test_full_lifecycle_reaches_completed_only_with_effect_evidence(harness):
    target, authority, digest, recorded = prepare(harness)
    binding = begin(harness, target, authority, digest, recorded)
    assert binding["operationState"] == "authorized"
    executing = harness.runtime.mark_executing(binding["operationId"])
    assert executing["operationState"] == "executing"
    settled = harness.runtime.settle_operation(
        operation_id=binding["operationId"],
        outcome="completed",
        disposition="applied",
        effect_refs=[f"{target}/effect-0123456789abcdef.json"],
    )
    assert settled["outcome"] == "completed"
    assert settled["effectDisposition"] == "applied"
    assert settled["reconciliationState"] == "not-applicable"


def test_completed_without_effect_evidence_is_refused(harness):
    target, authority, digest, recorded = prepare(harness, "b")
    binding = begin(harness, target, authority, digest, recorded)
    with pytest.raises(ControlError) as excinfo:
        harness.runtime.settle_operation(
            operation_id=binding["operationId"],
            outcome="completed",
            disposition="applied",
            effect_refs=[],
        )
    assert excinfo.value.code == "INVALID_INPUT"


def test_outcome_and_disposition_disagreement_is_refused(harness):
    target, authority, digest, recorded = prepare(harness, "c")
    binding = begin(harness, target, authority, digest, recorded)
    with pytest.raises(ControlError) as excinfo:
        harness.runtime.settle_operation(
            operation_id=binding["operationId"],
            outcome="completed",
            disposition="unknown",
            effect_refs=["x"],
        )
    assert excinfo.value.code == "INVALID_INPUT"


def test_failed_settlement_requires_not_applied(harness):
    target, authority, digest, recorded = prepare(harness, "d")
    binding = begin(harness, target, authority, digest, recorded)
    settled = harness.runtime.settle_operation(
        operation_id=binding["operationId"],
        outcome="failed",
        disposition="not-applied",
        effect_refs=[],
    )
    assert settled["outcome"] == "failed"
    assert settled["reconciliationState"] == "not-applicable"


def test_unknown_settlement_is_unresolved_and_never_auto_promoted(harness):
    target, authority, digest, recorded = prepare(harness, "e")
    binding = begin(harness, target, authority, digest, recorded)
    harness.runtime.mark_executing(binding["operationId"])
    settled = harness.runtime.settle_operation(
        operation_id=binding["operationId"],
        outcome="unknown",
        disposition="unknown",
        effect_refs=[],
    )
    assert settled["outcome"] == "unknown"
    assert settled["reconciliationState"] == "unresolved"
    # a second settlement cannot overwrite the terminal outcome
    with pytest.raises(ControlError):
        harness.runtime.settle_operation(
            operation_id=binding["operationId"],
            outcome="completed",
            disposition="applied",
            effect_refs=["x"],
        )


def test_replay_returns_the_recorded_receipt_without_a_second_effect(harness):
    target, authority, digest, recorded = prepare(harness, "f")
    idempotency_key = key()
    binding = begin(harness, target, authority, digest, recorded, key_=idempotency_key)
    harness.runtime.settle_operation(
        operation_id=binding["operationId"],
        outcome="failed",
        disposition="not-applied",
        effect_refs=[],
    )
    replay = begin(harness, target, authority, digest, recorded, key_=idempotency_key)
    assert replay["replayed"] is True
    assert replay["operationId"] == binding["operationId"]
    assert replay["outcome"] == "failed"


def test_changed_input_under_the_same_key_conflicts(harness):
    target, authority, digest, recorded = prepare(harness, "1")
    idempotency_key = key()
    begin(harness, target, authority, digest, recorded, key_=idempotency_key)
    changed = "2" * 64
    changed_evidence = harness.evidence(target=target, input_hash=changed)
    with pytest.raises(ControlError) as excinfo:
        begin(harness, target, authority, changed, changed_evidence, key_=idempotency_key)
    assert excinfo.value.code == "CONFLICT"


def test_missing_and_mismatched_evidence_are_refused_before_any_effect(harness):
    target, authority, digest, recorded = prepare(harness, "3")
    missing = str(uuid4())
    with pytest.raises(ControlError) as excinfo:
        harness.runtime.begin_operation(
            actor=harness.actor,
            authority_id=authority,
            operation="platform.file.write",
            target=target,
            input_hash=digest,
            environment=harness.environment,
            evidence_id=missing,
            generation=1,
            idempotency_key=key(),
            effect_reference="x",
        )
    assert excinfo.value.code == "POLICY_UNRESOLVED"
    other = harness.target()
    mismatched = harness.evidence(target=other, input_hash=digest)
    with pytest.raises(ControlError) as mismatch:
        begin(harness, target, authority, digest, mismatched)
    assert mismatch.value.code == "CONFLICT"
