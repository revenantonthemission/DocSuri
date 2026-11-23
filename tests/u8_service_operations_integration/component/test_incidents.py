"""Service incidents and the tolerance watcher (U8 plan Step 16; BR3.7, O3, NFR9.3).

Incidents live in a real ledger in a private temporary folder. The watcher reads a
fixed set of derived states (the readiness module's own `CapabilityState`), and time
moves only through the injected clock.
"""

from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest

from backend.modules.operations.errors import OperationsError
from backend.modules.operations.incidents import CUTOVER, Incidents, ToleranceWatcher
from backend.modules.operations.ledger import Ledger, utc_text
from backend.modules.operations.readiness import CapabilityState
from backend.u8_policy import SYNTHETIC_OPERATIONS
from backend.u8_registry import CAPABILITIES, REQUIRED

POLICY = SYNTHETIC_OPERATIONS


class States:
    """The readiness module's answer, set by the test."""

    def __init__(self):
        self.current = {cap.capability_id: CapabilityState(cap.capability_id, "available",
                                                            None) for cap in CAPABILITIES}

    def set(self, capability: str, state: str, reason: str | None = None, *, errors: int = 0):
        self.current[capability] = CapabilityState(capability, state, reason,
                                                   error_count=errors, total_count=errors)

    def states(self):
        return dict(self.current)


@pytest.fixture
def ledger(tmp_path, clock):
    folder = tmp_path / "ledger"
    folder.mkdir(mode=0o700)
    value = Ledger.open(folder, clock=clock)
    yield value
    value.close()


@pytest.fixture
def setup(ledger, clock):
    incidents = Incidents(ledger, environment="live")
    states = States()
    return incidents, states, ToleranceWatcher(incidents, states, POLICY, clock)


def open_incidents(ledger) -> list[dict]:
    return [record for record in ledger.records("service-incident")
            if record["state"] != "resolved"]


# --- 1. Required capabilities ------------------------------------------------------------


def test_an_incident_opens_at_once_when_required_is_unavailable(setup, ledger):
    incidents, states, watcher = setup
    states.set("export", "unavailable", "store-unavailable")
    opened = watcher.run_once()
    assert len(opened) == 1
    record = incidents.get(opened[0])
    assert (record["capabilities"], record["openedBy"], record["state"]) == (
        ["export"], "tolerance-exceeded", "open")
    assert watcher.run_once() == []  # one signal per streak


@pytest.mark.parametrize("state", ["degraded", "unknown", "stale"])
def test_after_the_tolerance_a_degraded_unknown_or_stale_required_capability_opens_one(
    setup, clock, state,
):
    incidents, states, watcher = setup
    states.set("library.saved-work", state, "observation-stale")
    assert watcher.run_once() == []
    clock.advance(POLICY.required_incident_seconds - 1)
    assert watcher.run_once() == []
    clock.advance(1)
    opened = watcher.run_once()
    assert len(opened) == 1 and incidents.get(opened[0])["capabilities"] == [
        "library.saved-work"]


def test_a_recovery_before_the_tolerance_resets_the_streak(setup, clock):
    _, states, watcher = setup
    states.set("usage.wallet", "degraded", "producer-failed")
    watcher.run_once()
    clock.advance(POLICY.required_incident_seconds - 1)
    states.set("usage.wallet", "available")
    watcher.run_once()
    states.set("usage.wallet", "degraded", "producer-failed")
    clock.advance(2)
    assert watcher.run_once() == []


def test_a_provider_outage_opens_no_incident(setup, clock):
    _, states, watcher = setup
    for capability in ("provider.models", "provider.resend", "platform.status",
                       "assistance.summary"):
        states.set(capability, "unavailable", "runtime-unreachable")
    watcher.run_once()
    clock.advance(10_000)
    assert watcher.run_once() == []


# --- 2. One incident per capability ---------------------------------------------------------


