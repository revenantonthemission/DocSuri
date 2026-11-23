"""The standing job's lanes (U8 plan Steps 36 and 67; reliability-design § 11, R4, BR4.2,
BR9.17, NFR4.3, NFR8.6, L1-5, L1-42, L1-48, L1-51).

The scheduler runs each lane in a thread of its own on one injected clock. The schedule's
requests are real RecoveryRequests in a private ledger; the procedures that would run
them, the checks' transport and the agent are stand-ins that record what they were
asked, so each lane's sequence is seen without touching the realm's volume or services.
The day-without-a-set tests run the real RecoveryProcedures over the test ledger, with an
operator stand-in whose lone copy is the in-process backup agent rig's own `ledger-copy`.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import os
import stat
import subprocess
import threading
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.modules.operations.incidents import Incidents
from backend.modules.operations.ledger_cli import LedgerCommand
from backend.modules.operations.recovery import RecoveryRequests
from backend.modules.operations.recovery_procedures import Platform, RecoveryProcedures
from backend.modules.operations.tombstones import Tombstones
from backend.u8_policy import PRODUCTION_OPERATIONS, SYNTHETIC_OPERATIONS
from docsuri_ops import production_wiring as wiring
from docsuri_ops.arrangement.paths import ArrangementPaths, DatabaseNames
from docsuri_ops.standing import macos
from docsuri_ops.standing.availability import AvailabilityRecord
from docsuri_ops.standing.healthchecks import Healthchecks
from docsuri_ops.standing.heartbeat import Answer, StartWatch
from docsuri_ops.standing.housekeeping import Housekeeping, starts_pruner
from docsuri_ops.standing.lanes import (
    FAILED,
    SEOUL,
    SKIPPED,
    Lane,
    Lanes,
    daily_at,
    every,
    slot_of,
    weekly_at,
)
from docsuri_ops.standing.main import (
    INTERRUPTED_TARGETS,
    AgentStatus,
    ScheduledRecovery,
    build_lanes,
    evidence_recorder,
    isolation_lane,
    ledger_identities,
    realm_parts,
)
from docsuri_ops.u8_platform.drivers import facts_of
from docsuri_ops.u8_platform.u8_protocols import retry_key
from tests.u8_service_operations_integration import agent_flows as af
from tests.u8_service_operations_integration import cutover_flows as cf
from tests.u8_service_operations_integration import platform_flows as pf
from tests.u8_service_operations_integration import recovery_flows as rf
from tests.u8_service_operations_integration.conftest import Clock

# A Sunday in Seoul, 03:00 local.
SUNDAY = dt.datetime(2026, 10, 25, 3, 0, tzinfo=SEOUL).astimezone(dt.UTC)
ADDRESSES = {name: f"http://127.0.0.1:18115/{name}" for name in ("heartbeat", "backup",
                                                                   "verification")}
FAIL = {name: ADDRESSES[name] + "/fail" for name in ("backup", "verification")}


def seoul(month: int, day: int, hour: int, minute: int = 0, second: int = 0) -> dt.datetime:
    return dt.datetime(2026, month, day, hour, minute, second, tzinfo=SEOUL).astimezone(dt.UTC)


class Sent:
    """The checks' transport, recorded; `events` also receives each ping in order, and
    `observe` reads something at the moment of the ping."""

    def __init__(self, events: list | None = None, observe=None):
        self.urls, self.events, self.observe, self.observed = [], events, observe, []

    def __call__(self, url: str, seconds: float) -> int:
        self.urls.append(url)
        if self.events is not None:
            self.events.append(("ping", url))
        if self.observe is not None:
            self.observed.append(self.observe())
        return 200

    def of(self, check: str) -> list[str]:
        return [url for url in self.urls if url.startswith(ADDRESSES[check])]


@pytest.fixture
def ledger(tmp_path, clock):
    value = rf.open_ledger(tmp_path, clock)
    yield value
    value.close()


def fresh_ledger(tmp_path, name: str, clock):
    folder = tmp_path / name
    folder.mkdir()
    return rf.open_ledger(folder, clock)


def test_the_schedules_fall_on_their_instants_in_seoul():
    at = dt.datetime(2026, 10, 22, 19, 7, 31, tzinfo=dt.UTC)  # 04:07 Seoul, Friday
    assert slot_of(at) == dt.datetime(2026, 10, 22, 19, 5, tzinfo=dt.UTC)
    assert every(3600)(at) == dt.datetime(2026, 10, 22, 19, 0, tzinfo=dt.UTC)
    assert daily_at(4)(at).astimezone(SEOUL).hour == 4
    assert daily_at(5)(at) < at and daily_at(5)(at).astimezone(SEOUL).day == 22  # yesterday
    sunday = weekly_at(6, 5)(at).astimezone(SEOUL)
    assert sunday.weekday() == 6 and sunday.hour == 5
    assert weekly_at(6, 5, also=lambda now: True)(at) == daily_at(5)(at)
    with pytest.raises(ValueError):
        every(0)


def test_no_lane_waits_for_another(clock):
    release, quick_ran = threading.Event(), threading.Event()
    slow = Lane("backup", every(60), lambda now: release.wait(5))
    quick = Lane("heartbeat", every(60), lambda now: quick_ran.set() or "ok")
    lanes = Lanes([slow, quick])
    lanes.start(clock())
    clock.advance(61)
    assert sorted(lanes.tick(clock())) == ["backup", "heartbeat"]
    assert quick_ran.wait(5)  # the heartbeat ran while the backup still runs
    assert slow.running()
    release.set()
    lanes.join()
    assert {turn.lane for turn in lanes.turns if turn.outcome == "ran"} == {"backup", "heartbeat"}


def test_an_overlapping_turn_is_skipped_recorded_and_fails_its_check(clock):
    release = threading.Event()
    recorded, failed = [], []
    backup = Lane("backup", every(60), lambda now: release.wait(5))
    status = Lane("agent-status", every(60), lambda now: release.wait(5))
    lanes = Lanes([backup, status], record=recorded.append, fail=failed.append)
    lanes.start(clock())
    clock.advance(61)
    lanes.tick(clock())
    clock.advance(60)
    assert lanes.tick(clock()) == []  # both still run: neither starts twice
    skipped = [turn for turn in recorded if turn.outcome == "skipped"]
    assert {(turn.lane, turn.reason) for turn in skipped} == {("backup", SKIPPED),
                                                             ("agent-status", SKIPPED)}
    assert failed == ["backup"]  # only a backup or a verification pings /fail
    assert lanes.tick(clock()) == []  # the spent turn is not queued
    release.set()
    lanes.join()


def test_a_failing_lane_is_recorded_and_the_job_goes_on(clock):
    def broken(now):
        raise RuntimeError("boom")

    lanes = Lanes([Lane("housekeeping", every(60), broken)])
    lanes.start(clock())
    clock.advance(61)
    lanes.tick(clock())
    lanes.join()
    assert lanes.turns[-1].outcome == "failed" and lanes.failures == {
        "housekeeping": "RuntimeError"}
    with pytest.raises(ValueError):
        Lanes([Lane("a", every(60), broken), Lane("a", every(60), broken)])


class Procedures:
    """The procedures a scheduled request runs through, recorded. With `requests` set,
    a run starts the request and ends it as `state` says, as the real ones do."""

    requests = None

    def __init__(self, state: str = "succeeded"):
        self.state, self.calls, self.ran = state, [], []
        self.platform = SimpleNamespace(database_of=lambda environment: "docsuri_u8")
        self.copy_error: Exception | None = None

    def _ended(self, request_id) -> dict:
        if self.requests is None:
            return {"state": self.state}
        self.requests.start(request_id)
        if self.state == "succeeded":
            self.requests.advance(request_id, "verifying", allowed_from=("running",))
            return self.requests.advance(request_id, "succeeded", allowed_from=("verifying",))
        return self.requests.advance(request_id, "failed", allowed_from=("running",),
                                     evidence=["failed:stand-in"])

    def backup(self, request_id, *, via):
        self.calls.append(("backup", via))
        self.ran.append(str(request_id))
        return self._ended(request_id)

    def verify(self, request_id, *, via):
        self.calls.append(("verify", via))
        return self._ended(request_id)

    def ledger_copy_alone(self, environment, *, owner_key, via):
        self.calls.append(("ledger_copy_alone", environment, owner_key))
        if self.copy_error is not None:
            raise self.copy_error
        return {}

    def reconcile_interrupted(self, targets):
        self.calls.append(("reconcile_interrupted", tuple(targets)))
        return []

    def reconcile(self, request_id):
        """The standing job's own reconciliation of a scheduled request left unknown
        (review finding, Minor, R16): settled failed here, as a reconciliation not
        applied would settle it."""
        self.calls.append(("reconcile", request_id))
        if self.requests is None:
            return {"state": "failed"}
        return self.requests.settle_unknown(request_id, "failed")


def recovery(ledger, clock, procedures, sent, disposals, *, environment="live",
             policy=SYNTHETIC_OPERATIONS):
    requests = RecoveryRequests(ledger, policy, clock=clock)
    checks = Healthchecks(ADDRESSES, send=sent)

    def disposal() -> dict:
        disposals.append("pass")
        procedures.calls.append(("disposal",))
        return {}

    serving = environment if callable(environment) else (lambda: environment)
    return ScheduledRecovery(requests, procedures, checks, environment=serving,
                             disposal=disposal, policy=policy)


def lanes_over(scheduled, *, slot: int = 3600, policy=SYNTHETIC_OPERATIONS, record=None,
               heartbeat=None, housekeeping=None):
    parts = SimpleNamespace(
        heartbeat=SimpleNamespace(run=heartbeat or (lambda now: "ok")), checks=scheduled.checks,
        agent=SimpleNamespace(run=lambda now: "volume-available"),
        isolation=lambda now: "isolation-checked", recovery=scheduled,
        housekeeping=SimpleNamespace(run=housekeeping or (lambda now: {})), policy=policy,
        slot_seconds=slot)
    return build_lanes(parts, record=record)


def owner_of(environment: str, now: dt.datetime) -> str:
    return f"standing-ledger-copy:{environment}:{daily_at(4)(now).astimezone(SEOUL):%Y%m%d}"


def test_catch_up_runs_a_missed_backup_and_a_due_verification_at_start(ledger, clock):
    clock.now = SUNDAY + dt.timedelta(hours=27)  # Monday 06:00 Seoul
    rf.set_record(ledger, now=clock() - dt.timedelta(hours=25))
    procedures, sent, disposals = Procedures(), Sent(), []
    scheduled = recovery(ledger, clock, procedures, sent, disposals)
    assert scheduled.backup_overdue(clock()) and scheduled.verification_due(clock())
    lanes = lanes_over(scheduled, slot=5)
    assert sorted(lanes.start(clock())) == ["backup", "verification"]
    lanes.join()
    assert sorted(call[0] for call in procedures.calls if call[0] in ("backup", "verify")) == [
        "backup", "verify"]
    assert disposals == ["pass"]  # the disposal pass follows the scheduled backup
    assert {url.rsplit("/", 1)[-1] for url in sent.urls} == {"backup", "verification"}


def test_nothing_catches_up_when_the_runs_are_current(ledger, clock):
    clock.now = SUNDAY + dt.timedelta(hours=3)  # Sunday 06:00 Seoul
    backup = rf.set_record(ledger, now=clock() - dt.timedelta(hours=1))
    scheduled = recovery(ledger, clock, Procedures(), Sent(), [])
    cf.verified_restore(ledger, backup, now=clock() - dt.timedelta(minutes=30),
                        environment="live")
    assert not scheduled.backup_overdue(clock())
    assert not scheduled.verification_due(clock())
    # A tombstone claimed at Sunday 06:00 waits at Monday's 05:00, not at Sunday's (L1-42).
    Tombstones(ledger).claim(uuid4(), uuid4())
    sunday_0500 = SUNDAY + dt.timedelta(hours=2)
    assert not scheduled.erasure_waits(sunday_0500)
    assert not scheduled.verification_due(clock())
    assert scheduled.erasure_waits(sunday_0500 + dt.timedelta(days=1))


class Verifying(Procedures):
    """Its verification ends the request succeeded and records a live verified
    RestoreVerification reaching the register's head, so it covers every tombstone."""

    def __init__(self, ledger, clock):
        super().__init__()
        self.ledger, self.clock = ledger, clock

    def verify(self, request_id, *, via):
        done = super().verify(request_id, via=via)
        head = Tombstones(self.ledger).head()
        now = rf.utc_text(self.clock())
        self.ledger.append("restore-verification", {
            "verificationId": str(uuid4()), "environment": "live",
            "backupId": self.requests.get(request_id)["targetId"], "startedAt": now,
            "finishedAt": now, "registerHeadSequence": head["sequence"],
            "registerHeadDigest": head["digest"], "integrity": "passed",
            "erasedOwnersSurviving": 0, "result": "verified",
            "evidenceRef": "verification:fixture", "scratchRemovedAt": now},
            expect_revision=0)
        return done


