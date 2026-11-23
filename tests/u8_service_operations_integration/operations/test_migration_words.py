"""The operator tool's migration words (U8 plan Step 32; the person's decision of
2026-10-24, "Add operator commands"; BR8.9, BR8.11, BR8.15, Workflows 9–10).

The words drive the MigrationTool over the realm's PlatformControl store and a ledger of
the test's own. Your decisions take two calls: the first shows the subject and its
digest and records nothing; the second, confirmed with that digest, records the
decision through `platform.decision.record` and goes on. The isolation gate here passes
the start and then lapses, so a dry run is interrupted before anything is copied and
nothing outside the ledger is touched.
"""

from __future__ import annotations

import io
import json
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.modules.operations.errors import OperationsError
from backend.modules.operations.migration.misfits import MAPPING_RULES, PROPOSALS
from backend.modules.operations.migration_records import MigrationRuns, MisfitDecisions
from backend.modules.operations.retained_copies import RetainedCopies
from backend.u8_policy import SYNTHETIC_OPERATIONS
from docsuri_ops.arrangement.paths import REALM_DATABASES
from docsuri_ops.migration import words
from docsuri_ops.migration.tool import MigrationPlatform, MigrationTool
from docsuri_ops.u8_platform.decisions import Decisions
from docsuri_ops.u8_platform.u8_protocols import realm_operator
from tests.u8_service_operations_integration import platform_flows as pf
from tests.u8_service_operations_integration import recovery_flows as rf


class Gate:
    """Passes the start's reading, then lapses: the run stops at its first boundary."""

    def __init__(self, passes: int = 1):
        self.passes, self.reads = passes, 0

    def read(self):
        self.reads += 1
        return SimpleNamespace(passed=self.reads <= self.passes, reason="isolation-stale",
                               checked_at=None)


class Stage:
    def __init__(self, tmp_path, realm, clock, gate: Gate):
        self.journey = pf.journey(tmp_path, realm)
        self.ledger = rf.open_ledger(tmp_path, clock)
        self.clock = clock
        operator = realm_operator(self.journey.profile, "operator", self.ledger, clock=clock)
        unreached = SimpleNamespace()
        platform = MigrationPlatform(
            operator=operator, names=REALM_DATABASES, snapshot=unreached,
            create_rehearsal=unreached, create_import=unreached, restore_import=unreached,
            import_reader=unreached, owners_for=unreached, stream_back=unreached,
            isolation=gate, disk=unreached, spool=tmp_path, evidence=tmp_path / "evidence",
            installed=lambda: True, database_bytes=unreached)
        copies = RetainedCopies(self.ledger, SYNTHETIC_OPERATIONS, clock=clock)
        self.runs = MigrationRuns(self.ledger, clock=clock)
        tool = MigrationTool(self.runs, copies, platform, clock=clock, tool_commit="0" * 40)
        in_person = words.InPerson(Decisions(operator, words.realm_appender(self.ledger, clock),
                                             clock=clock))
        self.words = words.MigrationWords(tool, MisfitDecisions(self.ledger, clock=clock),
                                          in_person)

    def confirmed(self, word: str, document: dict) -> dict:
        shown = self.words.run(word, document)
        assert shown["state"] == "shown", shown
        return self.words.run(word, {**document, "confirm": shown["digest"]})

    def approvals(self) -> list[dict]:
        return self.ledger.records("maintainer-approval")


@pytest.fixture
def stage(tmp_path, realm, clock):
    value = Stage(tmp_path, realm, clock, Gate())
    yield value
    value.ledger.close()


# --- 1. preconditions and refusals, in person ------------------------------------------------


def test_a_go_ahead_is_shown_first_and_nothing_is_recorded(stage):
    shown = stage.words.run("dry-run", {})
    assert shown["state"] == "shown" and shown["step"] == "dry-run-go-ahead"
    assert shown["subject"]["source"] == "v1" and len(shown["digest"]) == 64
    assert stage.approvals() == [] and stage.runs.ledger.records("migration-run") == []


