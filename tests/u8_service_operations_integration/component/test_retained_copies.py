"""Retained copies in the ledger (U8 plan Steps 29–30; BR9.12, BR9.17, BR4.10, BR9.7).

A copy is recorded before anything is written to it, with its backstop or your decided
date; it then only moves forward: completed, pending disposal, disposed on a receipt,
retired with its volume, or returned to service.
"""

from __future__ import annotations

import datetime as dt
from uuid import uuid4

import pytest

from backend.modules.operations.errors import OperationsError
from backend.modules.operations.retained_copies import (
    DECIDED_KINDS,
    RetainedCopies,
    is_open,
    receipt_facts,
)
from backend.u8_policy import SYNTHETIC_OPERATIONS
from tests.u8_service_operations_integration import recovery_flows as rf


@pytest.fixture
def copies(tmp_path, clock):
    ledger = rf.open_ledger(tmp_path, clock)
    yield RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
    ledger.close()


def disposal_receipt(clock, outcome="succeeded") -> dict:
    facts = rf.receipt("platform.copy.dispose", "copies", outcome, now=clock())
    return {**facts, "outcome": outcome}


def test_a_copy_is_recorded_with_its_backstop_before_anything_is_written(copies, clock):
    record = copies.record("dry-run-snapshot", "run:1", ["archives/a", "archives/a"],
                           staging_location="staging/a")
    assert record["locations"] == ["archives/a"] and record["stagingLocation"] == "staging/a"
    backstop = dt.timedelta(seconds=SYNTHETIC_OPERATIONS.dry_run_copy_backstop_seconds)
    assert copies.backstop("dry-run-snapshot", clock()) == clock() + backstop
    # The same identity recorded twice is the first record.
    again = copies.record("dry-run-snapshot", "run:1", ["archives/a"], copy_id=record["copyId"])
    assert again == record
    with pytest.raises(OperationsError):
        copies.backstop("anything-else", clock())


def test_the_decided_kinds_need_your_date_and_decision(copies, clock):
    assert DECIDED_KINDS == {"v1-final-snapshot", "v1-stores", "rolled-back-v2-database"}
    with pytest.raises(OperationsError) as missing:
        copies.record("v1-final-snapshot", "cutover:1", ["archives/final"])
    assert missing.value.code == "POLICY_UNRESOLVED"
    with pytest.raises(OperationsError):
        copies.record("dry-run-snapshot", "run:1", ["archives/a"], approval_id=uuid4())
    decided = clock() + dt.timedelta(days=30)
    record = copies.record("v1-final-snapshot", "cutover:1", ["archives/final"],
                           dispose_after=decided, approval_id=uuid4())
    assert record["disposalApprovalId"] and record["disposeAfter"].startswith(
        decided.strftime("%Y-%m-%d"))


def test_complete_pending_and_disposed_move_forward(copies, clock):
    record = copies.record("dry-run-snapshot", "run:1", ["archives/a"])
    done = copies.complete(record["copyId"], checksum="c" * 64, source_database_bytes=10,
                           staging_removed_at=clock())
    assert done["checksum"] == "c" * 64 and done["completedAt"] and done["stagingRemovedAt"]
    assert copies.complete(record["copyId"], checksum="d" * 64) == done
    pending = copies.disposal_pending(record["copyId"])
    assert "disposalPendingSince" in pending
    assert copies.disposal_pending(record["copyId"]) == pending
    with pytest.raises(OperationsError):
        copies.disposed(record["copyId"], disposal_receipt(clock, "failed"))
    disposed = copies.disposed(record["copyId"], disposal_receipt(clock))
    assert disposed["disposedAt"] and "disposalPendingSince" not in disposed
    assert copies.ledger.get("receipt-facts", disposed["disposalReceiptRef"])["operation"] == (
        "platform.copy.dispose")
    assert not is_open(disposed) and copies.undisposed() == []
    with pytest.raises(OperationsError):
        copies.complete(record["copyId"])
    assert copies.disposed(record["copyId"], disposal_receipt(clock)) == disposed


def test_due_lists_only_open_copies_past_their_point(copies, clock):
    first = copies.record("scratch-restore", "verification:1", ["database/x"])
    copies.record("rehearsal-database", "run:2", ["database/y"])
    assert copies.due() == []
    clock.advance(SYNTHETIC_OPERATIONS.scratch_restore_backstop_seconds + 1)
    assert [item["copyId"] for item in copies.due()] == [first["copyId"]]
    assert [item["kind"] for item in copies.undisposed("rehearsal-database")] == [
        "rehearsal-database"]