def test_one_open_incident_per_capability_with_signals_attached(setup, ledger):
    incidents, _, _ = setup
    first = incidents.signal("export", "tolerance-exceeded", correlation="job:a")
    again = incidents.signal("export", "job-failure-correlated", correlation="job:b")
    same = incidents.signal("export", "operator", correlation="job:b")
    assert first["incidentId"] == again["incidentId"] == same["incidentId"]
    assert again["correlationIds"] == ["job:a", "job:b"] and again["revision"] == 2
    assert ledger.revision("service-incident", first["incidentId"]) == 2
    other = incidents.signal("export", "operator", environment="rehearsal")
    assert other["incidentId"] != first["incidentId"]
    assert len(open_incidents(ledger)) == 2
    assert incidents.open_for("export")["incidentId"] == first["incidentId"]


# --- 3. The isolation check ---------------------------------------------------------------


@pytest.mark.parametrize("state", ["unavailable", "unknown", "stale"])
def test_an_isolation_lapse_or_unknown_check_opens_an_incident_after_15_minutes(
    setup, clock, state,
):
    incidents, states, watcher = setup
    states.set("platform.isolation", state, "runtime-isolation-lapsed")
    watcher.run_once()
    clock.advance(POLICY.isolation_incident_seconds - 1)
    assert watcher.run_once() == []
    clock.advance(1)
    opened = watcher.run_once()
    assert incidents.get(opened[0])["capabilities"] == ["platform.isolation"]
    assert POLICY.isolation_incident_seconds == 15  # 15 minutes in production


def test_the_cutover_check_opens_one_only_when_unavailable_past_its_tolerance(setup, clock):
    incidents, states, watcher = setup
    states.set(CUTOVER, "unknown", "evidence-unavailable")
    watcher.run_once()
    clock.advance(10_000)
    assert watcher.run_once() == []
    states.set(CUTOVER, "unavailable", "cutover-route-differs")
    watcher.run_once()
    clock.advance(POLICY.cutover_incident_seconds)
    assert len(watcher.run_once()) == 1


# --- 4. Correlated job failures ------------------------------------------------------------


def test_correlated_job_failures_open_one(setup):
    incidents, states, watcher = setup
    states.set("research", "degraded", "model-runtime-waiting", errors=3)
    opened = watcher.run_once()
    assert incidents.get(opened[0])["openedBy"] == "job-failure-correlated"


def test_failed_jobs_on_background_work_open_its_incident_at_once(setup):
    """Step 59(i) (L1-41, L1-70)."""
    incidents, states, watcher = setup
    states.set("background.work", "available", errors=1)
    assert watcher.run_once() == []
    states.set("background.work", "degraded", "lane-behind-deadline", errors=1)
    opened = watcher.run_once()
    assert len(opened) == 1
    record = incidents.get(opened[0])
    assert (record["capabilities"], record["openedBy"]) == (
        ["background.work"], "job-failure-correlated")


def test_storage_capacity_counts_open_no_incident_at_once(setup, clock):
    """Step 59(i) (L1-29): failed connections and transactions are not job failures."""
    incidents, states, watcher = setup
    states.set("storage.capacity", "degraded", "capacity-approaching", errors=1)
    assert watcher.run_once() == []
    clock.advance(POLICY.required_incident_seconds - 1)
    assert watcher.run_once() == []
    clock.advance(1)
    opened = watcher.run_once()
    assert len(opened) == 1
    assert incidents.get(opened[0])["openedBy"] == "tolerance-exceeded"


