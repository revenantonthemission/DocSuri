"""ServiceOperations' backups evidence and its readiness (U8 plan Step 18; BR2.5, BR2.6).

The evidence is computed from a real ledger in a private temporary folder, with the
injected clock; the records are appended through the ledger component.
"""

from __future__ import annotations

import datetime as dt
from uuid import uuid4

import pytest

from backend.modules.operations.ledger import Ledger, utc_text
from backend.modules.operations.lifecycle import (
    INTERNAL_DISK_KINDS,
    EvidencePending,
    OperationsLifecycleParticipant,
    backups_evidence,
    covering_verification,
)
from backend.modules.operations.tombstones import Tombstones
from backend.u8_policy import PRODUCTION_OPERATIONS

POLICY = PRODUCTION_OPERATIONS
DAY = dt.timedelta(days=1)


@pytest.fixture
def ledger(tmp_path, clock):
    folder = tmp_path / "ledger"
    folder.mkdir(mode=0o700)
    clock.now = dt.datetime(2026, 10, 22, 4, 0, tzinfo=dt.UTC)
    value = Ledger.open(folder, clock=clock)
    yield value
    value.close()


def when(ledger, delta: dt.timedelta = dt.timedelta()) -> str:
    return utc_text(ledger.clock() + delta)


def add_set(ledger, *, environment="live", integrity="passed", retain=14 * DAY,
            staging_removed=True, **fields) -> dict:
    receipt = str(uuid4())
    record = {
        "backupId": str(uuid4()), "environment": environment, "revision": 1,
        "trigger": "scheduled", "takenAt": when(ledger), "checksum": "b" * 64,
        "sizeBytes": 10, "sourceDatabaseBytes": 20, "location": "archives/a.dump",
        "databaseIncarnation": "cluster:docsuri_v2:1", "stagingLocation": "staging/a.dump",
        "retainUntil": when(ledger, retain),
        "integrity": integrity, "operatorReceiptRef": receipt, **fields,
    }
    if staging_removed:
        record["stagingRemovedAt"] = when(ledger)
    ledger.append("backup-set", record, expect_revision=0, receipts=[{
        "receiptId": receipt, "operationId": str(uuid4()), "operation":
        "platform.database.backup", "targetId": "docsuri_v2", "inputHash": "c" * 64,
        "outcome": "succeeded", "confirmedAt": when(ledger)}])
    return record


def add_copy(ledger, kind: str, dispose_after: dt.timedelta, **fields) -> dict:
    record = {
        "copyId": str(uuid4()), "kind": kind, "sourceRef": str(uuid4()),
        "createdAt": when(ledger), "locations": ["db:docsuri_v2_import_0123456789ab"],
        "disposeAfter": when(ledger, dispose_after), **fields,
    }
    ledger.append("retained-copy", record, expect_revision=0)
    return record


BUILT_KEYS = ("setsCounted", "copiesCounted", "retiredCounted", "latestGoneAt")


def built(evidence: dict) -> dict:
    """The four keys the evidence carried before Step 64(f)'s lists."""
    return {key: evidence[key] for key in BUILT_KEYS if key in evidence}


def test_the_dates_retain_until_the_approved_date_the_backstop_and_the_internal_tail(ledger):
    add_set(ledger, retain=14 * DAY)
    add_set(ledger, environment="rehearsal", retain=8 * 7 * DAY)
    assert backups_evidence(ledger, POLICY, schedule_active=True)["latestGoneAt"] == when(
        ledger, 56 * DAY)
    add_copy(ledger, "v1-final-snapshot", 100 * DAY)  # your approved date, on the volume
    assert backups_evidence(ledger, POLICY, schedule_active=True)["latestGoneAt"] == when(
        ledger, 100 * DAY)
    add_copy(ledger, "dry-run-snapshot", 14 * DAY)  # an event copy's backstop
    add_copy(ledger, "import-database", 110 * DAY)  # on the internal disk: +24 hours
    evidence = backups_evidence(ledger, POLICY, schedule_active=True)
    assert built(evidence) == {"setsCounted": 2, "copiesCounted": 3, "retiredCounted": 0,
                               "latestGoneAt": when(ledger, 111 * DAY)}
    assert sorted(item["goneAt"] for item in evidence["undisposed"]) == sorted(
        when(ledger, days * DAY) for days in (14, 56, 100, 14, 111))
    assert evidence["retired"] == []
    assert {"rehearsal-database", "import-database", "scratch-restore",
            "v1-stores"} == INTERNAL_DISK_KINDS