def verifying_job(ledger, clock, sent, *, set_at: dt.datetime, record=None):
    """A live job whose newest passed set is `set_at` and whose last verification ran at
    Sunday 2026-10-25 05:00 Seoul."""
    backup = rf.set_record(ledger, now=set_at)
    cf.verified_restore(ledger, backup, now=seoul(10, 25, 5), environment="live")
    procedures = Verifying(ledger, clock)
    scheduled = recovery(ledger, clock, procedures, sent, [])
    procedures.requests = scheduled.requests
    return scheduled, lanes_over(scheduled, record=record)


def drive(lanes, clock, instants, before=None) -> list[tuple[str, dt.datetime]]:
    """A tick at each instant (`before(at)` first), joined when it launched anything."""
    launched = []
    for at in instants:
        if before is not None:
            before(at)
        clock.now = at
        started = lanes.tick(at)
        if started:
            lanes.join()
            launched.extend((name, at) for name in started)
    return launched


def minutes(start: dt.datetime, end: dt.datetime, *extra: dt.datetime) -> list[dt.datetime]:
    count = int((end - start).total_seconds()) // 60
    return sorted({start + dt.timedelta(minutes=index) for index in range(1, count + 1)}
                  | set(extra))


def test_a_waiting_erasures_verification_starts_at_the_next_0500(ledger, clock, tmp_path):
    """L1-42: a tombstone waits for the next 05:00, never for the next Sunday."""
    sent, turns = Sent(), []
    start = seoul(10, 25, 6)
    clock.now = start
    scheduled, lanes = verifying_job(ledger, clock, sent, set_at=seoul(10, 25, 4),
                                     record=turns.append)
    assert lanes.start(start) == []
    appended = [seoul(10, 26, 4, 59), seoul(10, 26, 5, 0, 30), seoul(11, 1, 6)]
    waiting = list(appended)

    def claim(at: dt.datetime) -> None:
        while waiting and waiting[0] <= at:
            clock.now = waiting.pop(0)
            Tombstones(ledger).claim(uuid4(), uuid4())

    instants = minutes(start, seoul(11, 3, 5), seoul(10, 26, 4, 59, 59),
                       seoul(10, 26, 5, 0, 30), seoul(10, 27, 4, 59, 59))
    launched = drive(lanes, clock, instants, before=claim)
    starts = [at for name, at in launched if name == "verification"]
    assert starts == [seoul(10, 26, 5), seoul(10, 27, 5), seoul(11, 1, 5), seoul(11, 2, 5)]
    for tombstone, started in zip(appended, (starts[0], starts[1], starts[3]), strict=True):
        assert dt.timedelta(0) < started - tombstone < dt.timedelta(hours=24)
    assert not any(url.endswith("/fail") for url in sent.urls)
    assert not [turn for turn in turns if turn.outcome in ("skipped", "failed")]
    # On fresh ledgers: a start after a 12:00 tombstone catches nothing up; a start after
    # a 03:00 tombstone with no 05:00 run (the job was down) catches it up at once.
    for name, tombstone, at, expected in (
            ("fresh-noon", seoul(10, 26, 12), seoul(10, 26, 12, 30), []),
            ("fresh-night", seoul(10, 26, 3), seoul(10, 26, 6), ["verification"])):
        other = fresh_ledger(tmp_path, name, clock)
        try:
            _, job = verifying_job(other, clock, Sent(), set_at=seoul(10, 26, 4))
            clock.now = tombstone
            Tombstones(other).claim(uuid4(), uuid4())
            clock.now = at
            assert job.start(at) == expected, name
            job.join()
        finally:
            other.close()


class Week:
    """The recovery side, recorded: an erasure waits at `at` for each tombstone appended at
    or before it that its verification has not yet covered."""

    def __init__(self, appended: list[dt.datetime]):
        self.tombstones = [{"at": at, "covered": False} for at in appended]

    def erasure_waits(self, at: dt.datetime) -> bool:
        return any(not item["covered"] and item["at"] <= at for item in self.tombstones)

    def backup_overdue(self, now) -> bool:
        return False

    def verification_due(self, now) -> bool:
        return False

    def backup(self, now) -> str:
        return "backup-succeeded"

    def verification(self, now) -> str:
        for item in self.tombstones:
            if item["at"] <= now:
                item["covered"] = True
        return "verification-succeeded"


def test_a_production_week_runs_each_lane_at_its_instants():
    week, turns = Week([seoul(10, 27, 4, 59), seoul(10, 28, 10)]), []
    checks = Healthchecks(ADDRESSES, send=Sent())
    week.checks = checks
    lanes = lanes_over(week, slot=300, policy=PRODUCTION_OPERATIONS, record=turns.append)
    start, clock = seoul(10, 26, 0), Clock(seoul(10, 26, 0))
    assert lanes.start(start) == []
    instants = [start + dt.timedelta(seconds=60 * index) for index in range(1, 8 * 1440 + 1)]
    drive(lanes, clock, instants)
    ran = [turn for turn in turns if turn.outcome == "ran"]

    def at(lane: str) -> list[dt.datetime]:
        return [turn.at for turn in ran if turn.lane == lane]

    slots = [start + dt.timedelta(seconds=300 * index) for index in range(1, 8 * 288 + 1)]
    for lane in ("heartbeat", "agent-status", "isolation"):
        assert sorted(slot_of(moment) for moment in at(lane)) == slots, lane
    assert at("backup") == [seoul(10, day, 4) for day in range(26, 32)] + [
        seoul(11, 1, 4), seoul(11, 2, 4)]
    assert at("verification") == [seoul(10, 27, 5), seoul(10, 29, 5), seoul(11, 1, 5)]
    assert seoul(10, 28, 10) not in at("verification")
    hours = [start + dt.timedelta(hours=index) for index in range(1, 8 * 24 + 1)]
    assert at("housekeeping") == hours
    assert not [turn for turn in turns if turn.outcome in ("skipped", "failed")]


def test_scheduled_requests_are_admitted_run_and_pinged(ledger, clock, tmp_path):
    procedures = Procedures()
    sent, disposals = Sent(events=procedures.calls), []
    scheduled = recovery(ledger, clock, procedures, sent, disposals)
    assert scheduled.verification(clock()) == "no-passed-set"
    assert sent.urls[-1].endswith("/verification/fail")
    procedures.calls.clear()
    assert scheduled.backup(clock()) == "backup-succeeded"
    assert sent.urls[-1] == ADDRESSES["backup"] and disposals == ["pass"]
    # The turn settles what an interrupted turn left open before it files its request
    # (Step 66(b)); a succeeded backup pings ok, then runs the disposal pass.
    assert procedures.calls == [("reconcile_interrupted", INTERRUPTED_TARGETS),
                                ("backup", "standing"), ("ping", ADDRESSES["backup"]),
                                ("disposal",)]
    # A retry in the same scheduled hour recovers the same request (BR4.9).
    assert scheduled.backup(clock()) == "backup-succeeded"
    [first] = ledger.records("recovery-request")
    rf.set_record(ledger, now=clock())
    procedures.state = "failed"
    assert scheduled.verification(clock()) == "verification-failed"
    assert sent.urls[-1].endswith("/verification/fail")
    # While a switch holds the live environment, the scheduled backup is not admitted: no
    # disposal pass, and one lone ledger copy (L1-48).
    scheduled.requests.cancel(first["recoveryRequestId"])
    cf.switching(ledger, clock)
    procedures.calls.clear()
    assert scheduled.backup(clock()) == "backup-not-admitted"
    assert sent.urls[-1] == FAIL["backup"]
    assert procedures.calls == [("reconcile_interrupted", INTERRUPTED_TARGETS),
                                ("ledger_copy_alone", "live", owner_of("live", clock())),
                                ("ping", FAIL["backup"])]
    # On a fresh ledger, a failed procedure answers backup-failed, pings /backup/fail and
    # then runs the disposal pass.
    other = fresh_ledger(tmp_path, "fresh", clock)
    try:
        failing = Procedures("failed")
        failed_sent = Sent(events=failing.calls)
        job = recovery(other, clock, failing, failed_sent, [])
        assert job.backup(clock()) == "backup-failed"
        assert failing.calls == [("reconcile_interrupted", INTERRUPTED_TARGETS),
                                 ("backup", "standing"),
                                 ("ledger_copy_alone", "live", owner_of("live", clock())),
                                 ("ping", FAIL["backup"]), ("disposal",)]
    finally:
        other.close()