def test_the_watcher_runs_every_60_seconds(setup, monkeypatch):
    """Step 59(i): `run(stopping)` with no seconds argument waits the literal 60."""
    import asyncio

    _, _, watcher = setup
    stopping = asyncio.Event()
    events: list = []
    waits: list = []

    def run_once():
        events.append("run")
        if len(events) == 3:  # the second run raises; the loop goes on
            raise RuntimeError("a watcher pass failed")
        return []

    async def recorded_wait(awaitable, timeout):
        awaitable.close()
        waits.append(timeout)
        events.append("wait")
        if len(waits) == 3:
            stopping.set()
        raise TimeoutError

    logged: list = []

    class Log:
        def exception(self, component, event, error, **fields):
            logged.append((component, event, type(error).__name__))

    watcher.log = Log()
    monkeypatch.setattr(watcher, "run_once", run_once)
    monkeypatch.setattr(asyncio, "wait_for", recorded_wait)
    asyncio.run(watcher.run(stopping))
    assert events[:2] == ["run", "wait"]  # run_once runs before the first wait
    assert events == ["run", "wait", "run", "wait", "run", "wait"]
    assert waits == [60, 60, 60] and all(type(item) is int for item in waits)
    assert logged == [("operations", "watcher.failed", "RuntimeError")]


def test_the_workers_entry_passes_no_watch_seconds():
    """Step 59(i): `run_background` calls `run_workers(composition, stopping)` alone."""
    import ast
    from pathlib import Path

    import backend.u8_main as entry

    tree = ast.parse(Path(entry.__file__).read_text())
    [function] = [node for node in ast.walk(tree)
                  if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef)
                  and node.name == "run_background"]
    calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)
             and getattr(node.func, "id", None) == "run_workers"]
    assert len(calls) == 1
    [call] = calls
    assert [arg.id for arg in call.args] == ["composition", "stopping"]
    assert call.keywords == []


# --- 5. Resolution needs the evidence of its kind --------------------------------------------


def cutover_with(ledger, **fields) -> dict:
    record = {
        "cutoverId": str(uuid4()), "releaseTag": "v2.0.0", "state": "preparing",
        "soakPeriodSeconds": 604800, "soakClean": False, "switchTimeBoundSeconds": 14400,
        "rollbackWindowSeconds": 1209600, "effectReceipts": [], "approvals": [], **fields,
    }
    ledger.append("cutover-record", record, expect_revision=0)
    return record


def record_review(ledger, cutover: dict) -> None:
    receipt = str(uuid4())
    ledger.append("maintainer-approval", {
        "approvalId": str(uuid4()), "step": "abort-review", "subjectRef": cutover["cutoverId"],
        "subjectDigest": hashlib.sha256(b"abort").hexdigest(), "decision": "approved",
        "recordedAt": utc_text(ledger.clock()), "operatorReceiptRef": receipt,
    }, expect_revision=0, receipts=[{
        "receiptId": receipt, "operationId": str(uuid4()), "operation":
        "platform.decision.record", "targetId": "decision", "inputHash": "c" * 64,
        "outcome": "succeeded", "confirmedAt": utc_text(ledger.clock()),
    }])


def test_each_resolution_kind_needs_its_own_evidence(setup, ledger):
    incidents, _, _ = setup
    available = {"export": CapabilityState("export", "available", None)}
    degraded = {"export": CapabilityState("export", "degraded", "export-effect-late")}
    ordinary = incidents.signal("export", "tolerance-exceeded")
    with pytest.raises(OperationsError) as empty:
        incidents.resolve(ordinary["incidentId"], "capability-available", [], states=available)
    assert empty.value.code == "EVIDENCE_REQUIRED"
    with pytest.raises(OperationsError):
        incidents.resolve(ordinary["incidentId"], "capability-available", ["obs:1"],
                          states=degraded)
    for kind in ("abort-reviewed", "rollback-copy-settled"):
        with pytest.raises(OperationsError):
            incidents.resolve(ordinary["incidentId"], kind, ["receipt:1"])
    # A linked recovery must have succeeded first.
    incidents.begin_diagnosis(ordinary["incidentId"], "store-unavailable")
    request = str(uuid4())
    incidents.link_recovery(ordinary["incidentId"], request)
    with pytest.raises(OperationsError):
        incidents.resolve(ordinary["incidentId"], "capability-available", ["obs:1"],
                          states=available)
    incidents.recovery_failed(ordinary["incidentId"])
    assert incidents.get(ordinary["incidentId"])["state"] == "investigating"
    other = incidents.signal("library.saved-work", "tolerance-exceeded")
    resolved = incidents.resolve(other["incidentId"], "capability-available", ["obs:2"],
                                 states={"library.saved-work": CapabilityState(
                                     "library.saved-work", "available", None)})
    assert (resolved["state"], resolved["resolutionKind"]) == ("resolved",
                                                              "capability-available")
    stopped = incidents.resolve(ordinary["incidentId"], "environment-stopped",
                                ["receipt:stop"])
    assert stopped["resolutionKind"] == "environment-stopped"
    with pytest.raises(OperationsError):
        incidents.resolve(ordinary["incidentId"], "environment-stopped", ["receipt:stop"])
    rehearsal = incidents.signal("export", "operator", environment="rehearsal")
    with pytest.raises(OperationsError):
        incidents.resolve(rehearsal["incidentId"], "environment-stopped", ["receipt:stop"])
    # Step 59(i): a kind outside the registered four is refused as an invalid argument.
    with pytest.raises(OperationsError) as unknown:
        incidents.resolve(rehearsal["incidentId"], "manual", ["x"])
    assert unknown.value.code == "INVALID_ARGUMENT"


