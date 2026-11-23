"""The live exclusion holds both ways (U8 plan Step 44, the review's fixes of 2026-10-26;
BR4.4, cicd-pipeline § 5.1 "One at a time", § 6).

- `ReleaseRecords.begin` and `begin_rollback` ask, inside their atomic step, whether a
  switch, an abort, a cutover rollback or a live production restore holds the exclusion,
  as well as another install or release rollback.
- In the other direction, no cutover word that switches, rolls back or restarts v2, and
  no `service stop|start`, runs while an install or a release rollback holds it: the
  machine's `approve_start` and `rollback` refuse inside their own step, and the tool's
  `begin`, `start`, `rollback`, the dry run's move and the soak's start of v2 answer the
  release's reason before any effect is bound.
- `service stop|start`, the soak's start and `cutover check`'s set retry also read the
  release command's run marker (`release.release_run_active`, readable without a
  password and without locking anything; the lock itself is root-only), right before
  they act and again once their receipt is bound, and refuse while a release command
  runs (the person's decision of 2026-10-26, "Check the release run lock"; review
  findings, Major, R19–R21): a ledger copy taken before the release command began
  (production's `LedgerClient`) shows nothing, and the marker does.
"""

from __future__ import annotations

import contextlib
import datetime as dt
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.modules.operations.cutover import Cutover
from backend.modules.operations.errors import OperationsError
from backend.modules.operations.release_records import ReleaseRecords, exclusion_blocker_of
from backend.u8_policy import SYNTHETIC_OPERATIONS
from docsuri_ops.arrangement.paths import ArrangementPaths
from docsuri_ops.cutover.tool import CutoverTool
from docsuri_ops.release import release_run_active, run_lock
from tests.u8_service_operations_integration import recovery_flows as rf

NOW = dt.datetime(2026, 10, 26, 9, 0, tzinfo=dt.UTC)
LABELS = tuple(f"dev.docsuri.u8.run.{name}" for name in ("host", "workers", "scheduler"))
COMMIT = "c" * 40


class View:
    """One atomic view holding exactly the records a case states; appends are kept."""

    def __init__(self, **kinds):
        self.kinds = {kind.replace("_", "-"): list(items) for kind, items in kinds.items()}
        self.appended: list = []

    def records(self, kind):
        return list(self.kinds.get(kind, []))

    def get(self, kind, key):
        return next((item for item in self.kinds.get(kind, [])
                     if item.get("releaseTag") == key), None)

    def revision(self, kind, key):
        return 0

    def append(self, kind, record, **options):
        self.appended.append((kind, record))

    def atomic(self, step):
        return step(self)


HOLDERS = [
    ({"recovery_request": [{"operation": "restore.production", "environment": "live",
                            "state": "running"}]}, "production-restore-active"),
    ({"cutover_record": [{"state": "switching"}]}, "cutover-switching"),
    ({"cutover_record": [{"state": "aborting"}]}, "cutover-aborting"),
    ({"cutover_record": [{"state": "rolling-back"}]}, "cutover-rolling-back"),
    ({"release_record": [{"releaseTag": "v2.0.1", "state": "installing"}]},
     "release-install-active"),
    ({"release_record": [{"releaseTag": "v2.0.1", "state": "rolling-back"}]},
     "release-rollback-active"),
]


@pytest.mark.parametrize(("kinds", "reason"), HOLDERS)
def test_begin_and_begin_rollback_refuse_inside_their_step(kinds, reason):
    installed = {"releaseTag": "v2.0.0", "releaseCommit": COMMIT, "state": "installed",
                 "installedAt": "2026-10-20T00:00:00Z", "updatedAt": "2026-10-20T00:00:00Z"}
    view = View(**{**kinds, "release_record": [*kinds.get("release_record", []), installed]})
    records = ReleaseRecords(view, clock=lambda: NOW)
    assert exclusion_blocker_of(view) == reason
    with pytest.raises(OperationsError) as caught:
        records.begin("v2.1.0", COMMIT, previous_tag="v2.0.0")
    assert caught.value.current["reasonKey"] == reason
    with pytest.raises(OperationsError) as caught:
        records.begin_rollback("v2.0.0")
    assert caught.value.current["reasonKey"] == reason
    assert view.appended == []