def test_a_staging_file_left_behind_counts_until_the_day_after_its_write(ledger):
    # A disposed set whose staging file a failed write left on the volume.
    add_set(ledger, retain=14 * DAY, staging_removed=False, disposedAt=when(ledger, DAY))
    add_set(ledger, retain=3 * DAY)
    evidence = backups_evidence(ledger, POLICY, schedule_active=True)
    assert evidence["setsCounted"] == 2
    assert evidence["latestGoneAt"] == when(ledger, 3 * DAY)


def test_a_set_held_by_the_floor_blocks_the_scope(ledger):
    add_set(ledger, retain=14 * DAY, heldByFloorSince=when(ledger))
    with pytest.raises(EvidencePending) as pending:
        backups_evidence(ledger, POLICY, schedule_active=True)
    assert str(pending.value) == "last-backup-held"


def test_a_copy_retired_with_a_lost_volume_is_listed_as_retired(ledger):
    add_set(ledger, retain=14 * DAY)
    add_set(ledger, retain=40 * DAY, retiredWithVolumeAt=when(ledger))
    add_copy(ledger, "v1-final-snapshot", 90 * DAY, retiredWithVolumeAt=when(ledger))
    add_copy(ledger, "v1-stores", 5 * DAY, returnedToServiceAt=when(ledger))
    evidence = backups_evidence(ledger, POLICY, schedule_active=True)
    assert built(evidence) == {"setsCounted": 1, "copiesCounted": 0, "retiredCounted": 2,
                               "latestGoneAt": when(ledger, 14 * DAY)}
    # Neither carries `retirementReceiptRef`: one group, its volume unknown.
    assert evidence["retired"] == [{"volume": None, "retiredAt": when(ledger), "count": 2}]
    assert [item["kind"] for item in evidence["undisposed"]] == ["backup-set"]


def test_the_scope_stays_blocked_while_no_live_set_has_passed(ledger):
    with pytest.raises(EvidencePending) as none:
        backups_evidence(ledger, POLICY, schedule_active=True)
    assert str(none.value) == "no-live-backup-passed"
    add_set(ledger, environment="rehearsal")
    add_set(ledger, integrity="failed")
    add_set(ledger, integrity="unchecked")
    with pytest.raises(EvidencePending):
        backups_evidence(ledger, POLICY, schedule_active=True)
    add_set(ledger)
    with pytest.raises(EvidencePending) as inactive:
        backups_evidence(ledger, POLICY, schedule_active=False)
    assert str(inactive.value) == "backup-schedule-inactive"
    assert backups_evidence(ledger, POLICY, schedule_active=True)["setsCounted"] == 4


def test_readiness_spends_one_attempt_then_waits_for_evidence(ledger):
    participant = OperationsLifecycleParticipant(None, ledger, POLICY,
                                                 schedule_active=lambda: True,
                                                 open_operations=lambda names: [],
                                                 agent_status=lambda target: None)
    request = {"id": uuid4(), "account_id": uuid4(), "action": "erase"}
    assert participant.ready(request, "backups")  # the first attempt is claimed
    participant._record(str(request["id"]), "backups", "erase",
                        {"state": "waiting", "reasonKey": "no-live-backup-passed"})
    assert not participant.ready(request, "backups")
    add_set(ledger)
    assert participant.ready(request, "backups")
    # restore_enforcement: the first claim appends the tombstone; then it waits for a
    # verification that covers it.
    assert participant.ready(request, "restore_enforcement")
    tombstone = Tombstones(ledger).claim(request["account_id"], request["id"])
    assert not participant.ready(request, "restore_enforcement")
    head = Tombstones(ledger).head()
    verification = {
        "verificationId": str(uuid4()), "environment": "live", "backupId": str(uuid4()),
        "startedAt": when(ledger), "registerHeadSequence": head["sequence"],
        "registerHeadDigest": head["digest"], "integrity": "passed",
        "erasedOwnersSurviving": 0, "result": "verified", "evidenceRef": "evidence/v.json",
        "scratchRemovedAt": when(ledger),
    }
    ledger.append("restore-verification", verification, expect_revision=0)
    assert covering_verification(ledger, tombstone)["verificationId"] == (
        verification["verificationId"])
    assert participant.ready(request, "restore_enforcement")
    withdraw = {**request, "id": uuid4(), "action": "withdraw"}
    assert participant.ready(withdraw, "restore_enforcement")