def test_a_confirmation_that_is_not_the_shown_digest_records_nothing(stage):
    answer = stage.words.run("dry-run", {"confirm": "0" * 64})
    assert answer["state"] == "subject-changed" and answer["digest"] != "0" * 64
    assert stage.approvals() == []
    with pytest.raises(words.Refused) as refused:
        stage.words.run("dry-run", {"confirm": "short"})
    assert refused.value.reason == "confirm-is-the-shown-digest"


def test_a_dry_run_is_refused_while_isolation_has_not_passed(tmp_path, realm, clock):
    lapsed = Stage(tmp_path, realm, clock, Gate(passes=0))
    try:
        with pytest.raises(OperationsError) as refused:
            lapsed.confirmed("dry-run", {})
        assert refused.value.current == {"reasonKey": "isolation-stale"}
        # Your go-ahead is recorded; no run started.
        assert [item["step"] for item in lapsed.approvals()] == ["dry-run-go-ahead"]
        assert lapsed.runs.ledger.records("migration-run") == []
    finally:
        lapsed.ledger.close()


@pytest.mark.parametrize(("word", "document", "reason"), [
    ("dry-run", {"runId": "r"}, "word-or-input-refused"),
    ("resume", {}, "word-or-input-refused"),
    ("abandon", {"runId": "r", "extra": 1}, "word-or-input-refused"),
    ("decide", {"kind": "account", "reasonKey": "no-email", "decision": "keep"},
     "misfit-decision-outside-its-set"),
    ("finalize", {}, "migration-word-outside-its-set"),
])
def test_each_word_refuses_input_outside_its_form(stage, word, document, reason):
    with pytest.raises(words.Refused) as refused:
        stage.words.run(word, document)
    assert refused.value.reason == reason


def test_a_report_decision_needs_a_reported_dry_run(stage):
    run = stage.confirmed("dry-run", {})
    with pytest.raises(words.Refused) as refused:
        stage.words.run("accept", {"runId": run["runId"]})
    assert refused.value.reason == "run-is-interrupted"


# --- 2. started, resumed and abandoned through the words alone -------------------------------


def test_a_dry_run_is_started_resumed_and_abandoned_through_the_words_alone(stage):
    started = stage.confirmed("dry-run", {})
    assert started["state"] == "interrupted" and started["interruptedPhase"] == "preparing"
    assert started["reason"] == "isolation-stale"
    resumed = stage.words.run("resume", {"runId": started["runId"]})
    assert resumed["state"] == "interrupted" and resumed["interruptedPhase"] == "preparing"
    abandoned = stage.words.run("abandon", {"runId": started["runId"]})
    assert abandoned["state"] == "failed" and abandoned["reason"] == "abandoned"
    with pytest.raises(OperationsError) as refused:
        stage.words.run("resume", {"runId": started["runId"]})
    assert refused.value.code == "CONFLICT"
    # Its five versions: started, interrupted, resumed, interrupted again, failed.
    assert stage.ledger.revision("migration-run", started["runId"]) == 5
    assert stage.runs.require(started["runId"])["state"] == "failed"


def test_a_misfit_decision_is_listed_then_recorded_in_two_calls(stage):
    run = stage.confirmed("dry-run", {})
    assert stage.words.run("decide", {"runId": run["runId"]}) == {"state": "listed",
                                                                 "misfits": []}
    kind, reason = next(pair for pair, decision in PROPOSALS.items() if decision == "map")
    decided = stage.confirmed("decide", {"kind": kind, "reasonKey": reason, "decision": "map"})
    assert decided["state"] == "decided" and decided["decision"] == "map"
    current = MisfitDecisions(stage.ledger, clock=stage.clock).current()
    assert current.of(kind, reason) == "map" and MAPPING_RULES[(kind, reason)]


# --- 3. the migration words move the cutover (your decision of 2026-10-24, BR9.3) ----------------


class Decided:
    """Your decision, already confirmed: the words' second call."""

    def __init__(self):
        self.steps = []

    def decide(self, step, ref, subject, decision, confirm):
        self.steps.append((step, decision))
        return {"approvalId": "approval-1"}


class Moved:
    def __init__(self):
        self.calls = []

    def after_dry_run(self, run_id, database):
        self.calls.append((run_id, database))
        return {"cutover": "rehearsing", "rehearsalDatabase": database, "soak": "started"}


