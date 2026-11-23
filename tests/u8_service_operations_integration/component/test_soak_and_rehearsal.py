"""The soak's clean rule and v1's restart rehearsal (U8 plan Step 34; BR9.3, BR9.16).

The soak's verdict reads ledger evidence only: incidents, scheduled rehearsal sets and
restore verifications over the soak period. v1's restart rehearsal runs through the
operator tool's bound steps on the composed realm's PlatformControl store and realm
driver (the journey's own platform state), with v1's fixed checkout a git repository of
the test's own, so a change to it is seen to void the rehearsal.
"""

from __future__ import annotations

import datetime as dt
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from backend.modules.operations.cutover import rehearsal_current, soak_verdict
from backend.modules.operations.incidents import Incidents
from backend.u8_policy import SYNTHETIC_OPERATIONS
from docsuri_ops.cutover.preconditions import SwitchEvidence
from docsuri_ops.cutover.tool import (
    CutoverPlatform,
    CutoverTool,
    V1Checkout,
    rehearsal_fingerprint_reader,
)
from docsuri_ops.migration.isolation_gate import IsolationGate
from tests.u8_service_operations_integration import cutover_flows as cf
from tests.u8_service_operations_integration import platform_flows as pf
from tests.u8_service_operations_integration import recovery_flows as rf

DAY = 86400


@pytest.fixture
def ledger(tmp_path, clock):
    value = rf.open_ledger(tmp_path, clock)
    yield value
    value.close()


def started(record: dict) -> dt.datetime:
    return dt.datetime.fromisoformat(record["soakStartedAt"].replace("Z", "+00:00"))


def evidence_for(ledger, record, *, days: int = 7, verify: bool = True):
    sets = cf.scheduled_sets(ledger, started(record), days)
    if verify:
        cf.verified_restore(ledger, sets[0], now=started(record) + dt.timedelta(hours=2))
    return sets


def test_a_soak_with_every_piece_of_evidence_is_clean(ledger, clock):
    cutover, record = cf.rehearsing(ledger, clock)
    evidence_for(ledger, record)
    assert soak_verdict(ledger, record, clock()) == (False, ["soak-period-running"])
    clock.advance(7 * DAY + 1)
    assert soak_verdict(ledger, record, clock()) == (True, [])
    evaluated, reasons = cutover.evaluate_soak()
    assert evaluated["soakClean"] is True and reasons == []


@pytest.mark.parametrize("gap", ["day-missing", "set-failed", "no-verification"])
def test_missing_backup_or_verification_evidence_keeps_it_unclean(ledger, clock, gap):
    cutover, record = cf.rehearsing(ledger, clock)
    evidence_for(ledger, record, days=6 if gap == "day-missing" else 7,
                 verify=gap != "no-verification")
    if gap == "set-failed":
        cf.scheduled_sets(ledger, started(record) + dt.timedelta(hours=3), 1, integrity="failed")
    clock.advance(7 * DAY + 1)
    clean, reasons = soak_verdict(ledger, record, clock())
    expected = {"day-missing": "scheduled-backups-missing", "set-failed":
                "scheduled-backup-failed", "no-verification": "restore-verification-missing"}
    assert not clean and reasons == [expected[gap]]


def test_an_incident_not_resolved_with_verification_or_open_at_the_end_counts(ledger, clock):
    cutover, record = cf.rehearsing(ledger, clock)
    evidence_for(ledger, record)
    incidents = Incidents(ledger, environment="rehearsal")
    clock.advance(DAY)
    opened = incidents.signal("platform.isolation", "tolerance-exceeded")
    ledger.append("service-incident", {**opened, "revision": 2, "state": "resolved",
                                       "resolutionKind": "environment-stopped",
                                       "resolvedAt": rf.utc_text(clock())}, expect_revision=1)
    still = incidents.signal("library.saved-work", "tolerance-exceeded")
    clock.advance(6 * DAY + 1)
    clean, reasons = soak_verdict(ledger, record, clock())
    assert not clean
    assert reasons == ["incident-not-resolved-with-verification", "incident-open"]
    # Resolved with verification, the open one no longer counts.
    ledger.append("service-incident", {**still, "revision": 2, "state": "resolved",
                                       "resolutionKind": "capability-available",
                                       "resolvedAt": rf.utc_text(clock())}, expect_revision=1)
    assert soak_verdict(ledger, record, clock())[1] == [
        "incident-not-resolved-with-verification"]