def test_a_rehearsal_or_failed_verification_never_covers_a_tombstone(ledger):
    tombstone = Tombstones(ledger).claim(uuid4(), uuid4())
    head = Tombstones(ledger).head()
    base = {
        "backupId": str(uuid4()), "startedAt": when(ledger),
        "registerHeadSequence": head["sequence"], "registerHeadDigest": head["digest"],
        "evidenceRef": "evidence/v.json",
    }
    ledger.append("restore-verification", {**base, "verificationId": str(uuid4()),
                                            "environment": "rehearsal", "result": "verified",
                                            "integrity": "passed", "erasedOwnersSurviving": 0,
                                            "scratchRemovedAt": when(ledger)},
                  expect_revision=0)
    ledger.append("restore-verification", {**base, "verificationId": str(uuid4()),
                                            "environment": "live", "result": "failed",
                                            "integrity": "failed"}, expect_revision=0)
    assert covering_verification(ledger, tombstone) is None


# --- Step 65(a)-(b): tails, named items, waiting while written, the verification's times ---


def facts_for(ledger, receipt: str, operation: str = "platform.decision.record") -> dict:
    return {"receiptId": receipt, "operationId": str(uuid4()), "operation": operation,
            "targetId": "decisions", "inputHash": "c" * 64, "outcome": "succeeded",
            "confirmedAt": when(ledger)}


def add_retirement(ledger, volume: str) -> str:
    """A `backup-volume-retirement` approval whose subject is `volume`; its receipt."""
    receipt = str(uuid4())
    ledger.append("maintainer-approval", {
        "approvalId": str(uuid4()), "step": "backup-volume-retirement", "subjectRef": volume,
        "subjectDigest": "d" * 64, "decision": "approved", "recordedAt": when(ledger),
        "operatorReceiptRef": receipt}, expect_revision=0, receipts=[facts_for(ledger, receipt)])
    return receipt


def status(ledger, *, age=dt.timedelta(), **observations) -> dict:
    """The agent's latest status as the platform part's evidence reader answers it."""
    values = {"catalogue": "intact", "deletionAllowed": True, "unrecordedCount": 0,
              "unrecordedFiles": [], **observations}
    return {"observations": values, "observedAt": (ledger.clock() - age).isoformat(),
            "maxAgeSeconds": 600}


def disposed(ledger, kind: str, at: dt.datetime, dispose_after=DAY) -> dict:
    return add_copy(ledger, kind, dispose_after, disposedAt=utc_text(at),
                    disposalAgentRef=f"agent-disposed:{kind}")