def scheduled_request(requests, environment: str, *, state: str) -> str:
    made = requests.request(origin="schedule", operation="backup.create",
                            environment=environment, target_id="docsuri_u8",
                            expected_revision=requests.backup_revision(environment),
                            submission_id=uuid4())
    identity = made["recoveryRequestId"]
    requests.admit(identity)
    requests.start(identity)
    if state == "unknown":
        requests.outcome_unknown(identity, evidence=["pending:op-3"])
    return identity


def test_a_scheduled_request_left_unknown_is_settled_by_the_standing_job_first(ledger,
                                                                              clock):
    """Review finding (Minor, R16): a scheduled request whose effect's outcome stayed
    unknown is the scheduler's to reconcile (the store refuses the in-person word for
    its operation), so each lane settles its own unknown requests before it requests
    again; an in-person request left unknown is never touched, and one the procedures
    refuse stays unknown for the next turn. Step 66(b): a scheduled backup an earlier
    turn left running is run again first, in either environment."""
    from backend.modules.operations.errors import OperationsError
    from backend.modules.operations.ledger import utc_text

    procedures, sent, disposals = Procedures(), Sent(), []
    scheduled = recovery(ledger, clock, procedures, sent, disposals)
    requests = scheduled.requests
    # An in-person request left unknown is not the standing job's: untouched.
    administrator = RecoveryRequests(ledger, SYNTHETIC_OPERATIONS, clock=clock,
                                     mfa_current=lambda who, at: True)
    in_person = administrator.request(origin="administrator", operation="backup.create",
                                      environment="live", target_id="docsuri_u8",
                                      expected_revision=0, submission_id=uuid4(),
                                      requested_by=uuid4(), mfa_verified_at=utc_text(clock()))
    administrator.admit(in_person["recoveryRequestId"])
    assert administrator.start(in_person["recoveryRequestId"])["state"] == "running"
    requests.outcome_unknown(in_person["recoveryRequestId"], evidence=["pending:op-2"])
    assert scheduled.settle_unknown() == [] and procedures.calls == []
    assert requests.get(in_person["recoveryRequestId"])["state"] == "unknown"
    requests.settle_unknown(in_person["recoveryRequestId"], "failed")  # by its own path
    unknown = requests.request(origin="schedule", operation="backup.create",
                               environment="live", target_id="docsuri_u8",
                               expected_revision=0, submission_id=uuid4())
    requests.admit(unknown["recoveryRequestId"])
    requests.start(unknown["recoveryRequestId"])
    requests.outcome_unknown(unknown["recoveryRequestId"], evidence=["pending:op-1"])
    assert [item["recoveryRequestId"] for item in requests.unknown("live")] == [
        unknown["recoveryRequestId"]]
    # Refused by the store (another actor's) or the ledger: it stays unknown.
    refusing = Procedures()
    refusing.reconcile = lambda request_id: (_ for _ in ()).throw(
        OperationsError("FORBIDDEN", current={"reasonKey": "operation-bound-by-another-actor"}))
    assert recovery(ledger, clock, refusing, Sent(), []).settle_unknown() == []
    assert requests.get(unknown["recoveryRequestId"])["state"] == "unknown"
    # The lane's next turn settles it first (the unknown request would otherwise block the
    # new one's admission), then requests again.
    procedures.requests = requests
    assert scheduled.backup(clock()) == "backup-succeeded"
    assert procedures.calls[0] == ("reconcile", unknown["recoveryRequestId"])
    assert requests.get(unknown["recoveryRequestId"])["state"] == "failed"
    procedures.calls.clear()
    # With the request settled, nothing is reconciled on the next turn.
    assert scheduled.settle_unknown() == [] and procedures.calls == []
    # The next day: the previous day's live request left running, and the rehearsal one a
    # turn before the mode changed left unknown, are run again or settled first.
    clock.advance(86400)
    running = scheduled_request(requests, "live", state="running")
    other = scheduled_request(requests, "rehearsal", state="unknown")
    procedures.ran.clear()
    assert scheduled.backup(clock()) == "backup-succeeded"
    assert procedures.ran[0] == running and len(procedures.ran) == 2
    assert requests.get(running)["state"] == "succeeded"
    assert requests.get(other)["state"] == "failed"
    assert requests.get(procedures.ran[1])["state"] == "succeeded"  # the day's own
    # A rehearsal request left running is run again by a live turn (the other
    # environment's, Step 67(c)), and an administrator's running request is never
    # touched: it holds the live environment, so the live turn's own request is not
    # admitted and the day takes its lone copy.
    clock.advance(86400)
    left = scheduled_request(requests, "rehearsal", state="running")
    in_person = administrator.request(origin="administrator", operation="backup.create",
                                      environment="live", target_id="docsuri_u8",
                                      expected_revision=0, submission_id=uuid4(),
                                      requested_by=uuid4(), mfa_verified_at=utc_text(clock()))
    administrator.admit(in_person["recoveryRequestId"])
    administrator.start(in_person["recoveryRequestId"])
    procedures.ran.clear()
    assert scheduled.backup(clock()) == "backup-not-admitted"
    assert procedures.ran == [left] and requests.get(left)["state"] == "succeeded"
    assert in_person["recoveryRequestId"] not in procedures.ran
    assert requests.get(in_person["recoveryRequestId"])["state"] == "running"


# --- a day without a passed set (Step 66(b), NFR4.3, L1-5, L1-48) ----------------------------

TUESDAY_0400 = seoul(10, 27, 4)  # 2026-10-26T19:00:00Z
REHEARSAL_DATABASE = DatabaseNames("docsuri_u8").new("rehearsal")


def set_refs(record_id: str, integrity: str, now: dt.datetime) -> list[str]:
    return [f"backup-volume/archives/set-{record_id}.archive", f"fact:recordId={record_id}",
            "fact:sha256=" + "a" * 64, "fact:size=2048", "fact:databaseBytes=4096",
            "fact:incarnation=docsuri_u8:16384", "fact:stagingLocation=staging/x",
            f"fact:stagingRemovedAt={rf.utc_text(now)}",
            f"fact:disposeAfter={rf.utc_text(now + dt.timedelta(days=14))}",
            f"fact:integrity={integrity}"]


class Rigged:
    """The operator stand-in: prepared receipts for `platform.database.backup`, and for
    `platform.ledger.copy` the in-process agent rig's own `ledger-copy` result on the test
    ledger's copy. A key already answered replays its receipt, as PlatformControl does;
    its store holds nothing unresolved."""

    def __init__(self, root: Path, ledger, clock):
        self.profile = SimpleNamespace(effects_root=root / "effects")
        self.store = SimpleNamespace(promote_in_flight=lambda: 0,
                                     list_unresolved=lambda actor, authority: [])
        self.actor, self.authorities = "_docsuri_u8_scheduler", {"routine": str(uuid4())}
        self.ledger, self.clock = ledger, clock
        self.rig = af.build(root, clock)
        self.set, self.copy, self.settle = "passed", "agent", "unresolved"
        self.beside = "agent"
        self.rehearsal: str | None = REHEARSAL_DATABASE
        self.seen: dict[str, dict] = {}
        self.keys: list[tuple[str, str]] = []
        self.heads: list[dict] = []
        self.agents: list[dict] = []

    def agent_copy(self) -> tuple[dict, dict]:
        stream = io.BytesIO()
        head = self.ledger.copy(stream)
        status, result, _ = af.invoke(self.rig, "ledger-copy", stream.getvalue(),
                                      caller=af.SCHEDULER)
        assert status == 0, result
        self.heads.append(head)
        self.agents.append(result)
        return result, head

    def beside_copy(self) -> dict:
        if self.beside == "raises":
            raise OSError("the agent did not answer")
        agent, head = self.agent_copy()
        if self.beside == "unverified":
            agent = {**agent, "integrity": "failed"}
        return {"agent": agent, "head": head}

    def _answer(self, operation: str, target: str, inputs: dict) -> dict:
        base = {"receiptId": str(uuid4()), "operationId": str(uuid4()),
                "operation": operation, "targetId": target, "inputHash": "c" * 64}
        if operation == "platform.database.backup":
            if self.set == "refused":
                return {**base, "outcome": "failed", "refusal": "volume-check-failed"}
            if self.set == "unknown":
                return {**base, "outcome": "unknown"}
            integrity = "failed" if self.set == "integrity" else "passed"
            return {**base, "outcome": "succeeded",
                    "effectRefs": set_refs(inputs["recordId"], integrity, self.clock())}
        if operation == "platform.ledger.copy":
            if self.copy in ("failed", "unknown"):
                return {**base, "outcome": self.copy}
            agent, head = self.agent_copy()
            facts = facts_of({**agent, "headSequence": head["count"],
                              "headDigest": head["head"]})
            return {**base, "outcome": "succeeded",
                    "effectRefs": [f"backup-volume/{agent['location']}", *facts]}
        return {**base, "outcome": "failed"}

    def execute(self, operation, target, inputs, *, key, **options):
        self.keys.append((operation, key))
        if key in self.seen:
            return {**self.seen[key], "replayed": True}
        receipt = self._answer(operation, target, inputs)
        self.seen[key] = receipt
        return dict(receipt)

    def reconcile(self, operation_id):
        return {"outcome": "unknown", "reconciliationState": self.settle,
                "operationId": operation_id, "receiptId": str(uuid4())}


class Signals(Incidents):
    """A real Incidents, its signals also recorded."""

    def __init__(self, ledger, *, environment: str):
        super().__init__(ledger, environment=environment)
        self.signals: list[tuple] = []

    def signal(self, capability, opened_by, *, correlation=None, environment=None):
        self.signals.append((capability, correlation, environment))
        return super().signal(capability, opened_by, correlation=correlation,
                              environment=environment)