@pytest.mark.parametrize("kinds", [
    {"recovery_request": [{"operation": "restore.production", "environment": "live",
                           "state": "succeeded"}]},
    {"recovery_request": [{"operation": "restore.production", "environment": "live",
                           "state": "awaiting-operator"}]},
    {"recovery_request": [{"operation": "restore.production", "environment": "rehearsal",
                           "state": "running"}]},
    {"cutover_record": [{"state": "switching"}, {"state": "rolled-back"}]},
    {},
])
def test_begin_runs_when_nothing_holds_the_exclusion(kinds):
    view = View(**kinds)
    record = ReleaseRecords(view, clock=lambda: NOW).begin("v2.1.0", COMMIT, previous_tag=None)
    assert record["state"] == "installing" and view.appended == [("release-record", record)]


@pytest.fixture
def ledger(tmp_path):
    value = rf.open_ledger(tmp_path, lambda: NOW)
    yield value
    value.close()


def hold(ledger, kind: str) -> None:
    """An install (`installing`) or a release rollback (`rolling-back`) holding the live
    exclusion, as the release command's record holds it."""
    records = ReleaseRecords(ledger, clock=lambda: NOW)
    if kind == "rollback":
        records.begin("v2.0.0", COMMIT, previous_tag=None)
        records.finish("v2.0.0", "installed")
        records.begin_rollback("v2.0.0")
    else:
        records.begin("v2.0.1", COMMIT, previous_tag=None)


REASONS = {"install": "release-install-active", "rollback": "release-rollback-active"}


def walk(ledger, *states: str) -> dict:
    record = rf.cutover_record(ledger, "preparing")
    for state in states:
        record = rf.advance_cutover(ledger, record, state)
    return record


@pytest.mark.parametrize("kind", ["install", "rollback"])
def test_the_machine_refuses_a_switch_or_a_cutover_rollback_inside_its_step(ledger, kind):
    machine = Cutover(ledger, SYNTHETIC_OPERATIONS, clock=lambda: NOW)
    record = walk(ledger, "rehearsing", "ready-to-switch")
    approval = rf.approval_record(ledger, "switch-start", record["cutoverId"], now=NOW)
    hold(ledger, kind)
    with pytest.raises(OperationsError) as caught:
        machine.approve_start(approval["approvalId"], [])
    assert caught.value.current["reasonKey"] == REASONS[kind]
    assert machine.require()["state"] == "ready-to-switch"
    record = rf.advance_cutover(ledger, machine.require(), "switching")
    record = rf.advance_cutover(ledger, record, "switched")
    approval = rf.approval_record(ledger, "rollback", record["cutoverId"], now=NOW)
    with pytest.raises(OperationsError) as caught:
        machine.rollback(approval["approvalId"])
    assert caught.value.current["reasonKey"] == REASONS[kind]
    assert machine.require()["state"] == "switched"


class NoEffects:
    """A platform under which any bound effect fails the test."""

    v2_labels = LABELS

    def __init__(self, folder):
        self.evidence_folder = folder
        self.release_unprobed = lambda: None
        self.stopped_labels = lambda: {}
        self.release_tag = lambda: "v2.0.0"
        self.operator = SimpleNamespace(
            execute=lambda *args, **options: pytest.fail("an effect was bound"),
            facts=lambda: SimpleNamespace(current_rehearsal=None))

    def steps(self, name, bound, work):
        pytest.fail(f"a step ran: {name}")