def reported_tool(state: str = "accepted"):
    target = REALM_DATABASES.new("rehearsal")
    report = {"reportRef": "r", "reportDigest": "d" * 64, "kinds": {}, "reconciles": True}
    return SimpleNamespace(
        ledger=SimpleNamespace(get=lambda kind, key: report), tool_commit="0" * 40,
        runs=SimpleNamespace(require=lambda run_id: {"runId": run_id, "kind": "dry",
                                                      "state": "reported"}),
        decide=lambda run_id, approval: {"runId": run_id, "kind": "dry", "state": state},
        target_of=lambda run: target, target_disposed=lambda run: False), target


def test_an_accepted_report_moves_the_cutover_and_a_rejected_one_does_not():
    tool, target = reported_tool()
    moved = Moved()
    built = []

    def cutover():
        built.append(1)
        return moved

    migration = words.MigrationWords(tool, None, Decided(), cutover=cutover)
    result = migration.run("accept", {"runId": "run-1", "confirm": "0" * 64})
    assert result["state"] == "accepted" and moved.calls == [("run-1", target)]
    assert result["cutover"]["soak"] == "started" and built == [1]
    rejected, _ = reported_tool("rejected")
    migration = words.MigrationWords(rejected, None, Decided(), cutover=cutover)
    result = migration.run("reject", {"runId": "run-2", "confirm": "0" * 64})
    assert result["state"] == "rejected" and "cutover" not in result and built == [1]


def test_accepting_a_run_whose_rehearsal_database_was_removed_is_refused_before_deciding():
    """A dry run whose target copy is disposed (a rollback or opening removed its
    database) cannot be accepted: the profile would name a database that does not exist.
    Nothing is decided and nothing moves; rejecting it stays possible."""
    decided_runs = []
    tool, _ = reported_tool()
    tool.target_disposed = lambda run: True
    tool.decide = lambda run_id, approval: decided_runs.append(run_id) or {
        "runId": run_id, "kind": "dry", "state": "rejected"}
    decided, moved = Decided(), Moved()
    migration = words.MigrationWords(tool, None, decided, cutover=lambda: moved)
    with pytest.raises(words.Refused) as refused:
        migration.run("accept", {"runId": "run-1", "confirm": "0" * 64})
    assert (refused.value.code, refused.value.reason) == ("CONFLICT",
                                                          "rehearsal-database-disposed")
    assert decided.steps == [] and decided_runs == [] and moved.calls == []
    assert migration.run("reject", {"runId": "run-1", "confirm": "0" * 64})[
        "state"] == "rejected"


def test_target_disposed_reads_the_runs_target_copy(tmp_path, clock):
    """`MigrationTool.target_disposed`: a dry run's target copy disposed, or missing, is
    gone; an open one is not; a final run has none."""
    ledger = rf.open_ledger(tmp_path, clock)
    try:
        copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
        tool = MigrationTool(MigrationRuns(ledger, clock=clock), copies, SimpleNamespace(),
                             clock=clock, tool_commit="0" * 40)
        copy = copies.record("rehearsal-database", "run:x",
                             [f"database/{REALM_DATABASES.new('rehearsal')}"])
        run = {"kind": "dry", "targetCopyId": copy["copyId"]}
        assert tool.target_disposed(run) is False
        copies.disposed(copy["copyId"], rf.receipt("platform.database.remove",
                                                   "database-rehearsal", now=clock()))
        assert tool.target_disposed(run) is True
        assert tool.target_disposed({"kind": "dry", "targetCopyId": str(uuid4())}) is True
        assert tool.target_disposed({"kind": "final"}) is False
        assert tool.target_disposed({"kind": "dry"}) is False
    finally:
        ledger.close()