def real_job(root: Path, *, environment: str, start: dt.datetime = TUESDAY_0400):
    """The real RecoveryProcedures over a test ledger of their own, with the stand-in
    operator, a real Incidents and the checks over `Sent`."""
    root.mkdir()
    clock = Clock(start)
    ledger = rf.open_ledger(root, clock)
    operator = Rigged(root, ledger, clock)
    platform = Platform(
        operator=operator, production="docsuri_u8", labels=("u8",),
        scratch_name=lambda: "docsuri_u8_scratch_" + "ab" * 6, free_bytes=lambda: 10**15,
        scratch_checks=lambda database, accounts: {},
        restore_evaluate=lambda database, accounts: {},
        production_integrity=lambda database: {}, ready=lambda: True,
        drop_scratch=lambda name: None, rehearsal=lambda: operator.rehearsal,
        ledger_copy=operator.beside_copy)
    requests = RecoveryRequests(ledger, SYNTHETIC_OPERATIONS, clock=clock,
                                mfa_current=lambda who, at: True)
    incidents = Signals(ledger, environment="live")
    procedures = RecoveryProcedures(requests, platform, incidents=incidents,
                                    tombstones=Tombstones(ledger), policy=SYNTHETIC_OPERATIONS,
                                    clock=clock)
    sent, disposals = Sent(), []
    scheduled = ScheduledRecovery(requests, procedures, Healthchecks(ADDRESSES, send=sent),
                                  environment=lambda: environment,
                                  disposal=lambda: disposals.append("pass") or {},
                                  policy=SYNTHETIC_OPERATIONS)
    return SimpleNamespace(clock=clock, ledger=ledger, operator=operator, incidents=incidents,
                           sent=sent, disposals=disposals, scheduled=scheduled,
                           requests=requests)


def lone_copies(ledger) -> list[dict]:
    return [item for item in ledger.records("ledger-copy") if "backupId" not in item]


def hold(job, environment: str) -> None:
    """The backup not admitted: in live a switch holds the exclusion; in rehearsal a
    rehearsal database's removal holds it."""
    if environment == "live":
        cf.switching(job.ledger, job.clock)
        job.clock.now = TUESDAY_0400
        return
    from backend.modules.operations.retained_copies import RetainedCopies

    copies = RetainedCopies(job.ledger, SYNTHETIC_OPERATIONS, clock=job.clock)
    copy = copies.record("rehearsal-database", "run:fixture",
                         [f"database/{DatabaseNames('docsuri_u8').new('rehearsal')}"])
    copies.disposal_pending(copy["copyId"])


CASES = {
    "not-admitted": ("backup-not-admitted", lambda job, environment: hold(job, environment)),
    "refused": ("backup-failed", lambda job, environment: setattr(job.operator, "set",
                                                                  "refused")),
    "integrity": ("backup-failed", lambda job, environment: setattr(job.operator, "set",
                                                                    "integrity")),
    "copy-beside": ("backup-failed", lambda job, environment: setattr(job.operator, "beside",
                                                                      "raises")),
    "unknown": ("backup-failed", lambda job, environment: setattr(job.operator, "set",
                                                                  "unknown")),
}


def test_a_day_without_a_set_still_takes_a_ledger_copy_and_pings_fail(tmp_path):
    cases = [(environment, name) for environment in ("live", "rehearsal") for name in CASES]
    cases.append(("rehearsal", "no-rehearsal-database"))
    for environment, name in cases:
        job = real_job(tmp_path / f"{environment}-{name}", environment=environment)
        try:
            if name == "no-rehearsal-database":
                expected = "no-rehearsal-database"
                job.operator.rehearsal = None
                # The ledger is never empty in service: an empty chain does not verify, so
                # the turn files nothing and the ledger holds one earlier live set.
                rf.set_record(job.ledger, now=job.clock() - dt.timedelta(days=1))
            else:
                expected, arrange = CASES[name]
                arrange(job, environment)
            requests_before = len(job.ledger.records("recovery-request"))
            before = len(lone_copies(job.ledger))
            assert job.scheduled.backup(job.clock()) == expected, (environment, name)
            copies = lone_copies(job.ledger)
            assert len(copies) == before + 1, (environment, name)
            copy = copies[-1]
            facts = job.ledger.get("receipt-facts", copy["operatorReceiptRef"])
            assert facts["operation"] == "platform.ledger.copy"
            head = job.operator.heads[-1]
            assert (copy["headSequence"], copy["headDigest"]) == (head["count"], head["head"])
            assert copy.get("verifiedAt"), (environment, name, job.operator.agents[-1])
            assert rf_parse(copy["retainUntil"]) == dt.datetime(2026, 11, 9, 19, tzinfo=dt.UTC)
            assert job.sent.of("backup") == [FAIL["backup"]], (environment, name)
            if name == "no-rehearsal-database":
                assert len(job.ledger.records("recovery-request")) == requests_before
        finally:
            job.ledger.close()
    # The lone copy's operation failing: ledger-copy-failed, one storage.capacity signal,
    # and a retry the same day runs the copy under the next retry key.
    owner = owner_of("live", TUESDAY_0400)
    job = real_job(tmp_path / "copy-failed", environment="live")
    try:
        job.operator.set, job.operator.copy = "refused", "failed"
        assert job.scheduled.backup(job.clock()) == "ledger-copy-failed"
        correlated = [item for item in job.incidents.signals
                      if item[1] == f"ledger-copy:{owner}"]
        assert correlated == [("storage.capacity", f"ledger-copy:{owner}", "live")]
        assert lone_copies(job.ledger) == [] and job.sent.of("backup") == [FAIL["backup"]]
        job.operator.copy = "agent"
        job.scheduled.backup(job.clock())
        key = f"{owner}:ledger-copy"
        assert [item for operation, item in job.operator.keys
                if operation == "platform.ledger.copy"] == [key, key, retry_key(key, 1)]
        assert len(lone_copies(job.ledger)) == 1
    finally:
        job.ledger.close()
    # The copy's outcome left unknown: ledger-copy-failed, one /backup/fail, and the
    # refused set's turn still runs the disposal pass.
    job = real_job(tmp_path / "copy-unknown", environment="live")
    try:
        job.operator.set, job.operator.copy = "refused", "unknown"
        assert job.scheduled.backup(job.clock()) == "ledger-copy-failed"
        assert job.sent.of("backup") == [FAIL["backup"]] and job.disposals == ["pass"]
    finally:
        job.ledger.close()
    # A day whose set passed takes no extra copy.
    job = real_job(tmp_path / "passed", environment="live")
    try:
        assert job.scheduled.backup(job.clock()) == "backup-succeeded"
        assert lone_copies(job.ledger) == []
        [beside] = job.ledger.records("ledger-copy")
        assert beside["backupId"] and job.sent.of("backup") == [ADDRESSES["backup"]]
    finally:
        job.ledger.close()


def rf_parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def test_ledger_copies_are_never_more_than_a_day_apart(tmp_path):
    job = real_job(tmp_path / "week", environment="rehearsal", start=seoul(10, 26, 4))
    administrator = job.requests
    try:
        outcomes = ["passed", "not-admitted", "failed", "unknown", "passed", "not-admitted",
                    "failed"]
        for index, outcome in enumerate(outcomes):
            job.clock.now = seoul(10, 26, 4) + dt.timedelta(days=index)
            job.operator.set = {"failed": "refused", "unknown": "unknown"}.get(outcome,
                                                                              "passed")
            # The day after an unknown outcome, its reconciliation finds it not applied.
            job.operator.settle = "reconciled-not-applied" if index == 4 else "unresolved"
            holding = None
            if outcome == "not-admitted":
                made = administrator.request(
                    origin="administrator", operation="backup.create",
                    environment="rehearsal", target_id=REHEARSAL_DATABASE,
                    expected_revision=administrator.backup_revision("rehearsal"),
                    submission_id=uuid4(), requested_by=uuid4(),
                    mfa_verified_at=rf.utc_text(job.clock()))
                holding = made["recoveryRequestId"]
                administrator.admit(holding)
            before = len(job.ledger.records("ledger-copy"))
            job.scheduled.backup(job.clock())
            assert len(job.ledger.records("ledger-copy")) == before + 1, outcome
            if holding is not None:
                administrator.cancel(holding)
        taken = sorted(rf_parse(item["takenAt"]) for item in job.ledger.records("ledger-copy"))
        assert len(taken) == 7
        assert all((later - earlier).total_seconds() <= 86400
                   for earlier, later in zip(taken, taken[1:], strict=False))
    finally:
        job.ledger.close()


class LowSpace(Procedures):
    """The agent refuses a backup with `backup-volume-low` while `low` holds, but still
    deletes; the disposal pass deletes a due set and clears it."""

    def __init__(self):
        super().__init__()
        self.low = True

    def backup(self, request_id, *, via):
        self.state = "failed" if self.low else "succeeded"
        return super().backup(request_id, via=via)


def test_a_failed_backup_still_runs_the_disposal_pass_so_low_space_clears(ledger, clock):
    procedures, sent = LowSpace(), Sent()
    scheduled = recovery(ledger, clock, procedures, sent, [])
    procedures.requests = scheduled.requests

    def disposal() -> dict:
        procedures.low = False
        procedures.calls.append(("disposal",))
        return {"disposed": ["due-set"]}

    scheduled.disposal = disposal
    assert scheduled.backup(clock()) == "backup-failed"
    assert procedures.calls[-1] == ("disposal",) and procedures.low is False
    clock.advance(86400)
    assert scheduled.backup(clock()) == "backup-succeeded"
    assert sent.urls[-1] == ADDRESSES["backup"]


# --- every failure pings its check (Step 66(c)) --------------------------------------------