@pytest.mark.parametrize("kind", ["install", "rollback"])
def test_no_cutover_word_switches_rolls_back_or_restarts_v2_during_a_release(
        tmp_path, ledger, kind):
    tool = CutoverTool(ledger, SYNTHETIC_OPERATIONS, NoEffects(tmp_path / "evidence"),
                       clock=lambda: NOW)
    hold(ledger, kind)
    reason = REASONS[kind]
    # `cutover begin` (it restarts v2), refused before anything is recorded.
    with pytest.raises(OperationsError) as caught:
        tool.begin()
    assert caught.value.current["reasonKey"] == reason
    assert ledger.records("cutover-record") == []
    record = walk(ledger, "rehearsing", "ready-to-switch")
    for word in (lambda: tool.start("approval", {}), lambda: tool.rollback("approval", {})):
        with pytest.raises(OperationsError) as caught:
            word()
        assert caught.value.current["reasonKey"] == reason
    # The dry run's move (it restarts v2): answered, retried by `cutover check`.
    tool._write_evidence(tool._move_evidence("run-1"), {"runId": "run-1",
                                                       "database": "rehearsal_x"})
    moved = tool._move_to_dry_run(record, "run-1")
    assert moved["reason"] == reason and moved["offered"] == ["check"]
    # The soak's start of v2 after a rollback.
    for state in ("switching", "switched", "rolling-back"):
        record = rf.advance_cutover(ledger, record, state)
    rf.advance_cutover(ledger, record, "rolled-back", acceptedDryRunId=str(uuid4()),
                       verificationRunId=str(uuid4()))
    assert tool.soak_report() == {"soak": None, "v2Start": {"reason": reason,
                                                            "offered": ["check"]}}


@pytest.mark.parametrize("kind", ["install", "rollback"])
@pytest.mark.parametrize("word", ["stop", "start"])
def test_service_control_refuses_during_a_release_before_anything_is_bound(ledger, kind,
                                                                           word):
    from docsuri_ops.platform_control.errors import ControlError
    from docsuri_ops.u8_platform.service_words import run_service

    operator = SimpleNamespace(standing=False, profile=SimpleNamespace(labels=LABELS),
                               execute=lambda *a, **o: pytest.fail("bound"))
    hold(ledger, kind)
    with pytest.raises(ControlError) as caught:
        run_service(word, LABELS[0], operator, ledger=ledger)
    assert caught.value.code == "CONFLICT"
    assert caught.value.as_wire_error()["messageKey"] == REASONS[kind]


# --- the second review's finding (Minor, R13): checked again where they act ----------------


class BeginsBetween:
    """The realm's operator, with an install (or a release rollback) beginning its record
    right after the caller's first exclusion check and before the binding: the race the
    first check alone could not see."""

    def __init__(self, operator, ledger, kind: str):
        self.operator, self.ledger, self.kind, self.bound = operator, ledger, kind, []

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key, **options):
        if not self.bound:
            hold(self.ledger, self.kind)
        self.bound.append(key)
        return self.operator.execute(operation, target, inputs, key=key, **options)


def receipt_of(operator, key: str) -> dict:
    """The receipt bound under `key`, replayed (nothing runs again)."""
    return operator.execute("platform.service.control", LABELS[0],
                            {"label": LABELS[0], "action": "start"}, key=key)


@pytest.mark.parametrize("kind", ["install", "rollback"])
def test_a_service_control_bound_after_a_release_began_runs_no_effect(tmp_path, realm, ledger,
                                                                      kind):
    """`service start`'s first check passes; the install begins before its receipt is
    bound. The check asked again under the binding refuses it: the receipt settles as not
    applied, no effect runs (the label's wanted state is never written), and the answer is
    the release's reason."""
    from docsuri_ops.platform_control.errors import ControlError
    from docsuri_ops.u8_platform.service_words import run_service
    from tests.u8_service_operations_integration import platform_flows as pf

    journey = pf.journey(tmp_path, realm)
    racing = BeginsBetween(journey.operator(ledger=ledger, clock=lambda: NOW), ledger, kind)
    with pytest.raises(ControlError) as caught:
        run_service("start", LABELS[0], racing, ledger=ledger,
                    key=f"race-{kind}-{tmp_path.name}-{pf.RUN}")
    assert caught.value.as_wire_error()["messageKey"] == REASONS[kind]
    assert journey.read_state("services", f"{LABELS[0]}.json") is None
    (key,) = racing.bound
    replayed = receipt_of(racing.operator, key)
    assert replayed["replayed"] is True and replayed["outcome"] == "failed", replayed