def test_an_internal_disk_copys_date_is_its_removal_or_backstop_plus_a_day(ledger, clock):
    add_set(ledger, retain=dt.timedelta(hours=1))
    tail = dt.timedelta(seconds=86_400)
    for kind in ("rehearsal-database", "import-database", "scratch-restore"):
        add_copy(ledger, kind, 3 * DAY)
        add_copy(ledger, kind, 4 * DAY, disposalPendingSince=when(ledger))
    evidence = backups_evidence(ledger, POLICY, schedule_active=True)
    dates = sorted(item["goneAt"] for item in evidence["undisposed"]
                   if item["kind"] != "backup-set")
    assert dates == sorted([when(ledger, 3 * DAY + tail)] * 3 + [when(ledger, 4 * DAY + tail)] * 3)
    # Each of those disposed at T counts until T + 86,400 s, and not at that instant.
    removed_at = ledger.clock()
    gone = {disposed(ledger, kind, removed_at)["copyId"]
            for kind in ("rehearsal-database", "import-database", "scratch-restore")}
    # A disposed dry-run snapshot, final snapshot and rolled-back copy are not counted.
    volume = {disposed(ledger, kind, removed_at)["copyId"]
              for kind in ("dry-run-snapshot", "v1-final-snapshot", "rolled-back-v2-database")}
    clock.now = removed_at + dt.timedelta(seconds=86_399)
    named = {item["recordId"]: item["goneAt"]
             for item in backups_evidence(ledger, POLICY, schedule_active=True)["undisposed"]}
    assert all(named[copy] == utc_text(removed_at + tail) for copy in gone)
    assert not volume & set(named)  # where the tail would still count them
    clock.now = removed_at + tail
    named = {item["recordId"] for item in backups_evidence(
        ledger, POLICY, schedule_active=True)["undisposed"]}
    assert not gone & named
    assert not volume & named
    # Undisposed volume kinds carry no tail.
    snapshot = add_copy(ledger, "dry-run-snapshot", 14 * DAY)
    named = {item["recordId"]: item["goneAt"]
             for item in backups_evidence(ledger, POLICY, schedule_active=True)["undisposed"]}
    assert named[snapshot["copyId"]] == snapshot["disposeAfter"]
    # v1's stores: the tail while undisposed; no longer counted once disposed in person.
    stores = add_copy(ledger, "v1-stores", 90 * DAY, disposalApprovalId=str(uuid4()))
    named = {item["recordId"]: item["goneAt"]
             for item in backups_evidence(ledger, POLICY, schedule_active=True)["undisposed"]}
    assert named[stores["copyId"]] == when(ledger, 90 * DAY + tail)
    later = disposed(ledger, "v1-stores", ledger.clock())
    named = {item["recordId"] for item in backups_evidence(
        ledger, POLICY, schedule_active=True)["undisposed"]}
    assert later["copyId"] not in named