def test_every_backup_and_verification_failure_pings_fail(tmp_path):
    cases = {
        "effect": lambda operator: setattr(operator, "set", "refused"),
        "integrity": lambda operator: setattr(operator, "set", "integrity"),
        "copy-raises": lambda operator: setattr(operator, "beside", "raises"),
        "copy-unverified": lambda operator: setattr(operator, "beside", "unverified"),
    }
    for name, arrange in cases.items():
        job = real_job(tmp_path / name, environment="live")
        try:
            arrange(job.operator)
            assert job.scheduled.backup(job.clock()) == "backup-failed", name
            [request] = job.ledger.records("recovery-request")
            assert request["state"] == "failed", name
            assert job.sent.urls == [FAIL["backup"]], name
        finally:
            job.ledger.close()
    job = real_job(tmp_path / "scratch", environment="live")
    try:
        rf.set_record(job.ledger, now=job.clock())
        assert job.scheduled.verification(job.clock()) == "verification-failed"
        assert job.sent.urls == [FAIL["verification"]]
    finally:
        job.ledger.close()
    job = real_job(tmp_path / "success", environment="live")
    try:
        job.sent.observe = lambda: (len(job.ledger.records("backup-set")),
                                    len(job.ledger.records("ledger-copy")))
        assert job.scheduled.backup(job.clock()) == "backup-succeeded"
        assert job.sent.urls == [ADDRESSES["backup"]] and job.sent.observed == [(1, 1)]
    finally:
        job.ledger.close()


class Raising:
    def __init__(self, error: Exception | None = None, release: threading.Event | None = None):
        self.error, self.release = error, release

    def __call__(self, now):
        if self.release is not None:
            self.release.wait(10)
            return "done"
        raise self.error


def stand_in_recovery(checks, *, backup, verification):
    return SimpleNamespace(checks=checks, backup=backup, verification=verification,
                           backup_overdue=lambda now: False,
                           verification_due=lambda now: False,
                           erasure_waits=lambda at: False)


def test_a_raising_backup_or_verification_lane_pings_fail():
    sent = Sent()
    checks = Healthchecks(ADDRESSES, send=sent)
    error = RuntimeError("raised")
    turns = []
    lanes = lanes_over(stand_in_recovery(checks, backup=Raising(error),
                                         verification=Raising(error)),
                       housekeeping=Raising(error), record=turns.append)
    clock = Clock(SUNDAY)
    lanes.start(SUNDAY)
    drive(lanes, clock, [seoul(10, 25, 4), seoul(10, 25, 5)])
    assert sent.urls == [FAIL["backup"], FAIL["verification"]]  # housekeeping pings nothing
    assert {turn.lane for turn in turns if turn.reason == FAILED} == {
        "backup", "verification", "housekeeping"}
    # Skipped backup and verification turns still ping /fail.
    release, sent.urls[:] = threading.Event(), []
    lanes = lanes_over(stand_in_recovery(checks, backup=Raising(release=release),
                                         verification=Raising(release=release)))
    lanes.start(SUNDAY)
    lanes.tick(seoul(10, 25, 4))
    lanes.tick(seoul(10, 25, 5))
    assert not {"backup", "verification"} & set(lanes.tick(seoul(11, 1, 5)))
    assert sent.urls == [FAIL["backup"], FAIL["verification"]]
    assert {(turn.lane, turn.reason) for turn in lanes.turns if turn.outcome == "skipped"} == {
        ("backup", SKIPPED), ("verification", SKIPPED)}
    release.set()
    lanes.join()


class LedgerSeam:
    """`docsuri-ledger` run here: the real component on a ledger folder, or, while
    `refusing`, a refusal of every call."""

    REFUSED = b'{"ok": false, "reason": "ledger-unavailable"}\n'

    def __init__(self, folder: Path, evidence: Path, clock):
        self.command = LedgerCommand(folder, evidence, SimpleNamespace(read=lambda key: {}),
                                     clock=clock)
        self.refusing = False

    def __call__(self, argv, *, input, capture_output, timeout, check):
        if self.refusing:
            return SimpleNamespace(returncode=1, stdout=self.REFUSED, stderr=self.REFUSED)
        stdout, stderr = io.BytesIO(), io.BytesIO()
        code = self.command.run(argv[-1], io.BytesIO(input), stdout, stderr)
        return SimpleNamespace(returncode=code, stdout=stdout.getvalue(),
                               stderr=stderr.getvalue())


def ledger_client(root: Path, clock, *, set_at: dt.datetime, tombstone: dt.datetime | None = None):
    """A seeded ledger reached through `production_wiring.LedgerClient` and a seam: a
    passed live set at `set_at`, a verification at Sunday 2026-10-25 05:00 Seoul and an
    optional tombstone."""
    root.mkdir()
    seeded = rf.open_ledger(root, clock)
    try:
        backup = rf.set_record(seeded, now=set_at)
        cf.verified_restore(seeded, backup, now=seoul(10, 25, 5), environment="live")
        if tombstone is not None:
            clock.now = tombstone
            Tombstones(seeded).claim(uuid4(), uuid4())
    finally:
        seeded.close()
    seam = LedgerSeam(root / "operations-ledger", root / "evidence", clock)
    client = wiring.LedgerClient(via="standing", clock=clock, run=seam,
                                 paths=ArrangementPaths.under(root / "Library" / "DocSuri"))
    return client, seam


def client_job(client, clock, sent, *, heartbeat=None, record=None, disposal=None):
    procedures = Procedures()
    scheduled = recovery(client, clock, procedures, sent, [])
    procedures.requests = scheduled.requests
    if disposal is not None:
        scheduled.disposal = disposal
    return lanes_over(scheduled, slot=300, heartbeat=heartbeat, record=record)


def test_a_failed_ledger_call_makes_the_backup_and_verification_pings_report_fail(tmp_path):
    clock = Clock(seoul(10, 31, 3, 30))
    client, seam = ledger_client(tmp_path / "saturday", clock, set_at=seoul(10, 30, 4))
    sent, turns = Sent(), []
    try:
        lanes = client_job(client, clock, sent, record=turns.append)
        clock.now = seoul(10, 31, 3, 30)
        assert lanes.start(clock()) == []
        seam.refusing = True
        client.close()
        drive(lanes, clock, [seoul(10, 31, 4)])
        assert [(turn.at, turn.reason) for turn in turns if turn.lane == "backup"] == [
            (seoul(10, 31, 4), FAILED)]
        assert sent.of("backup") == [FAIL["backup"]]
    finally:
        client.close()
    clock = Clock(seoul(11, 1, 4, 30))
    client, seam = ledger_client(tmp_path / "sunday", clock, set_at=seoul(11, 1, 4))
    sent, turns = Sent(), []
    try:
        lanes = client_job(client, clock, sent, record=turns.append)
        clock.now = seoul(11, 1, 4, 30)
        assert lanes.start(clock()) == []
        seam.refusing = True
        client.close()
        drive(lanes, clock, [seoul(11, 1, 5)])
        assert [(turn.lane, turn.at, turn.reason) for turn in turns
                if turn.lane in ("backup", "verification")] == [
            ("verification", seoul(11, 1, 5), FAILED)]
        assert sent.urls == [FAIL["verification"]]
    finally:
        client.close()


def test_a_ledger_refusing_from_the_start_never_stops_the_standing_job(tmp_path):
    clock = Clock(seoul(10, 26, 10))
    client, seam = ledger_client(tmp_path / "refusing", clock, set_at=seoul(10, 25, 10),
                                 tombstone=seoul(10, 26, 3))
    sent = Sent()
    checks = Healthchecks(ADDRESSES, send=sent)

    def heartbeat(now) -> str:
        checks.ping("heartbeat", ok=True)
        return "ok"

    try:
        lanes = client_job(client, clock, sent, heartbeat=heartbeat)
        asked = {"backup": 0, "verification": 0}
        for name in asked:
            original = lanes.lanes[name].catch_up

            def counted(now, original=original, name=name):
                asked[name] += 1
                return original(now)

            lanes.lanes[name].catch_up = counted
        seam.refusing = True
        client.close()
        clock.now = seoul(10, 26, 10)
        assert lanes.start(clock()) == []
        instants = [seoul(10, 26, 10) + dt.timedelta(seconds=index) for index in range(1, 3601)]
        launched = drive(lanes, clock, instants)
        assert {name for name, _ in launched} == {"heartbeat", "agent-status", "isolation",
                                                  "housekeeping"}
        assert sent.of("heartbeat") == [ADDRESSES["heartbeat"]] * 12
        assert asked == {"backup": 3601, "verification": 3601}
        assert sent.of("backup") == [FAIL["backup"]]
        assert sent.of("verification") == [FAIL["verification"]]
        # The ledger answers again: the overdue backup (25 h) and the verification an
        # erasure left due at 05:00 start at the next tick (R4).
        # The backup's run reads the shared client from its own thread while the tick asks
        # the verification's catch-up: the client's lock keeps both reads whole.
        seam.refusing = False
        clock.now = seoul(10, 26, 11, 0, 30)
        started = lanes.tick(clock())
        lanes.join()
        assert sorted(started) == ["backup", "verification"]
    finally:
        client.close()
    # A ledger with nothing overdue, refusing at the 10:00 start and answering at 10:30:
    # neither the backup nor the verification starts that day.
    clock = Clock(seoul(10, 26, 10))
    client, seam = ledger_client(tmp_path / "current", clock, set_at=seoul(10, 26, 9))
    try:
        lanes = client_job(client, clock, Sent())
        seam.refusing = True
        client.close()
        clock.now = seoul(10, 26, 10)
        lanes.start(clock())

        def answer(at: dt.datetime) -> None:
            if at >= seoul(10, 26, 10, 30):
                seam.refusing = False

        launched = drive(lanes, clock, minutes(seoul(10, 26, 10), seoul(10, 26, 23, 59)),
                         before=answer)
        assert not {name for name, _ in launched} & {"backup", "verification"}
    finally:
        client.close()


def test_a_disposal_failure_after_a_successful_backup_pings_fail_last(ledger, clock):
    clock.now = SUNDAY
    backup = rf.set_record(ledger, now=SUNDAY - dt.timedelta(hours=1))
    cf.verified_restore(ledger, backup, now=seoul(10, 24, 12), environment="live")
    sent, turns = Sent(), []

    def refused() -> dict:
        raise wiring.WiringRefused("ledger-answered-no-result")

    lanes = client_job(ledger, clock, sent, record=turns.append, disposal=refused)
    assert lanes.start(SUNDAY) == []
    drive(lanes, clock, [seoul(10, 25, 4)])
    assert sent.urls == [ADDRESSES["backup"], FAIL["backup"]]
    assert [(turn.lane, turn.outcome, turn.reason) for turn in turns
            if turn.lane == "backup"] == [("backup", "failed", FAILED)]


# --- the start record and the newest set (Step 66(e), NFR8.6, NFR4.3) -----------------------