@pytest.mark.parametrize("kind", ["install", "rollback"])
def test_the_soaks_start_of_v2_bound_after_a_release_began_runs_no_effect(tmp_path, realm,
                                                                         ledger, kind):
    """The soak's start of v2 (`_start_superseded`) checks the release exclusion again once
    each start is bound: a release that began after `soak_report`'s check fails the step
    with its reason, and no role starts."""
    from docsuri_ops.cutover.tool import StepFailed
    from tests.u8_service_operations_integration import platform_flows as pf

    journey = pf.journey(tmp_path, realm)
    platform = NoEffects(tmp_path / "evidence")
    platform.operator = BeginsBetween(journey.operator(ledger=ledger, clock=lambda: NOW),
                                      ledger, kind)
    tool = CutoverTool(ledger, SYNTHETIC_OPERATIONS, platform, clock=lambda: NOW)
    record = walk(ledger, "rehearsing")
    with pytest.raises(StepFailed) as caught:
        tool._start_superseded(record, f"soak-start-v2:{uuid4()}")
    assert caught.value.reason == REASONS[kind]
    assert all(journey.read_state("services", f"{label}.json") is None for label in LABELS)


# --- the release command's run lock (the person's decision of 2026-10-26) --------------------

RUN_ACTIVE = "release-run-active"


@contextlib.contextmanager
def release_command_running(paths: ArrangementPaths):
    """A release command holding its run lock, as `ReleaseInstall._locked` holds it
    (`release.run_lock`): the exclusive lock on the root-only
    `control/releases/release-run.lock`, with the readable marker written beside it, for
    as long as the block runs."""
    with run_lock(paths, "install") as marker:
        yield marker


class Stale:
    """Production's ledger as the service words see it: a copy taken before the release
    command began, which shows no release record however often it is read."""

    def records(self, kind):
        return []


class LocksBetween:
    """The realm's operator, with a release command taking its run lock right after the
    caller's first check and before the binding."""

    def __init__(self, operator, paths: ArrangementPaths):
        self.operator, self.paths, self.bound = operator, paths, []
        self.held = contextlib.ExitStack()
        self.holding = False

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key, **options):
        if not self.holding:
            self.held.enter_context(run_lock(self.paths, "install"))
            self.holding = True
        self.bound.append(key)
        return self.operator.execute(operation, target, inputs, key=key, **options)

    def release(self) -> None:
        if self.holding:
            self.held.close()
            self.holding = False


@pytest.mark.parametrize("word", ["stop", "start"])
def test_service_control_refuses_while_a_release_command_holds_its_run_lock(tmp_path, realm,
                                                                           word):
    """Step 44 test item 4: `service stop|start` reads the run lock right before it acts
    and refuses while a release command holds it, with the ledger showing nothing (a
    stale copy); once the lock is released it acts."""
    from docsuri_ops.platform_control.errors import ControlError
    from docsuri_ops.u8_platform.service_words import run_service
    from tests.u8_service_operations_integration import platform_flows as pf

    paths = ArrangementPaths.under(tmp_path / "prefix")
    run_lock = lambda: release_run_active(paths)  # noqa: E731 - the reader the tool uses
    refusing = SimpleNamespace(standing=False, profile=SimpleNamespace(labels=LABELS),
                               execute=lambda *a, **o: pytest.fail("bound"))
    with release_command_running(paths):
        with pytest.raises(ControlError) as caught:
            run_service(word, LABELS[0], refusing, ledger=Stale(), run_lock=run_lock)
        assert caught.value.code == "CONFLICT"
        assert caught.value.as_wire_error()["messageKey"] == RUN_ACTIVE
        with pytest.raises(ControlError) as without:
            run_service(word, LABELS[0], refusing, ledger=None, run_lock=run_lock)
        assert without.value.as_wire_error()["messageKey"] == RUN_ACTIVE
    # Released: the control runs, through the realm's own bound operation.
    journey = pf.journey(tmp_path, realm)
    operator = journey.operator(clock=lambda: NOW)
    result = run_service(word, LABELS[0], operator, ledger=Stale(), run_lock=run_lock,
                         key=f"lock-released-{word}-{tmp_path.name}-{pf.RUN}")
    assert result["outcome"] == "succeeded" and result["action"] == word
    assert journey.read_state("services", f"{LABELS[0]}.json")["state"] == (
        "stopped" if word == "stop" else "running")