def test_the_backups_evidence_names_each_undisposed_set_and_copy_with_its_date(ledger, clock):
    from docsuri_ops.platform_control.errors import ControlError

    live = add_set(ledger, retain=14 * DAY)
    sunday = add_set(ledger, environment="rehearsal", retain=56 * DAY)
    left = add_set(ledger, retain=14 * DAY, staging_removed=False, disposedAt=when(ledger, DAY))
    copies = {kind: add_copy(ledger, kind, days * DAY) for kind, days in (
        ("dry-run-snapshot", 14), ("import-database", 14), ("rehearsal-database", 60))}
    copies["v1-final-snapshot"] = add_copy(ledger, "v1-final-snapshot", 120 * DAY,
                                           disposalApprovalId=str(uuid4()))
    copies["rolled-back-v2-database"] = add_copy(ledger, "rolled-back-v2-database", 90 * DAY,
                                                 disposalApprovalId=str(uuid4()))
    receipt = add_retirement(ledger, "standin-volume-0001")
    add_set(ledger, retain=40 * DAY, retiredWithVolumeAt=when(ledger),
            retirementReceiptRef=receipt)
    disposed(ledger, "dry-run-snapshot", ledger.clock())  # never listed
    stray = str(uuid4())
    current = status(ledger, unrecordedCount=2, unrecordedFiles=[
        {"recordId": stray, "path": "archives/stray.archive",
         "disposeAfter": when(ledger, 5 * DAY)},
        {"recordId": live["backupId"], "path": "archives/a.dump",
         "disposeAfter": live["retainUntil"]}])
    evidence = backups_evidence(ledger, POLICY, schedule_active=True,
                                agent_status=lambda target: current)
    tail = DAY
    expected = {
        (live["backupId"], "backup-set", live["retainUntil"]),
        (sunday["backupId"], "backup-set", sunday["retainUntil"]),
        (left["backupId"], "staging-file", utc_text(ledger.clock() + DAY)),
        (copies["dry-run-snapshot"]["copyId"], "dry-run-snapshot", when(ledger, 14 * DAY)),
        (copies["import-database"]["copyId"], "import-database", when(ledger, 14 * DAY + tail)),
        (copies["rehearsal-database"]["copyId"], "rehearsal-database",
         when(ledger, 60 * DAY + tail)),
        (copies["v1-final-snapshot"]["copyId"], "v1-final-snapshot", when(ledger, 120 * DAY)),
        (copies["rolled-back-v2-database"]["copyId"], "rolled-back-v2-database",
         when(ledger, 90 * DAY)),
        (stray, "volume-file", when(ledger, 5 * DAY)),
    }
    listed = {(item["recordId"], item["kind"], item["goneAt"])
              for item in evidence["undisposed"]}
    assert listed == expected and len(evidence["undisposed"]) == len(expected)
    assert evidence["latestGoneAt"] == when(ledger, 120 * DAY)
    assert evidence["retired"] == [{"volume": "standin-volume-0001", "retiredAt": when(ledger),
                                    "count": 1}]
    assert evidence["unrecordedCounted"] == 1 and evidence["agentStatusRecorded"] is True
    unusable = {
        "absent": None,
        "old": status(ledger, age=dt.timedelta(seconds=601)),
        "damaged": status(ledger, catalogue="damaged"),
        "denied": status(ledger, deletionAllowed=False),
        "uncounted": {**status(ledger), "observations": {"catalogue": "intact",
                                                         "deletionAllowed": True}},
    }
    for name, answer in unusable.items():
        realm = backups_evidence(ledger, POLICY, schedule_active=True,
                                 agent_status=lambda target, answer=answer: answer)
        assert realm["agentStatusRecorded"] is False, name
        assert not [item for item in realm["undisposed"] if item["kind"] == "volume-file"]
        with pytest.raises(EvidencePending) as held:
            backups_evidence(ledger, POLICY, schedule_active=True, status_required=True,
                             agent_status=lambda target, answer=answer: answer)
        assert str(held.value) == ("agent-status-stale" if name == "old"
                                   else "agent-status-unrecorded"), name
    over = status(ledger, unrecordedCount=3, unrecordedFiles=current["observations"][
        "unrecordedFiles"])
    with pytest.raises(EvidencePending) as bound:
        backups_evidence(ledger, POLICY, schedule_active=True, agent_status=lambda target: over)
    assert str(bound.value) == "volume-files-over-bound"

    def unreachable(target):
        raise ControlError("DEPENDENCY_UNAVAILABLE", "store unreachable")

    with pytest.raises(EvidencePending) as reader:
        backups_evidence(ledger, POLICY, schedule_active=True, agent_status=unreachable)
    assert str(reader.value) == "platform-reader-unavailable"
    undated = status(ledger, unrecordedCount=1, unrecordedFiles=[{"recordId": stray}])
    with pytest.raises(EvidencePending) as dateless:
        backups_evidence(ledger, POLICY, schedule_active=True, agent_status=lambda t: undated)
    assert str(dateless.value) == "volume-file-undated"


def add_request(ledger, state: str, *, environment: str = "live") -> dict:
    """A scheduled `backup.create` walked to `state` through its allowed transitions."""
    now = when(ledger)
    record = {
        "recoveryRequestId": str(uuid4()), "revision": 1, "environment": environment,
        "origin": "schedule", "operation": "backup.create", "targetId": "docsuri_v2",
        "expectedRevision": 0, "submissionId": str(uuid4()), "idempotencyKey": "e" * 64,
        "state": "requested", "evidenceRefs": [], "createdAt": now, "updatedAt": now,
    }
    path = {"running": ["awaiting-operator", "running"],
            "unknown": ["awaiting-operator", "running", "unknown"]}[state]
    ledger.append("recovery-request", record, expect_revision=0)
    for revision, step in enumerate(path, start=2):
        record = {**record, "state": step, "revision": revision}
        ledger.append("recovery-request", record, expect_revision=revision - 1)
    return record


def settle_request(ledger, record: dict, state: str) -> None:
    path = {"succeeded": ["verifying", "succeeded"], "failed": ["failed"]}[state]
    for step in path:
        record = {**record, "state": step, "revision": record["revision"] + 1}
        ledger.append("recovery-request", record, expect_revision=record["revision"] - 1)