def test_the_standing_job_records_a_start_and_when_readiness_turned_true(tmp_path):
    start = dt.datetime(2026, 10, 26, tzinfo=dt.UTC)
    clock = Clock(start)
    probes: list[dt.datetime] = []

    def local(ready_from: dt.datetime | None):
        def answer() -> Answer:
            probes.append(clock())
            ready = ready_from is not None and clock() >= ready_from
            return Answer("answered", 200 if ready else 503)

        return answer

    folder = tmp_path / "scheduler" / "evidence" / "starts"
    watch = StartWatch(folder, local(start + dt.timedelta(seconds=60)), clock,
                       sleep=lambda seconds: clock.advance(seconds))
    watch.start().join(10)
    path = folder / "2026-10-26.jsonl"
    assert [json.loads(line) for line in path.read_text().splitlines()] == [
        {"startedAt": "2026-10-26T00:00:00Z", "readyAt": "2026-10-26T00:01:00Z", "seconds": 60}]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    assert len(probes) == 13 and probes[-1] == start + dt.timedelta(seconds=60)
    # A start whose probe never answers ready writes readyAt null at start + 600 s.
    probes.clear()
    other = tmp_path / "never" / "starts"
    clock.now = start
    StartWatch(other, local(None), clock, sleep=lambda seconds: clock.advance(seconds)).watch()
    assert json.loads((other / "2026-10-26.jsonl").read_text()) == {
        "startedAt": "2026-10-26T00:00:00Z", "readyAt": None}
    assert len(probes) == 121 and probes[-1] == clock() == start + dt.timedelta(seconds=600)
    # A second process start at 01:00 adds a second line.
    clock.now = start + dt.timedelta(hours=1)
    StartWatch(folder, local(clock()), clock, sleep=lambda seconds: clock.advance(seconds)
               ).watch()
    assert len(path.read_text().splitlines()) == 2
    # That the start record stays out of the availability folder is shown on the wiring's
    # own folders: test_production_wiring.test_the_standing_jobs_production_parts runs the
    # watch on production's starts folder and lists the availability folder after it.
    # Housekeeping deletes the day files more than 14 days old.
    (folder / "2026-10-27.jsonl").write_text("{}\n")
    housekeeping = Housekeeping(lambda: [], lambda now: 0, lambda now: [],
                                prune_starts=starts_pruner(folder))
    report = housekeeping.run(dt.datetime(2026, 11, 10, 1, tzinfo=dt.UTC))
    assert report["prunedStarts"] == 1
    assert sorted(item.name for item in folder.iterdir()) == ["2026-10-27.jsonl"]


class Recording(Procedures):
    """The backup records a passed live set at the clock's time, then ends succeeded."""

    def __init__(self, ledger, clock):
        super().__init__()
        self.ledger, self.clock = ledger, clock

    def backup(self, request_id, *, via):
        if self.state == "succeeded":
            rf.set_record(self.ledger, now=self.clock())
        return super().backup(request_id, via=via)


def test_the_newest_passed_set_is_never_older_than_a_day(ledger, clock):
    rf.set_record(ledger, now=seoul(10, 25, 4))
    procedures, sent = Recording(ledger, clock), Sent()
    scheduled = recovery(ledger, clock, procedures, sent, [])
    procedures.requests = scheduled.requests
    lanes = lanes_over(scheduled)
    start = seoul(10, 26, 0)
    clock.now = start
    lanes.start(start)
    lanes.join()
    for index in range(1, 10 * 24 + 1):
        at = start + dt.timedelta(hours=index)
        drive(lanes, clock, [at])
        newest = scheduled.newest_passed("live")
        assert at - rf_parse(newest["takenAt"]) <= dt.timedelta(hours=24), at
    procedures.state = "failed"
    drive(lanes, clock, [seoul(11, 5, 4)])
    assert sent.of("backup")[-1] == FAIL["backup"]


def test_the_backup_lane_runs_at_0400_seoul_on_the_current_database(tmp_path, realm, ledger,
                                                                    clock):
    from docsuri_ops.u8_platform.recovery_words import realm_procedures

    lanes = lanes_over(stand_in_recovery(Healthchecks(ADDRESSES, send=Sent()),
                                         backup=lambda now: None,
                                         verification=lambda now: None),
                       policy=PRODUCTION_OPERATIONS, slot=300)
    backup = lanes.lanes["backup"]
    assert backup.latest(dt.datetime(2026, 10, 22, 19, 7, tzinfo=dt.UTC)) == dt.datetime(
        2026, 10, 22, 19, tzinfo=dt.UTC)
    assert backup.latest(dt.datetime(2026, 10, 22, 18, 59, tzinfo=dt.UTC)) == dt.datetime(
        2026, 10, 21, 19, tzinfo=dt.UTC)
    for mode, rehearsal, expected in (("rehearsal", REHEARSAL_DATABASE, REHEARSAL_DATABASE),
                                      ("live", None, "docsuri_u8")):
        root = tmp_path / mode
        root.mkdir()
        journey = pf.journey(root, realm, mode=mode, rehearsal=rehearsal)
        procedures = realm_procedures(journey.profile, ledger, clock=clock,
                                      role="scheduler").procedures
        environment = "live" if mode == "live" else "rehearsal"
        effect = procedures.backup_effect(environment, request=None, via="standing",
                                          owner_key=f"standing-test:{mode}")
        assert procedures.platform.database_of(environment) == expected
        assert effect["inputs"]["database"] == expected
    assert ledger.records("backup-set") == []  # no dump ran


# --- housekeeping, the agent status, the isolation lane, the wiring --------------------------


def test_housekeeping_expires_requests_at_24_hours_and_prunes_the_record(ledger, clock,
                                                                         tmp_path):
    requests = RecoveryRequests(ledger, SYNTHETIC_OPERATIONS, clock=clock)
    request = requests.request(origin="schedule", operation="backup.create",
                               environment="rehearsal", target_id="docsuri_u8",
                               expected_revision=0, submission_id=uuid4())
    record = AvailabilityRecord(tmp_path / "availability")
    deleted = []

    def delete(now, *, limit=1000):
        deleted.append(now)
        return 1000 if len(deleted) == 1 else 3

    housekeeping = Housekeeping(requests.expire_due, delete, record.prune)
    first = housekeeping.run(clock())
    assert first["expiredRequests"] == 0  # not yet 24 hours
    assert first["deletedObservations"] == 1003  # batches until one comes back short
    clock.advance(24 * 3600 + 1)
    report = housekeeping.run(clock())
    assert report["expiredRequests"] == 1 and report["deletedObservations"] == 3
    assert requests.get(request["recoveryRequestId"])["state"] == "expired"
    clock.now = dt.datetime(2027, 12, 10, tzinfo=dt.UTC)
    for month in ("2026-10", "2026-11", "2027-12"):
        record.append(dt.datetime.fromisoformat(f"{month}-02T00:00:00+00:00"), True, "ok")
    assert housekeeping.run(clock())["prunedMonths"] == 1  # 2026-10 only: past 13 months
    assert sorted(path.name for path in (tmp_path / "availability").iterdir()) == [
        "2026-11.jsonl", "2027-12.jsonl"]
    broken = Housekeeping(lambda: 1 / 0, delete, record.prune)
    assert broken.run(clock())["expiredRequests"] == "failed:ZeroDivisionError"


def test_the_agent_status_is_recorded_and_a_passing_again_runs_disposal(ledger):
    recorded, disposals = [], []
    answers = iter([{"available": True}, {"available": False}, {"available": True}])
    agent = AgentStatus(lambda: next(answers), recorded.append,
                        lambda: disposals.append("pass") or {},
                        identities=ledger_identities(ledger))
    assert agent.run(None) == "volume-available"
    assert agent.run(None) == "volume-unavailable"
    assert agent.run(None) == "volume-check-passed-again" and disposals == ["pass"]

    def unreachable():
        raise OSError("gone")

    silent = AgentStatus(unreachable, recorded.append, lambda: {},
                         identities=ledger_identities(ledger))
    assert silent.run(None) == "volume-unavailable"
    assert recorded[-1]["findings"] == ["backup-agent-unreachable"]
    stored = []
    store = SimpleNamespace(record_evidence=lambda **fields: stored.append(fields))
    evidence_recorder(store, environment="u8-realm:x", max_age_seconds=900)({"available": True})
    assert stored[0]["target"] == "backup-volume" and len(stored[0]["input_hash"]) == 64


def listed(record_id: str, day: int) -> dict:
    return {"recordId": record_id, "recordKind": "BackupSet", "place": "archives",
            "disposeAfter": f"2026-11-{day:02d}T04:00:00+00:00"}


def test_the_agent_status_evidence_names_only_files_the_ledger_does_not_record(ledger, clock):
    """L1-51: the volume's catalogue compared with the ledger, bounded for PlatformControl's
    8,192-byte observations."""
    held = [rf.set_record(ledger, now=clock()), rf.set_record(ledger, now=clock())]
    loose = str(uuid4())
    status = {"available": True, "deletionAllowed": True, "catalogue": "intact",
              "catalogued": [listed(held[0]["backupId"], 10), listed(held[1]["backupId"], 11),
                             listed(loose, 12)]}
    recorded = []
    agent = AgentStatus(lambda: dict(status), recorded.append, lambda: {},
                        identities=ledger_identities(ledger))
    assert agent.run(None) == "volume-available"
    observed = recorded[-1]
    assert "catalogued" not in observed
    assert observed["unrecordedFiles"] == [listed(loose, 12)]
    assert (observed["unrecordedCount"], observed["cataloguedCount"]) == (1, 3)
    # Forty unrecorded files: thirty-two listed, the latest disposal point first.
    many = [listed(str(uuid4()), 1 + index % 28) for index in range(40)]
    status["catalogued"] = many
    agent.run(None)
    observed = recorded[-1]
    points = [item["disposeAfter"] for item in observed["unrecordedFiles"]]
    assert len(points) == 32 and points == sorted(points, reverse=True)
    assert observed["unrecordedCount"] == 40 and observed["cataloguedCount"] == 40
    assert len(json.dumps(observed)) < 8192
    # A ledger whose reads raise: the status is still recorded, without the comparison.

    def raising() -> set[str]:
        raise OSError("ledger refused")

    status["available"] = False
    blind = AgentStatus(lambda: dict(status), recorded.append, lambda: {}, identities=raising)
    assert blind.run(None) == "volume-unavailable"
    assert not {"catalogued", "unrecordedFiles", "unrecordedCount",
                "cataloguedCount"} & set(recorded[-1])


