"""The production restore on the composed realm with the realm driver (U8 plan Step 30;
BR4.4, BR4.7, BR4.8, BR9.10, Workflow 7; security-design § 15 "The extension (D14)"
item 3 and "Email allowance (D12)" item 4).

Each test restores a production stand-in of its own in the realm's instance
(`recovery_flows.JourneyDatabase`), never `docsuri_u8`: two owners' schemas with tables,
rows, a foreign key and an HNSW index. The operator runs Workflow 7 in person through
PlatformControl's bound operations: the public stand-in's routing and the realm's
service control write the journey's own state, the backup agent writes the journey's own
stand-in volume, the recreate and the restore act on the journey's database, and your
decisions go through `platform.decision.record`. Failure paths use U7's injected
permission failure on the named step, so they run through real receipts.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.modules.operations.allowance import LedgerAllowance
from backend.modules.operations.tombstones import Tombstones
from backend.u8_host import unauthorized_restore
from backend.u8_policy import SYNTHETIC_OPERATIONS
from docsuri_ops.u8_platform.recovery_words import realm_procedures
from docsuri_ops.u8_platform.u8_protocols import PreconditionRefused
from tests.u8_service_operations_integration import platform_flows as pf
from tests.u8_service_operations_integration import recovery_flows as rf

ROOM = 100 * rf.GIB
HOST = "dev.docsuri.u8.run.host"


class Stage:
    def __init__(self, tmp_path, realm, clock):
        self.realm, self.clock = realm, clock
        self.database = rf.JourneyDatabase(realm).create()
        self.owner = self.database.add_owner()
        agent = rf.journey_agent(tmp_path, realm, self.database, clock)
        self.journey = pf.journey(tmp_path, realm, mode="live", admission="open",
                                  agentFolder=str(agent))
        self.ledger = rf.open_ledger(tmp_path, clock)
        self.wiring = realm_procedures(self.journey.profile, self.ledger, clock=clock,
                                       ready=lambda: True, free_bytes=lambda: ROOM,
                                       mfa_current=lambda account, at: True,
                                       names=self.database.names)
        self.procedures = self.wiring.procedures
        self.requests = self.procedures.requests
        self.operator = self.procedures.platform.operator
        self.backup = self.live_set()

    def live_set(self) -> dict:
        request = self.requests.request(
            origin="schedule", operation="backup.create", environment="live",
            target_id=self.database.name,
            expected_revision=self.requests.backup_revision("live"), submission_id=uuid4())
        self.requests.admit(request["recoveryRequestId"])
        done = self.procedures.backup(request["recoveryRequestId"], via="in-person")
        assert done["state"] == "succeeded", done
        return next(item for item in self.ledger.records("backup-set")
                    if item["recoveryRequestId"] == request["recoveryRequestId"])

    def restore_request(self, *, backup: dict | None = None, predecessor: str | None = None,
                        admit: bool = True, incident_id: str | None = None) -> dict:
        from backend.modules.operations.ledger import utc_text

        chosen = backup or self.backup
        request = self.requests.request(
            origin="administrator", operation="restore.production", environment="live",
            target_id=chosen["backupId"],
            expected_revision=self.ledger.revision("backup-set", chosen["backupId"]),
            submission_id=uuid4(), requested_by=uuid4(), mfa_verified_at=utc_text(self.clock()),
            incident_id=incident_id)
        if not admit:
            return request
        approval = self.decide("production-restore", request["recoveryRequestId"])
        return self.requests.admit(request["recoveryRequestId"], approval_id=approval,
                                   predecessor_id=predecessor)

    def decide(self, step: str, subject: str) -> str:
        return rf.decide(self.operator, self.ledger, self.clock, step, subject)

    def fail(self, operation: str, fragment: str, times: int = 1) -> rf.FaultyOperator:
        faulty = rf.FaultyOperator(self.operator, {(operation, fragment): times})
        self.procedures.platform.operator = faulty
        return faulty

    def heal(self) -> None:
        self.procedures.platform.operator = self.operator

    def held(self) -> dict:
        """A restore held after its recreate: its restore step failed."""
        request = self.restore_request()
        self.fail("platform.database.restore", ":restore:")
        held = self.procedures.restore(request["recoveryRequestId"])
        self.heal()
        assert held["state"] == "held", held
        return held

    def close(self) -> None:
        self.ledger.close()
        self.database.drop()


@pytest.fixture
def stage(tmp_path, realm, clock):
    value = Stage(tmp_path, realm, clock)
    yield value
    value.close()


KEY_FOLDERS = ("export-keys", "control-keys", "verifier-key", "cursor-key")


def key_files(root) -> dict:
    """Each key folder's sorted file listing with each file's SHA-256."""
    import hashlib

    listing = {}
    for name in KEY_FOLDERS:
        folder = root / name
        listing[name] = sorted(
            (path.relative_to(folder).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest())
            for path in folder.rglob("*") if path.is_file()) if folder.is_dir() else None
    return listing


def test_the_full_path_records_every_receipt_and_keeps_every_owner(stage):
    from backend.modules.operations.errors import OperationsError
    from backend.modules.operations.incidents import Incidents
    from backend.modules.operations.readiness import CapabilityState

    before = stage.database.snapshot()
    allowance = LedgerAllowance(stage.ledger, SYNTHETIC_OPERATIONS)
    allowance.reserve("account", str(uuid4()))
    allowance.reserve("digest", str(uuid4()))
    counted = allowance.counts()
    # Step 89(c) (NFR9.3, BR4.8): the incident the restore answers stays in the ledger.
    incidents = Incidents(stage.ledger, environment="live")
    incident = incidents.signal("storage.capacity", "tolerance-exceeded", correlation="a")
    assert incidents.signal("storage.capacity", "tolerance-exceeded", correlation="b")[
        "incidentId"] == incident["incidentId"]
    identity = incident["incidentId"]
    incidents.begin_diagnosis(identity, "storage-capacity-restore")
    available = {"storage.capacity": CapabilityState("storage.capacity", "available", None)}
    request = stage.restore_request(incident_id=identity)
    incidents.link_recovery(identity, request["recoveryRequestId"])
    assert stage.ledger.get("service-incident", identity)["state"] == "recovering"
    with pytest.raises(OperationsError) as refused:
        incidents.resolve(identity, "capability-available", ["obs:1"], states=available)
    assert refused.value.code == "EVIDENCE_REQUIRED"
    keys = key_files(stage.realm.root)
    assert keys["verifier-key"] and keys["cursor-key"]  # non-empty before (L1-4)
    revisions = stage.ledger.revision("service-incident", identity)
    done = stage.procedures.restore(request["recoveryRequestId"])
    assert done["state"] == "succeeded", done["evidenceRefs"][-3:]
    kept = stage.ledger.get("service-incident", identity)
    assert stage.ledger.revision("service-incident", identity) == revisions
    assert (kept["correlationIds"], kept["recoveryRequestIds"], kept["diagnosisKey"],
            kept["state"]) == (["a", "b"], [request["recoveryRequestId"]],
                               "storage-capacity-restore", "recovering")
    for kind in ("abort-reviewed", "rollback-copy-settled"):
        with pytest.raises(OperationsError) as refused:
            incidents.resolve(identity, kind, ["obs:1"], states=available)
        assert refused.value.code == "EVIDENCE_REQUIRED", kind
    assert incidents.resolve(identity, "capability-available", ["obs:1"],
                             states=available)["state"] == "resolved"
    assert key_files(stage.realm.root) == keys
    refs = done["evidenceRefs"]
    for prefix in ("route-maintenance:", "stop:", "recreate:", "restore:", "integrity:passed",
                   "start-authorized", "start:", "route-back:", "routed-back"):
        assert any(ref.startswith(prefix) for ref in refs), (prefix, refs)
    pre = stage.ledger.get("backup-set", done["preRestoreBackupId"])
    post = stage.ledger.get("backup-set", done["postRestoreBackupId"])
    assert (pre["trigger"], post["trigger"]) == ("pre-restore", "post-restore")
    assert pre["integrity"] == post["integrity"] == "passed"
    assert done["startAuthorizedAt"] >= done["createdAt"]
    # Every receipt a record cites has its binding facts in the ledger.
    facts = {item["receiptId"] for item in stage.ledger.records("receipt-facts")}
    assert {pre["operatorReceiptRef"], post["operatorReceiptRef"]} <= facts
    # The public address routes back to v2, and v2's services run again.
    assert stage.journey.tunnel()["origin"] == "v2-host"
    assert stage.journey.read_state("services", f"{HOST}.json")["state"] == "running"
    # The restore login, which is not a superuser, kept every owner's ownership (D14).
    after = stage.database.snapshot()
    assert after == before
    with rf.login(stage.realm, "restore", stage.database.name) as conn:
        assert conn.execute("SELECT rolsuper FROM pg_roles WHERE rolname=current_user"
                            ).fetchone()[0] is False
    # The email allowance's count is unchanged by the restore (D12 item 4).
    assert allowance.counts() == counted


def test_an_erasure_newer_than_the_set_is_replayed(stage):
    request = stage.restore_request()
    Tombstones(stage.ledger).claim(stage.owner, uuid4())
    done = stage.procedures.restore(request["recoveryRequestId"])
    assert done["state"] == "succeeded", done
    assert "replayed:1" in done["evidenceRefs"]
    rows = stage.database.snapshot()["rows"]
    assert rows["library"] == []
    assert [row[2:] for row in rows["accounts"]] == [(False, "erased")]


def test_v2_start_is_refused_while_the_restore_runs_without_its_authorization(stage):
    request = stage.restore_request()
    running = stage.requests.start(request["recoveryRequestId"])
    assert running["state"] == "running"
    with pytest.raises(PreconditionRefused) as refused:
        stage.operator.execute("platform.service.control", HOST,
                               {"label": HOST, "action": "start"}, key=f"start-{uuid4()}")
    assert refused.value.reason == "restore-active-without-start-authorization"
    # A boot-time start meets the same refusal in v2's own start check.
    assert unauthorized_restore(stage.ledger.records("recovery-request")) == (
        request["recoveryRequestId"])


def test_a_failed_post_restore_backup_waits_and_retries_without_a_new_decision(stage):
    request = stage.restore_request()
    stage.fail("platform.database.backup", ":post-restore:")
    pending = stage.procedures.restore(request["recoveryRequestId"])
    stage.heal()
    assert pending["state"] == "post-restore-pending", pending
    # It still holds the live environment's exclusion: no disposal pass, no backup.
    assert stage.requests.production_restore_active()["recoveryRequestId"] == (
        request["recoveryRequestId"])
    assert "startAuthorizedAt" not in pending
    assert stage.journey.tunnel()["origin"] == "maintenance"
    decisions = len(stage.ledger.records("maintainer-approval"))
    done = stage.procedures.retry_post_restore(request["recoveryRequestId"])
    assert done["state"] == "succeeded", done
    assert len(stage.ledger.records("maintainer-approval")) == decisions


def test_a_held_restore_hands_its_exclusion_only_to_a_successor_that_runs(stage):
    before = stage.database.snapshot()
    held = stage.held()
    pre = stage.ledger.get("backup-set", held["preRestoreBackupId"])
    # A successor cancelled before it runs leaves the request held.
    first = stage.restore_request(backup=pre, predecessor=held["recoveryRequestId"])
    assert first["predecessorRequestId"] == held["recoveryRequestId"]
    stage.requests.cancel(first["recoveryRequestId"])
    assert stage.requests.get(held["recoveryRequestId"])["state"] == "held"
    successor = stage.restore_request(backup=pre, predecessor=held["recoveryRequestId"])
    assert stage.requests.get(held["recoveryRequestId"])["state"] == "held"
    done = stage.procedures.restore(successor["recoveryRequestId"])
    assert done["state"] == "succeeded", done
    ended = stage.requests.get(held["recoveryRequestId"])
    assert ended["state"] == "failed"
    assert ended["successorRequestId"] == successor["recoveryRequestId"]
    # A successor takes no pre-restore set: its predecessor's is its fallback.
    assert "preRestoreBackupId" not in done
    assert stage.database.snapshot() == before


def test_the_in_person_ledger_copy_lies_beside_both_restore_sets(stage, tmp_path):
    """Production's in-person ledger copy (role `operator`), not the realm's: the pre- and
    post-restore sets each have their LedgerCopy, asked for in person (review finding,
    Critical, R15)."""
    copies = rf.InPersonCopy(stage.procedures, stage.ledger, tmp_path)
    request = stage.restore_request()
    done = stage.procedures.restore(request["recoveryRequestId"])
    assert done["state"] == "succeeded", done["evidenceRefs"][-3:]
    copied = {item["backupId"] for item in stage.ledger.records("ledger-copy")}
    assert {done["preRestoreBackupId"], done["postRestoreBackupId"]} <= copied
    assert copies.vias == ["in-person", "in-person"]


def test_a_pre_restore_set_whose_ledger_copy_fails_restores_nothing(stage, tmp_path):
    """The pre-restore set is taken and recorded, but its in-person ledger copy is
    refused: the restore fails before its recreate with the fixed reason, v2 runs again
    on the untouched database, and nothing escapes after the set was recorded."""
    before = stage.database.snapshot()
    rf.InPersonCopy(stage.procedures, stage.ledger, tmp_path, failures=1)
    request = stage.restore_request()
    failed = stage.procedures.restore(request["recoveryRequestId"])
    assert failed["state"] == "failed", failed["evidenceRefs"]
    assert "failed:ledger-copy-failed" in failed["evidenceRefs"]
    assert not any(ref.startswith("recreate:") for ref in failed["evidenceRefs"])
    pre = [item for item in stage.ledger.records("backup-set")
           if item.get("recoveryRequestId") == request["recoveryRequestId"]]
    assert [item["trigger"] for item in pre] == ["pre-restore"]  # kept as evidence
    assert stage.database.snapshot() == before
    assert stage.journey.read_state("services", f"{HOST}.json")["state"] == "running"
    assert stage.requests.production_restore_active() is None


def test_a_post_restore_set_whose_ledger_copy_fails_waits_and_its_retry_copies(stage,
                                                                              tmp_path):
    """The post-restore set's ledger copy refused: `post-restore-pending` with the fixed
    reason, the exclusion still held; the retry takes its set with a copy beside it."""
    request = stage.restore_request()
    copies = rf.InPersonCopy(stage.procedures, stage.ledger, tmp_path)
    original = stage.procedures.platform.ledger_copy
    calls = []

    def second_refused() -> dict:
        calls.append(1)
        if len(calls) == 2:
            copies.failures = 1
        return original()

    stage.procedures.platform.ledger_copy = second_refused
    pending = stage.procedures.restore(request["recoveryRequestId"])
    assert pending["state"] == "post-restore-pending", pending["evidenceRefs"]
    assert "pending:ledger-copy-failed" in pending["evidenceRefs"]
    assert stage.requests.production_restore_active()["recoveryRequestId"] == (
        request["recoveryRequestId"])
    done = stage.procedures.retry_post_restore(request["recoveryRequestId"])
    assert done["state"] == "succeeded", done["evidenceRefs"]
    copied = {item["backupId"] for item in stage.ledger.records("ledger-copy")}
    assert done["postRestoreBackupId"] in copied


class Unsettled(rf.FaultyOperator):
    """The real operator with one injected fault (U7's `disk`: the outcome is lost), whose
    first `unsettled` reconciliations cannot settle it."""

    def __init__(self, operator, fault, *, unsettled: int = 1):
        super().__init__(operator)
        self.fault, self.unsettled = fault, unsettled

    def execute(self, operation, target, inputs, *, key, injected_fault=None, **options):
        for (name, fragment), fault in self.fault.items():
            if name == operation and fragment in key:
                self.fault = {}
                return self.operator.execute(operation, target, inputs, key=key,
                                             injected_fault=fault, **options)
        return self.operator.execute(operation, target, inputs, key=key, **options)

    def reconcile(self, operation_id):
        if self.unsettled:
            self.unsettled -= 1
            return {"reconciliationState": "unresolved", "operationId": operation_id}
        return self.operator.reconcile(operation_id)


def test_a_failure_before_the_recreate_restores_nothing_and_restarts_v2(stage):
    before = stage.database.snapshot()
    request = stage.restore_request()
    # The pre-restore set's outcome is lost; reconciliation finds it not applied, so the
    # step failed before anything was recreated.
    stage.procedures.platform.operator = Unsettled(
        stage.operator, {("platform.database.backup", ":pre-restore:"): "disk"}, unsettled=0)
    failed = stage.procedures.restore(request["recoveryRequestId"])
    stage.heal()
    assert failed["state"] == "failed", failed["evidenceRefs"]
    assert not any(ref.startswith("recreate:") for ref in failed["evidenceRefs"])
    # The request ended first; then v2 started on the untouched database and routed back.
    assert stage.database.snapshot() == before
    assert stage.journey.read_state("services", f"{HOST}.json")["state"] == "running"
    assert stage.journey.tunnel()["origin"] == "v2-host"
    assert stage.requests.production_restore_active() is None


def test_an_unknown_outcome_stays_active_until_its_receipt_settles_it(stage):
    request = stage.restore_request()
    stage.procedures.platform.operator = Unsettled(
        stage.operator, {("platform.database.restore", ":restore:"): "disk"})
    unknown = stage.procedures.restore(request["recoveryRequestId"])
    assert unknown["state"] == "unknown", unknown["evidenceRefs"]
    # Still active: a conflicting request waits, and v2 stays stopped.
    assert stage.requests.production_restore_active()["state"] == "unknown"
    assert unauthorized_restore(stage.ledger.records("recovery-request")) == (
        request["recoveryRequestId"])
    settled = stage.procedures.reconcile(request["recoveryRequestId"])
    stage.heal()
    # The recreate had begun, so the settled request is held, never re-run.
    assert settled["state"] == "held"
    assert "reconciled:reconciled-not-applied" in settled["evidenceRefs"]
    assert stage.procedures.reconcile(request["recoveryRequestId"]) == settled


def test_an_abandonment_recreates_empty_and_ends_only_after_its_receipt(stage):
    held = stage.held()
    identity = held["recoveryRequestId"]
    waiting = stage.restore_request(predecessor=identity)
    approval = stage.decide("restore-abandonment", identity)
    from backend.modules.operations.errors import OperationsError

    with pytest.raises(OperationsError) as refused:
        stage.requests.decide_abandonment(identity, approval)
    assert refused.value.current == {"reasonKey": "successor-waiting"}
    stage.requests.cancel(waiting["recoveryRequestId"])
    stage.requests.decide_abandonment(identity, approval)
    # A recreate that fails leaves it held, to retry under the same decision.
    stage.fail("platform.database.recreate", ":abandon-recreate:")
    retried = stage.procedures.abandon(identity)
    stage.heal()
    assert retried["state"] == "held" and "abandonedAt" not in retried
    ended = stage.procedures.abandon(identity)
    assert ended["state"] == "failed", ended
    assert ended["abandonedAt"] and ended["lossReportRef"]
    receipt = ended["abandonmentRecreateReceiptRef"]
    assert stage.ledger.get("receipt-facts", receipt)["operation"] == (
        "platform.database.recreate")
    # The database is empty: its schemas stand, no owner's table came back.
    assert stage.database.tables() == []
    # The same decision authorizes the start: v2 runs and the address routes back.
    assert stage.journey.tunnel()["origin"] == "v2-host"
