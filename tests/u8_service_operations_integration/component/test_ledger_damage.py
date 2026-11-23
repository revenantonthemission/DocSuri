"""The ledger's own damage (U8 plan Step 16; your decision of 2026-10-22, BR6.10).

A damaged ledger cannot hold its own incident. While it is damaged, readiness shows
`operations.ledger` as unavailable and the tolerance watcher writes a counted
`incident.unrecordable` line, appending nothing. The repair (`docsuri-ledger repair`)
records the incident with the time the damage was first found, and the watcher resolves
it as `capability-available` once the ledger check passes. The ledger is a real one in
a private temporary folder; time moves only through the injected clock.
"""

from __future__ import annotations

import io
import json
import logging
import os

import pytest

from backend.log_events import EventLog
from backend.modules.operations import ledger_cli
from backend.modules.operations.errors import LedgerDamaged
from backend.modules.operations.incidents import (
    LEDGER,
    LEDGER_DAMAGED,
    Incidents,
    ToleranceWatcher,
)
from backend.modules.operations.ledger import (
    DAMAGE_MARKER,
    Ledger,
    LedgerStore,
    read_damage,
    utc_text,
)
from backend.modules.operations.ledger_cli import LedgerCommand, UnboundReceiptReader, run
from backend.modules.operations.producers import LedgerProducer
from backend.modules.operations.readiness import CapabilityState, Readiness
from backend.u8_host import Activation
from backend.u8_policy import SYNTHETIC_OPERATIONS
from backend.u8_registry import CAPABILITIES, CONTRIBUTIONS, MANIFEST

POLICY = SYNTHETIC_OPERATIONS
ALL_ACTIVE = {entry.contribution_id: Activation(entry.contribution_id, "active")
              for entry in CONTRIBUTIONS}


class States:
    """The readiness module's answer, set by the test."""

    def __init__(self, clock):
        self.clock = clock
        self.current = {cap.capability_id: CapabilityState(cap.capability_id, "available",
                                                            None) for cap in CAPABILITIES}

    def set(self, capability: str, state: str, reason: str | None = None):
        self.current[capability] = CapabilityState(capability, state, reason,
                                                   observed_at=self.clock())

    def states(self):
        return dict(self.current)


@pytest.fixture
def folders(tmp_path):
    ledger, evidence = tmp_path / "ledger", tmp_path / "evidence"
    ledger.mkdir(mode=0o700)
    evidence.mkdir(mode=0o700)
    return ledger, evidence


@pytest.fixture
def ledger(folders, clock):
    value = Ledger.open(folders[0], clock=clock)
    yield value
    value.close()


@pytest.fixture
def watcher(ledger, clock):
    states = States(clock)
    log = EventLog(strict=True)
    return ToleranceWatcher(Incidents(ledger, environment="live"), states, POLICY, clock,
                            log=log), states


@pytest.fixture
def command(folders, clock):
    return LedgerCommand(folder=folders[0], evidence=folders[1],
                         receipts=UnboundReceiptReader(), clock=clock, environment="live")


def healthy_copy(ledger) -> bytes:
    """Three ordinary incidents, then the verified copy a repair would stream in."""
    incidents = Incidents(ledger, environment="live")
    for capability in ("export", "research", "library.saved-work"):
        incidents.signal(capability, "operator")
    sink = io.BytesIO()
    ledger.copy(sink)
    return sink.getvalue()


def damage(folder) -> bytes:
    """One changed byte inside the chain: it no longer verifies up to its head."""
    log = folder / LedgerStore.LOG
    damaged = log.read_bytes().replace(b'"operator"', b'"Operator"', 1)
    descriptor = os.open(log, os.O_WRONLY | os.O_TRUNC)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(damaged)
    return damaged


def repair(command, copy: bytes) -> tuple[int, dict]:
    stdout, stderr = io.BytesIO(), io.BytesIO()
    status = run(["repair"], command, environ={}, stdin=io.BytesIO(copy), stdout=stdout,
                 stderr=stderr)
    return status, json.loads(stdout.getvalue().decode().strip().splitlines()[-1])


def ledger_incidents(folder, clock) -> list[dict]:
    reopened = Ledger.open(folder, clock=clock)
    try:
        return [item for item in reopened.records("service-incident")
                if item["openedBy"] == LEDGER_DAMAGED]
    finally:
        reopened.close()


