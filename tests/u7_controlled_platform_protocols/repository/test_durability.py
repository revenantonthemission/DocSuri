from __future__ import annotations

from uuid import uuid4

import pytest

from docsuri_ops.platform_control.store import Store

pytestmark = pytest.mark.u7_repository


def key() -> str:
    return uuid4().hex


def bound_operation(harness, *, digest="a"):
    target = harness.target()
    authority = harness.grant(target=target)
    input_hash = (digest * 64)[:64]
    recorded = harness.evidence(target=target, input_hash=input_hash)
    binding = harness.runtime.begin_operation(
        actor=harness.actor,
        authority_id=authority,
        operation="platform.file.write",
        target=target,
        input_hash=input_hash,
        environment=harness.environment,
        evidence_id=recorded["evidenceId"],
        generation=recorded["generation"],
        idempotency_key=key(),
        effect_reference=f"{target}/effect-0123456789abcdef.json",
    )
    return target, input_hash, authority, binding


def test_receipt_binding_survives_a_restart(harness):
    target, input_hash, authority, binding = bound_operation(harness)
    harness.runtime.settle_operation(
        operation_id=binding["operationId"],
        outcome="completed",
        disposition="applied",
        effect_refs=[f"{target}/effect-0123456789abcdef.json"],
    )
    # a fresh store/connection stands in for a restarted operator process
    restarted = Store.runtime(harness.profile)
    receipt = restarted.read_receipt(harness.actor, authority, binding["operationId"])
    assert receipt["targetId"] == target
    assert receipt["inputHash"] == input_hash
    assert receipt["authorityRef"] == authority
    assert receipt["outcome"] == "completed"


def test_unresolved_unknowns_stay_visible_until_reconciled(harness):
    target, _input, authority, binding = bound_operation(harness, digest="b")
    harness.runtime.mark_executing(binding["operationId"])
    harness.runtime.settle_operation(
        operation_id=binding["operationId"],
        outcome="unknown",
        disposition="unknown",
        effect_refs=[],
    )
    unresolved = harness.unresolved(authority)
    assert binding["operationId"] in [item["operationId"] for item in unresolved]
    # a read never clears the unresolved list
    assert binding["operationId"] in [
        item["operationId"]
        for item in Store.runtime(harness.profile).list_unresolved(harness.actor, authority)
    ]


def test_status_counts_track_every_terminal_state(harness):
    target = harness.target()
    authority = harness.grant(target=target)
    counts = harness.counts(authority)
    assert set(counts) >= {"authorized", "executing", "completed", "failed", "unknown", "unresolved"}
    assert all(isinstance(value, int) for value in counts.values())


def test_replayed_receipt_revision_is_stable_across_reads(harness):
    target, _input, authority, binding = bound_operation(harness, digest="c")
    settled = harness.runtime.settle_operation(
        operation_id=binding["operationId"],
        outcome="failed",
        disposition="not-applied",
        effect_refs=[],
    )
    first = harness.receipt(binding["operationId"], authority)
    second = Store.runtime(harness.profile).read_receipt(
        harness.actor, authority, binding["operationId"]
    )
    assert first["revision"] == second["revision"] == settled["revision"]


def test_receipt_read_creates_no_operation(harness):
    target, _input, authority, binding = bound_operation(harness, digest="d")
    before = harness.counts(authority)
    harness.receipt(binding["operationId"], authority)
    after = harness.counts(authority)
    assert before == after