def test_a_service_control_bound_after_a_release_command_took_its_lock_runs_no_effect(
        tmp_path, realm):
    """The run lock is read again once the receipt is bound: a release command that took
    its lock after the first check, which the stale ledger copy never shows, refuses the
    control before its effect runs; the receipt settles as not applied."""
    from docsuri_ops.platform_control.errors import ControlError
    from docsuri_ops.u8_platform.service_words import run_service
    from tests.u8_service_operations_integration import platform_flows as pf

    paths = ArrangementPaths.under(tmp_path / "prefix")
    journey = pf.journey(tmp_path, realm)
    racing = LocksBetween(journey.operator(clock=lambda: NOW), paths)
    try:
        with pytest.raises(ControlError) as caught:
            run_service("start", LABELS[0], racing, ledger=Stale(),
                        run_lock=lambda: release_run_active(paths),
                        key=f"lock-race-{tmp_path.name}-{pf.RUN}")
        assert caught.value.as_wire_error()["messageKey"] == RUN_ACTIVE
        assert journey.read_state("services", f"{LABELS[0]}.json") is None
        (key,) = racing.bound
        replayed = receipt_of(racing.operator, key)
        assert replayed["replayed"] is True and replayed["outcome"] == "failed", replayed
    finally:
        racing.release()


def test_the_soaks_start_refuses_while_a_release_command_holds_its_run_lock(tmp_path, realm,
                                                                           ledger):
    """The soak's start reads the run lock right before it starts v2 (`soak_report`), and
    again under each start's binding (`_start_superseded`): held, nothing starts and the
    answer is the release's reason; released, the starts are bound and run."""
    from docsuri_ops.cutover.tool import StepFailed
    from tests.u8_service_operations_integration import platform_flows as pf

    paths = ArrangementPaths.under(tmp_path / "prefix")
    platform = NoEffects(tmp_path / "evidence")
    platform.release_run = lambda: release_run_active(paths)
    tool = CutoverTool(ledger, SYNTHETIC_OPERATIONS, platform, clock=lambda: NOW)
    record = walk(ledger, "rehearsing", "ready-to-switch", "switching", "switched",
                  "rolling-back")
    rf.advance_cutover(ledger, record, "rolled-back", acceptedDryRunId=str(uuid4()),
                       verificationRunId=str(uuid4()))
    with release_command_running(paths):
        assert tool.soak_report() == {"soak": None, "v2Start": {"reason": RUN_ACTIVE,
                                                                "offered": ["check"]}}
        assert "soakStartedAt" not in tool.machine.require()
    # Taken between the check and the binding: refused under the binding, no role starts.
    journey = pf.journey(tmp_path, realm)
    racing = LocksBetween(journey.operator(ledger=ledger, clock=lambda: NOW), paths)
    platform.operator = racing
    try:
        with pytest.raises(StepFailed) as caught:
            tool._start_superseded(walk(ledger, "rehearsing"), f"soak-start-v2:{uuid4()}")
        assert caught.value.reason == RUN_ACTIVE
        assert all(journey.read_state("services", f"{label}.json") is None for label in LABELS)
    finally:
        racing.release()
    # Released: the starts run.
    platform.operator = racing.operator
    platform.steps = lambda name, bound, work: work()
    receipts = tool._start_superseded(walk(ledger, "rehearsing"), f"soak-start-v2:{uuid4()}")
    assert len(receipts) == len(LABELS)
    assert all(journey.read_state("services", f"{label}.json")["state"] == "running"
               for label in LABELS)


