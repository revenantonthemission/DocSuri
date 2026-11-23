"""Retiring a lost backup volume (U8 plan Steps 30 and 65(e); BR4.10, NFR7.11, L1-18).

The fixed order runs through the realm's PlatformControl store and the realm driver on a
journey of the test's own: a production stand-in (`JourneyDatabase`), the backup agent's
own folder for it (`rf.journey_agent`) and a private ledger, so a take dumps the journey's
database and never the realm's. The agent's real `prepare-volume`, `configure` and
`status` act on a replacement folder under the test's temporary folder; the profile
operation changes the journey's own platform profile. The tests refused before the
profile step keep a recording stand-in agent, so each refusal is seen call by call.
"""

from __future__ import annotations

import json
from uuid import uuid4

import psycopg
import pytest

from backend.local_profile import private_bytes
from backend.modules.operations.errors import OperationsError
from backend.modules.operations.incidents import Incidents
from backend.modules.operations.ledger import utc_text
from backend.modules.operations.lifecycle import backups_evidence
from backend.modules.operations.retained_copies import RetainedCopies
from backend.u8_policy import SYNTHETIC_OPERATIONS
from docsuri_ops.backup_agent.catalogue import Catalogue
from docsuri_ops.u8_platform.recovery_words import realm_procedures
from docsuri_ops.u8_platform.u8_protocols import readers
from tests.u8_service_operations_integration import platform_flows as pf
from tests.u8_service_operations_integration import recovery_flows as rf

IDENTITY = "replacement-volume-0002"
OPEN = ("platform.database.backup", "platform.ledger.copy")


class Agent:
    """The agent's in-person words, recorded; its status reports `identity`."""

    def __init__(self, identity: str = IDENTITY, available: bool = True):
        self.identity, self.available, self.calls = identity, available, []

    def __call__(self, word: str, document: dict, *, via: str) -> dict:
        self.calls.append((word, via))
        if word == "status":
            return {"available": self.available, "volumeIdentity": self.identity}
        return {"ok": True}


@pytest.fixture
def setting(tmp_path, realm, clock):
    database = rf.JourneyDatabase(realm).create()
    database.add_owner()
    agent = rf.journey_agent(tmp_path, realm, database, clock)
    ledger = rf.open_ledger(tmp_path, clock)
    journey = pf.journey(tmp_path, realm, mode="live", admission="open",
                         agentFolder=str(agent), ledgerFolder=str(tmp_path / "operations-ledger"))
    wiring = realm_procedures(journey.profile, ledger, clock=clock, ready=lambda: True,
                              names=database.names, free_bytes=lambda: 100 * rf.GIB,
                              mfa_current=lambda account, at: True)
    replacement = tmp_path / "replacement"
    replacement.mkdir(mode=0o700)
    extra: list[rf.JourneyDatabase] = []
    value = {"ledger": ledger, "procedures": wiring.procedures, "journey": journey,
             "clock": clock, "database": database, "replacement": replacement,
             "mount": str(replacement), "extra": extra, "realm": realm,
             "old_volume": tmp_path / "volume"}
    try:
        yield value
    finally:
        ledger.close()
        for item in [database, *extra]:
            item.drop()


def decided(setting) -> str:
    approval = rf.decide(setting["procedures"].platform.operator, setting["ledger"],
                         setting["clock"], "backup-volume-retirement", "standin-volume-0001")
    setting["clock"].advance(1)  # the run follows your decision
    return approval


def retire(setting, approval: str) -> dict:
    return setting["procedures"].retire_volume(approval, mount=setting["mount"],
                                               identity=IDENTITY)


def old_records(setting) -> tuple[dict, dict, dict]:
    """A set, its ledger copy and a snapshot on the lost volume, recorded before your
    decision."""
    ledger, clock = setting["ledger"], setting["clock"]
    backup = rf.set_record(ledger, now=clock(), database=setting["database"].name)
    copy_receipt = rf.receipt(now=clock())
    copy = {
        "ledgerCopyId": str(uuid4()), "backupId": backup["backupId"],
        "takenAt": backup["takenAt"], "location": "archives/ledger-copy-1.archive",
        "stagingLocation": "staging/ledger-copy-1", "digest": "a" * 64, "headSequence": 3,
        "headDigest": "b" * 64, "retainUntil": backup["retainUntil"],
        "operatorReceiptRef": copy_receipt["receiptId"], "verifiedAt": backup["takenAt"],
    }
    ledger.append("ledger-copy", copy, expect_revision=0, receipts=(copy_receipt,))
    snapshot = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock).record(
        "dry-run-snapshot", "run:1", ["backup-volume/archives/snap"])
    return backup, copy, snapshot


