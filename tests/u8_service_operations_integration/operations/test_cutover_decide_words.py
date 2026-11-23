"""`docsuri-ops cutover decide <kind>` (U8 plan Step 34; the person's decision of
2026-10-24, "Add decision commands"; Workflows 12–14, Workflow 18, BR9.14).

The cutover runs on the component journeys' stage (`component/test_cutover_words.Stage`:
the realm's PlatformControl store and driver on the journey's own platform state, a
production stand-in of the test's own). Every approval the cutover commands take is
recorded here through the decide word alone: the first call shows the subject and its
digest and records nothing; the second, confirmed with that digest, records through
`platform.decision.record`, and the one command that takes that step takes it.
"""

from __future__ import annotations

import datetime as dt
from uuid import uuid4

import pytest

from backend.modules.operations.errors import OperationsError
from backend.modules.operations.ledger import utc_text
from backend.modules.operations.migration_records import MigrationRuns
from docsuri_ops.cutover.decide import KINDS
from docsuri_ops.cutover.tool import run_word
from docsuri_ops.migration.words import InPerson, realm_appender
from docsuri_ops.u8_platform.decisions import Decisions
from tests.u8_service_operations_integration import cutover_flows as cf
from tests.u8_service_operations_integration.component.test_cutover_words import Stage

DAY = 86400


class Words:
    """The decide word and the cutover commands, as the operator tool runs them."""

    def __init__(self, stage: Stage):
        self.stage, self.ledger, self.clock = stage, stage.ledger, stage.clock
        self.in_person = InPerson(Decisions(stage.operator,
                                            realm_appender(stage.ledger, stage.clock),
                                            clock=stage.clock))
        runs = MigrationRuns(stage.ledger, clock=stage.clock)
        stage.platform.final_decide = lambda run_id, approval: runs.decide_report(
            run_id, approval)
        stage.final_run = self.final_run
        stage.platform.final_run = self.final_run

    def final_run(self, approval: str, dispose_after: dt.datetime) -> dict:
        """The final run, reported with a reconciling parity report, and its completed
        final snapshot at the date the start computed (Step 71(g))."""
        run_id = str(uuid4())
        copy = cf.final_snapshot(self.ledger, run_id, approval=approval,
                                 dispose_after=dispose_after, now=self.clock())
        run = cf.final_run(self.ledger, now=self.clock(), state="reported", runId=run_id,
                           snapshotCopyId=copy["copyId"])
        MigrationRuns(self.ledger, clock=self.clock).record_report(
            run["runId"], reference=f"evidence/migration/parity-{run['runId']}.json",
            digest="e" * 64, kinds=12, reconciles=True)
        return run

    def approvals(self) -> int:
        return len(self.ledger.records("maintainer-approval"))

    def decide(self, kind: str, document: dict | None = None) -> dict:
        return run_word(self.stage.tool, "decide", document or {}, kind=kind,
                        in_person=self.in_person)

    def decided(self, kind: str, document: dict | None = None) -> dict:
        """Both calls: the first shows and records nothing, the second records."""
        before = self.approvals()
        shown = self.decide(kind, document)
        assert shown["state"] == "shown" and shown["step"] == kind, shown
        assert len(shown["digest"]) == 64 and self.approvals() == before
        answer = self.decide(kind, {**(document or {}), "confirm": shown["digest"]})
        assert answer["state"] == "decided" and answer["kind"] == kind, answer
        assert self.approvals() == before + 1
        approval = self.ledger.get("maintainer-approval", answer["approvalId"])
        assert approval["step"] == kind and approval["subjectDigest"] == shown["digest"]
        assert approval["operatorReceiptRef"]
        return answer

    def command(self, word: str, answer: dict) -> dict:
        document = {"approvalId": answer["approvalId"]}
        if "subject" in answer:
            document["subject"] = answer["subject"]
        return run_word(self.stage.tool, word, document)


def rehearsing(stage: Stage, **accepted) -> None:
    """Every BR9.2 precondition but the restart rehearsal (`Stage.ready`'s evidence);
    `accepted` reaches the accepted dry run."""
    machine = stage.tool.machine
    machine.begin(cf.TAG)
    stage.accept_dry_run(**accepted)
    machine.verification_passed(uuid4(), cf.TAG)
    record = machine.start_soak()
    start = dt.datetime.fromisoformat(record["soakStartedAt"].replace("Z", "+00:00"))
    stage.soak_evidence(start)
    stage.clock.advance(7 * DAY + 60)
    # The inventory at the check's clock, after the soak (L1-21).
    machine.inventory_taken(cf.complete_inventory(stage.ledger, now=stage.clock())[
        "inventoryId"])


