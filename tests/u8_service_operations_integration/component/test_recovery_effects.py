"""How a recovery procedure reads one bound effect's answer (U8 plan Step 29; BR4.4,
BR4.8, C10).

`RecoveryProcedures._effect` runs one operation through the operator tool: a refused
precondition or a control error is a refusal with a fixed reason key; an unknown outcome
is reconciled from its target at once, and becomes a success carrying the references the
applied effect recorded beside itself, a failure, or `OutcomeUnknown` when still unknown.
A rehearsal request without a rehearsal database fails before anything runs.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.modules.operations.lifecycle import backups_evidence
from backend.modules.operations.recovery import RecoveryRequests
from backend.modules.operations.recovery_procedures import (
    OutcomeUnknown,
    Platform,
    ProcedureFailed,
    RecoveryProcedures,
    reason_of,
)
from backend.u8_policy import SYNTHETIC_OPERATIONS
from docsuri_ops.arrangement.paths import DatabaseNames
from docsuri_ops.platform_control.errors import ControlError
from docsuri_ops.u8_platform.drivers import input_hash, write_input
from docsuri_ops.u8_platform.u8_protocols import (
    PreconditionRefused,
    effect_token,
    recorded_databases,
    retry_key,
)
from tests.u8_service_operations_integration import recovery_flows as rf
from tests.u8_service_operations_integration.conftest import Clock


class Operator:
    """An operator tool stand-in answering one prepared receipt and reconciliation."""

    def __init__(self, root, *, answer=None, raises=None, settled=None):
        self.profile = SimpleNamespace(effects_root=root)
        self.answer, self.raises, self.settled = answer, raises, settled
        self.reconciled = []

    def execute(self, operation, target, inputs, *, key):
        if self.raises is not None:
            raise self.raises
        return self.answer

    def reconcile(self, operation_id):
        self.reconciled.append(operation_id)
        return dict(self.settled or {})


def procedures(tmp_path, operator, *, rehearsal=lambda: None) -> RecoveryProcedures:
    clock = Clock()
    ledger = rf.open_ledger(tmp_path, clock)
    platform = Platform(
        operator=operator, production="docsuri_u8", labels=("u8",),
        scratch_name=lambda: "scratch", free_bytes=lambda: 0,
        scratch_checks=lambda database, accounts: {},
        restore_evaluate=lambda database, accounts: {},
        production_integrity=lambda database: {}, ready=lambda: True,
        drop_scratch=lambda name: None, rehearsal=rehearsal,
    )
    return RecoveryProcedures(RecoveryRequests(ledger, SYNTHETIC_OPERATIONS, clock=clock),
                              platform, incidents=None, tombstones=None,
                              policy=SYNTHETIC_OPERATIONS)


INPUTS = {"database": "docsuri_u8"}
UNKNOWN = {"outcome": "unknown", "operationId": "op-1"}


def effect(procedure):
    return procedure._effect("platform.database.backup", "database-production", INPUTS,
                             key="recovery:r:backup:1")


def test_a_refused_precondition_is_a_refusal_with_its_reason(tmp_path):
    answer = effect(procedures(tmp_path, Operator(tmp_path,
                                                  raises=PreconditionRefused("held-by-gate"))))
    assert answer == {"outcome": "refused", "refusal": "held-by-gate"}


def test_a_control_error_is_a_refusal_with_its_code_as_a_key(tmp_path):
    error = ControlError.__new__(ControlError)
    error.code = "POLICY_UNRESOLVED"
    answer = effect(procedures(tmp_path, Operator(tmp_path, raises=error)))
    assert answer == {"outcome": "refused", "refusal": "policy-unresolved"}


def test_a_known_outcome_is_returned_as_it_is(tmp_path):
    receipt = {"outcome": "succeeded", "operationId": "op-1"}
    operator = Operator(tmp_path, answer=receipt)
    assert effect(procedures(tmp_path, operator)) == receipt and operator.reconciled == []


def test_an_unknown_outcome_reconciled_applied_carries_its_recorded_refs(tmp_path):
    token = effect_token("database-production", input_hash(INPUTS), "recovery:r:backup:1")
    folder = tmp_path / "database-production"
    folder.mkdir()
    (folder / f"effect-{token}.json").write_text(json.dumps({"refs": ["fact:bytes=10"]}))
    operator = Operator(tmp_path, answer=UNKNOWN,
                        settled={"reconciliationState": "reconciled-applied"})
    answer = effect(procedures(tmp_path, operator))
    assert answer["outcome"] == "succeeded" and answer["effectRefs"] == ["fact:bytes=10"]
    assert operator.reconciled == ["op-1"]


def test_an_applied_effect_without_its_record_carries_no_refs(tmp_path):
    operator = Operator(tmp_path, answer=UNKNOWN,
                        settled={"reconciliationState": "reconciled-applied"})
    assert effect(procedures(tmp_path, operator))["effectRefs"] == []


def test_an_unknown_outcome_reconciled_not_applied_is_a_failure(tmp_path):
    operator = Operator(tmp_path, answer=UNKNOWN,
                        settled={"reconciliationState": "reconciled-not-applied"})
    assert effect(procedures(tmp_path, operator))["outcome"] == "failed"


def test_an_outcome_still_unknown_after_reconciliation_raises(tmp_path):
    operator = Operator(tmp_path, answer=UNKNOWN, settled={"reconciliationState": "unknown"})
    with pytest.raises(OutcomeUnknown) as raised:
        effect(procedures(tmp_path, operator))
    assert raised.value.operation_id == "op-1"


def test_reconcile_names_the_path_that_settles_another_actors_operation(tmp_path):
    """Review finding (Minor, R16): the store settles an operation only for the actor
    that bound it, so `reconcile` run in person on a scheduled request (the scheduler's
    operation) answers `operation-bound-by-another-actor` and names the standing job as
    the path that settles it, and the request stays unknown; any other store refusal
    passes through as it is, and a reconciliation the store admits settles the request."""
    from uuid import uuid4

    from backend.modules.operations.errors import OperationsError

    operator = Operator(tmp_path, raises=ControlError("FORBIDDEN",
                                                       "operation bound by another actor"))
    operator.reconcile = lambda operation_id: (_ for _ in ()).throw(operator.raises)
    procedure = procedures(tmp_path, operator)
    requests = procedure.requests
    request = requests.request(origin="schedule", operation="backup.create",
                               environment="live", target_id="docsuri_u8",
                               expected_revision=0, submission_id=uuid4())
    identity = request["recoveryRequestId"]
    requests.admit(identity)
    requests.start(identity)
    requests.outcome_unknown(identity, evidence=["pending:op-1"])
    with pytest.raises(OperationsError) as refused:
        procedure.reconcile(identity)
    assert refused.value.code == "FORBIDDEN"
    assert refused.value.current == {"reasonKey": "operation-bound-by-another-actor",
                                     "settledBy": "standing-job"}
    assert requests.get(identity)["state"] == "unknown"
    operator.raises = ControlError("DEPENDENCY_UNAVAILABLE", "store unreachable")
    with pytest.raises(ControlError) as other:
        procedure.reconcile(identity)
    assert other.value.code == "DEPENDENCY_UNAVAILABLE"
    operator.reconcile = lambda operation_id: {"reconciliationState": "reconciled-not-applied"}
    assert procedure.reconcile(identity)["state"] == "failed"


def test_a_rehearsal_request_needs_its_rehearsal_database(tmp_path):
    procedure = procedures(tmp_path, Operator(tmp_path))
    assert procedure.platform.database_of("live") == "docsuri_u8"
    with pytest.raises(ProcedureFailed) as failed:
        procedure.platform.database_of("rehearsal")
    assert failed.value.reason == "no-rehearsal-database"
    import dataclasses

    named = dataclasses.replace(procedure.platform,
                                rehearsal=lambda: "docsuri_u8_rehearsal_0123456789ab")
    assert named.database_of("rehearsal") == "docsuri_u8_rehearsal_0123456789ab"


class Incidents:
    def __init__(self):
        self.signals = []

    def signal(self, kind, opened_by, *, correlation, environment):
        self.signals.append((kind, correlation, environment))


def verifying(tmp_path, operator):
    """Procedures with a real register and one recorded live set, and an admitted
    verification of it."""
    from uuid import uuid4

    from backend.modules.operations.tombstones import Tombstones

    procedure = procedures(tmp_path, operator)
    procedure.tombstones, procedure.incidents = Tombstones(procedure.ledger), Incidents()
    procedure.platform = dataclasses.replace(procedure.platform, free_bytes=lambda: 10**15)
    backup = rf.set_record(procedure.ledger, now=procedure.clock())
    request = procedure.requests.request(
        origin="schedule", operation="restore.verify", environment="live",
        target_id=backup["backupId"],
        expected_revision=procedure.ledger.revision("backup-set", backup["backupId"]),
        submission_id=uuid4())
    procedure.requests.admit(request["recoveryRequestId"])
    return procedure, request["recoveryRequestId"]


def test_a_request_of_another_operation_is_refused_by_each_procedure(tmp_path):
    from backend.modules.operations.errors import OperationsError

    procedure, request_id = verifying(tmp_path, Operator(tmp_path))
    with pytest.raises(OperationsError):
        procedure.backup(request_id)


def test_a_scratch_restore_that_fails_fails_the_verification_and_opens_an_incident(tmp_path):
    procedure, request_id = verifying(
        tmp_path, Operator(tmp_path, answer={"outcome": "failed", "operationId": "op-2"}))
    done = procedure.verify(request_id)
    assert done["state"] == "failed"
    assert "failed:scratch-restore-failed" in done["evidenceRefs"]
    [record] = procedure.ledger.records("restore-verification")
    assert (record["result"], record["integrity"]) == ("failed", "failed")
    assert len(procedure.incidents.signals) == 1
    assert procedure.incidents.signals[0][0] == "storage.capacity"


def test_a_scratch_restore_still_unknown_leaves_the_request_outcome_unknown(tmp_path):
    procedure, request_id = verifying(
        tmp_path, Operator(tmp_path, answer=UNKNOWN, settled={"reconciliationState": "x"}))
    done = procedure.verify(request_id)
    assert done["state"] == "unknown", done
    assert "pending:op-1" in done["evidenceRefs"]
    assert procedure.ledger.records("restore-verification") == []


def test_a_check_that_cannot_finish_fails_the_verification_and_still_drops_the_copy(
    tmp_path,
):
    """A replay that cannot finish (a row it may not remove) is a failed verification,
    and the scratch copy is dropped rather than left behind."""
    procedure, request_id = verifying(tmp_path, Operator(tmp_path))
    backup = procedure.ledger.records("backup-set")[0]
    # The scratch restore succeeded and restored the requested set.
    procedure.platform.operator.answer = {
        "outcome": "succeeded", "operationId": "op-3",
        "effectRefs": [f"fact:setRecordId={backup['backupId']}"]}
    dropped = []

    def unfinished(database, accounts):
        raise RuntimeError("tombstone replay could not remove every personal row")

    procedure.platform = dataclasses.replace(procedure.platform, scratch_checks=unfinished,
                                             drop_scratch=dropped.append)
    done = procedure.verify(request_id)
    assert done["state"] == "failed" and "failed:verification-failed" in done["evidenceRefs"]
    [record] = procedure.ledger.records("restore-verification")
    assert (record["integrity"], record["result"]) == ("failed", "failed")
    assert dropped == ["scratch"] and record["scratchRemovedAt"]


@pytest.mark.parametrize("receipt,expected", [
    ({"refusal": "disk-room-short"}, "disk-room-short"),
    ({"refusal": "Injected permission fault: the operator said no"}, "fallback"),
    ({}, "fallback"),
])
def test_only_a_key_form_refusal_is_kept(receipt, expected):
    assert reason_of(receipt, "fallback") == expected


# --- Step 65(c): the scratch copy first, reconciled sets, lone copies, HNSW time -----------

TAIL = dt.timedelta(seconds=86_400)
GIB = 1024**3


def scratch_copies(ledger) -> list[dict]:
    return [item for item in ledger.records("retained-copy") if item["kind"] == "scratch-restore"]


def restored(backup: dict, *extra: str) -> dict:
    return {"outcome": "succeeded", "operationId": str(uuid4()),
            "effectRefs": [f"fact:setRecordId={backup['backupId']}", *extra]}


class Watching(Operator):
    """A stand-in that reads the ledger when the scratch restore runs."""

    def __init__(self, root, **options):
        super().__init__(root, **options)
        self.seen: list[list[dict]] = []
        self.ledger = None

    def execute(self, operation, target, inputs, *, key):
        if operation == "platform.database.restore":
            self.seen.append([item for item in scratch_copies(self.ledger)
                              if "disposedAt" not in item])
        return super().execute(operation, target, inputs, key=key)


def watched(tmp_path, name: str, **options):
    folder = tmp_path / name
    folder.mkdir()
    operator = Watching(folder, **options)
    procedure, request_id = verifying(folder, operator)
    operator.ledger = procedure.ledger
    backup = procedure.ledger.records("backup-set")[0]
    if operator.answer is None and operator.raises is None:
        operator.answer = restored(backup)
    procedure.platform = dataclasses.replace(
        procedure.platform, scratch_checks=lambda d, a: {"integrity": "passed", "surviving": 0})
    return procedure, request_id, operator


def test_a_scratch_copy_is_recorded_before_its_restore_and_closed_by_its_drop(tmp_path):
    procedure, request_id, operator = watched(tmp_path, "dropped")
    procedure.verify(request_id)
    [[seen]] = operator.seen
    assert seen["locations"] == ["database/scratch"]
    created = dt.datetime.fromisoformat(seen["createdAt"].replace("Z", "+00:00"))
    assert seen["disposeAfter"] == (created + TAIL).isoformat(
        timespec="milliseconds").replace("+00:00", "Z")
    [copy] = scratch_copies(procedure.ledger)
    verification = procedure.ledger.records("restore-verification")[0]["verificationId"]
    assert copy["disposalVerificationRef"] == f"verification:{verification}" and copy[
        "disposedAt"]
    dropped = dt.datetime.fromisoformat(copy["disposedAt"].replace("Z", "+00:00"))
    procedure.clock.now = dropped + TAIL - dt.timedelta(seconds=1)
    named = {item["recordId"] for item in backups_evidence(
        procedure.ledger, SYNTHETIC_OPERATIONS, schedule_active=True)["undisposed"]}
    assert copy["copyId"] in named
    procedure.clock.now = dropped + TAIL
    named = {item["recordId"] for item in backups_evidence(
        procedure.ledger, SYNTHETIC_OPERATIONS, schedule_active=True)["undisposed"]}
    assert copy["copyId"] not in named
    # A drop that fails leaves the copy open, and the recorded databases list it.
    procedure, request_id, _ = watched(tmp_path, "kept")

    def refuse(name):
        raise RuntimeError("drop refused")

    procedure.platform = dataclasses.replace(procedure.platform, drop_scratch=refuse)
    procedure.verify(request_id)
    [kept] = scratch_copies(procedure.ledger)
    assert "disposedAt" not in kept and recorded_databases(procedure.ledger)() == {"scratch"}
    # A restore refused before anything was created closes it.
    procedure, request_id, _ = watched(tmp_path, "refused",
                                       raises=PreconditionRefused("scratch-name-refused"))
    done = procedure.verify(request_id)
    assert "failed:scratch-name-refused" in done["evidenceRefs"]
    [closed] = scratch_copies(procedure.ledger)
    assert closed["disposedAt"] and closed["disposalVerificationRef"].startswith("verification:")
    # An unknown outcome leaves it open.
    procedure, request_id, _ = watched(tmp_path, "unknown", answer=UNKNOWN,
                                       settled={"reconciliationState": "x"})
    assert procedure.verify(request_id)["state"] == "unknown"
    [left] = scratch_copies(procedure.ledger)
    assert "disposedAt" not in left
    # Another open scratch copy holds NFR8.15's one place: refused before anything.
    procedure, request_id, operator = watched(tmp_path, "limit")
    other = DatabaseNames("docsuri_u8").new("scratch")
    procedure.copies.record("scratch-restore", "verification:earlier", [f"database/{other}"])
    done = procedure.verify(request_id)
    assert done["state"] == "failed" and "failed:scratch-database-limit" in done["evidenceRefs"]
    [failed] = procedure.ledger.records("restore-verification")
    assert failed["result"] == "failed" and "scratchRemovedAt" not in failed
    assert [signal[0] for signal in procedure.incidents.signals] == ["storage.capacity"]
    assert len(scratch_copies(procedure.ledger)) == 1 and operator.seen == []


def backup_facts(record_id: str, *, location: bool = True, taken: str) -> list[str]:
    refs = [f"fact:recordId={record_id}", "fact:sha256=" + "a" * 64, "fact:size=2048",
            "fact:databaseBytes=4096", "fact:incarnation=docsuri_u8:16384",
            "fact:stagingLocation=staging/x", f"fact:stagingRemovedAt={taken}",
            "fact:disposeAfter=2026-12-01T00:00:00.000Z", "fact:integrity=passed"]
    return ([f"backup-volume/archives/live-set-{record_id}.archive"] if location else []) + refs


def copy_answer(*, integrity: str = "passed") -> dict:
    return {"agent": {"recordId": str(uuid4()), "location": "ledger/copy.archive",
                      "stagingLocation": "staging/ledger", "sha256": "f" * 64,
                      "disposeAfter": "2026-12-01T00:00:00.000Z", "integrity": integrity,
                      "stagingRemovedAt": "2026-11-10T04:00:00.000Z"},
            "head": {"count": 3, "head": "e" * 64}}


def with_copies(procedure, answers: list[dict]):
    procedure.incidents = Incidents()
    procedure.platform = dataclasses.replace(procedure.platform,
                                             ledger_copy=lambda: answers.pop(0))
    return procedure


def reconciling(tmp_path, name: str, refs: list[str] | None, state="reconciled-applied"):
    """A `backup.create` left unknown, its bound input and effect record beside its
    reference, and a stand-in reconciliation answering `state`."""
    folder = tmp_path / name
    folder.mkdir()
    operator = Operator(folder)
    procedure = with_copies(procedures(folder, operator), [copy_answer()])
    procedure.clock.now = dt.datetime(2026, 11, 9, 4, 0, tzinfo=dt.UTC)
    request = procedure.requests.request(origin="schedule", operation="backup.create",
                                         environment="live", target_id="docsuri_u8",
                                         expected_revision=0, submission_id=uuid4())
    identity = request["recoveryRequestId"]
    procedure.requests.admit(identity)
    procedure.requests.start(identity)
    procedure.requests.outcome_unknown(identity, evidence=["pending:op-9"])
    record_id = str(uuid4())
    inputs = {"database": "docsuri_u8", "recordId": record_id, "via": "standing"}
    token = effect_token("database-production", input_hash(inputs), "recovery:x:backup:1")
    write_input(folder / "database-production", token, inputs)
    if refs is not None:
        (folder / "database-production" / f"effect-{token}.json").write_text(
            json.dumps({"refs": refs}))
    operator.settled = {
        "reconciliationState": state, "outcome": "unknown", "receiptId": str(uuid4()),
        "operationId": str(uuid4()), "operation": "platform.database.backup",
        "targetId": "database-production", "inputHash": input_hash(inputs),
        "effectReference": f"database-production/effect-{token}.json"}
    procedure.clock.now += dt.timedelta(days=1)  # reconciled a day after the dump
    return procedure, identity, record_id


def test_an_applied_backup_settled_by_reconcile_records_its_set(tmp_path):
    taken = "2026-11-09T04:10:00.000Z"
    # The effect record's refs carry the input's own record identity.
    procedure, identity, record_id = reconciling(tmp_path, "applied", None)
    folder = tmp_path / "applied" / "database-production"
    token = procedure.platform.operator.settled["effectReference"].split("effect-")[1][:-5]
    (folder / f"effect-{token}.json").write_text(json.dumps(
        {"refs": backup_facts(record_id, taken=taken)}))
    done = procedure.reconcile(identity)
    assert done["state"] == "failed"
    [backup] = procedure.ledger.records("backup-set")
    assert backup["backupId"] == record_id and backup["takenAt"] == taken
    [copy] = procedure.ledger.records("ledger-copy")
    assert copy["backupId"] == record_id and copy["verifiedAt"]
    facts = procedure.ledger.get("receipt-facts", backup["operatorReceiptRef"])
    assert facts["outcome"] == "succeeded"
    procedure.reconcile(identity)  # settled already: nothing recorded twice
    assert len(procedure.ledger.records("backup-set")) == 1
    named = {item["recordId"]: item["goneAt"] for item in backups_evidence(
        procedure.ledger, SYNTHETIC_OPERATIONS, schedule_active=True)["undisposed"]}
    assert named[record_id] == backup["retainUntil"]
    # Reconciled not applied: nothing recorded.
    procedure, identity, _ = reconciling(tmp_path, "not-applied", [],
                                         state="reconciled-not-applied")
    assert procedure.reconcile(identity)["state"] == "failed"
    assert procedure.ledger.records("backup-set") == []
    # The location ref missing: settled failed, with the recording's reason.
    procedure, identity, record_id = reconciling(tmp_path, "incomplete", [])
    token = procedure.platform.operator.settled["effectReference"].split("effect-")[1][:-5]
    (tmp_path / "incomplete" / "database-production" / f"effect-{token}.json").write_text(
        json.dumps({"refs": backup_facts(record_id, location=False, taken=taken)}))
    done = procedure.reconcile(identity)
    assert done["state"] == "failed"
    assert "record-failed:backup-receipt-incomplete" in done["evidenceRefs"]
    assert procedure.ledger.records("backup-set") == []


def applied_receipt(record_id: str, *, now: dt.datetime) -> tuple[dict, dict]:
    effect = {"operation": "platform.database.backup", "target": "database-production",
              "inputs": {"database": "docsuri_u8", "recordId": record_id, "via": "standing"},
              "key": f"standing:{record_id}:backup", "environment": "live"}
    receipt = {"outcome": "succeeded", "receiptId": str(uuid4()), "operationId": str(uuid4()),
               "operation": "platform.database.backup", "targetId": "database-production",
               "inputHash": "c" * 64,
               "effectRefs": backup_facts(record_id, taken="2026-11-10T04:00:00.000Z")}
    return effect, receipt


def lone_copy(ledger, now: dt.datetime) -> dict:
    facts = rf.receipt("platform.ledger.copy", "ledger-copy", now=now)
    record = {"ledgerCopyId": str(uuid4()), "takenAt": rf.utc_text(now),
              "location": "ledger/lone.archive", "stagingLocation": "staging/lone",
              "digest": "d" * 64, "headSequence": 2, "headDigest": "e" * 64,
              "retainUntil": rf.utc_text(now + dt.timedelta(days=14)),
              "operatorReceiptRef": facts["receiptId"], "verifiedAt": rf.utc_text(now)}
    ledger.append("ledger-copy", record, expect_revision=0, receipts=(facts,))
    return record


def test_a_set_recorded_after_a_standalone_ledger_copy_takes_its_own_copy(tmp_path):
    answers = [copy_answer(), copy_answer(integrity="failed"), copy_answer()]
    procedure = with_copies(procedures(tmp_path, Operator(tmp_path)), answers)
    now = procedure.clock()
    lone_copy(procedure.ledger, now)
    first = str(uuid4())
    effect, receipt = applied_receipt(first, now=now)
    procedure.record_applied(effect, "scheduled", None, receipt)
    beside = [item for item in procedure.ledger.records("ledger-copy")
              if item.get("backupId") == first]
    assert len(beside) == 1 and beside[0]["verifiedAt"]
    # A new copy without `verifiedAt` fails the set; recording again takes a new copy.
    second = str(uuid4())
    effect, receipt = applied_receipt(second, now=now)
    with pytest.raises(ProcedureFailed) as unverified:
        procedure.record_applied(effect, "scheduled", None, receipt)
    assert unverified.value.reason == "ledger-copy-unverified"
    procedure.record_applied(effect, "scheduled", None, receipt)
    copies = [item for item in procedure.ledger.records("ledger-copy")
              if item.get("backupId") == second]
    assert [("verifiedAt" in item) for item in copies] == [False, True]
    assert answers == []


def test_a_requested_set_has_its_ledger_copy(tmp_path):
    procedure = with_copies(procedures(tmp_path, Operator(tmp_path)), [copy_answer()])
    procedure.requests.mfa_current = lambda requester, verified: True
    request = procedure.requests.request(
        origin="administrator", operation="backup.create", environment="live",
        target_id="docsuri_u8", expected_revision=0, submission_id=uuid4(),
        requested_by=uuid4(), mfa_verified_at=rf.utc_text(procedure.clock()))
    identity = request["recoveryRequestId"]
    procedure.requests.admit(identity)
    record_id = None

    def answer(operation, target, inputs, *, key):
        nonlocal record_id
        record_id = inputs["recordId"]
        return applied_receipt(record_id, now=procedure.clock())[1]

    procedure.platform.operator.execute = answer
    assert procedure.backup(identity, via="in-person")["state"] == "succeeded"
    [backup] = procedure.ledger.records("backup-set")
    assert backup["trigger"] == "requested"
    [copy] = procedure.ledger.records("ledger-copy")
    assert copy["backupId"] == record_id and copy["headSequence"] > 0 and copy["verifiedAt"]


class LoneOperator:
    """A stand-in answering `platform.ledger.copy` by key, as `execute_settled` asks it."""

    def __init__(self, root, answers: dict):
        self.profile = SimpleNamespace(effects_root=root)
        self.answers, self.keys = answers, []

    def execute(self, operation, target, inputs, *, key, **options):
        assert (operation, target, inputs["via"]) == ("platform.ledger.copy", "ledger-copy",
                                                      "standing")
        self.keys.append(key)
        answer = self.answers[key]
        if isinstance(answer, Exception):
            raise answer
        return dict(answer)

    def reconcile(self, operation_id):
        return {"outcome": "unknown", "reconciliationState": "unresolved",
                "operationId": operation_id}


def lone_receipt(*, outcome="succeeded", integrity="passed", record=None, **extra) -> dict:
    record = record or str(uuid4())
    refs = ["ledger-copy/effect-x.json", "backup-volume/ledger/lone-copy.archive",
            f"fact:recordId={record}", "fact:sha256=" + "a" * 64, "fact:size=99",
            f"fact:integrity={integrity}", "fact:disposeAfter=2026-12-01T00:00:00.000Z",
            "fact:stagingRemovedAt=2026-11-10T04:01:00.000Z",
            "fact:stagingLocation=staging/lone", "fact:headSequence=7",
            "fact:headDigest=" + "b" * 64]
    return {"outcome": outcome, "receiptId": str(uuid4()), "operationId": str(uuid4()),
            "operation": "platform.ledger.copy", "targetId": "ledger-copy",
            "inputHash": "c" * 64, "effectRefs": refs if outcome == "succeeded" else [],
            **extra}


def lone(tmp_path, name: str, answers: dict):
    folder = tmp_path / name
    folder.mkdir()
    procedure = procedures(folder, LoneOperator(folder, answers))
    procedure.incidents = Incidents()
    return procedure


def test_a_lone_ledger_copy_is_recorded_from_its_own_receipt(tmp_path):
    key = "standing-ledger-copy:live:20261110:ledger-copy"
    owner = "standing-ledger-copy:live:20261110"
    receipt = lone_receipt()
    procedure = lone(tmp_path, "applied", {key: receipt})
    record = procedure.ledger_copy_alone("live", owner_key=owner, via="standing")
    assert "backupId" not in record and record["headSequence"] == 7
    assert record["headDigest"] == "b" * 64 and record["takenAt"] == "2026-11-10T04:01:00.000Z"
    assert record["operatorReceiptRef"] == receipt["receiptId"] and record["verifiedAt"]
    facts = procedure.ledger.get("receipt-facts", receipt["receiptId"])
    assert (facts["operation"], facts["outcome"]) == ("platform.ledger.copy", "succeeded")
    procedure.platform.operator.answers[key] = {**receipt, "replayed": True}
    assert procedure.ledger_copy_alone("live", owner_key=owner, via="standing") == record
    assert len(procedure.ledger.records("ledger-copy")) == 1
    assert procedure.incidents.signals == []
    cases = {
        "refused": ({key: lone_receipt(outcome="failed", refusal="volume-check-failed")},
                    ProcedureFailed, "volume-check-failed"),
        "failed": ({key: lone_receipt(outcome="failed")}, ProcedureFailed, "ledger-copy-failed"),
        "precondition": ({key: PreconditionRefused("input-refused")}, ProcedureFailed,
                         "input-refused"),
        "unknown": ({key: lone_receipt(outcome="unknown")}, OutcomeUnknown, None),
    }
    for name, (answers, raised, reason) in cases.items():
        procedure = lone(tmp_path, name, answers)
        with pytest.raises(raised) as failure:
            procedure.ledger_copy_alone("rehearsal", owner_key=owner, via="standing")
        if reason is not None:
            assert failure.value.reason == reason, name
        assert procedure.incidents.signals == [
            ("storage.capacity", f"ledger-copy:{owner}", "rehearsal")], name
        assert procedure.ledger.records("ledger-copy") == [], name
    procedure = lone(tmp_path, "unverified", {key: lone_receipt(integrity="failed")})
    unverified = procedure.ledger_copy_alone("live", owner_key=owner, via="standing")
    assert "verifiedAt" not in unverified
    assert procedure.incidents.signals == [("storage.capacity", f"ledger-copy:{owner}", "live")]
    # Called again after a failure: the failure replays and the next retry key runs.
    failed = lone_receipt(outcome="failed")
    procedure = lone(tmp_path, "retried", {key: failed})
    with pytest.raises(ProcedureFailed):
        procedure.ledger_copy_alone("live", owner_key=owner, via="standing")
    operator = procedure.platform.operator
    operator.answers.update({key: {**failed, "replayed": True},
                             retry_key(key, 1): lone_receipt()})
    copied = procedure.ledger_copy_alone("live", owner_key=owner, via="standing")
    assert operator.keys == [key, key, retry_key(key, 1)] and copied["verifiedAt"]


def test_a_backup_the_agent_refuses_fails_and_opens_a_storage_incident(tmp_path):
    procedure = procedures(tmp_path, Operator(tmp_path, answer={
        "outcome": "failed", "operationId": str(uuid4()), "refusal": "volume-check-failed"}))
    procedure.incidents = Incidents()
    request = procedure.requests.request(origin="schedule", operation="backup.create",
                                         environment="live", target_id="docsuri_u8",
                                         expected_revision=0, submission_id=uuid4())
    identity = request["recoveryRequestId"]
    procedure.requests.admit(identity)
    done = procedure.backup(identity)
    assert done["state"] == "failed" and "failed:volume-check-failed" in done["evidenceRefs"]
    assert procedure.incidents.signals == [("storage.capacity", f"recovery:{identity}", "live")]


@pytest.mark.parametrize(("size", "projected"), [(GIB, 56), (3 * GIB, 19), (0, None)])
def test_a_verification_records_the_agents_hnsw_rebuild_time(tmp_path, size, projected):
    from backend.modules.operations.tombstones import Tombstones

    operator = Watching(tmp_path)
    procedure = procedures(tmp_path, operator)
    operator.ledger = procedure.ledger
    procedure.tombstones, procedure.incidents = Tombstones(procedure.ledger), Incidents()
    procedure.platform = dataclasses.replace(
        procedure.platform, free_bytes=lambda: 10**15,
        scratch_checks=lambda d, a: {"integrity": "passed", "surviving": 0})
    # A set of the given size, verified with the agent's timed rebuild.
    sized = rf.set_record(procedure.ledger, now=procedure.clock(), sourceDatabaseBytes=size)
    request = procedure.requests.request(
        origin="schedule", operation="restore.verify", environment="live",
        target_id=sized["backupId"],
        expected_revision=procedure.ledger.revision("backup-set", sized["backupId"]),
        submission_id=uuid4())
    identity = request["recoveryRequestId"]
    operator.answer = restored(sized, "fact:hnswRebuildSeconds=7")
    procedure.requests.admit(identity)
    assert procedure.verify(identity)["state"] == "succeeded"
    [record] = procedure.ledger.records("restore-verification")
    assert record["hnswRebuildSeconds"] == 7
    assert record.get("hnswProjectedSeconds") == projected


def test_a_verification_without_the_time_records_neither(tmp_path):
    procedure, request_id, _ = watched(tmp_path, "untimed")
    procedure.verify(request_id)
    [record] = procedure.ledger.records("restore-verification")
    assert "hnswRebuildSeconds" not in record and "hnswProjectedSeconds" not in record


# --- Step 73(c): a left-behind scratch disposed with its receipt (L1-23) -------------------------


class Removing:
    """An operator stand-in for `remove-scratch`: it records `(operation, target, inputs,
    key)` for each `execute` and answers from a queue (a receipt, or an exception it
    raises); a key it answered before gets that receipt again, marked `replayed`."""

    def __init__(self, root, answers=()):
        self.profile = SimpleNamespace(effects_root=root)
        self.answers = list(answers)
        self.asked: list[tuple] = []
        self.answered: dict[str, dict] = {}
        self.settled: dict[str, dict] = {}

    def execute(self, operation, target, inputs, *, key, **options):
        self.asked.append((operation, target, dict(inputs), key))
        if key in self.answered:
            return {**self.answered[key], "replayed": True}
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        self.answered[key] = dict(answer)
        return dict(answer)

    def reconcile(self, operation_id):
        return dict(self.settled.get(operation_id, {
            "outcome": "unknown", "reconciliationState": "unresolved",
            "operationId": operation_id}))


def left_behind(tmp_path, name: str, answers=()):
    """A scratch copy as Step 64(d) leaves one after a failed drop: open, at
    `database/scratch`, citing its verification, beside that verification's failed
    RestoreVerification without `scratchRemovedAt`; the request has ended."""
    procedure, request_id, _ = watched(tmp_path, name)

    def refuse(database):
        raise RuntimeError("drop refused: a session is still connected")

    procedure.platform = dataclasses.replace(procedure.platform, drop_scratch=refuse)
    assert procedure.verify(request_id)["state"] == "failed"
    [copy] = scratch_copies(procedure.ledger)
    [verification] = procedure.ledger.records("restore-verification")
    assert copy["sourceRef"] == f"verification:{verification['verificationId']}"
    assert verification["result"] == "failed" and "scratchRemovedAt" not in verification
    assert "disposedAt" not in copy
    remover = Removing(tmp_path / name, answers)
    procedure.platform = dataclasses.replace(procedure.platform, operator=remover)
    return procedure, copy, remover


def remove(procedure, copy_id: str) -> dict:
    from docsuri_ops.u8_platform.recovery_words import run_word

    return run_word("remove-scratch", {"copyId": copy_id}, procedure)


def removal(clock) -> dict:
    return rf.receipt("platform.database.remove", "database-scratch", now=clock())


def test_remove_scratch_disposes_a_left_behind_copy_with_its_receipt(tmp_path):
    from uuid import NAMESPACE_URL, uuid5

    from backend.modules.operations.errors import OperationsError

    # Removed: on the effect's succeeded receipt.
    procedure, copy, remover = left_behind(tmp_path, "removed")
    succeeded = removal(procedure.clock)
    remover.answers.append(succeeded)
    key = f"remove-scratch:{copy['copyId']}"
    answer = remove(procedure, copy["copyId"])
    assert remover.asked == [("platform.database.remove", "database-scratch",
                              {"database": "scratch", "via": "in-person"}, key)]
    assert answer == {"copyId": copy["copyId"], "disposed": True,
                      "receiptId": succeeded["receiptId"]}
    closed = procedure.copies.get(copy["copyId"])
    assert closed["disposedAt"] and closed["disposalReceiptRef"] == succeeded["receiptId"]
    # Refused before asking: a closed copy, an unknown one, and one of another kind.
    with pytest.raises(OperationsError) as refused:
        remove(procedure, copy["copyId"])
    assert (refused.value.code, refused.value.current) == (
        "CONFLICT", {"reasonKey": "not-an-open-scratch"})
    with pytest.raises(OperationsError) as missing:
        remove(procedure, str(uuid4()))
    assert missing.value.code == "NOT_FOUND"
    other = procedure.copies.record("import-database", "migration:run",
                                    ["database/docsuri_u8_import_0123456789ab"])
    with pytest.raises(OperationsError) as kind:
        remove(procedure, other["copyId"])
    assert kind.value.current == {"reasonKey": "not-an-open-scratch"}
    assert len(remover.asked) == 1

    # A failed removal, then its retry under the next retry key.
    procedure, copy, remover = left_behind(tmp_path, "retried")
    failed = rf.receipt("platform.database.remove", "database-scratch", "failed",
                        now=procedure.clock())
    second = removal(procedure.clock)
    remover.answers.extend([failed, second])
    key = f"remove-scratch:{copy['copyId']}"
    answer = remove(procedure, copy["copyId"])
    assert answer == {"copyId": copy["copyId"], "disposed": False,
                      "reason": "scratch-removal-failed"}
    pending = procedure.copies.get(copy["copyId"])
    assert pending["disposalPendingSince"] and "disposedAt" not in pending
    answer = remove(procedure, copy["copyId"])
    assert [item[3] for item in remover.asked] == [key, key, retry_key(key, 1)]
    assert answer["disposed"] is True and answer["receiptId"] == second["receiptId"]
    done = procedure.copies.get(copy["copyId"])
    assert done["disposedAt"] and done["disposalReceiptRef"] == second["receiptId"]

    # Refused after asking: a precondition, then an outcome still unknown.
    procedure, copy, remover = left_behind(
        tmp_path, "in-use", [PreconditionRefused("rehearsal-database-in-use")])
    assert remove(procedure, copy["copyId"])["reason"] == "rehearsal-database-in-use"
    held = procedure.copies.get(copy["copyId"])
    assert held["disposalPendingSince"] and "disposedAt" not in held
    procedure, copy, remover = left_behind(tmp_path, "unknown", [
        {**removal(procedure.clock), "outcome": "unknown"}])
    assert remove(procedure, copy["copyId"]) == {
        "copyId": copy["copyId"], "disposed": False, "reason": "effect-outcome-unknown"}
    still = procedure.copies.get(copy["copyId"])
    assert "disposedAt" not in still and "disposalPendingSince" not in still

    # The copy of a verification still running: refused before asking, then removed
    # once that request settles `failed` with no RestoreVerification record.
    (tmp_path / "running").mkdir()
    procedure, request_id = verifying(tmp_path / "running", Removing(tmp_path / "running"))
    remover = procedure.platform.operator
    procedure.requests.start(request_id, disk_room=lambda request: True)
    verification_id = str(uuid5(NAMESPACE_URL, f"docsuri-verification:{request_id}"))
    running = procedure.copies.record(
        "scratch-restore", f"verification:{verification_id}", ["database/scratch"],
        copy_id=uuid5(NAMESPACE_URL, f"docsuri-scratch-copy:{verification_id}"))
    with pytest.raises(OperationsError) as busy:
        remove(procedure, running["copyId"])
    assert busy.value.current == {"reasonKey": "scratch-in-use"} and remover.asked == []
    procedure.requests.outcome_unknown(request_id, evidence=["pending:op-restore"])
    remover.settled["op-restore"] = {"reconciliationState": "reconciled-not-applied"}
    assert procedure.reconcile(request_id)["state"] == "failed"
    assert procedure.ledger.records("restore-verification") == []
    removed = removal(procedure.clock)
    remover.answers.append(removed)
    assert remove(procedure, running["copyId"])["receiptId"] == removed["receiptId"]
    assert procedure.copies.get(running["copyId"])["disposalReceiptRef"] == removed["receiptId"]


# --- Step 122(b): a running restore verification stops below the critical floor ----------

FLOOR = SYNTHETIC_OPERATIONS.internal_disk_critical_bytes


def test_a_scratch_restore_stopped_below_the_critical_floor_fails_with_its_reason_and_drops_the_copy(  # noqa: E501
    tmp_path,
):
    """The agent's `internal-disk-critical` refusal, settled into the restore's receipt,
    is kept as the request's reason; the scratch database is dropped, its copy closed
    citing the verification, and `storage.capacity` signalled with `recovery:<id>`. Any
    other key-form refusal keeps the built reason, `scratch-restore-failed`."""
    for name, refusal, reason in (
        ("critical", "internal-disk-critical", "internal-disk-critical"),
        ("other", "restore-failed", "scratch-restore-failed"),
    ):
        folder = tmp_path / name
        folder.mkdir()
        operator = Operator(folder, answer={"outcome": "failed", "operationId": str(uuid4()),
                                            "refusal": refusal})
        procedure, request_id = verifying(folder, operator)
        dropped = []
        procedure.platform = dataclasses.replace(procedure.platform, drop_scratch=dropped.append)
        done = procedure.verify(request_id)
        assert done["state"] == "failed", done
        failures = [ref for ref in done["evidenceRefs"] if ref.startswith("failed:")]
        assert failures == [f"failed:{reason}"]
        [record] = procedure.ledger.records("restore-verification")
        assert (record["result"], record["integrity"]) == ("failed", "failed")
        assert record["scratchRemovedAt"]
        assert dropped == ["scratch"]
        [copy] = scratch_copies(procedure.ledger)
        assert copy["disposedAt"]
        assert copy["disposalVerificationRef"] == f"verification:{record['verificationId']}"
        assert procedure.incidents.signals == [
            ("storage.capacity", f"recovery:{request_id}", "live")]


class Restoring(Operator):
    """A stand-in that notes when the scratch restore has run."""

    def __init__(self, root, **options):
        super().__init__(root, **options)
        self.restored = False

    def execute(self, operation, target, inputs, *, key):
        if operation == "platform.database.restore":
            self.restored = True
        return super().execute(operation, target, inputs, key=key)


def test_the_floor_crossed_after_the_restore_stops_before_any_check(tmp_path):
    """After a restore that succeeded and restored the requested set, the floor is read
    once more: one byte below it drops the scratch database and fails the verification
    with `internal-disk-critical`, running no check; exactly at it, the checks run."""
    assert FLOOR == 10 * GIB
    for name, after, verified in (("below", FLOOR - 1, False), ("at", FLOOR, True)):
        folder = tmp_path / name
        folder.mkdir()
        operator = Restoring(folder)
        procedure, request_id = verifying(folder, operator)
        operator.answer = restored(procedure.ledger.records("backup-set")[0])
        checked, dropped = [], []

        def checking(database, accounts, checked=checked):
            checked.append((database, list(accounts)))
            return {"integrity": "passed", "surviving": 0}

        procedure.platform = dataclasses.replace(
            procedure.platform, scratch_checks=checking, drop_scratch=dropped.append,
            free_bytes=lambda operator=operator, after=after: (
                after if operator.restored else 10**15))
        done = procedure.verify(request_id)
        [record] = procedure.ledger.records("restore-verification")
        assert dropped == ["scratch"] and record["scratchRemovedAt"]
        if verified:
            assert done["state"] == "succeeded", done
            assert checked == [("scratch", [])] and record["result"] == "verified"
            continue
        assert checked == []
        assert done["state"] == "failed"
        assert "failed:internal-disk-critical" in done["evidenceRefs"]
        assert (record["result"], record["integrity"]) == ("failed", "failed")