def new_sets(setting) -> list[dict]:
    return [item for item in setting["ledger"].records("backup-set")
            if item["trigger"] == "volume-retirement"]


def on_replacement(setting, location: str) -> bool:
    folder = setting["replacement"] / "docsuri-v2"
    catalogue = Catalogue.open(folder, clock=setting["clock"])
    try:
        listed = location in catalogue.files()
    finally:
        catalogue.close()
    return listed and (folder / location).is_file()


def storage_incidents(setting, environment: str) -> list[str]:
    incident = Incidents(setting["ledger"], environment=environment).open_for("storage.capacity")
    return [] if incident is None else list(incident["correlationIds"])


def test_the_fixed_order_and_every_record_closed(setting):
    ledger = setting["ledger"]
    rf.cutover_record(ledger, "preparing")
    backup, _, snapshot = old_records(setting)
    copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=setting["clock"])
    database = copies.record("rehearsal-database", "run:1", ["database/docsuri_u8_rehearsal_x"])
    result = retire(setting, decided(setting))
    assert result["order"] == ["decision", "prepare-volume", "configure", "status", "profile",
                               "comparison", "backup"]
    assert setting["journey"].read_state("profile.json")["backupVolume"] == {
        "identity": IDENTITY, "mount": setting["mount"]}
    # Every record with files on the lost volume is closed; the new set and copy are not.
    assert result["closed"] == 3 and "takeFailed" not in result
    assert "retiredWithVolumeAt" in ledger.get("backup-set", backup["backupId"])
    assert "retiredWithVolumeAt" in copies.get(snapshot["copyId"])
    [taken] = new_sets(setting)
    assert "retiredWithVolumeAt" not in taken
    copies_of = [item for item in ledger.records("ledger-copy")
                 if item.get("backupId") == taken["backupId"]]
    assert len(copies_of) == 1 and "retiredWithVolumeAt" not in copies_of[0]
    # A database on the internal disk was never on the volume.
    assert "retiredWithVolumeAt" not in copies.get(database["copyId"])


@pytest.mark.parametrize("environment", ["live", "rehearsal"])
def test_a_backup_and_a_ledger_copy_go_to_the_replacement_at_once(setting, environment):
    ledger = setting["ledger"]
    rf.cutover_record(ledger, "preparing")
    database = setting["database"].name
    if environment == "rehearsal":
        rehearsal = rf.JourneyDatabase(setting["realm"],
                                       name=setting["database"].names.new("rehearsal")).create()
        setting["extra"].append(rehearsal)
        setting["journey"].set_profile(mode="rehearsal", rehearsalDatabase=rehearsal.name)
        database = rehearsal.name
    backup, copy, _ = old_records(setting)
    before = sorted(str(path) for path in setting["old_volume"].rglob("*"))
    result = retire(setting, decided(setting))
    assert "takeFailed" not in result, result
    [taken] = new_sets(setting)
    assert (taken["integrity"], taken["environment"]) == ("passed", environment)
    assert taken["databaseIncarnation"].startswith(f"{database}:")
    [beside] = [item for item in ledger.records("ledger-copy")
                if item.get("backupId") == taken["backupId"]]
    retired_at = ledger.get("backup-set", backup["backupId"])["retiredWithVolumeAt"]
    assert ledger.get("ledger-copy", copy["ledgerCopyId"])["retiredWithVolumeAt"] == retired_at
    assert taken["takenAt"] >= retired_at and beside["takenAt"] >= retired_at
    assert "retiredWithVolumeAt" not in taken and "retiredWithVolumeAt" not in beside
    assert on_replacement(setting, taken["location"])
    assert on_replacement(setting, beside["location"])
    # The old volume gains no file, and the profile names the replacement.
    assert sorted(str(path) for path in setting["old_volume"].rglob("*")) == before
    assert setting["journey"].read_state("profile.json")["backupVolume"]["identity"] == IDENTITY