def test_retired_with_a_lost_volume_and_returned_to_service(copies, clock):
    snapshot = copies.record("dry-run-snapshot", "run:1", ["archives/a"])
    retired = copies.retire(snapshot["copyId"])
    assert retired["retiredWithVolumeAt"] and not is_open(retired)
    assert copies.retire(snapshot["copyId"]) == retired
    with pytest.raises(OperationsError):
        copies.disposed(snapshot["copyId"], disposal_receipt(clock))
    with pytest.raises(OperationsError):
        copies.returned_to_service(snapshot["copyId"])
    stores = copies.record("v1-stores", "cutover:1", ["database/v1"],
                           dispose_after=clock() + dt.timedelta(days=90), approval_id=uuid4())
    returned = copies.returned_to_service(stores["copyId"])
    assert returned["returnedToServiceAt"] and not is_open(returned)
    with pytest.raises(OperationsError) as missing:
        copies.complete(uuid4())
    assert missing.value.code == "NOT_FOUND"


def test_receipt_facts_carry_only_the_binding_facts(clock):
    receipt = {**rf.receipt(now=clock()), "effectRefs": ["x"], "authorityRef": "y"}
    facts = receipt_facts(receipt, now=clock())
    assert set(facts) == {"receiptId", "operationId", "operation", "targetId", "inputHash",
                          "outcome", "confirmedAt"}
    with pytest.raises(ValueError):
        receipt_facts({**receipt, "outcome": "maybe"}, now=clock())


# --- Step 65(d): each kind's backstop, and a re-dated copy -------------------------------

BACKSTOP_DAYS = {"dry-run-snapshot": 14, "import-database": 14, "rehearsal-database": 60,
                 "scratch-restore": 1, "v1-final-snapshot": 120, "v1-stores": 180,
                 "rolled-back-v2-database": 90}


def test_each_kinds_backstop_is_nfr3_12s(tmp_path, clock):
    from backend.u8_policy import PRODUCTION_OPERATIONS

    clock.now = dt.datetime(2026, 11, 10, 4, 0, tzinfo=dt.UTC)
    ledger = rf.open_ledger(tmp_path, clock)
    try:
        for policy in (PRODUCTION_OPERATIONS, SYNTHETIC_OPERATIONS):
            copies = RetainedCopies(ledger, policy, clock=clock)
            decided = clock() + dt.timedelta(days=30)
            for kind, days in BACKSTOP_DAYS.items():
                options = ({"dispose_after": decided, "approval_id": uuid4()}
                           if kind in DECIDED_KINDS else {})
                record = copies.record(kind, f"source:{kind}", [f"places/{kind}"], **options)
                assert copies.backstop_of(record) == clock() + dt.timedelta(days=days), kind
                expected = decided if kind in DECIDED_KINDS else clock() + dt.timedelta(
                    days=days)
                assert record["disposeAfter"] == rf.utc_text(expected), kind
                if kind in DECIDED_KINDS:
                    with pytest.raises(OperationsError) as unresolved:
                        copies.record(kind, f"source:{kind}", [f"places/{kind}"])
                    assert unresolved.value.code == "POLICY_UNRESOLVED"
    finally:
        ledger.close()


def test_a_redated_copy_cites_its_decision(copies, clock):
    clock.now = dt.datetime(2026, 11, 10, 4, 0, tzinfo=dt.UTC)
    first = rf.approval_record(copies.ledger, "disposal-date", "copy:1", now=clock())
    stores = copies.record("v1-stores", "cutover:1", ["v1-stores/papers"],
                           dispose_after=clock() + dt.timedelta(days=90),
                           approval_id=first["approvalId"])
    later = rf.approval_record(copies.ledger, "disposal-date", "copy:1", now=clock())
    moved = copies.redated(stores["copyId"], dispose_after=clock() + dt.timedelta(days=120),
                           approval=later)
    assert moved["disposeAfter"] == rf.utc_text(clock() + dt.timedelta(days=120))
    assert moved["disposalApprovalId"] == later["approvalId"]
    assert moved["redateReceiptRef"] == later["operatorReceiptRef"]
    with pytest.raises(OperationsError) as past:
        copies.redated(stores["copyId"], dispose_after=clock() + dt.timedelta(days=181),
                       approval=later)
    assert past.value.code == "INVALID_INPUT"
    snapshot = copies.record("dry-run-snapshot", "run:2", ["archives/b"])
    with pytest.raises(OperationsError) as event:
        copies.redated(snapshot["copyId"], dispose_after=clock(), approval=later)
    assert event.value.code == "INVALID_INPUT"
    final = copies.record("v1-final-snapshot", "cutover:1", ["archives/final"],
                          dispose_after=clock() + dt.timedelta(days=30),
                          approval_id=first["approvalId"])
    copies.retire(final["copyId"])
    with pytest.raises(OperationsError) as closed:
        copies.redated(final["copyId"], dispose_after=clock(), approval=later)
    assert closed.value.code == "CONFLICT"
    sized = copies.complete(snapshot["copyId"], checksum="a" * 64,
                            part_sizes={"index": 10, "objects": 20})
    assert sized["partSizes"] == {"index": 10, "objects": 20} and sized["checksum"] == "a" * 64