def test_a_new_release_tag_resets_the_clean_period(ledger, clock):
    cutover, record = cf.rehearsing(ledger, clock)
    evidence_for(ledger, record)
    clock.advance(7 * DAY + 1)
    assert cutover.evaluate_soak()[0]["soakClean"] is True
    reset = cutover.new_release("v2.0.1")
    assert reset["soakClean"] is False
    assert soak_verdict(ledger, reset, clock()) == (False, ["soak-not-started"])
    cutover.verification_passed(uuid4(), "v2.0.1")
    again = cutover.restart_soak()
    # The evidence from the old period does not carry over to the new one.
    clean, reasons = soak_verdict(ledger, again, clock())
    assert not clean and "soak-period-running" in reasons
    assert "scheduled-backups-missing" in reasons


# --- v1's restart rehearsal --------------------------------------------------------------


def git(path: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(path), *args], capture_output=True,
                               check=True, timeout=30)
    return completed.stdout.decode().strip()


@pytest.fixture
def checkout(tmp_path) -> Path:
    path = tmp_path / "v1-checkout"
    path.mkdir()
    git(path, "init", "-q")
    git(path, "config", "user.email", "fixture@example.invalid")
    git(path, "config", "user.name", "fixture")
    (path / "app.py").write_text("print('v1')\n")
    git(path, "add", "app.py")
    git(path, "commit", "-q", "-m", "v1 fixed checkout")
    return path


class Probes:
    def __init__(self):
        self.v1, self.public_answers, self.calls = True, True, []

    def v1_ready(self) -> bool:
        self.calls.append("v1-ready")
        return self.v1

    def public(self, kind: str) -> bool:
        self.calls.append(f"public:{kind}")
        return self.public_answers


def tool_on(tmp_path, realm, ledger, clock, checkout_path: Path, probes: Probes):
    journey = pf.journey(tmp_path, realm)
    operator = journey.operator(ledger=ledger, clock=clock)
    folder = tmp_path / "cutover-evidence"
    evidence = SwitchEvidence(
        verification=lambda run: None, v1_checkout=V1Checkout(checkout_path, ()),
        rehearsal_fingerprint=rehearsal_fingerprint_reader(folder),
        agent_status=lambda: {"available": True, "freeBytes": 0},
        service_volume=lambda: "stand-in",
        isolation=IsolationGate(tmp_path / "isolation", freshness_seconds=900, clock=clock),
        rehearsal_database=lambda: None)
    labels = journey.profile.labels
    platform = CutoverPlatform(
        operator=operator, production="docsuri_u8",
        v1_labels=tuple(item for item in labels if ".v1-" in item),
        v2_labels=tuple(item for item in labels if item.endswith((".host", ".workers",
                                                                  ".scheduler"))),
        v2_ready=lambda: True, v1_ready=probes.v1_ready, public=probes.public,
        evidence=evidence, evidence_folder=folder)
    return CutoverTool(ledger, SYNTHETIC_OPERATIONS, platform, clock=clock), journey


def test_the_restart_rehearsal_runs_every_step_and_records_v1s_commit(tmp_path, realm, ledger,
                                                                        clock, checkout):
    probes = Probes()
    tool, journey = tool_on(tmp_path, realm, ledger, clock, checkout, probes)
    cutover, record = cf.rehearsing(ledger, clock)
    approval = cf.decision(ledger, "v1-restart-rehearsal", record["cutoverId"], now=clock())
    result = tool.rehearse_restart(approval)
    assert result["rehearsed"] is True, result
    rehearsed = cutover.current()
    assert rehearsed["v1CheckoutCommit"] == git(checkout, "rev-parse", "HEAD")
    # Maintenance, each v1 service stopped then started, the route back: six receipts.
    assert len(rehearsed["effectReceipts"]) == 2 + 2 * len(tool.platform.v1_labels)
    assert journey.tunnel()["origin"] == "v1-web"
    assert all(journey.read_state("services", f"{label}.json")["state"] == "running"
               for label in tool.platform.v1_labels)
    assert probes.calls[-2:] == ["public:v1-health", "public:v1-signed-out"]
    fingerprint = tool.platform.evidence.v1_checkout()["fingerprint"]
    assert tool.platform.evidence.rehearsal_fingerprint(record["cutoverId"]) == fingerprint
    assert rehearsal_current(rehearsed, clock(), window_seconds=7 * DAY,
                             commit=rehearsed["v1CheckoutCommit"],
                             fingerprint_matches=True) is None


def test_a_change_to_v1s_checkout_voids_the_rehearsal(tmp_path, realm, ledger, clock, checkout):
    tool, _ = tool_on(tmp_path, realm, ledger, clock, checkout, Probes())
    cutover, record = cf.rehearsing(ledger, clock)
    tool.rehearse_restart(cf.decision(ledger, "v1-restart-rehearsal", record["cutoverId"],
                                      now=clock()))
    assert "restart-rehearsal-void" not in tool.missing()
    (checkout / "app.py").write_text("print('changed')\n")  # an uncommitted change
    assert "restart-rehearsal-void" in tool.missing()
    git(checkout, "commit", "-q", "-am", "a later change")  # a new commit
    assert "restart-rehearsal-void" in tool.missing()