def held_restore(setting) -> str:
    ledger, clock = setting["ledger"], setting["clock"]
    requests = setting["procedures"].requests
    target = rf.set_record(ledger, now=clock(), database=setting["database"].name)
    request = requests.request(origin="administrator", operation="restore.production",
                               environment="live", target_id=target["backupId"],
                               expected_revision=1, submission_id=uuid4(),
                               requested_by=uuid4(), mfa_verified_at=utc_text(clock()))
    approval = rf.approval_record(ledger, "production-restore", request["recoveryRequestId"],
                                  now=clock())
    requests.admit(request["recoveryRequestId"], approval_id=approval["approvalId"])
    requests.start(request["recoveryRequestId"])
    requests.advance(request["recoveryRequestId"], "held", allowed_from=("running",))
    return request["recoveryRequestId"]


def rolling_back(setting) -> None:
    ledger = setting["ledger"]
    record = rf.cutover_record(ledger, "preparing")
    for step in ("rehearsing", "ready-to-switch", "switching", "switched", "rolling-back"):
        record = rf.advance_cutover(ledger, record, step)
    rf.advance_cutover(ledger, record, "rolling-back",
                       rollbackCopyPendingSince=utc_text(setting["clock"]()))


@pytest.mark.parametrize("case", ["restore", "rollback", "nothing-to-dump"])
def test_with_a_restore_a_rollback_or_nothing_to_dump_only_the_ledger_copy_is_taken(setting,
                                                                                     case):
    ledger = setting["ledger"]
    environment = "live"
    if case == "restore":
        rf.cutover_record(ledger, "preparing")
        held_restore(setting)
    elif case == "rollback":
        rolling_back(setting)
    else:
        rf.cutover_record(ledger, "preparing")
        setting["journey"].set_profile(mode="rehearsal", rehearsalDatabase=None)
        environment = "rehearsal"
    sets_before = len(ledger.records("backup-set"))
    result = retire(setting, decided(setting))
    assert result["order"][-2:] == ["comparison", "ledger-copy"]
    assert "takeFailed" not in result, result
    assert len(ledger.records("backup-set")) == sets_before
    [lone] = [item for item in ledger.records("ledger-copy") if "backupId" not in item]
    assert on_replacement(setting, lone["location"]) and lone["verifiedAt"]
    facts = ledger.get("receipt-facts", lone["operatorReceiptRef"])
    assert (facts["operation"], facts["outcome"]) == ("platform.ledger.copy", "succeeded")
    assert storage_incidents(setting, environment) == []
    if case == "restore":
        assert not [item for item in ledger.records("backup-set")
                    if item["trigger"] == "post-restore"]


def test_a_failed_backup_on_the_replacement_is_reported_and_the_retirement_stands(setting):
    ledger = setting["ledger"]
    rf.cutover_record(ledger, "preparing")
    backup, _, _ = old_records(setting)
    platform = setting["procedures"].platform
    approval = decided(setting)
    platform.operator = rf.FaultyOperator(platform.operator,
                                          {("platform.database.backup", "retire-volume"): 1})
    result = retire(setting, approval)
    assert setting["journey"].read_state("profile.json")["backupVolume"]["identity"] == IDENTITY
    assert "retiredWithVolumeAt" in ledger.get("backup-set", backup["backupId"])
    assert result["takeFailed"] == "backup-failed"
    assert f"retire-volume:{approval}" in storage_incidents(setting, "live")


def test_a_second_run_closes_nothing_on_the_replacement(setting):
    rf.cutover_record(setting["ledger"], "preparing")
    old_records(setting)
    approval = decided(setting)
    first = retire(setting, approval)
    assert first["closed"] == 3
    [taken] = new_sets(setting)
    setting["clock"].advance(60)
    second = retire(setting, approval)
    assert second["closed"] == 0 and "takeFailed" not in second
    assert new_sets(setting) == [taken]  # the take replayed: no second set
    ledger = setting["ledger"]
    assert "retiredWithVolumeAt" not in ledger.get("backup-set", taken["backupId"])
    beside = [item for item in ledger.records("ledger-copy")
              if item.get("backupId") == taken["backupId"]]
    assert len(beside) == 1 and "retiredWithVolumeAt" not in beside[0]