class Lines(logging.Handler):
    """Every line the registered log writes, captured on its own logger (another test
    may have stopped it propagating)."""

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(json.loads(record.getMessage()))

    def unrecordable(self) -> list[dict]:
        return [line for line in self.lines if line["event"] == "incident.unrecordable"]


@pytest.fixture
def events():
    logger = logging.getLogger("docsuri.events")
    handler, level = Lines(), logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    yield handler
    logger.removeHandler(handler)
    logger.setLevel(level)


# --- 1. While damaged: unavailable, and the watcher appends nothing ----------------------


def test_damage_makes_the_ledger_capability_unavailable_in_readiness(ledger, folders, clock):
    healthy_copy(ledger)
    damage(folders[0])
    observed = LedgerProducer(ledger).observe(clock())
    assert (observed.outcome, observed.reason) == ("unavailable", "ledger-damaged")
    view = Readiness(MANIFEST, ALL_ACTIVE, {}, None, POLICY, clock)
    latest = {cap.capability_id: {
        "outcome": "available", "reason_key": None, "limitation_keys": [],
        "observed_at": clock(), "error_count": 0, "total_count": 1,
    } for cap in CAPABILITIES}
    latest[LEDGER] = {**latest[LEDGER], "outcome": observed.outcome,
                      "reason_key": observed.reason}
    states = view.derive(latest, clock())
    assert states[LEDGER].brief() == {"state": "unavailable", "reason": "ledger-damaged"}
    report = view.report(states)
    assert report["ready"] is False and LEDGER in report["missing"]
    with pytest.raises(LedgerDamaged):
        ledger.records("service-incident")  # every dependent read and write is refused


def test_the_watcher_writes_one_counted_unrecordable_line_and_appends_nothing(
    ledger, folders, clock, watcher, events,
):
    healthy_copy(ledger)
    damaged = damage(folders[0])
    assert ledger.check()["status"] == "unavailable"
    head = (folders[0] / LedgerStore.HEAD).read_bytes()
    tolerance, states = watcher
    states.set(LEDGER, "unavailable", "ledger-damaged")
    assert tolerance.run_once() == []
    lines = events.unrecordable()
    assert len(lines) == 1 and tolerance.unrecorded == 1
    assert (lines[0]["state"], lines[0]["level"], lines[0]["errorType"]) == (
        LEDGER, "error", "LedgerDamaged")
    # Nothing was appended: the damaged files are exactly as they were.
    assert (folders[0] / LedgerStore.LOG).read_bytes() == damaged
    assert (folders[0] / LedgerStore.HEAD).read_bytes() == head
    tolerance.run_once()
    assert tolerance.unrecorded == 2 and len(events.unrecordable()) == 2


def test_the_first_finding_of_the_damage_is_kept_beside_the_ledger(ledger, folders, clock):
    healthy_copy(ledger)
    damage(folders[0])
    found = clock()
    assert ledger.check()["status"] == "unavailable"
    assert ledger.damage_found_at == found
    clock.advance(600)
    # Another process finds it later; the earliest finding stays.
    with pytest.raises(LedgerDamaged):
        Ledger.open(folders[0], clock=clock)
    second = Ledger(LedgerStore(folders[0], clock=clock, log_name=LedgerStore.LOG,
                                head_name=LedgerStore.HEAD), clock=clock)
    second._mark("chain-break")
    marker = read_damage(folders[0])
    assert marker == {"category": ledger.damaged, "foundAt": utc_text(found)}
    info = (folders[0] / DAMAGE_MARKER).lstat()
    assert info.st_mode & 0o777 == 0o600


# --- 2. The repair records the incident at its first finding --------------------------------


def test_the_repair_records_the_incident_with_the_time_the_damage_was_first_found(
    ledger, folders, clock, command,
):
    copy = healthy_copy(ledger)
    damage(folders[0])
    found = clock()
    assert ledger.check()["status"] == "unavailable"
    clock.advance(3600)  # the repair comes an hour later
    status, answer = repair(command, copy)
    assert status == 0 and answer["ok"] is True
    [incident] = ledger_incidents(folders[0], clock)
    assert incident["incidentId"] == answer["incidentId"]
    assert (incident["capabilities"], incident["state"], incident["environment"]) == (
        [LEDGER], "open", "live")
    assert incident["openedAt"] == utc_text(found)
    assert incident["evidenceRefs"] == [answer["aside"]]
    # The marker moved aside with the damaged files.
    assert not (folders[0] / DAMAGE_MARKER).exists()
    aside = folders[1] / answer["aside"].removeprefix("evidence/")
    assert json.loads((aside / DAMAGE_MARKER).read_bytes())["foundAt"] == utc_text(found)
    # The running process's ledger reopens the repaired one without a restart.
    assert ledger.check()["status"] == "available"
    assert ledger.get("service-incident", incident["incidentId"]) == incident