class Waiting:
    """A ledger holding one rehearsal set whose database was removed: the set
    `retry_left_sets` disposes of in person."""

    def __init__(self, database: str):
        self.database = database
        self.kinds = {
            "retained-copy": [{"copyId": "c-1", "kind": "rehearsal-database",
                               "locations": [f"database/{database}"],
                               "disposedAt": "2026-10-26T08:00:00Z"}],
            "backup-set": [{"backupId": "b-1", "environment": "rehearsal",
                            "databaseIncarnation": f"{database}:1",
                            "location": "archives/rehearsal-b-1.archive",
                            "retainUntil": "2030-01-01T00:00:00Z", "integrity": "passed"}],
        }

    def records(self, kind):
        return list(self.kinds.get(kind, []))

    def get(self, kind, key):
        return next((item for item in self.kinds.get(kind, [])
                     if item.get("backupId") == key), None)

    def revision(self, kind, key):
        return 1

    def append(self, kind, record, **options):
        self.kinds.setdefault(kind, []).append(record)


class Tries:
    """An operator that refuses each disposal at its precondition, keeping what it was
    asked (the disposal was tried, with the lock read again under its binding)."""

    def __init__(self):
        self.asked = []
        self.facts = lambda: SimpleNamespace(current_rehearsal=None)

    def execute(self, operation, target, inputs, *, key, **options):
        from docsuri_ops.u8_platform.u8_protocols import PreconditionRefused

        self.asked.append((operation, inputs["recordId"], options.get("recheck")))
        raise PreconditionRefused("stand-in-refusal")


def test_retry_left_sets_refuses_while_a_release_command_holds_its_run_lock(tmp_path):
    """`cutover check`'s set retry reads the run lock right before it disposes: held, each
    waiting set is reported with the release's reason and nothing is bound; released, it
    acts on each set, reading the lock again under the binding."""
    paths = ArrangementPaths.under(tmp_path / "prefix")
    database = "docsuri_u8_rehearsal_" + "a" * 12
    platform = NoEffects(tmp_path / "evidence")
    platform.release_run = lambda: release_run_active(paths)
    tool = CutoverTool(Waiting(database), SYNTHETIC_OPERATIONS, platform, clock=lambda: NOW)
    record = {"cutoverId": str(uuid4()), "state": "rehearsing", "approvals": []}
    with release_command_running(paths):
        assert tool.retry_left_sets(record) == {
            "rehearsalSetsDisposed": [],
            "rehearsalSetsWaiting": [{"backupId": "b-1", "reason": RUN_ACTIVE}]}
    tries = Tries()
    platform.operator = tries
    result = tool.retry_left_sets(record)
    assert result == {"rehearsalSetsDisposed": [],
                      "rehearsalSetsWaiting": [{"backupId": "b-1",
                                                "reason": "stand-in-refusal"}]}
    (asked,) = tries.asked
    assert asked[:2] == ("platform.copy.dispose", "b-1")
    assert asked[2] is not None and asked[2]() is None
    with release_command_running(paths):
        assert asked[2]() == RUN_ACTIVE  # the recheck under the binding reads the lock


@pytest.mark.parametrize("kind", ["install", "rollback"])
def test_the_soak_start_refuses_inside_its_own_step_during_a_release(ledger, kind):
    """`Cutover.start_soak` reads the release exclusion inside its own atomic step, so a
    release that began after the tool's checks still holds the soak back."""
    machine = Cutover(ledger, SYNTHETIC_OPERATIONS, clock=lambda: NOW)
    record = walk(ledger, "rehearsing", "ready-to-switch", "switching", "switched",
                  "rolling-back")
    rf.advance_cutover(ledger, record, "rolled-back", acceptedDryRunId=str(uuid4()),
                       verificationRunId=str(uuid4()))
    hold(ledger, kind)
    with pytest.raises(OperationsError) as caught:
        machine.start_soak()
    assert caught.value.current["reasonKey"] == REASONS[kind]
    assert machine.require()["state"] == "rolled-back"
    assert "soakStartedAt" not in machine.require()