class Cut(BaseException):
    """The operator tool closed in the middle of the take."""


def store_rows(setting, query: str, params: tuple) -> list[tuple]:
    """PlatformControl's own rows, through the realm's administrator login."""
    realm, profile = setting["realm"], setting["journey"].profile
    password = json.loads(private_bytes(realm.root / "migration-credentials.json"))[
        "databaseAdminPassword"]
    with psycopg.connect(host="127.0.0.1", port=profile.port, dbname=profile.database,
                         user="postgres", password=password, autocommit=True,
                         connect_timeout=5) as conn:
        return conn.execute(query, params).fetchall()


def settle_open(setting, operator, operation: str) -> None:
    """The take's operation, if still open, settled through the login that bound it."""
    [(state, reconciliation)] = store_rows(setting, (
        "SELECT o.state, r.reconciliation_state FROM platform_control.operation o JOIN "
        "platform_control.receipt r USING (operation_id) WHERE o.operation_id = %s"),
        (operation,))
    if state == "authorized":
        operator.store.mark_executing(operation)
        state = "executing"
    if state == "executing":
        operator.store.settle_operation(operation_id=operation, outcome="failed",
                                        disposition="not-applied", effect_refs=[])
    elif reconciliation == "unresolved":
        operator.store.reconcile_receipt(operation_id=operation, applied=False,
                                         evidence=["test-cleanup"])


def test_an_interrupted_take_is_settled_by_running_the_retirement_again(setting):
    rf.cutover_record(setting["ledger"], "preparing")
    old_records(setting)
    approval = decided(setting)
    operator = setting["procedures"].platform.operator
    built = operator.run_effect

    def cut(**request):
        if request["operation_name"] == "platform.database.backup":
            raise Cut()  # the take's own effect, cut off mid-effect
        return built(**request)

    operator.run_effect = cut
    with pytest.raises(Cut):
        retire(setting, approval)
    operator.run_effect = built
    key = f"retire-volume:{approval}:backup"
    # The try opens before the lookup (review fix, batch 4): a lookup that finds no row
    # still settles whatever the cut left open on the realm's shared store.
    try:
        [(operation,)] = store_rows(setting, (
            "SELECT operation_id::text FROM platform_control.operation WHERE "
            "authority_actor = %s AND idempotency_key = %s"), (operator.actor, key))
        inspector = readers(setting["journey"].profile)[2]
        store_rows(setting, (
            "UPDATE platform_control.target_lease SET deadline_at = clock_timestamp() - "
            "interval '1 second' WHERE operation_id = %s RETURNING operation_id"), (operation,))
        assert operation in {item["operationId"] for item in inspector.open_operations(OPEN)}
        second = retire(setting, approval)
        assert second["closed"] == 0 and second["takeFailed"]
        assert operation not in {item["operationId"] for item in inspector.open_operations(OPEN)}
        assert new_sets(setting) == []
    finally:
        for (bound,) in store_rows(setting, (
                "SELECT operation_id::text FROM platform_control.operation WHERE "
                "authority_actor = %s AND starts_with(idempotency_key, %s)"),
                (operator.actor, f"retire-volume:{approval}:")):
            settle_open(setting, operator, bound)


def test_each_closed_record_carries_the_retirements_receipt(setting):
    ledger = setting["ledger"]
    rf.cutover_record(ledger, "preparing")
    old_records(setting)
    approval_id = decided(setting)
    retire(setting, approval_id)
    approval = ledger.get("maintainer-approval", approval_id)
    closed = [item for kind in ("backup-set", "ledger-copy", "retained-copy")
              for item in ledger.records(kind) if "retiredWithVolumeAt" in item]
    assert len(closed) == 3
    assert {item["retirementReceiptRef"] for item in closed} == {approval["operatorReceiptRef"]}
    facts = ledger.get("receipt-facts", approval["operatorReceiptRef"])
    assert facts["operation"] == "platform.decision.record"
    evidence = backups_evidence(ledger, SYNTHETIC_OPERATIONS, schedule_active=True)
    [group] = evidence["retired"]
    assert group["volume"] == approval["subjectRef"] and group["count"] == 3
    assert group["retiredAt"] == closed[0]["retiredWithVolumeAt"]