def test_a_damage_no_process_found_first_is_recorded_at_the_repairs_own_finding(
    ledger, folders, clock, command,
):
    copy = healthy_copy(ledger)
    ledger.close()
    damage(folders[0])
    clock.advance(120)
    status, answer = repair(command, copy)
    assert status == 0
    [incident] = ledger_incidents(folders[0], clock)
    assert incident["openedAt"] == utc_text(clock())


def test_the_incident_resolves_as_capability_available_once_the_ledger_check_passes(
    ledger, folders, clock, command, watcher,
):
    copy = healthy_copy(ledger)
    damage(folders[0])
    assert ledger.check()["status"] == "unavailable"
    status, answer = repair(command, copy)
    assert status == 0
    tolerance, states = watcher
    states.set(LEDGER, "unavailable", "ledger-damaged")  # the producer has not looked yet
    tolerance.run_once()
    assert tolerance.settled == []
    assert ledger_incidents(folders[0], clock)[0]["state"] == "open"
    assert ledger.check()["status"] == "available"
    clock.advance(60)
    states.set(LEDGER, "available")
    tolerance.run_once()
    resolved = ledger.get("service-incident", answer["incidentId"])
    assert tolerance.settled == [answer["incidentId"]]
    assert (resolved["state"], resolved["resolutionKind"]) == (
        "resolved", "capability-available")
    assert resolved["resolvedAt"] == utc_text(clock())
    tolerance.run_once()
    assert tolerance.settled == []  # resolved once


# --- 3. A second repair records nothing twice ----------------------------------------------


def test_a_second_repair_records_nothing_twice(ledger, folders, clock, command):
    copy = healthy_copy(ledger)
    damage(folders[0])
    assert ledger.check()["status"] == "unavailable"
    status, first = repair(command, copy)
    assert status == 0
    head = (folders[0] / LedgerStore.HEAD).read_bytes()
    status, second = repair(command, copy)
    assert (status, second["reason"]) == (1, "ledger-not-damaged")
    assert (folders[0] / LedgerStore.HEAD).read_bytes() == head
    assert [item["incidentId"] for item in ledger_incidents(folders[0], clock)] == [
        first["incidentId"]]


def test_an_interrupted_repair_finishes_on_its_next_run_and_records_one_incident(
    ledger, folders, clock, command, monkeypatch,
):
    copy = healthy_copy(ledger)
    damage(folders[0])
    assert ledger.check()["status"] == "unavailable"
    rename = os.rename
    failed = []

    def interrupted(source, target, *args, **kwargs):
        if os.path.basename(source) == DAMAGE_MARKER and not failed:
            failed.append(source)
            raise OSError("interrupted")
        return rename(source, target, *args, **kwargs)

    monkeypatch.setattr(ledger_cli.os, "rename", interrupted)
    with pytest.raises(OSError):
        repair(command, copy)
    assert (folders[0] / DAMAGE_MARKER).exists()
    first = ledger_incidents(folders[0], clock)
    assert len(first) == 1  # recorded before the interruption
    status, answer = repair(command, copy)  # the ledger verifies; the marker finishes it
    assert status == 0 and answer["incidentId"] == first[0]["incidentId"]
    assert not (folders[0] / DAMAGE_MARKER).exists()
    assert ledger_incidents(folders[0], clock) == first
    status, again = repair(command, copy)
    assert (status, again["reason"]) == (1, "ledger-not-damaged")


def test_a_repair_with_no_known_environment_is_refused_before_anything_changes(
    ledger, folders, clock,
):
    copy = healthy_copy(ledger)
    damaged = damage(folders[0])
    unknown = LedgerCommand(folder=folders[0], evidence=folders[1],
                            receipts=UnboundReceiptReader(), clock=clock)
    status, answer = repair(unknown, copy)
    assert (status, answer["reason"]) == (1, "environment-unknown")
    assert (folders[0] / LedgerStore.LOG).read_bytes() == damaged
    assert not (folders[0] / DAMAGE_MARKER).exists()  # no finding written by the refusal