def test_the_backups_scope_waits_while_a_backup_or_a_lone_ledger_copy_is_being_written(
        ledger):
    from docsuri_ops.platform_control.errors import ControlError

    counted = add_set(ledger)
    open_now: list[dict] = []
    participant = OperationsLifecycleParticipant(
        None, ledger, POLICY, schedule_active=lambda: True,
        open_operations=lambda names: [item for item in open_now if item["operation"] in names],
        agent_status=lambda target: None)

    def waits_then_ready(settle) -> None:
        request = {"id": uuid4(), "account_id": uuid4(), "action": "erase"}
        with pytest.raises(EvidencePending) as pending:
            backups_evidence(ledger, POLICY, schedule_active=True,
                             open_operations=participant.open_operations)
        assert str(pending.value) == "backup-in-flight"
        assert participant.ready(request, "backups")  # the first attempt is claimed
        participant._record(str(request["id"]), "backups", "erase",
                            {"state": "waiting", "reasonKey": "backup-in-flight"})
        assert not participant.ready(request, "backups")
        settle()
        assert participant.ready(request, "backups")
        evidence = participant._backups()
        assert counted["backupId"] in {item["recordId"] for item in evidence["undisposed"]}

    running = add_request(ledger, "running")
    waits_then_ready(lambda: settle_request(ledger, running, "succeeded"))
    unknown = add_request(ledger, "unknown", environment="rehearsal")
    waits_then_ready(lambda: settle_request(ledger, unknown, "failed"))
    for operation in ("platform.database.backup", "platform.ledger.copy"):
        open_now.append({"operationId": str(uuid4()), "operation": operation,
                         "targetId": "ledger-copy"})
        waits_then_ready(open_now.clear)
    open_now.append({"operationId": str(uuid4()), "operation": "platform.isolation.check",
                     "targetId": "isolation"})
    assert participant._backups()["setsCounted"] == 1  # another protocol never holds it
    with pytest.raises(EvidencePending) as unbound:
        backups_evidence(ledger, POLICY, schedule_active=True, open_operations=None)
    assert str(unbound.value) == "platform-reader-unbound"

    def unreachable(names):
        raise ControlError("DEPENDENCY_UNAVAILABLE", "store unreachable")

    with pytest.raises(EvidencePending) as reader:
        backups_evidence(ledger, POLICY, schedule_active=True, open_operations=unreachable)
    assert str(reader.value) == "platform-reader-unavailable"


@pytest.mark.parametrize(("after", "late"), [(86_401, True), (86_400, False)])
def test_the_restore_evidence_carries_its_verifications_times(ledger, clock, after, late):
    participant = OperationsLifecycleParticipant(
        None, ledger, POLICY, schedule_active=lambda: True,
        open_operations=lambda names: [], agent_status=lambda target: None)
    account, request = uuid4(), uuid4()
    tombstone = Tombstones(ledger).claim(account, request)
    head = Tombstones(ledger).head()
    started = _parse_time(tombstone["appendedAt"]) + dt.timedelta(seconds=after)
    verification = {
        "verificationId": str(uuid4()), "environment": "live", "backupId": str(uuid4()),
        "startedAt": utc_text(started), "finishedAt": utc_text(started + dt.timedelta(minutes=9)),
        "registerHeadSequence": head["sequence"], "registerHeadDigest": head["digest"],
        "integrity": "passed", "erasedOwnersSurviving": 0, "result": "verified",
        "evidenceRef": "evidence/v.json", "scratchRemovedAt": utc_text(started),
    }
    ledger.append("restore-verification", verification, expect_revision=0)
    ticket = {"scope": "restore_enforcement", "account_id": account, "request_id": request}
    evidence = participant._evidence(ticket, "erase")
    assert evidence["verificationStartedAt"] == verification["startedAt"]
    assert evidence["verificationFinishedAt"] == verification["finishedAt"]
    assert evidence.get("verificationStartLate", False) is late


def _parse_time(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