def test_a_cutover_wiring_refusal_records_no_decision_and_the_word_runs_again():
    """The cutover's tool is put together before your decision is recorded: a production
    part not in place refuses with its key, nothing is decided, and the same word works
    once the part is in place."""
    from docsuri_ops.production_wiring import WiringRefused

    decided_runs = []
    tool, target = reported_tool()
    tool.decide = lambda run_id, approval: decided_runs.append(run_id) or {
        "runId": run_id, "kind": "dry", "state": "accepted"}
    decided = Decided()
    parts = {"in place": False}
    moved = Moved()

    def cutover():
        if not parts["in place"]:
            raise WiringRefused("operator-login-not-released")
        return moved

    migration = words.MigrationWords(tool, None, decided, cutover=cutover)
    with pytest.raises(words.Refused) as refused:
        migration.run("accept", {"runId": "run-1", "confirm": "0" * 64})
    assert (refused.value.code, refused.value.reason) == ("POLICY_UNRESOLVED",
                                                          "operator-login-not-released")
    assert decided.steps == [] and decided_runs == [] and moved.calls == []
    parts["in place"] = True
    result = migration.run("accept", {"runId": "run-1", "confirm": "0" * 64})
    assert result["state"] == "accepted" and moved.calls == [("run-1", target)]
    assert decided.steps == [("dry-run-report", "approved")] and decided_runs == ["run-1"]


def test_a_wiring_refusal_met_during_a_word_is_answered_not_raised(monkeypatch, capsys):
    from docsuri_ops.production_wiring import WiringRefused

    class Refusing:
        def run(self, word, document):
            raise WiringRefused("platform-authorities-not-installed")

    monkeypatch.setattr(words, "_words", lambda kind, args, clock: (Refusing(), None))
    monkeypatch.setattr(sys, "stdin", type("In", (), {"buffer": io.BytesIO(b"{}")})())
    assert words.main("migration", ["accept", "--production"]) == 1
    answer = json.loads(capsys.readouterr().out)
    assert answer == {"ok": False, "code": "POLICY_UNRESOLVED",
                      "reasonKey": "platform-authorities-not-installed"}


def test_an_accepted_dry_run_moves_the_record_the_profile_and_the_roles(tmp_path, realm, clock):
    from backend.modules.operations.migration.misfits import Decisions as MisfitSet
    from docsuri_ops.production_wiring import ledger_profile_state
    from tests.u8_service_operations_integration import cutover_flows as cf
    from tests.u8_service_operations_integration.component.test_cutover_words import (
        Stage as CutoverStage,
    )

    cut = CutoverStage(tmp_path, realm, clock)
    try:
        cut.platform.sleep = clock.advance
        restarts, restart = [], cut.tool.restart_v2
        cut.tool.restart_v2 = lambda record, step: restarts.append(step) or restart(record, step)
        run = cf.accepted_dry_run(cut.ledger, now=clock(),
                                  decisionsDigest=MisfitSet.from_ledger(cut.ledger).digest())
        assert cut.tool.after_dry_run(run["runId"], "unused") == {"cutover": "none"}
        machine = cut.tool.machine
        machine.begin(cf.TAG)
        database = cut.database.names.new("rehearsal")
        # As the dry run itself records it before anything is written to it.
        cut.tool.copies.record("rehearsal-database", f"run:{run['runId']}",
                               [f"database/{database}"])
        moved = cut.tool.after_dry_run(run["runId"], database)
        assert moved["cutover"] == "preparing" and moved["soak"] is None, moved
        assert moved["ready"] is True and moved["rehearsalDatabase"] == database
        assert machine.current()["acceptedDryRunId"] == run["runId"]
        assert ledger_profile_state(cut.ledger)["rehearsalDatabase"] == database
        assert restarts == [f"dry-run:{run['runId']}"]
        # The soak starts once the release's verification is recorded, and only once.
        machine.verification_passed(uuid4(), cf.TAG)
        assert cut.tool.soak_after_verification() == "started"
        assert machine.current()["state"] == "rehearsing"
        assert cut.tool.soak_after_verification() is None
    finally:
        cut.close()


class Inventory:
    def __init__(self, complete: bool):
        consumer = {"clientRef": "client-1", "routesUsed": ["/api"], "source": "observed",
                    "requests": 3}
        self.ledger = SimpleNamespace(get=lambda kind, key: {"consumers": [consumer]})
        self.complete = complete

    def dispose(self, inventory_id, client, disposition, approval):
        return {"complete": self.complete}


class Machine:
    def __init__(self, record):
        self.record, self.linked = record, []

    def current(self):
        return self.record

    def inventory_taken(self, inventory_id):
        self.linked.append(inventory_id)
        return {"consumerInventoryId": inventory_id}