def ready(stage: Stage, words: Words) -> None:
    rehearsing(stage)
    rehearsed = words.command("rehearse-restart", words.decided("v1-restart-rehearsal"))
    assert rehearsed["rehearsed"], rehearsed
    stage.isolation_passed()
    assert stage.tool.check() == {"state": "ready-to-switch", "missing": []}


def switched(stage: Stage, words: Words) -> None:
    """To the switch through the decide word: the start, the final report, the opening."""
    ready(stage, words)
    first = words.command("start", words.decided("switch-start"))
    assert first["waiting"] == "final-report", first
    second = words.command("start", words.decided("final-report"))
    assert second == {"state": "switching", "waiting": "maintainer-window"}, second
    opened = words.command("open", words.decided(
        "admission-opening", {"providersAcceptedUnavailable": []}))
    assert opened["state"] == "switched", opened


@pytest.fixture
def stage(tmp_path, realm, clock):
    value = Stage(tmp_path, realm, clock)
    yield value
    value.close()


@pytest.fixture
def words(stage):
    return Words(stage)


# --- 1. each kind's first call records nothing; its command takes the second's -----------


def test_each_kinds_first_call_records_nothing_and_its_command_takes_the_approval(
        stage, words):
    seen = set()
    switched(stage, words)
    seen |= {"v1-restart-rehearsal", "switch-start", "final-report", "admission-opening"}
    # A rollback whose v1 restart fails waits before v1 serves; your decision cancels it.
    stage.probes.v1 = False
    waiting = words.command("rollback", words.decided("rollback"))
    assert waiting["state"] == "rolling-back" and waiting["offered"] == ["cancel-rollback"]
    stage.probes.v1 = True
    cancelled = words.command("cancel-rollback", words.decided("rollback-cancel"))
    assert cancelled == {"state": "switched"}
    # A rollback whose copy cannot be written waits; your waiver ends it without one.
    stage.agent.copies = False
    pending = words.command("rollback", words.decided("rollback"))
    assert pending["copyPending"] is True, pending
    waived = words.command("waive-copy", words.decided("rollback-copy-waiver"))
    assert waived["state"] == "rolled-back", waived
    waiver = stage.ledger.get("maintainer-approval", stage.tool.machine.current()[
        "approvals"][-1])
    assert waiver["step"] == "rollback-copy-waiver"
    seen |= {"rollback", "rollback-cancel", "rollback-copy-waiver"}
    # Settlement and the disposal-date decision: the re-date tests below (Step 71(d)); the
    # providers' two kinds: the window's tests below (Step 107(h)).
    assert seen == set(KINDS) - {"settlement", "disposal-date", "provider-sign-in",
                                 "provider-first-effect"}


