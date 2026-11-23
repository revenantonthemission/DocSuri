"""Recording your decision (U8 plan Step 28; Workflow 18, BR9.14, NFR1.4, A5).

A decision binds the exact digest of what was shown through `platform.decision.record`'s
receipt in the composed realm's store, then the MaintainerApproval goes in through the
ledger component's `append` word, which confirms that receipt with the service
account's reader. A subject that changed since it was shown is refused and shown anew;
an unknown outcome is reconciled before anything relies on it; and the web application
has no route that records one.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import threading
from pathlib import Path

import pytest

from backend.modules.operations.ledger import Ledger, LedgerStore
from backend.modules.operations.ledger_cli import LedgerCommand, in_person_authorities, run
from docsuri_ops.platform_control.executor import EffectOutcome
from docsuri_ops.u8_platform.decisions import (
    Decisions,
    DecisionUnsettled,
    SubjectChanged,
    render,
)
from docsuri_ops.u8_platform.drivers import input_hash
from docsuri_ops.u8_platform.u8_protocols import readers_for
from tests.u8_service_operations_integration import platform_flows as pf

ROOT = Path(__file__).resolve().parents[3]
SUBJECT = {"restore": "r-1", "set": "live/2026-10-22.dump", "loss": "none"}


@pytest.fixture
def ledger_folder(tmp_path) -> Path:
    folder = tmp_path / "ledger"
    folder.mkdir(mode=0o700)
    (tmp_path / "evidence").mkdir(mode=0o700)
    return folder


@pytest.fixture
def append(ledger_folder, realm, clock):
    """The ledger component's `append` word in process, confirming with the realm's
    service-account reader."""
    command = LedgerCommand(folder=ledger_folder, evidence=ledger_folder.parent / "evidence",
                            receipts=readers_for(realm)[0], clock=clock, environment="live",
                            decision_authorities=in_person_authorities(
                                Path(realm.root) / "platform-authorities.json"))

    def call(document: dict) -> dict:
        stdout = io.BytesIO()
        run(["append"], command, environ={}, stdin=io.BytesIO(json.dumps(document).encode()),
            stdout=stdout, stderr=io.BytesIO())
        return json.loads(stdout.getvalue().decode().splitlines()[-1])

    return call


def approvals(folder: Path, clock) -> list[dict]:
    ledger = Ledger.open(folder, clock=clock)
    try:
        return ledger.records("maintainer-approval"), ledger.records("receipt-facts")
    finally:
        ledger.close()


def test_a_decision_binds_the_exact_digest_shown(tmp_path, realm, append, ledger_folder,
                                                 clock):
    journey = pf.journey(tmp_path, realm)
    decisions = Decisions(journey.operator(), append, clock=clock)
    shown = decisions.show("production-restore", "restore:r-1", SUBJECT)
    assert shown.shown == render(SUBJECT)
    assert shown.digest == hashlib.sha256(render(SUBJECT)).hexdigest()
    result = decisions.record(shown, "approved", current=lambda: dict(SUBJECT))
    receipt = result["receipt"]
    assert receipt["operation"] == "platform.decision.record"
    assert receipt["inputHash"] == input_hash({
        "step": "production-restore", "subjectRef": "restore:r-1",
        "subjectDigest": shown.digest, "decision": "approved"})
    recorded, facts = approvals(ledger_folder, clock)
    assert [(item["approvalId"], item["subjectDigest"], item["operatorReceiptRef"])
            for item in recorded] == [(result["approvalId"], shown.digest, receipt["receiptId"])]
    assert [item["operation"] for item in facts] == ["platform.decision.record"]
    assert journey.read_state("decisions", f"{receipt['operationId']}.json")[
        "subjectDigest"] == shown.digest
    with pytest.raises(ValueError):
        decisions.show("not-a-step", "x", SUBJECT)


def test_a_changed_subject_is_refused_and_shown_anew(tmp_path, realm, append, ledger_folder,
                                                     clock):
    journey = pf.journey(tmp_path, realm)
    decisions = Decisions(journey.operator(), append, clock=clock)
    shown = decisions.show("production-restore", "restore:r-1", SUBJECT)
    changed = {**SUBJECT, "loss": "four hours"}
    with pytest.raises(SubjectChanged) as caught:
        decisions.record(shown, "approved", current=lambda: changed)
    assert caught.value.shown == render(changed)
    # Nothing was bound and nothing appended.
    assert not (journey.state / "decisions").exists()
    assert not (ledger_folder / LedgerStore.LOG).exists()


def lost(**request) -> EffectOutcome:
    from docsuri_ops.platform_control.executor import run_effect

    applied = run_effect(**request)
    assert applied.status == "applied", applied
    return EffectOutcome("unknown", [], {"kind": "internal", "message": "deadline"})


def never(**request) -> EffectOutcome:
    return EffectOutcome("unknown", [], {"kind": "internal", "message": "deadline"})


def test_an_unknown_outcome_is_reconciled_before_the_approval_is_appended(
    tmp_path, realm, append, ledger_folder, clock,
):
    journey = pf.journey(tmp_path, realm)
    decisions = Decisions(journey.operator(run_effect=lost), append, clock=clock)
    shown = decisions.show("restore-abandonment", "restore:r-1", SUBJECT)
    result = decisions.record(shown, "approved", current=lambda: SUBJECT)
    assert result["receipt"]["reconciliationState"] == "reconciled-applied"
    assert [item["approvalId"] for item in approvals(ledger_folder, clock)[0]] == [
        result["approvalId"]]
    # An outcome that stays unknown appends nothing.
    unsettled = Decisions(journey.operator(run_effect=never), append, clock=clock)
    shown = unsettled.show("restore-abandonment", "restore:r-2", SUBJECT)
    with pytest.raises(DecisionUnsettled):
        unsettled.record(shown, "approved", current=lambda: SUBJECT)
    assert len(approvals(ledger_folder, clock)[0]) == 1


def test_the_in_person_actor_is_the_account_sudo_authenticated(realm):
    from docsuri_ops.platform_control.errors import ControlError
    from docsuri_ops.u8_platform.in_person import actor_from_sudo, realm_actor

    class Account:
        pw_name = "maintainer"

    def lookup(uid: int):
        if uid != 501:
            raise KeyError(uid)
        return Account()

    assert actor_from_sudo({"SUDO_UID": "501", "USER": "someone"}, lookup=lookup) == (
        "maintainer")
    for environ in ({}, {"SUDO_UID": "root"}, {"SUDO_UID": "502"}):
        with pytest.raises(ControlError):
            actor_from_sudo(environ, lookup=lookup)
    with pytest.raises(ControlError):
        actor_from_sudo({"SUDO_UID": "501"}, lookup=lambda uid: object())
    assert realm_actor(realm.root).startswith("realm-operator:")


def test_a_bound_step_shows_its_time_and_is_never_cut_off():
    from docsuri_ops.u8_platform.in_person import StepClock

    shown: list[str] = []
    ticks = iter([0.0, 130.0])
    clock = StepClock(shown.append, monotonic=lambda: next(ticks), refresh_seconds=3600)
    result, record = clock.run("restore", 120, lambda: "finished")
    # The step ran to its own end past its bound, and the overrun is recorded.
    assert result == "finished" and record.over_bound is True
    assert record.as_dict() == {"step": "restore", "boundSeconds": 120,
                                "elapsedSeconds": 130.0, "overBound": True}
    assert shown == ["restore: 130 s of 120 s (over its bound)"]
    watched: list[str] = []
    progress = threading.Event()

    def show(line: str) -> None:
        watched.append(line)
        progress.set()

    def until_progress_shown() -> int:
        # The step's work ends once the watcher has shown a progress line (at most 5 s),
        # never after a fixed time.
        assert progress.wait(5), "the watcher never showed a progress line"
        return 7

    live = StepClock(show, refresh_seconds=0.01)
    result, record = live.run("snapshot", 60, until_progress_shown)
    assert result == 7 and record.over_bound is False
    assert len(watched) >= 2 and watched[-1].endswith("(within its bound)")
    with pytest.raises(ValueError):
        live.run("x", 0, lambda: None)


def test_the_web_application_has_no_route_that_records_a_decision():
    from backend.u8_host import route_classes

    classes = route_classes()
    for path in ("/api/v2/decisions", "/api/v2/c10/record-decision", "/decisions/record",
                 "/api/v2/maintainer-approvals"):
        assert classes.classify("POST", path) is None
        assert classes.classify("PUT", path) is None
    assert not any("decision" in path for _, path, _, _ in classes._entries)
    # No backend module reaches the decision recorder or the operator.
    offenders = [str(source.relative_to(ROOT)) for source in (ROOT / "backend").rglob("*.py")
                 if ".venv" not in source.parts
                 and _reaches_the_recorder(source.read_text(encoding="utf-8"))]
    assert offenders == []


RECORDER_MODULES = ("u8_platform.decisions", "u8_platform.in_person",
                    "u8_platform.credential_release")


def _reaches_the_recorder(text: str) -> bool:
    for node in ast.walk(ast.parse(text)):
        names = ([node.module or ""] if isinstance(node, ast.ImportFrom)
                 else [alias.name for alias in node.names] if isinstance(node, ast.Import)
                 else [])
        if any(name.endswith(RECORDER_MODULES) for name in names):
            return True
    return False


def test_the_recorder_scan_finds_a_planted_import():
    """The scan above names U8's modules where they now live, so it cannot pass vacuously
    (U8 plan Step 44, the move out of U7)."""
    for planted in ("from docsuri_ops.u8_platform.decisions import Decisions\n",
                    "import docsuri_ops.u8_platform.in_person\n",
                    "def f():\n"
                    "    from docsuri_ops.u8_platform.credential_release import release\n"):
        assert _reaches_the_recorder(planted)
    assert not _reaches_the_recorder("from docsuri_ops.platform_control import evidence\n")