def test_a_complete_inventory_is_linked_to_the_cutover_record():
    from docsuri_ops.migration.inventory import DISPOSITIONS

    disposition = sorted(DISPOSITIONS)[0]
    document = {"inventoryId": "inv-1", "clientRef": "client-1", "disposition": disposition,
                "confirm": "0" * 64}
    machine = Machine({"cutoverId": "c"})
    linked = words.InventoryWords(Inventory(True), Decided(), cutover=machine).run(
        "record", document)
    assert linked["cutover"] == "inv-1" and machine.linked == ["inv-1"]
    machine = Machine({"cutoverId": "c"})
    partial = words.InventoryWords(Inventory(False), Decided(), cutover=machine).run(
        "record", document)
    assert "cutover" not in partial and machine.linked == []
    machine = Machine(None)
    unbegun = words.InventoryWords(Inventory(True), Decided(), cutover=machine).run(
        "record", document)
    assert "cutover" not in unbegun and machine.linked == []


# --- the command line ---------------------------------------------------------------------------


def run_main(monkeypatch, kind: str, argv: list[str], payload: bytes = b"{}"):
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(payload)))
    monkeypatch.setattr(sys, "stdout", out)
    status = words.main(kind, argv)
    return status, json.loads(out.getvalue())


def test_the_production_words_refuse_on_a_mac_without_the_arrangement(monkeypatch):
    """`--production` reaches the production migration platform (the person's decision
    of 2026-10-24); on a Mac where the arrangement is not installed its operator is not
    in place, so the words refuse before any ledger read, sudo or keychain."""
    from docsuri_ops.arrangement.paths import ArrangementPaths

    assert not (ArrangementPaths().control / "platform-authorities.json").exists()
    status, result = run_main(monkeypatch, "migration", ["dry-run", "--production"])
    assert status == 1 and result == {
        "ok": False, "code": "POLICY_UNRESOLVED",
        "reasonKey": "platform-authorities-not-installed"}


@pytest.mark.parametrize("payload", [b"[]", b"x" * (64 * 1024 + 1)])
def test_input_must_be_one_bounded_object(monkeypatch, payload):
    status, result = run_main(monkeypatch, "migration", ["resume", "--production"], payload)
    assert status == 1 and result["code"] == "INVALID_INPUT"


def test_the_operator_tool_routes_the_migration_words(monkeypatch):
    from docsuri_ops.u8_platform import operator_tool as cli

    out = io.StringIO()
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=io.BytesIO(b"{}")))
    monkeypatch.setattr(sys, "stdout", out)
    assert cli.main(["migration", "dry-run"]) == 1  # neither the realm nor production named
    assert json.loads(out.getvalue())["code"] == "POLICY_UNRESOLVED"


# --- the disk guard's estimate (U8 plan Steps 68(a), 69(a); L1-17) -----------------------------

GIB = 1024**3
THRESHOLD = 20 * GIB


def _recorded_run(ledger, runs, kind: str, end: str, *, started: str,
                  target_copy: str | None = None) -> str:
    """A run recorded straight into the ledger and moved through the machine to `end`."""
    run_id = str(uuid4())
    record = {"runId": run_id, "kind": kind,
              "target": "rehearsal" if kind == "dry" else "production",
              "toolCommit": "0" * 40, "decisionsDigest": "0" * 64, "state": "preparing",
              "startedAt": started}
    ledger.atomic(lambda view: view.append("migration-run", record, expect_revision=0))
    path = {"failed": ("copying", "failed"),
            "rejected": ("copying", "importing", "verifying", "reported", "rejected"),
            "accepted": ("copying", "importing", "verifying", "reported", "accepted")}[end]
    for index, state in enumerate(path):
        fields = {"targetCopyId": target_copy} if index == 0 and target_copy else {}
        runs.move(run_id, state, **fields)
    return run_id