def instant(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def round_clock(clock) -> None:
    clock.now = clock.now.replace(microsecond=clock.now.microsecond // 1000 * 1000)


def later(text: str, seconds: int) -> dt.datetime:
    return instant(text) + dt.timedelta(seconds=seconds)


def set_dates(stage: Stage, copy_id: str, date: dt.datetime, approval: dict) -> list[dict]:
    """The `set-date` calls the agent receives for the copy's three parts."""
    parts = stage.snapshot_parts(copy_id)
    decided = {"date": date.isoformat(), "receipt": approval["operatorReceiptRef"],
               "subjectDigest": approval["subjectDigest"]}
    return [{"path": parts[name]["path"], "decided": decided} for name in sorted(parts)]


def test_settlement_is_decided_and_taken_after_the_window(stage, words):
    """Step 71(d), L1-3: decided right after the opening and taken once the window has
    passed, the settlement re-dates the final snapshot to 30 days after the settlement's
    move, not after the decision."""
    round_clock(stage.clock)
    switched(stage, words)
    record = stage.tool.machine.current()
    copy_id = record["finalSnapshotCopyId"]
    settlement = words.decided("settlement")
    assert settlement["subject"]["finalSnapshotCopyId"] == copy_id
    assert settlement["subject"]["finalSnapshotDisposalSeconds"] == 2592000
    stage.clock.advance(record["rollbackWindowSeconds"] + 60)
    settled = words.command("settle", settlement)
    assert settled["state"] == "settled" and settled["finalSnapshotRedated"] is True, settled
    record = stage.tool.machine.current()
    approval = stage.ledger.get("maintainer-approval", settlement["approvalId"])
    date = later(record["settledAt"], 2592000)
    assert settled["finalSnapshotDisposeAfter"] == utc_text(date)
    assert utc_text(date) != utc_text(later(approval["recordedAt"], 2592000))
    assert stage.agent.set_dates == set_dates(stage, copy_id, date, approval)
    copy = stage.ledger.get("retained-copy", copy_id)
    assert copy["disposeAfter"] == utc_text(date)
    assert copy["redateReceiptRef"] == approval["operatorReceiptRef"]
    assert copy["disposalApprovalId"] == approval["approvalId"]
    versions = stage.ledger.revision("retained-copy", copy_id)
    # Run again on the settled record: the same date, no `set-date`, no version.
    again = words.command("settle", settlement)
    assert again["state"] == "settled" and again["finalSnapshotDisposeAfter"] == utc_text(date)
    assert len(stage.agent.set_dates) == 3
    assert stage.ledger.revision("retained-copy", copy_id) == versions


@pytest.mark.parametrize("case", ["late", "closed"])
def test_a_late_settlement_keeps_the_held_date_and_a_closed_snapshot_is_left_alone(
        stage, words, case):
    from backend.modules.operations.retained_copies import RetainedCopies
    from backend.u8_policy import SYNTHETIC_OPERATIONS

    round_clock(stage.clock)
    switched(stage, words)
    record = stage.tool.machine.current()
    copy_id = record["finalSnapshotCopyId"]
    settlement = words.decided("settlement")
    if case == "late":
        # 91 days after the check: 30 days after it is later than the 120-day date.
        stage.clock.now = later(record["switchCheckedAt"], 91 * DAY)
        versions = stage.ledger.revision("retained-copy", copy_id)
        settled = words.command("settle", settlement)
        assert settled["state"] == "settled" and settled["finalSnapshotRedated"] is False
        assert settled["finalSnapshotDisposeAfter"] == utc_text(
            later(record["switchCheckedAt"], 10368000))
        assert stage.ledger.revision("retained-copy", copy_id) == versions
    else:
        stage.clock.advance(record["rollbackWindowSeconds"] + 60)
        RetainedCopies(stage.ledger, SYNTHETIC_OPERATIONS, clock=stage.clock).disposed_by_agent(
            copy_id, "agent:disposed-test")
        settled = words.command("settle", settlement)
        assert settled["state"] == "settled" and settled["reason"] == "final-snapshot-closed"
    assert stage.agent.set_dates == []


def test_an_aborted_switchs_final_snapshot_goes_30_days_after_the_abort_on_your_decision(
        stage, words):
    """Step 71(d), L1-3, L1-66 ("Start waits")."""
    from backend.modules.operations.incidents import Incidents

    round_clock(stage.clock)
    ready(stage, words)
    # No abort: the decision is refused and the start never waits on it.
    with pytest.raises(OperationsError) as no_abort:
        words.decide("disposal-date")
    assert no_abort.value.code == "CONFLICT"
    assert no_abort.value.current["reasonKey"] == "no-aborted-final-snapshot"
    assert stage.tool.missing() == []
    words.command("start", words.decided("switch-start"))
    record = stage.tool.machine.current()
    copy_id = record["finalSnapshotCopyId"]
    assert stage.ledger.get("retained-copy", copy_id)["disposeAfter"] == utc_text(
        later(record["switchCheckedAt"], 10368000))
    # The abort records its clock and names the pending decision.
    abort_at = utc_text(stage.clock())
    assert run_word(stage.tool, "abort", {"reason": "operator-abort"})["state"] == "rehearsing"
    record = stage.tool.machine.current()
    assert record["state"] == "rehearsing" and record["abortStartedAt"] == abort_at
    assert run_word(stage.tool, "status", {})["finalSnapshotAwaitingDate"] == copy_id
    # The start waits: `check` keeps the record rehearsing, and a start is refused.
    review = cf.decision(stage.ledger, "abort-review", record["cutoverId"], now=stage.clock())
    Incidents(stage.ledger, environment="live").resolve(
        record["abortIncidentId"], "abort-reviewed", [f"approval:{review}"])
    stage.isolation_passed()
    checked = stage.tool.check()
    assert checked["state"] == "rehearsing", checked
    assert checked["missing"] == ["final-snapshot-awaiting-date"]
    assert stage.tool.machine.current()["abortStartedAt"] == abort_at
    stage.tool.machine.check_ready([])
    start = words.decided("switch-start")
    with pytest.raises(OperationsError) as waits:
        words.command("start", start)
    assert waits.value.code == "CONFLICT"
    assert waits.value.current["reasonKey"] == "precondition-missing"
    assert "final-snapshot-awaiting-date" in waits.value.current["missing"]
    record = stage.tool.machine.current()
    assert record["state"] == "ready-to-switch" and record["abortStartedAt"] == abort_at
    assert {stage.journey.read_state("services", f"{label}.json")["state"]
            for label in stage.platform.v1_labels} == {"running"}
    # The decision shows the date 30 days after the abort; a typed date is refused.
    date = later(abort_at, 2592000)
    shown = words.decide("disposal-date")
    assert shown["subject"]["finalSnapshotCopyId"] == copy_id
    assert shown["subject"]["finalSnapshotDisposeAfter"] == utc_text(date)
    with pytest.raises(OperationsError) as typed:
        words.decide("disposal-date", {"finalSnapshotDisposeAfter": utc_text(date)})
    assert typed.value.current["reasonKey"] == "word-or-input-refused"
    decision = words.decided("disposal-date")
    dated = words.command("date-final-snapshot", decision)
    assert dated["finalSnapshotRedated"] is True, dated
    approval = stage.ledger.get("maintainer-approval", decision["approvalId"])
    assert stage.agent.set_dates == set_dates(stage, copy_id, date, approval)
    copy = stage.ledger.get("retained-copy", copy_id)
    assert copy["disposeAfter"] == utc_text(date)
    assert copy["redateReceiptRef"] == approval["operatorReceiptRef"]
    assert "finalSnapshotAwaitingDate" not in run_word(stage.tool, "status", {})
    assert stage.tool.missing() == []  # the start no longer waits


def test_the_start_waits_only_while_the_aborted_snapshot_can_be_dated(tmp_path, clock):
    from backend.modules.operations.retained_copies import RetainedCopies
    from backend.u8_policy import SYNTHETIC_OPERATIONS
    from docsuri_ops.cutover.preconditions import awaiting_final_snapshot
    from tests.u8_service_operations_integration import recovery_flows as rf

    round_clock(clock)
    ledger = rf.open_ledger(tmp_path, clock)
    try:
        aborted = utc_text(clock())
        limit = later(aborted, 2592000)

        def snapshot(date: dt.datetime) -> str:
            return cf.final_snapshot(ledger, str(uuid4()), approval=str(uuid4()),
                                     dispose_after=date, now=clock())["copyId"]

        def awaiting(record: dict) -> str | None:
            return awaiting_final_snapshot(ledger, record, SYNTHETIC_OPERATIONS)

        exact, one_later = snapshot(limit), snapshot(limit + dt.timedelta(seconds=1))
        assert awaiting({"abortStartedAt": aborted, "finalSnapshotCopyId": exact}) is None
        assert awaiting({"abortStartedAt": aborted,
                         "finalSnapshotCopyId": one_later}) == one_later
        copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
        held = snapshot(limit + dt.timedelta(seconds=1))
        copies.disposed_by_agent(one_later, "agent:disposed-test")
        assert awaiting({"abortStartedAt": aborted, "finalSnapshotCopyId": one_later}) is None
        unfinished = copies.record("v1-final-snapshot", f"run:{uuid4()}",
                                   ["backup-volume:x:database"],
                                   dispose_after=limit + dt.timedelta(seconds=1),
                                   approval_id=str(uuid4()))
        assert awaiting({"abortStartedAt": aborted,
                         "finalSnapshotCopyId": unfinished["copyId"]}) is None
        assert awaiting({"finalSnapshotCopyId": held}) is None
    finally:
        ledger.close()


def refused_with(call) -> tuple[str, str]:
    with pytest.raises(OperationsError) as error:
        call()
    return error.value.code, error.value.current.get("reasonKey")


def test_the_decided_dates_follow_the_table(stage, words):
    """Step 71(c), L1-3: no date is typed; each command dates its copy at its event plus
    the policy's offset, and a subject whose rule differs by one second is refused before
    any effect."""
    round_clock(stage.clock)
    ready(stage, words)

    def differing(step: str, subject: dict, rule: str, word: str) -> None:
        record = stage.tool.machine.current()
        bad = {**subject, rule: subject[rule] + 1}
        approval = cf.decision(stage.ledger, step, record["cutoverId"], now=stage.clock(),
                               subject=bad)
        assert refused_with(lambda: run_word(stage.tool, word, {
            "approvalId": approval, "subject": bad})) == ("INVALID_INPUT",
                                                          "decided-rule-differs")
        after = stage.tool.machine.current()
        assert after["effectReceipts"] == record["effectReceipts"]
        assert after["state"] == record["state"]

    # Switch start: 120 days after the switch's check.
    assert refused_with(lambda: words.decide("switch-start", {
        "finalSnapshotDisposeAfter": "2027-03-01T00:00:00Z"})) == (
        "INVALID_INPUT", "word-or-input-refused")
    start = words.decided("switch-start")
    assert start["subject"]["finalSnapshotBackstopSeconds"] == 10368000
    differing("switch-start", start["subject"], "finalSnapshotBackstopSeconds", "start")
    words.command("start", start)
    record = stage.tool.machine.current()
    snapshot = stage.ledger.get("retained-copy", record["finalSnapshotCopyId"])
    assert snapshot["disposeAfter"] == utc_text(later(record["switchCheckedAt"], 10368000))
    assert instant(snapshot["disposeAfter"]) <= later(snapshot["createdAt"], 10368000)
    assert snapshot["disposalApprovalId"] == start["approvalId"]
    words.command("start", words.decided("final-report"))
    # Opening: 90 days after admission opens.
    assert refused_with(lambda: words.decide("admission-opening", {
        "v1StoresDisposeAfter": "2027-03-01T00:00:00Z",
        "providersAcceptedUnavailable": []})) == ("INVALID_INPUT", "word-or-input-refused")
    opening = words.decided("admission-opening", {"providersAcceptedUnavailable": []})
    assert opening["subject"]["v1StoresDisposalSeconds"] == 7776000
    differing("admission-opening", opening["subject"], "v1StoresDisposalSeconds", "open")
    opened = words.command("open", opening)
    record = stage.tool.machine.current()
    stores = stage.ledger.get("retained-copy", opened["v1StoresCopyId"])
    assert stores["disposeAfter"] == utc_text(later(record["admissionOpenedAt"], 7776000))
    # Rollback: 30 days after v1 serves again.
    assert refused_with(lambda: words.decide("rollback", {
        "rolledBackDisposeAfter": "2027-03-01T00:00:00Z"})) == (
        "INVALID_INPUT", "word-or-input-refused")
    rollback = words.decided("rollback")
    assert rollback["subject"]["rolledBackDisposalSeconds"] == 2592000
    differing("rollback", rollback["subject"], "rolledBackDisposalSeconds", "rollback")
    assert words.command("rollback", rollback)["state"] == "rolled-back"
    record = stage.tool.machine.current()
    (rolled,) = [copy for copy in stage.ledger.records("retained-copy")
                 if copy["kind"] == "rolled-back-v2-database"]
    assert rolled["disposeAfter"] == utc_text(later(record["rollbackV1ServingAt"], 2592000))


def write_lines(folder, lines: list[dict]) -> None:
    """Latency lines as `LatencyRecorder` writes them, each in its window's UTC day file."""
    import json

    for line in lines:
        start = instant(line["window"])
        path = folder / f"{start:%Y-%m-%d}.jsonl"
        with path.open("a") as stream:
            stream.write(json.dumps(line, sort_keys=True) + "\n")


def window(moment: dt.datetime) -> str:
    return moment.astimezone(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def test_the_switch_start_subject_shows_the_accepted_dry_runs_durations_and_the_soaks_95th_percentiles(  # noqa: E501
        stage, words):
    """Step 71(i), NFR8.8, performance-design § 10, L1-59."""
    phases = {"preparing": 60, "copying": 600, "importing": 4500, "verifying": 240}
    rehearsing(stage, durationSeconds=5400, phaseSeconds=phases, interruptions=0)
    record = stage.tool.machine.current()
    soak = instant(record["soakStartedAt"])
    until = soak + dt.timedelta(seconds=604800)

    def line(route_class: str, begun: dt.datetime, p95: float, count: int) -> dict:
        return {"window": window(begun), "class": route_class, "count": count,
                "medianMs": p95, "p95Ms": p95, "maxMs": p95, "errors5xx": 0}

    write_lines(stage.latency, [
        line("read", soak + dt.timedelta(seconds=60), 120, 10),
        line("read", soak + dt.timedelta(hours=1), 480, 30),
        line("search", soak + dt.timedelta(hours=2), 1800, 5),
        line("read", soak - dt.timedelta(seconds=1), 9000, 3),
        line("read", until - dt.timedelta(seconds=2), 7000, 4),
    ])
    words.command("rehearse-restart", words.decided("v1-restart-rehearsal"))
    stage.isolation_passed()
    assert stage.tool.check() == {"state": "ready-to-switch", "missing": []}
    shown = words.decide("switch-start")
    subject = shown["subject"]
    assert subject["acceptedDryRun"] == {"runId": record["acceptedDryRunId"],
                                         "durationSeconds": 5400, "phaseSeconds": phases,
                                         "interruptions": 0}
    measured = subject["soak"]
    assert measured["from"] == record["soakStartedAt"] and measured["until"] == utc_text(until)
    assert measured["windows"] == 3
    assert measured["p95Ms"]["read"] == 480 and measured["p95Ms"]["search"] == 1800
    assert measured["p95Ms"]["health"] is None and measured["requests"]["read"] == 40
    # A line after `until`, written between the calls, changes nothing shown.
    write_lines(stage.latency, [line("read", until + dt.timedelta(minutes=5), 9999, 50)])
    decided = words.decide("switch-start", {"confirm": shown["digest"]})
    assert decided["state"] == "decided", decided
    approval = stage.ledger.get("maintainer-approval", decided["approvalId"])
    assert approval["subjectDigest"] == shown["digest"]
    # A reader that fails, and a platform without one, record nothing.
    before = words.approvals()

    def unreadable(start, end):
        raise PermissionError("evidence folder")

    stage.platform.soak_latency = unreadable
    assert refused_with(lambda: words.decide("switch-start")) == (
        "CONFLICT", "soak-latency-unreadable")
    stage.platform.soak_latency = None
    with pytest.raises(OperationsError) as unwired:
        words.decide("switch-start")
    assert unwired.value.code == "DEPENDENCY_UNAVAILABLE"
    assert words.approvals() == before


# --- 2. a changed subject between the calls is refused ------------------------------------


def test_a_subject_that_changed_between_the_calls_is_refused_and_shown_again(stage, words):
    rehearsing(stage)
    shown = words.decide("v1-restart-rehearsal")
    before = words.approvals()
    # The cutover record moves between the two calls: its revision is in the subject.
    stage.tool.machine.inventory_taken(cf.complete_inventory(
        stage.ledger, now=stage.clock())["inventoryId"])
    again = words.decide("v1-restart-rehearsal", {"confirm": shown["digest"]})
    assert again["state"] == "subject-changed" and again["digest"] != shown["digest"]
    assert words.approvals() == before
    # A confirmation with another subject's digest (the restart rehearsal's) records
    # nothing either.
    stage.isolation_passed()
    rehearsal = words.decide("v1-restart-rehearsal")
    words.command("rehearse-restart", words.decided("v1-restart-rehearsal"))
    stage.tool.check()
    other = words.decide("switch-start", {"confirm": rehearsal["digest"]})
    assert other["state"] == "subject-changed" and words.approvals() == before + 1


def test_the_decide_word_refuses_input_outside_its_form(stage, words):
    rehearsing(stage)
    for kind, document, reason in (
        ("drop-everything", {}, "decision-kind-outside-its-set"),
        ("v1-restart-rehearsal", {"decision": "maybe"}, "decision-outside-its-set"),
        ("v1-restart-rehearsal", {"confirm": "short"}, "confirm-is-the-shown-digest"),
        ("v1-restart-rehearsal", {"extra": 1}, "word-or-input-refused"),
    ):
        with pytest.raises(OperationsError) as refused:
            words.decide(kind, document)
        assert refused.value.current["reasonKey"] == reason
    with pytest.raises(OperationsError) as refused:
        words.decide("switch-start", {})  # not ready to switch yet
    assert refused.value.current["reasonKey"] == "cutover-state-differs"
    with pytest.raises(OperationsError) as refused:
        run_word(stage.tool, "decide", {}, kind="settlement", in_person=None)
    assert refused.value.code == "DEPENDENCY_UNAVAILABLE"


# --- 3. a recorded approval is taken by its cutover command and by no other ----------------


def refused(call) -> str:
    with pytest.raises(OperationsError) as error:
        call()
    return error.value.current.get("reasonKey")


def test_an_approval_is_taken_by_its_command_and_by_no_other(stage, words):
    rehearsing(stage)
    rehearsal = words.decided("v1-restart-rehearsal")
    stage.isolation_passed()
    words.command("rehearse-restart", rehearsal)
    stage.tool.check()
    start = words.decided("switch-start")
    # The rehearsal's approval, with the switch's subject, does not start the switch.
    assert refused(lambda: run_word(stage.tool, "start", {
        "approvalId": rehearsal["approvalId"], "subject": start["subject"]})) == (
        "decision-required")
    assert stage.tool.machine.current()["state"] == "ready-to-switch"
    words.command("start", start)
    report = words.decided("final-report")
    # The switch-start approval is not a final-report decision, nor an opening.
    assert refused(lambda: run_word(stage.tool, "start", {
        "approvalId": start["approvalId"]})) == "decision-required"
    words.command("start", report)
    opening = words.decided("admission-opening", {"providersAcceptedUnavailable": []})
    assert refused(lambda: run_word(stage.tool, "open", {
        "approvalId": start["approvalId"], "subject": opening["subject"]})) == (
        "decision-required")
    words.command("open", opening)
    record = stage.tool.machine.current()
    stage.clock.advance(record["rollbackWindowSeconds"] + 60)
    settlement = words.decided("settlement")
    # Neither the opening's approval settles, nor settlement's starts a rollback.
    assert refused(lambda: run_word(stage.tool, "settle", {
        "approvalId": opening["approvalId"]})) == "decision-required"
    assert refused(lambda: run_word(stage.tool, "rehearse-restart", {
        "approvalId": settlement["approvalId"]})) == "decision-required"
    assert stage.tool.machine.current()["state"] == "switched"
    assert words.command("settle", settlement)["state"] == "settled"


# --- 4. a cutover command without an approval is refused --------------------------------------


def test_each_command_without_an_approval_is_refused_before_any_effect(stage, words):
    rehearsing(stage)
    effects = len(stage.ledger.records("receipt-facts"))
    assert refused(lambda: run_word(stage.tool, "rehearse-restart", {})) == "decision-required"
    assert len(stage.ledger.records("receipt-facts")) == effects  # nothing was stopped
    assert (stage.journey.tunnel() or {}).get("origin") != "maintenance"
    words.command("rehearse-restart", words.decided("v1-restart-rehearsal"))
    stage.isolation_passed()
    stage.tool.check()
    assert refused(lambda: run_word(stage.tool, "start", {})) == "decision-required"
    assert stage.tool.machine.current()["state"] == "ready-to-switch"
    words.command("start", words.decided("switch-start"))
    # Without the final-report decision the switch waits; it does not go on.
    assert run_word(stage.tool, "start", {})["waiting"] == "final-report"
    words.command("start", words.decided("final-report"))
    assert refused(lambda: run_word(stage.tool, "open", {})) == "decision-required"
    words.command("open", words.decided("admission-opening",
                                        {"providersAcceptedUnavailable": []}))
    assert refused(lambda: run_word(stage.tool, "rollback", {})) == "decision-required"
    assert refused(lambda: run_word(stage.tool, "settle", {})) == "decision-required"
    stage.probes.v1 = False
    words.command("rollback", words.decided("rollback"))
    assert refused(lambda: run_word(stage.tool, "cancel-rollback", {})) == "decision-required"
    assert stage.tool.machine.current()["state"] == "rolling-back"


# --- the providers in the maintainer-only window (U8 plan Step 107(h); CP-3) ---------------


def provider_window(stage: Stage, words: Words, tmp_path):
    """(Step 107(h)'s `window`, named apart from the latency `window` above.) To the
    maintainer-only window through the decide word, then a live
    ProviderActivation over the stage's ledger on its clock, with a maintainer of the
    test's own, every provider configured and a previews folder of its own; the stage's
    provider words are the function the production tool's words run."""
    from backend.modules.operations.provider_activation import (
        PROVIDERS,
        ActivationSettings,
        ProviderActivation,
        provider_word,
    )

    ready(stage, words)
    first = words.command("start", words.decided("switch-start"))
    assert first["waiting"] == "final-report", first
    second = words.command("start", words.decided("final-report"))
    assert second == {"state": "switching", "waiting": "maintainer-window"}, second
    folder = tmp_path / "activation"
    folder.mkdir(mode=0o700)
    settings = ActivationSettings("live", uuid4(), frozenset(PROVIDERS), folder / "previews")
    activation = ProviderActivation(stage.ledger, settings, clock=stage.clock)
    activation.start()
    stage.platform.provider_word = lambda word, document: provider_word(activation, word,
                                                                        document)
    return activation


def test_the_window_approves_each_provider_through_the_decide_word(stage, words, tmp_path):
    from backend.modules.accounts.integrations import account_mail
    from backend.modules.operations.provider_activation import ProviderActivation

    activation = provider_window(stage, words, tmp_path)
    content = b'{"to": ["maintainer@fixture.example.com"], "subject": "first"}'
    digest = activation.record_preview("resend", content)
    assert account_mail.gate_holds_all(activation)
    listed = run_word(stage.tool, "provider-previews", {"provider": "resend"})
    assert listed["previews"] == [{"digest": digest, "sizeBytes": len(content)}], listed
    shown = run_word(stage.tool, "provider-previews", {"provider": "resend", "digest": digest})
    assert shown["content"] == {"to": ["maintainer@fixture.example.com"], "subject": "first"}
    answer = words.decided("provider-first-effect", {"provider": "resend",
                                                     "previewDigest": digest})
    assert stage.ledger.get("maintainer-approval", answer["approvalId"])["subjectRef"] == (
        "provider:resend")
    applied = words.command("provider-decision", answer)
    assert (applied["providerState"], applied["approvalContentHash"]) == ("active", digest)
    assert activation.bounds_lifted("resend") and not account_mail.gate_holds_all(activation)
    google = words.command("provider-decision",
                           words.decided("provider-sign-in", {"provider": "google"}))
    assert google["providerState"] == "active", google
    # ORCID: a decision recorded, not applied, and then its real sign-in fails.
    orcid = words.decided("provider-sign-in", {"provider": "orcid"})
    failed = run_word(stage.tool, "provider-failed", {"provider": "orcid"})
    assert (failed["providerState"], failed["limitations"]) == (
        "unavailable", ["sign-in-verification-failed"])
    # v2 restarts: the approvals that hold are kept, the failure too.
    restarted = ProviderActivation(stage.ledger, activation.settings, clock=stage.clock)
    restarted.start()
    assert {provider: restarted.record(provider)["state"]
            for provider in ("resend", "google", "orcid", "notion")} == {
        "resend": "active", "google": "active", "orcid": "unavailable", "notion": "held"}
    opened = words.command("open", words.decided(
        "admission-opening", {"providersAcceptedUnavailable": ["notion", "orcid"]}))
    assert opened["state"] == "switched", opened
    # Reading CP-3(a): an outward provider accepted unavailable is approved after opening.
    page = restarted.record_preview("notion", b'{"page": "first"}')
    notion = words.command("provider-decision", words.decided(
        "provider-first-effect", {"provider": "notion", "previewDigest": page}))
    assert notion["providerState"] == "active" and restarted.state("notion") == "active"
    # A sign-in verification stays in the window.
    assert refused_with(lambda: words.command("provider-decision", orcid)) == (
        "CONFLICT", "sign-in-outside-the-window")
    assert refused_with(lambda: words.decide("provider-sign-in", {"provider": "orcid"})) == (
        "CONFLICT", "cutover-state-differs")
    assert refused_with(lambda: run_word(stage.tool, "provider-failed",
                                         {"provider": "orcid"})) == (
        "CONFLICT", "cutover-not-switching")


def test_a_superseded_or_unwired_provider_decision_changes_nothing(stage, words, tmp_path):
    activation = provider_window(stage, words, tmp_path)
    digest = activation.record_preview("resend", b'{"mail": "first"}')
    document = {"provider": "resend", "previewDigest": digest}
    approved = words.decided("provider-first-effect", document)
    declined = words.decided("provider-first-effect", {**document, "decision": "declined"})
    assert words.command("provider-decision", declined)["providerState"] == "held"
    assert refused_with(lambda: words.command("provider-decision", approved)) == (
        "CONFLICT", "approval-superseded")
    assert not {"approvedAt", "approvalId", "approvalContentHash"} & set(
        activation.record("resend"))
    count = words.approvals()
    assert refused_with(lambda: words.decide("provider-first-effect", {
        "provider": "resend", "previewDigest": "c" * 64})) == ("CONFLICT", "preview-not-recorded")
    assert words.approvals() == count
    latest = words.decided("provider-first-effect", document)
    edited = {**latest["subject"], "cutoverRevision": latest["subject"]["cutoverRevision"] + 1}
    assert refused_with(lambda: run_word(stage.tool, "provider-decision", {
        "approvalId": latest["approvalId"], "subject": edited})) == (
        "CONFLICT", "approval-subject-differs")
    assert activation.state("resend") == "held"
    stage.platform.provider_word = None
    count = words.approvals()
    unwired = ("DEPENDENCY_UNAVAILABLE", "provider-words-unwired")
    assert refused_with(lambda: run_word(stage.tool, "provider-previews",
                                         {"provider": "resend"})) == unwired
    assert refused_with(lambda: words.command("provider-decision", latest)) == unwired
    assert refused_with(lambda: run_word(stage.tool, "provider-failed",
                                         {"provider": "orcid"})) == unwired
    assert refused_with(lambda: words.decide("provider-first-effect", document)) == unwired
    assert refused_with(lambda: words.decide("provider-sign-in", {"provider": "orcid"})) == (
        unwired)
    assert words.approvals() == count and activation.state("resend") == "held"