def test_the_isolation_lane_runs_platformcontrols_bound_check(clock):
    calls = []
    operator = SimpleNamespace(execute=lambda *args, key: calls.append((args, key)) or {
        "outcome": "succeeded"})
    assert isolation_lane(operator)(clock()) == "isolation-checked"
    (operation, target, inputs), key = calls[0]
    assert (operation, target, inputs) == ("platform.isolation.check", "isolation",
                                           {"via": "standing"})
    assert key.startswith("standing-isolation:") and len(key) <= 128
    refused = SimpleNamespace(execute=lambda *args, key: {"outcome": "failed"})
    assert isolation_lane(refused)(clock()) == "isolation-not-checked"


def test_the_realm_wiring_composes_every_lane(tmp_path, realm, clock, ledger):
    parts = realm_parts(Path(realm.root) / "environment.json", ledger, clock=clock,
                        checks=Healthchecks(ADDRESSES, send=Sent()),
                        record_folder=tmp_path / "availability")
    lanes = build_lanes(parts)
    assert list(lanes.lanes) == ["heartbeat", "agent-status", "isolation", "backup",
                                 "verification", "housekeeping"]
    assert parts.slot_seconds == SYNTHETIC_OPERATIONS.availability_slot_seconds
    assert parts.housekeeping.delete_observations(clock()) == 0
    # The pass and the standing job's requests read one function (L1-65).
    assert parts.recovery.disposal.__self__.platform.environment is parts.recovery.environment
    # The start record's watch and its pruning (Step 66(e)).
    assert parts.start_watch.folder.parts[-3:] == ("scheduler", "evidence", "starts")
    assert parts.agent.identities is not None


class Completed:
    def __init__(self, stdout: bytes = b"", returncode: int = 0):
        self.stdout, self.returncode = stdout, returncode


def test_the_fixed_programs_run_through_sudo_without_a_prompt():
    seen = []

    def run(argv, **options):
        seen.append((argv, options))
        return Completed(b'{"ok": true, "available": true}\n')

    assert macos.run_fixed(macos.BACKUP, "docsuri-backup-agent", "status", run=run)[
        "available"] is True
    argv, options = seen[0]
    assert argv == ["/usr/bin/sudo", "-n", "-u", "_docsuri_r1t_backup",
                    "/Library/DocSuri/release/ops/bin/docsuri-backup-agent", "status"]
    assert options["env"] == {"PATH": "/usr/bin:/bin"} and options["input"] == b"{}"
    with pytest.raises(RuntimeError, match="volume-unavailable"):
        macos.run_fixed(macos.BACKUP, "docsuri-backup-agent", "status",
                        run=lambda argv, **o: Completed(
                            b'{"ok": false, "reason": "volume-unavailable"}', 1))
    with pytest.raises(ValueError):
        macos.last_json(b"")


class Process:
    def __init__(self, argv, stdin=None, stdout=None, stderr=None, env=None):
        self.argv, self.returncode = argv, 0
        self.stdin = stdin
        if "copy" in argv:
            self.stdout = io.BytesIO(b"ledger bytes")
            self.stderr = io.BytesIO(b'{"ok": true, "count": 3}\n')
        else:
            self.stdout, self.stderr = io.BytesIO(), io.BytesIO()
            self.received = stdin.read()

    def communicate(self, timeout=None):
        return b"", b'{"ok": true, "sha256": "' + b"a" * 64 + b'"}\n'

    def wait(self, timeout=None):
        return 0


def test_the_ledger_copy_reaches_the_agent_only_as_a_stream():
    started = []

    def popen(argv, **options):
        process = Process(argv, **options)
        started.append(process)
        return process

    result = macos.ledger_copy(popen=popen)
    source, sink = started
    assert source.argv[-2:] == ["/Library/DocSuri/release/ops/bin/docsuri-ledger", "copy"]
    assert source.argv[3] == "_docsuri_v2" and sink.argv[3] == "_docsuri_r1t_backup"
    assert sink.argv[-1] == "ledger-copy" and sink.received == b"ledger bytes"
    assert source.stdin is subprocess.DEVNULL
    assert result == {"head": {"ok": True, "count": 3},
                      "agent": {"ok": True, "sha256": "a" * 64}}
    assert json.dumps(result)


# --- review fixes, build batch 4 ------------------------------------------------------------


class Interleaved(Procedures):
    """`between()` runs once while the turn settles interrupted work: another process's
    write landing after the turn's first read."""

    def __init__(self):
        super().__init__()
        self.between = None

    def reconcile_interrupted(self, targets):
        result = super().reconcile_interrupted(targets)
        if self.between is not None:
            between, self.between = self.between, None
            between()
        return result


def second_writer(root: Path, clock):
    """Another process on the same ledger folder (the release, an administrator, the
    host), behind the standing job's `LedgerClient`."""
    from backend.modules.operations.ledger import Ledger

    return Ledger.open(root / "operations-ledger", clock=clock)


def profile_mode(ledger, mode: str, now: dt.datetime) -> None:
    """A switch's profile receipt, as the cutover tool's records add it."""
    from docsuri_ops.u8_platform.drivers import input_hash

    facts = rf.receipt("platform.profile.mode", "profile", now=now)
    facts["inputHash"] = input_hash({"field": "mode", "value": mode})
    ledger.atomic(lambda view: view._write("receipt-facts", facts))


def test_each_0400_turn_acts_on_what_another_process_recorded(tmp_path):
    """Review findings (Major, batch 4): over production's `LedgerClient`, a set and a
    profile receipt another process records between two turns are seen by the next turn,
    and a filing the ledger refuses still takes the day's lone copy."""
    clock = Clock(seoul(10, 26, 3, 30))
    root = tmp_path / "behind"
    client, _ = ledger_client(root, clock, set_at=seoul(10, 25, 4))
    other = second_writer(root, clock)
    procedures, sent, passes = Interleaved(), Sent(), []

    def serving() -> str:
        return "live" if wiring.ledger_profile_state(client)["mode"] == "live" else (
            "rehearsal")

    def disposal() -> dict:  # reads the ledger last, as the real pass does
        passes.append(len(client.records("retained-copy")))
        return {}

    try:
        scheduled = recovery(client, clock, procedures, sent, [], environment=serving)
        procedures.requests = scheduled.requests
        scheduled.disposal = disposal
        clock.now = seoul(10, 26, 4)
        assert scheduled.backup(clock()) == "backup-succeeded"
        [first] = client.records("recovery-request")
        assert (first["environment"], first["expectedRevision"]) == ("rehearsal", 0)
        # Another process: the release's pre-release live set, and the switch's receipt.
        clock.now = seoul(10, 26, 10)
        rf.set_record(other, now=clock())
        profile_mode(other, "live", clock())
        clock.now = seoul(10, 27, 4)
        assert scheduled.backup(clock()) == "backup-succeeded"
        [second] = [item for item in client.records("recovery-request")
                    if item["recoveryRequestId"] != first["recoveryRequestId"]]
        assert (second["environment"], second["expectedRevision"]) == ("live", 2)
        # A set recorded after the turn's first read: the filing is refused CONFLICT, the
        # backup is not admitted, the lone copy is taken, one /backup/fail, no pass.
        procedures.between = lambda: rf.set_record(other, now=clock())
        clock.now = seoul(10, 28, 4)
        before = len(passes)
        procedures.calls.clear()
        sent.urls.clear()
        assert scheduled.backup(clock()) == "backup-not-admitted"
        assert ("ledger_copy_alone", "live", owner_of("live", clock())) in procedures.calls
        assert ("backup", "standing") not in procedures.calls
        assert sent.urls == [FAIL["backup"]] and len(passes) == before
    finally:
        other.close()
        client.close()


def test_a_tombstone_another_process_appends_at_0440_is_verified_at_that_0500(tmp_path):
    """Review findings (Major, batch 4, L1-42): each 05:00 candidate is decided on a
    fresh read of production's `LedgerClient`."""
    clock = Clock(seoul(10, 26, 4, 30))
    root = tmp_path / "tombstone"
    client, _ = ledger_client(root, clock, set_at=seoul(10, 26, 4))
    other = second_writer(root, clock)
    sent, turns = Sent(), []
    try:
        procedures = Verifying(client, clock)
        scheduled = recovery(client, clock, procedures, sent, [])
        procedures.requests = scheduled.requests
        lanes = lanes_over(scheduled, record=turns.append)
        assert lanes.start(clock()) == []
        appended = seoul(10, 26, 4, 40)

        def claim(at: dt.datetime) -> None:
            if at == appended:
                clock.now = at
                Tombstones(other).claim(uuid4(), uuid4())

        launched = drive(lanes, clock, minutes(seoul(10, 26, 4, 30), seoul(10, 26, 5, 10)),
                         before=claim)
        assert [at for name, at in launched if name == "verification"] == [seoul(10, 26, 5)]
        assert not any(url.endswith("/fail") for url in sent.urls)
        assert not [turn for turn in turns if turn.outcome in ("skipped", "failed")]
    finally:
        other.close()
        client.close()


def open_descriptors() -> int:
    return len(os.listdir("/dev/fd"))


def test_the_ledger_client_closes_each_local_copy_it_drops(tmp_path):
    """Review finding (Major, batch 4): an append or an atomic step closes the copy it
    drops, so the standing job does not leak a descriptor per write."""
    clock = Clock(seoul(10, 26, 10))
    client, _ = ledger_client(tmp_path / "descriptors", clock, set_at=seoul(10, 26, 4))
    requests = RecoveryRequests(client, SYNTHETIC_OPERATIONS, clock=clock)
    backup_id = client.records("backup-set")[0]["backupId"]

    def writes() -> None:
        # One plain append (no receipt to confirm), one atomic step that writes, and one
        # that only reads.
        now = rf.utc_text(clock())
        head = Tombstones(client).head()
        client.append("restore-verification", {
            "verificationId": str(uuid4()), "environment": "live", "backupId": backup_id,
            "startedAt": now, "finishedAt": now, "registerHeadSequence": head["sequence"],
            "registerHeadDigest": head["digest"], "integrity": "passed",
            "erasedOwnersSurviving": 0, "result": "verified",
            "evidenceRef": "verification:fixture", "scratchRemovedAt": now},
            expect_revision=0)
        requests.request(origin="schedule", operation="backup.create",
                         environment="rehearsal", target_id="docsuri_u8",
                         expected_revision=0, submission_id=uuid4())
        client.atomic(lambda view: len(view.records("backup-set")))

    try:
        writes()
        before = open_descriptors()
        for index in range(10):
            writes()
            assert len(client.records("recovery-request")) == index + 2
        assert open_descriptors() <= before + 1  # the one local copy the last read holds
    finally:
        client.close()