def test_a_dry_run_import_counts_4_gib_until_a_run_is_accepted_then_that_runs_database(
    tmp_path, clock,
):
    import datetime as dt

    from backend.modules.operations.ledger import utc_text
    from docsuri_ops.migration.disk_guard import DiskGuard
    from docsuri_ops.migration.tool import Interrupted

    ledger = rf.open_ledger(tmp_path, clock)
    try:
        free = {"bytes": 0}
        readings: dict[str, int] = {}
        asked: list[str] = []

        def database_bytes(name: str) -> int:
            asked.append(name)
            return readings[name]

        platform = SimpleNamespace(disk=DiskGuard(lambda: free["bytes"], THRESHOLD),
                                   database_bytes=database_bytes)
        copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
        runs = MigrationRuns(ledger, clock=clock)
        tool = MigrationTool(runs, copies, platform, clock=clock, tool_commit="0" * 40)

        def database(reading: int) -> tuple[str, dict]:
            name = REALM_DATABASES.new("rehearsal")
            readings[name] = reading
            return name, copies.record("rehearsal-database", f"run:{uuid4()}",
                                       [f"database/{name}"])

        cur, target = database(2**21)
        run = {"runId": str(uuid4()), "kind": "dry", "targetCopyId": target["copyId"]}
        snapshot = {"sourceDatabaseBytes": 2**30}

        def guarded(estimate: int, held: int) -> None:
            free["bytes"] = THRESHOLD + 2**30 + estimate - held
            with pytest.raises(Interrupted) as stopped:
                tool._guard(run, snapshot)
            assert stopped.value.reason == "internal-disk-low"
            free["bytes"] += 1
            assert tool._guard(run, snapshot) == 2**30 + estimate

        # No accepted dry run: the policy's 4 GiB; the import database counts once recorded.
        guarded(4 * GIB, 2**21)
        imp = REALM_DATABASES.new("import")
        readings[imp] = 2**20
        copies.record("import-database", f"run:{run['runId']}", [f"database/{imp}"])
        guarded(4 * GIB, 2**21 + 2**20)
        held = 2**21 + 2**20

        # Rejected and failed dry runs and an accepted final run never count.
        t0 = clock()
        for end in ("rejected", "failed"):
            _, copy = database(GIB)
            _recorded_run(ledger, runs, "dry", end, started=utc_text(t0),
                          target_copy=copy["copyId"])
        _recorded_run(ledger, runs, "final", "accepted", started=utc_text(t0))
        guarded(4 * GIB, held)

        # The latest accepted dry run by its start: B, 60 s after A.
        a_name, a_copy = database(1 * GIB)
        b_name, b_copy = database(2 * GIB)
        _recorded_run(ledger, runs, "dry", "accepted", started=utc_text(t0),
                      target_copy=a_copy["copyId"])
        _recorded_run(ledger, runs, "dry", "accepted",
                      started=utc_text(t0 + dt.timedelta(seconds=60)),
                      target_copy=b_copy["copyId"])
        asked.clear()
        guarded(2 * GIB, held)
        assert b_name in asked

        # Read again at every guard.
        readings[b_name] = 3 * GIB
        guarded(3 * GIB, held)

        # B's rehearsal database removed: back to the 4 GiB estimate.
        copies.disposed(b_copy["copyId"], rf.receipt("platform.database.remove",
                                                     "database-rehearsal", now=clock()))
        guarded(4 * GIB, held)
        assert cur in asked
    finally:
        ledger.close()


def test_the_production_words_answer_a_refused_release(monkeypatch):
    """The maintainer's decision of 2026-11-16 ("Fix the test and answer refusals"): a
    credential release that refuses is one JSON refusal, never a traceback. A stand-in
    keychain for the release refuses, so nothing reaches this Mac's sudo or ledger."""
    from docsuri_ops.u8_platform.credential_release import ReleaseRefused

    monkeypatch.setattr("docsuri_ops.production_wiring._authorities",
                        lambda paths: {"actors": {"operator": "someone-else"}})
    asked = []

    def refused(login):
        asked.append(login)
        raise ReleaseRefused("the credential was not released")

    monkeypatch.setattr("docsuri_ops.u8_platform.credential_release.release_with_actor",
                        refused)
    status, result = run_main(monkeypatch, "migration", ["dry-run", "--production"])
    assert status == 1 and result == {
        "ok": False, "code": "POLICY_UNRESOLVED", "reasonKey": "credential-not-released"}
    assert asked == ["platform"]