def test_a_rehearsal_expires_after_its_window_and_a_failed_one_records_nothing(
    tmp_path, realm, ledger, clock, checkout
):
    probes = Probes()
    tool, _ = tool_on(tmp_path, realm, ledger, clock, checkout, probes)
    cutover, record = cf.rehearsing(ledger, clock)
    assert "restart-rehearsal-missing" in tool.missing()
    probes.public_answers = False
    failed = tool.rehearse_restart(cf.decision(ledger, "v1-restart-rehearsal",
                                               record["cutoverId"], now=clock()))
    assert failed == {"state": "rehearsing", "rehearsed": False,
                      "reason": "v1-not-answering-publicly"}
    assert "v1RestartRehearsedAt" not in cutover.current()
    probes.public_answers = True
    tool.rehearse_restart(cf.decision(ledger, "v1-restart-rehearsal", record["cutoverId"],
                                      now=clock()))
    clock.advance(7 * DAY + 1)
    assert "restart-rehearsal-expired" in tool.missing()


class ReplaySpy:
    """The operator, with each effect's `replayed` flag kept in order."""

    def __init__(self, operator):
        self.operator, self.replayed = operator, []

    def execute(self, operation, target, inputs, *, key, **options):
        receipt = self.operator.execute(operation, target, inputs, key=key, **options)
        self.replayed.append((inputs.get("action"), bool(receipt.get("replayed"))))
        return receipt

    def __getattr__(self, name):
        return getattr(self.operator, name)


def test_the_restart_rehearsal_waits_for_v1_and_records_its_restart_seconds(
    tmp_path, realm, ledger, clock, checkout
):
    """U8 plan Step 71(j), NFR8.6, L1-59: v1's local health is waited for every 5 s for
    up to 600 s, and v1's own restart seconds are recorded from its first start."""
    import json

    from backend.modules.operations.ledger import utc_text

    probes = Probes()
    tool, _ = tool_on(tmp_path, realm, ledger, clock, checkout, probes)
    tool.platform.sleep = clock.advance  # each wait moves the clock by its argument
    spy = ReplaySpy(tool.platform.operator)
    tool.platform.operator = spy
    cutover, record = cf.rehearsing(ledger, clock)
    evidence = tmp_path / "cutover-evidence" / f"restart-rehearsal-{record['cutoverId']}.json"
    polls: list = []

    def decide() -> str:
        return cf.decision(ledger, "v1-restart-rehearsal", record["cutoverId"], now=clock())

    # Never ready: 121 polls over 600 s, then `v1-restart-failed`, and nothing recorded.
    tool.platform.v1_ready = lambda: polls.append(clock()) and False
    started = clock()
    failed = tool.rehearse_restart(decide())
    assert failed == {"state": "rehearsing", "rehearsed": False, "reason": "v1-restart-failed"}
    assert len(polls) == 121 and (clock() - started).total_seconds() == 600
    assert "v1RestartRehearsedAt" not in cutover.current()
    # Not ready to its first three polls: 15.0 s, kept in the evidence file.
    polls.clear()
    tool.platform.v1_ready = lambda: polls.append(clock()) is None and len(polls) > 3
    approval = decide()
    started = clock()
    result = tool.rehearse_restart(approval)
    assert result["rehearsed"] is True and result["v1RestartSeconds"] == 15.0, result
    kept = json.loads(evidence.read_bytes())
    assert kept["v1RestartSeconds"] == 15.0 and kept["approvalId"] == approval
    assert kept["v1RestartStartedAt"] == utc_text(started)
    # Run again with the same approval: every receipt replays, nothing starts, the file's
    # 15.0 is kept.
    spy.replayed.clear()
    again = tool.rehearse_restart(approval)
    assert again["rehearsed"] is True and again["v1RestartSeconds"] == 15.0, again
    assert spy.replayed and all(replayed for _, replayed in spy.replayed)
    assert json.loads(evidence.read_bytes())["v1RestartSeconds"] == 15.0
    # A new decision whose first call failed at the public check: the second call's
    # starts replay, so no restart was measured.
    tool.platform.v1_ready = lambda: True
    probes.public_answers = False
    fresh = decide()
    assert tool.rehearse_restart(fresh)["reason"] == "v1-not-answering-publicly"
    probes.public_answers = True
    unmeasured = tool.rehearse_restart(fresh)
    assert unmeasured["rehearsed"] is True, unmeasured
    assert unmeasured["v1RestartSeconds"] is None and unmeasured["v1RestartMeasured"] is False
    kept = json.loads(evidence.read_bytes())
    assert kept["v1RestartSeconds"] is None and kept["v1RestartMeasured"] is False
    assert kept["approvalId"] == fresh