@pytest.mark.parametrize("state", ["switching", "aborting"])
def test_refused_while_a_switch_or_an_abort_holds_the_exclusion(setting, state):
    ledger = setting["ledger"]
    agent = Agent()
    setting["procedures"].platform.agent = agent
    record = rf.cutover_record(ledger, "preparing")
    for step in ("rehearsing", "ready-to-switch", "switching"):
        record = rf.advance_cutover(ledger, record, step)
    if state == "aborting":
        record = rf.advance_cutover(ledger, record, "aborting")
    with pytest.raises(OperationsError) as refused:
        retire(setting, decided(setting))
    assert refused.value.current == {"reasonKey": "live-exclusion-held"}
    assert agent.calls == []


def test_during_a_rollback_only_while_its_copy_waits(setting):
    ledger = setting["ledger"]
    record = rf.cutover_record(ledger, "preparing")
    for step in ("rehearsing", "ready-to-switch", "switching", "switched", "rolling-back"):
        record = rf.advance_cutover(ledger, record, step)
    approval = decided(setting)
    with pytest.raises(OperationsError) as refused:
        retire(setting, approval)
    assert refused.value.current == {"reasonKey": "rollback-not-waiting"}
    rf.advance_cutover(ledger, record, "rolling-back",
                       rollbackCopyPendingSince=utc_text(setting["clock"]()))
    assert retire(setting, approval)["order"][-1] == "ledger-copy"


def test_during_a_restore_only_while_it_waits(setting):
    ledger, clock = setting["ledger"], setting["clock"]
    rf.cutover_record(ledger, "preparing")
    requests = setting["procedures"].requests
    backup = rf.set_record(ledger, now=clock(), database=setting["database"].name)
    request = requests.request(origin="administrator", operation="restore.production",
                               environment="live", target_id=backup["backupId"],
                               expected_revision=1, submission_id=uuid4(),
                               requested_by=uuid4(), mfa_verified_at=utc_text(clock()))
    approval = rf.approval_record(ledger, "production-restore", request["recoveryRequestId"],
                                  now=clock())
    requests.admit(request["recoveryRequestId"], approval_id=approval["approvalId"])
    requests.start(request["recoveryRequestId"])
    retirement = decided(setting)
    with pytest.raises(OperationsError) as refused:
        retire(setting, retirement)
    assert refused.value.current == {"reasonKey": "restore-not-waiting"}
    requests.advance(request["recoveryRequestId"], "held", allowed_from=("running",))
    assert retire(setting, retirement)["closed"] == 1
    lone = [item for item in ledger.records("ledger-copy") if "backupId" not in item]
    assert len(lone) == 1


def test_the_status_check_must_pass_on_that_volume_before_the_profile_names_it(setting):
    rf.cutover_record(setting["ledger"], "preparing")
    setting["procedures"].platform.agent = Agent(identity="another-volume")
    before = setting["journey"].read_state("profile.json")["backupVolume"]
    with pytest.raises(OperationsError) as refused:
        retire(setting, decided(setting))
    assert refused.value.current == {"reasonKey": "volume-check-failed"}
    assert setting["journey"].read_state("profile.json")["backupVolume"] == before


def test_retirement_needs_your_decision(setting):
    agent = Agent()
    setting["procedures"].platform.agent = agent
    other = rf.approval_record(setting["ledger"], "production-restore", "x",
                               now=setting["clock"]())
    with pytest.raises(OperationsError) as refused:
        setting["procedures"].retire_volume(other["approvalId"], mount=setting["mount"],
                                            identity=IDENTITY)
    assert refused.value.code == "FORBIDDEN"
    assert agent.calls == []


def test_a_retirement_without_its_environment_is_refused(setting):
    import dataclasses

    procedures = setting["procedures"]
    procedures.platform = dataclasses.replace(procedures.platform, current_environment=None)
    with pytest.raises(OperationsError) as refused:
        retire(setting, decided(setting))
    assert refused.value.code == "DEPENDENCY_UNAVAILABLE"