def test_a_schedule_raising_at_start_waits_for_its_next_turn():
    """Step 66(c), 67(d): a catch-up check that answers and a schedule that then raises at
    start count the lane as started at that day's 05:00 candidate."""
    sent, turns, ran = Sent(), [], []
    checks = Healthchecks(ADDRESSES, send=sent)
    daily = daily_at(5)
    reads = []

    def latest(now: dt.datetime) -> dt.datetime:
        reads.append(now)
        if len(reads) == 1:
            raise OSError("the ledger refused")
        return daily(now)

    lanes = Lanes([Lane("verification", latest, lambda now: ran.append(now) or "ran",
                        catch_up=lambda now: False, turn=daily)],
                  record=turns.append, fail=checks.fail)
    start = seoul(10, 26, 10, 30)
    assert lanes.start(start) == []
    assert [(turn.lane, turn.reason) for turn in turns] == [("verification", FAILED)]
    assert sent.urls == [FAIL["verification"]]
    assert lanes.lanes["verification"].last_started == seoul(10, 26, 5)
    launched = drive(lanes, Clock(start), minutes(start, seoul(10, 27, 5, 30)))
    assert launched == [("verification", seoul(10, 27, 5))] and ran == [seoul(10, 27, 5)]
    assert sent.urls == [FAIL["verification"]]


def test_a_fail_ping_that_raises_never_stops_the_other_lanes():
    """Review finding (Minor, batch 4): an `http.client` error from a /fail ping is an
    undelivered ping, and a raising `fail` never reaches the tick thread."""
    import http.client

    def garbled(url: str, seconds: float) -> int:
        raise http.client.BadStatusLine("garbled")

    checks = Healthchecks(ADDRESSES, send=garbled)
    assert checks.fail("backup") is False and checks.last["backup"] == "undelivered"

    def refused(now: dt.datetime) -> dt.datetime:
        raise OSError("the ledger refused")

    def raising(check: str) -> bool:
        raise http.client.BadStatusLine("garbled")

    beats = []
    lanes = Lanes([Lane("backup", refused, lambda now: None, catch_up=refused,
                        turn=daily_at(4)),
                   Lane("verification", refused, lambda now: None, turn=daily_at(5)),
                   Lane("heartbeat", every(300), lambda now: beats.append(now) or "ok")],
                  fail=raising)
    start = seoul(10, 26, 10)
    lanes.start(start)
    for minute in range(1, 16):
        lanes.tick(start + dt.timedelta(minutes=minute))
        lanes.join()
    assert beats == [seoul(10, 26, 10, 5), seoul(10, 26, 10, 10), seoul(10, 26, 10, 15)]
    assert lanes.failures == {"backup": "OSError", "verification": "OSError"}


def test_the_backup_lanes_pass_and_the_passed_again_pass_never_overlap(ledger, clock):
    """Review finding (Minor, batch 4): one DisposalPass serves the backup lane and the
    agent-status lane from their own threads; a second run waits for the first."""
    from docsuri_ops.cutover.disposal import DisposalPass, DisposalPlatform

    platform = DisposalPlatform(operator=None, names=DatabaseNames("docsuri_u8"),
                                current_rehearsal=lambda: None,
                                dispose_due=lambda document: {},
                                environment=lambda: "live")
    disposal = DisposalPass(ledger, SYNTHETIC_OPERATIONS, platform, clock=clock)
    inside, overlap = [0], []
    entered, release = threading.Event(), threading.Event()

    def held() -> dict:  # the pass's body, held open while the other lane arrives
        inside[0] += 1
        overlap.append(inside[0])
        entered.set()
        release.wait(5)
        inside[0] -= 1
        return {"ran": True}

    disposal._run = held
    arrived = threading.Event()

    class NotingLock:
        """The pass's own lock, noting when a second caller finds it held and waits."""

        def __init__(self, lock) -> None:
            self.lock = lock

        def __enter__(self) -> NotingLock:
            if not self.lock.acquire(blocking=False):
                arrived.set()
                self.lock.acquire()
            return self

        def __exit__(self, *exc) -> None:
            self.lock.release()

    disposal._running = NotingLock(disposal._running)
    agent = AgentStatus(lambda: {"available": True}, lambda observed: None, disposal.run)
    agent.available = False  # the volume check failed last time: it passes again now
    procedures = Procedures()
    scheduled = recovery(ledger, clock, procedures, Sent(), [])
    procedures.requests = scheduled.requests
    scheduled.disposal = disposal.run
    backup = threading.Thread(target=scheduled.backup, args=(clock(),))
    backup.start()
    assert entered.wait(5)
    passed = threading.Thread(target=agent.run, args=(clock(),))
    passed.start()
    # Released once the second lane has reached the held pass, never after a fixed time.
    assert arrived.wait(5), "the passed-again pass never reached the backup lane's pass"
    assert passed.is_alive()  # waits for the backup lane's pass
    release.set()
    backup.join(5)
    passed.join(5)
    assert overlap == [1, 1]


def test_each_passed_again_pass_reads_a_current_ledger(tmp_path):
    """Review finding (Major, batch 4 re-review; BR9.17, L1-65): the agent-status lane's
    passed-again pass, over production's `LedgerClient`, sees what another process
    recorded after the client's last read: a switch's profile receipt moves its
    incidents to live, and a switch begun after that holds the pass."""
    from docsuri_ops.cutover.disposal import DisposalPass, DisposalPlatform

    clock = Clock(seoul(10, 26, 10))
    root = tmp_path / "passed-again"
    client, _ = ledger_client(root, clock, set_at=seoul(10, 26, 4))
    other = second_writer(root, clock)
    documents, passes, answers = [], [], []

    def serving() -> str:  # production's `serving`, over the same ledger
        return "live" if wiring.ledger_profile_state(client)["mode"] == "live" else (
            "rehearsal")

    platform = DisposalPlatform(operator=None, names=DatabaseNames("docsuri_u8"),
                                current_rehearsal=lambda: None,
                                dispose_due=lambda document: documents.append(document) or {},
                                environment=serving)
    disposal = DisposalPass(client, SYNTHETIC_OPERATIONS, platform, clock=clock)

    def passed_again() -> dict:
        passes.append(disposal.run())
        return passes[-1]

    agent = AgentStatus(lambda: answers.pop(0), lambda observed: None, passed_again)

    def fail_then_pass() -> None:
        answers.extend([{"available": False}, {"available": True}])
        assert agent.run(clock()) == "volume-unavailable"
        assert agent.run(clock()) == "volume-check-passed-again"

    try:
        # The client's last read: the pass runs in rehearsal, nothing held.
        assert disposal.run()["ran"] is True and disposal._serving == "rehearsal"
        # A switch's profile receipt another process records after that read.
        clock.now = seoul(10, 26, 15)
        profile_mode(other, "live", clock())
        fail_then_pass()
        assert passes[-1]["ran"] is True and disposal._serving == "live"
        # A switch another process begins after that pass: the next one holds.
        cf.switching(other, clock)
        before = len(documents)
        fail_then_pass()
        assert passes[-1] == {"ran": False, "reason": "live-exclusion-held"}
        assert len(documents) == before
    finally:
        other.close()
        client.close()


def test_a_lone_copy_found_applied_is_recorded_or_signalled(tmp_path):
    """Step 64(j), review findings (Minor, batch 4 and its re-review): a lone copy
    reconciliation finds applied is recorded from its effect record, read beside its
    `effectReference` (a reconciled receipt carries no refs of its own); one whose
    recording fails signals storage.capacity at once, in the copy's own environment from
    its bound input, since no later settle lists it again."""
    from docsuri_ops.u8_platform.drivers import input_hash, parse_facts, write_input

    cases =(("applied", True, "live"), ("incomplete", False, "live"),
             ("incomplete-rehearsal", False, "rehearsal"))
    for name, complete, environment in cases:
        job = real_job(tmp_path / name, environment="live")
        try:
            rf.set_record(job.ledger, now=job.clock() - dt.timedelta(days=1))
            receipt = job.operator._answer("platform.ledger.copy", "ledger-copy", {})
            refs = receipt.pop("effectRefs")
            if not complete:
                refs = ["backup-volume/archives/ledger-copy-x.archive"]
            inputs = {"via": "standing", "environment": environment}
            token = "ledger-copy-" + receipt["operationId"]
            folder = job.operator.profile.effects_root / "ledger-copy"
            write_input(folder, token, inputs)
            (folder / f"effect-{token}.json").write_text(json.dumps({"refs": refs}))
            receipt.update({"reconciliationState": "reconciled-applied", "outcome": "unknown",
                            "inputHash": input_hash(inputs),
                            "effectReference": f"ledger-copy/effect-{token}.json",
                            "authorityRef": job.operator.authorities["routine"]})
            job.operator.store.list_unresolved = lambda actor, authority, item=receipt: [item]
            job.operator.reconcile = lambda operation_id, item=receipt: dict(item)
            settled = job.scheduled.procedures.reconcile_interrupted(("ledger-copy",))
            assert [item["operationId"] for item in settled] == [receipt["operationId"]]
            signals = [item for item in job.incidents.signals
                       if item[1] == f"ledger-copy:reconciled:{receipt['operationId']}"]
            if complete:
                [copy] = lone_copies(job.ledger)
                assert copy["operatorReceiptRef"] == receipt["receiptId"]
                assert "effectRefs" not in receipt  # recorded from the effect record
                assert copy["location"] == refs[0].removeprefix("backup-volume/")
                assert copy["ledgerCopyId"] == parse_facts(refs)["recordId"]
                assert copy.get("verifiedAt") and signals == []
            else:
                assert lone_copies(job.ledger) == []
                assert signals == [("storage.capacity",
                                    f"ledger-copy:reconciled:{receipt['operationId']}",
                                    environment)]
        finally:
            job.ledger.close()
