from __future__ import annotations

from uuid import uuid4

import pytest

import supervise_docsuri_u7 as supervisor
from docsuri_ops.platform_control import enums, inventory

pytestmark = pytest.mark.u7_operations


def key() -> str:
    return uuid4().hex


def settled(harness, *, outcome="completed"):
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
        effect_reference=f"{target}/effect-0123456789abcdef.json",
    )
    harness.runtime.mark_executing(binding["operationId"])
    if outcome == "completed":
        harness.runtime.settle_operation(
            operation_id=binding["operationId"],
            outcome="completed",
            disposition="applied",
            effect_refs=[f"{target}/effect-0123456789abcdef.json"],
        )
    else:
        harness.runtime.settle_operation(
            operation_id=binding["operationId"],
            outcome="unknown",
            disposition="unknown",
            effect_refs=[],
        )
    return binding["operationId"], authority, target


def test_restart_preserves_receipts(harness):
    operation_id, authority, _target = settled(harness)
    before = harness.receipt(operation_id, authority)
    result = supervisor.restart()
    assert result["state"] == "running"
    after = harness.receipt(operation_id, authority)
    assert after == before


def test_backup_restore_round_trip(harness):
    settled(harness)
    backup = supervisor.backup()
    assert backup["receipts"] >= 1
    settled(harness)
    restored = supervisor.restore()
    assert restored["restoredReceipts"] >= backup["receipts"]


def test_rollback_keeps_receipts(harness):
    operation_id, authority, _target = settled(harness)
    result = supervisor.rollback()
    assert result["migrationMarker"] == "forward-compatible"
    assert result["receiptsAfter"]["completed"] >= result["receiptsBefore"]["completed"]
    assert harness.receipt(operation_id, authority)["outcome"] == "completed"


def test_unresolved_unknown_list_stays_visible_across_restart(harness):
    operation_id, authority, _target = settled(harness, outcome="unknown")
    assert operation_id in [item["operationId"] for item in harness.unresolved(authority)]
    supervisor.restart()
    assert operation_id in [item["operationId"] for item in harness.unresolved(authority)]


def test_supervisor_startup_promotes_an_over_deadline_in_flight_operation(harness, migrate):
    target = harness.target()
    authority = harness.grant(target=target)
    digest = "c" * 64
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
    harness.runtime.mark_executing(binding["operationId"])
    migrate.execute(
        "UPDATE platform_control.target_lease SET deadline_at = clock_timestamp() - interval '1 hour' WHERE target_id = %s",
        (target,),
    )
    migrate.commit()
    result = supervisor.restart()
    assert result["promotedOnStartup"] >= 1
    receipt = harness.receipt(binding["operationId"], authority)
    assert receipt["outcome"] == "unknown"
    assert binding["operationId"] in result["unresolvedOperations"]


def test_status_view_reports_local_receipts_only(harness):
    view = supervisor.status()
    assert view["state"] == "running"
    assert view["container"].startswith("docsuri-u7-")
    assert set(view["receiptCounts"]) >= {"completed", "failed", "unknown"}


def test_no_paid_or_cloud_dependency_is_configured(harness):
    # the retained inventory records cloud protocols as dispositions, not runtime paths
    recorded_only = [
        p
        for p in inventory.load_inventory().protocols
        if p.disposition != enums.DISPOSITION_RETAINED
    ]
    assert recorded_only and all(not p.is_executable for p in recorded_only)
    assert set(supervisor.COMMANDS) == {
        "status",
        "start",
        "stop",
        "restart",
        "backup",
        "restore",
        "rollback",
    }
    # the only external process the supervisor drives is the local container runtime
    assert supervisor.RESTORE_DB.startswith("docsuri_u7")