def test_an_aborts_incident_cannot_resolve_without_your_recorded_review(setup, ledger):
    incidents, _, _ = setup
    already = incidents.signal(CUTOVER, "tolerance-exceeded", correlation="route")
    taken = incidents.take_over_cutover("switch-aborted", correlation="abort")
    assert taken["incidentId"] == already["incidentId"]  # the open one is taken over
    assert taken["correlationIds"] == ["route", "abort"]
    cutover = cutover_with(ledger, abortIncidentId=taken["incidentId"])
    assert incidents.role(taken["incidentId"]) == "abort"
    with pytest.raises(OperationsError):
        incidents.resolve(taken["incidentId"], "abort-reviewed", ["receipt:recreate"])
    with pytest.raises(OperationsError):
        incidents.resolve(taken["incidentId"], "capability-available", ["obs:1"],
                          states={CUTOVER: CapabilityState(CUTOVER, "available", None)})
    with pytest.raises(OperationsError):
        incidents.resolve(taken["incidentId"], "environment-stopped", ["receipt:stop"])
    record_review(ledger, cutover)
    resolved = incidents.resolve(taken["incidentId"], "abort-reviewed", ["receipt:recreate"])
    assert resolved["resolutionKind"] == "abort-reviewed"
    # A rollback's copy-pending incident resolves only as rollback-copy-settled.
    pending = incidents.take_over_cutover("rollback-copy-pending")
    assert pending["openedBy"] == "rollback-copy-pending"
    cutover_with(ledger, rollbackCopyIncidentId=pending["incidentId"])
    with pytest.raises(OperationsError):
        incidents.resolve(pending["incidentId"], "environment-stopped", ["receipt:stop"])
    settled = incidents.resolve(pending["incidentId"], "rollback-copy-settled",
                                ["receipt:copy", "receipt:recreate"])
    assert settled["resolutionKind"] == "rollback-copy-settled"
    with pytest.raises(ValueError):
        incidents.take_over_cutover("operator")


# --- 6. A production restore never erases it -----------------------------------------------


def test_a_production_restore_never_erases_its_incident(tmp_path, clock):
    """The incident lives in the ledger, not the database; the restore itself is Step
    89(c)'s."""
    folder = tmp_path / "ledger"
    folder.mkdir(mode=0o700)
    ledger = Ledger.open(folder, clock=clock)
    record = Incidents(ledger, environment="live").signal("storage.capacity",
                                                          "tolerance-exceeded")
    ledger.close()
    reopened = Ledger.open(folder, clock=clock)
    try:
        kept = Incidents(reopened, environment="live").get(record["incidentId"])
        assert kept == record and kept["state"] == "open"
        assert set(REQUIRED) >= {"storage.capacity"}
    finally:
        reopened.close()
