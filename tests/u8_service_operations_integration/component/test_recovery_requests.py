"""The RecoveryRequest machine in the ledger (U8 plan Step 30; BR4.1–BR4.4, BR4.7, BR4.9,
functional-spec.md § State machine — RecoveryRequest).

The component runs over a real ledger in the test's own folder; the records a request
reads (BackupSets, your decisions, the cutover, retained copies) are appended to it with
their receipt facts, as the procedures and the decision operation append them.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.modules.operations.errors import OperationsError
from backend.modules.operations.ledger import utc_text
from backend.modules.operations.recovery import (
    MAX_EVIDENCE,
    RecoveryRequests,
    bounded_evidence,
    conflicting,
    idempotency_key,
)
from backend.modules.operations.retained_copies import RetainedCopies
from backend.u8_policy import SYNTHETIC_OPERATIONS
from tests.u8_service_operations_integration import recovery_flows as rf

ADMIN = str(uuid4())


@pytest.fixture
def ledger(tmp_path, clock):
    value = rf.open_ledger(tmp_path, clock)
    yield value
    value.close()


@pytest.fixture
def mfa():
    """AccountAccess's answer to whether the administrator's second factor is current."""
    state = {"current": True}
    return state


@pytest.fixture
def requests(ledger, clock, mfa):
    return RecoveryRequests(ledger, SYNTHETIC_OPERATIONS, clock=clock,
                            mfa_current=lambda account, at: mfa["current"])


def submit(requests, clock, operation="backup.create", *, origin="schedule", target=None,
           environment="live", submission=None, expected=None):
    options = {}
    if origin == "administrator":
        options = {"requested_by": ADMIN, "mfa_verified_at": utc_text(clock())}
    target = target or ("docsuri_u8" if operation == "backup.create" else None)
    if expected is None:
        expected = (requests.backup_revision(environment) if operation == "backup.create"
                    else requests.ledger.revision("backup-set", target))
    return requests.request(origin=origin, operation=operation, environment=environment,
                            target_id=target, expected_revision=expected,
                            submission_id=submission or uuid4(), **options)


def production(requests, ledger, clock, backup, *, predecessor=None, decision="approved"):
    request = submit(requests, clock, "restore.production", origin="administrator",
                     target=backup["backupId"])
    approval = rf.approval_record(ledger, "production-restore", request["recoveryRequestId"],
                                  now=clock(), decision=decision)
    return request, approval


# --- 1. every row of the machine ----------------------------------------------------------


def test_offered_operations_and_their_origins(requests, clock):
    with pytest.raises(OperationsError) as refused:
        submit(requests, clock, "restore.everything", target="x", expected=0)
    assert refused.value.code == "INVALID_INPUT"
    assert refused.value.current == {"reasonKey": "not-offered"}
    # The schedule requests only the first two (BR4.2).
    with pytest.raises(OperationsError) as scheduled:
        submit(requests, clock, "restore.production", target="x", expected=0)
    assert scheduled.value.code == "FORBIDDEN"


def test_an_administrator_needs_a_current_second_factor(requests, clock, mfa):
    mfa["current"] = False
    with pytest.raises(OperationsError) as refused:
        submit(requests, clock, origin="administrator")
    assert refused.value.current == {"reasonKey": "mfa-not-current"}
    unchecked = RecoveryRequests(requests.ledger, SYNTHETIC_OPERATIONS, clock=clock)
    with pytest.raises(OperationsError):
        submit(unchecked, clock, origin="administrator")


def test_a_backup_runs_requested_awaiting_running_verifying_succeeded(requests, clock):
    request = submit(requests, clock)
    assert request["state"] == "requested" and request["revision"] == 1
    admitted = requests.admit(request["recoveryRequestId"])
    assert admitted["state"] == "awaiting-operator"
    # Admitting twice changes nothing.
    assert requests.admit(request["recoveryRequestId"]) == admitted
    running = requests.start(request["recoveryRequestId"])
    assert running["state"] == "running"
    assert requests.start(request["recoveryRequestId"]) == running
    requests.advance(request["recoveryRequestId"], "verifying", allowed_from=("running",))
    done = requests.advance(request["recoveryRequestId"], "succeeded",
                            allowed_from=("verifying",))
    assert done["state"] == "succeeded" and done["revision"] == 5
    status = requests.status(request["recoveryRequestId"])
    assert status["state"] == "succeeded" and status["revision"] == "5"
    assert set(status) == {"recoveryRequestId", "revision", "environment", "origin",
                           "operation", "state", "evidenceRefs", "createdAt", "updatedAt"}
    with pytest.raises(OperationsError):
        requests.cancel(request["recoveryRequestId"])
    with pytest.raises(OperationsError):
        requests.record(request["recoveryRequestId"], evidence=["late"])


def test_waiting_requests_are_cancelled_refused_or_expire(requests, ledger, clock):
    cancelled = submit(requests, clock)
    assert requests.cancel(cancelled["recoveryRequestId"])["state"] == "cancelled"
    awaiting = submit(requests, clock)
    requests.admit(awaiting["recoveryRequestId"])
    assert requests.cancel(awaiting["recoveryRequestId"])["state"] == "cancelled"
    refused = submit(requests, clock)
    assert requests.refuse(refused["recoveryRequestId"], "volume-check-failed")[
        "evidenceRefs"] == ["refused:volume-check-failed"]
    # A waiting request expires after the start bound (the housekeeping lane).
    late = submit(requests, clock)
    clock.advance(SYNTHETIC_OPERATIONS.recovery_start_seconds + 1)
    assert requests.expire_due() == [late["recoveryRequestId"]]
    assert requests.get(late["recoveryRequestId"])["state"] == "expired"
    assert requests.expire_due() == []
    # One admitted and never started expires at its start too.
    stale = submit(requests, clock)
    requests.admit(stale["recoveryRequestId"])
    clock.advance(SYNTHETIC_OPERATIONS.recovery_start_seconds + 1)
    assert requests.start(stale["recoveryRequestId"])["state"] == "expired"
    requested = submit(requests, clock)
    clock.advance(SYNTHETIC_OPERATIONS.recovery_start_seconds + 1)
    assert requests.admit(requested["recoveryRequestId"])["state"] == "expired"


def test_a_production_restore_needs_your_decision_and_a_passed_set(requests, ledger, clock):
    backup = rf.set_record(ledger, now=clock())
    request = submit(requests, clock, "restore.production", origin="administrator",
                     target=backup["backupId"])
    with pytest.raises(OperationsError) as waiting:
        requests.admit(request["recoveryRequestId"])
    assert waiting.value.code == "POLICY_UNRESOLVED"
    assert requests.get(request["recoveryRequestId"])["state"] == "requested"
    # A decision for another subject is refused.
    other = rf.approval_record(ledger, "production-restore", str(uuid4()), now=clock())
    with pytest.raises(OperationsError) as wrong:
        requests.admit(request["recoveryRequestId"], approval_id=other["approvalId"])
    assert wrong.value.code == "FORBIDDEN"
    declined = rf.approval_record(ledger, "production-restore", request["recoveryRequestId"],
                                  now=clock(), decision="declined")
    assert requests.admit(request["recoveryRequestId"],
                          approval_id=declined["approvalId"])["state"] == "refused"
    failed = rf.set_record(ledger, integrity="failed", now=clock())
    unpassed, approval = production(requests, ledger, clock, failed)
    assert requests.admit(unpassed["recoveryRequestId"],
                          approval_id=approval["approvalId"])["state"] == "refused"
    restore, approval = production(requests, ledger, clock, backup)
    admitted = requests.admit(restore["recoveryRequestId"], approval_id=approval["approvalId"])
    assert admitted["state"] == "awaiting-operator"
    assert admitted["approvalId"] == approval["approvalId"]


def test_a_production_restore_runs_through_held_unknown_and_post_restore(requests, ledger,
                                                                          clock):
    backup = rf.set_record(ledger, now=clock())
    restore, approval = production(requests, ledger, clock, backup)
    identity = restore["recoveryRequestId"]
    requests.admit(identity, approval_id=approval["approvalId"])
    requests.start(identity)
    # An unknown outcome is settled by its receipt, as the matching row.
    assert requests.outcome_unknown(identity, evidence=["pending:x"])["state"] == "unknown"
    with pytest.raises(OperationsError):
        requests.settle_unknown(identity, "succeeded")
    assert requests.settle_unknown(identity, "verifying")["state"] == "verifying"
    with pytest.raises(OperationsError) as early:
        requests.authorize_start(identity)
    assert early.value.current == {"reasonKey": "post-restore-not-passed"}
    pending = requests.advance(identity, "post-restore-pending", allowed_from=("verifying",))
    assert pending["state"] == "post-restore-pending"
    requests.advance(identity, "verifying", allowed_from=("post-restore-pending",))
    post = rf.set_record(ledger, now=clock())
    requests.record(identity, postRestoreBackupId=post["backupId"])
    authorized = requests.authorize_start(identity)
    assert "startAuthorizedAt" in authorized
    assert requests.authorize_start(identity) == authorized
    assert requests.advance(identity, "succeeded", allowed_from=("verifying",))[
        "state"] == "succeeded"


def test_held_restore_is_ended_by_a_successor_that_starts_running(requests, ledger, clock):
    backup = rf.set_record(ledger, now=clock())
    held, approval = production(requests, ledger, clock, backup)
    requests.admit(held["recoveryRequestId"], approval_id=approval["approvalId"])
    requests.start(held["recoveryRequestId"])
    requests.advance(held["recoveryRequestId"], "held", allowed_from=("running",))
    # A successor cancelled before it runs leaves the held request held.
    first, decision = production(requests, ledger, clock, backup)
    requests.admit(first["recoveryRequestId"], approval_id=decision["approvalId"],
                   predecessor_id=held["recoveryRequestId"])
    # Only one successor waits at a time.
    second, decision2 = production(requests, ledger, clock, backup)
    with pytest.raises(OperationsError) as one:
        requests.admit(second["recoveryRequestId"], approval_id=decision2["approvalId"],
                       predecessor_id=held["recoveryRequestId"])
    assert one.value.current == {"reasonKey": "successor-waiting"}
    requests.cancel(first["recoveryRequestId"])
    assert requests.get(held["recoveryRequestId"])["state"] == "held"
    # The next successor takes the exclusion over only when it starts running.
    successor = requests.admit(second["recoveryRequestId"], approval_id=decision2["approvalId"],
                               predecessor_id=held["recoveryRequestId"])
    assert successor["predecessorRequestId"] == held["recoveryRequestId"]
    assert requests.get(held["recoveryRequestId"])["state"] == "held"
    assert requests.start(second["recoveryRequestId"])["state"] == "running"
    ended = requests.get(held["recoveryRequestId"])
    assert ended["state"] == "failed"
    assert ended["successorRequestId"] == second["recoveryRequestId"]
    # A request that is not held cannot be replaced.
    third, decision3 = production(requests, ledger, clock, backup)
    with pytest.raises(OperationsError) as not_held:
        requests.admit(third["recoveryRequestId"], approval_id=decision3["approvalId"],
                       predecessor_id=held["recoveryRequestId"])
    assert not_held.value.current == {"reasonKey": "predecessor-not-held"}


def test_an_abandonment_needs_your_decision_and_no_waiting_successor(requests, ledger, clock):
    backup = rf.set_record(ledger, now=clock())
    held, approval = production(requests, ledger, clock, backup)
    identity = held["recoveryRequestId"]
    requests.admit(identity, approval_id=approval["approvalId"])
    requests.start(identity)
    requests.advance(identity, "held", allowed_from=("running",))
    abandonment = rf.approval_record(ledger, "restore-abandonment", identity, now=clock())
    waiting, decision = production(requests, ledger, clock, backup)
    requests.admit(waiting["recoveryRequestId"], approval_id=decision["approvalId"],
                   predecessor_id=identity)
    with pytest.raises(OperationsError) as refused:
        requests.decide_abandonment(identity, abandonment["approvalId"])
    assert refused.value.current == {"reasonKey": "successor-waiting"}
    requests.cancel(waiting["recoveryRequestId"])
    decided = requests.decide_abandonment(identity, abandonment["approvalId"])
    assert decided["state"] == "held"
    assert decided["abandonmentApprovalId"] == abandonment["approvalId"]
    facts = rf.receipt("platform.database.recreate", now=clock())
    ended = requests.abandoned(identity, facts, loss_report_ref="loss-report:1")
    assert ended["state"] == "failed" and ended["abandonedAt"]
    assert ended["abandonmentRecreateReceiptRef"] == facts["receiptId"]
    assert f"abandon-recreate:{facts['receiptId']}" in ended["evidenceRefs"]


# --- 2. one submission's identity -----------------------------------------------------------


def test_a_retry_recovers_the_original_and_a_new_submission_makes_a_new_one(requests, clock):
    submission = uuid4()
    first = submit(requests, clock, submission=submission)
    assert submit(requests, clock, submission=submission) == first
    second = submit(requests, clock)
    assert second["recoveryRequestId"] != first["recoveryRequestId"]
    assert first["idempotencyKey"] == idempotency_key(
        origin="schedule", requester=None, operation="backup.create", target="docsuri_u8",
        expected_revision=0, submission_id=str(submission))
    # The same submission with other facts is a conflict, never a new request.
    with pytest.raises(OperationsError) as reused:
        submit(requests, clock, environment="rehearsal", target="docsuri_u8_rehearsal",
               submission=submission, expected=0)
    assert reused.value.current == {"reasonKey": "submission-reused"}


def test_a_stale_expected_revision_is_a_conflict(requests, ledger, clock):
    rf.set_record(ledger, now=clock())
    with pytest.raises(OperationsError) as stale:
        submit(requests, clock, expected=0)
    assert stale.value.code == "CONFLICT" and stale.value.current == {"revision": 1}
    with pytest.raises(OperationsError) as missing:
        submit(requests, clock, "restore.verify", target=str(uuid4()), expected=1)
    assert missing.value.code == "NOT_FOUND"


# --- 3. conflicts never overlap; a waiting request holds nothing ---------------------------


def test_conflicting_kinds():
    assert conflicting("backup.create", "backup.create")
    assert conflicting("backup.create", "restore.production")
    assert conflicting("restore.production", "restore.production")
    assert conflicting("restore.verify", "restore.verify")
    assert not conflicting("restore.verify", "backup.create")
    assert not conflicting("restore.production", "restore.verify")


def test_conflicting_requests_never_overlap_and_a_waiting_one_holds_nothing(requests, ledger,
                                                                            clock):
    first = submit(requests, clock)
    requests.admit(first["recoveryRequestId"])
    second = submit(requests, clock)
    with pytest.raises(OperationsError) as conflict:
        requests.admit(second["recoveryRequestId"])
    assert conflict.value.current == {"reasonKey": "conflicting-request-active",
                                      "waiting": True}
    assert requests.get(second["recoveryRequestId"])["state"] == "requested"
    # A waiting request holds nothing: a verification is admitted meanwhile, and a
    # second verification is not.
    backup = rf.set_record(ledger, now=clock())
    verify = submit(requests, clock, "restore.verify", target=backup["backupId"])
    assert requests.admit(verify["recoveryRequestId"])["state"] == "awaiting-operator"
    other = submit(requests, clock, "restore.verify", target=backup["backupId"])
    with pytest.raises(OperationsError):
        requests.admit(other["recoveryRequestId"])
    # The rehearsal environment is its own: its backup is admitted.
    rehearsal = submit(requests, clock, environment="rehearsal", target="docsuri_u8_rehearsal")
    assert requests.admit(rehearsal["recoveryRequestId"])["state"] == "awaiting-operator"
    # Once the first ends, the waiting one is admitted.
    requests.cancel(first["recoveryRequestId"])
    assert requests.admit(second["recoveryRequestId"])["state"] == "awaiting-operator"
    assert {item["recoveryRequestId"] for item in requests.active("live")} == {
        second["recoveryRequestId"], verify["recoveryRequestId"]}


def test_a_switch_and_a_rehearsal_database_removal_hold_their_environments(requests, ledger,
                                                                           clock):
    cutover = rf.cutover_record(ledger, "preparing")
    rf.advance_cutover(ledger, cutover, "rehearsing")
    rf.advance_cutover(ledger, {**cutover, "state": "rehearsing"}, "ready-to-switch")
    rf.advance_cutover(ledger, {**cutover, "state": "ready-to-switch"}, "switching")
    live = submit(requests, clock)
    with pytest.raises(OperationsError) as held:
        requests.admit(live["recoveryRequestId"])
    assert held.value.current == {"reasonKey": "live-exclusion-held", "waiting": True}
    copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
    copy = copies.record("rehearsal-database", "run:1", ["database/docsuri_u8_rehearsal_x"])
    copies.disposal_pending(copy["copyId"])
    rehearsal = submit(requests, clock, environment="rehearsal", target="docsuri_u8_rehearsal")
    with pytest.raises(OperationsError) as removing:
        requests.admit(rehearsal["recoveryRequestId"])
    assert removing.value.current == {"reasonKey": "rehearsal-database-being-removed",
                                      "waiting": True}


# --- 4. MFA ended by operator start -------------------------------------------------------


def test_mfa_that_has_ended_by_operator_start_is_refused(requests, ledger, clock, mfa):
    request = submit(requests, clock, origin="administrator")
    requests.admit(request["recoveryRequestId"])
    mfa["current"] = False
    refused = requests.start(request["recoveryRequestId"])
    assert refused["state"] == "refused"
    assert refused["evidenceRefs"] == ["refused:mfa-not-current"]


def test_the_disk_guard_refuses_a_verification_at_operator_start(requests, ledger, clock):
    backup = rf.set_record(ledger, now=clock())
    request = submit(requests, clock, "restore.verify", target=backup["backupId"])
    requests.admit(request["recoveryRequestId"])
    refused = requests.start(request["recoveryRequestId"], disk_room=lambda _: False)
    assert refused["evidenceRefs"] == ["refused:internal-disk-low"]


# --- 5. an unknown outcome blocks until it is reconciled ------------------------------------


def test_an_unknown_outcome_blocks_conflicting_requests_until_reconciled(requests, clock):
    first = submit(requests, clock)
    requests.admit(first["recoveryRequestId"])
    requests.start(first["recoveryRequestId"])
    requests.outcome_unknown(first["recoveryRequestId"], evidence=["pending:op"])
    assert [item["recoveryRequestId"] for item in requests.unknown("live")] == [
        first["recoveryRequestId"]]
    second = submit(requests, clock)
    with pytest.raises(OperationsError):
        requests.admit(second["recoveryRequestId"])
    requests.settle_unknown(first["recoveryRequestId"], "failed")
    assert requests.unknown("live") == []
    assert requests.admit(second["recoveryRequestId"])["state"] == "awaiting-operator"


def test_the_evidence_list_is_bounded_and_keeps_what_a_precondition_reads():
    kept = bounded_evidence(["recreate:a"], [f"step:{index}" for index in range(30)])
    assert len(kept) == MAX_EVIDENCE and kept[0] == "recreate:a"
    assert kept[-1] == "step:29"
    with pytest.raises(OperationsError):
        bounded_evidence([f"recreate:{index}" for index in range(17)], [])


def test_reading_a_request_never_changes_it(requests, clock):
    request = submit(requests, clock)
    before = requests.ledger.head
    requests.status(request["recoveryRequestId"])
    requests.active()
    assert requests.ledger.head == before
    with pytest.raises(OperationsError) as missing:
        requests.status(uuid4())
    assert missing.value.code == "NOT_FOUND"
    assert requests.production_restore_active() is None and not requests.restore_waits()
