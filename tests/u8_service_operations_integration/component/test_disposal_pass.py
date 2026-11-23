"""The disposal pass and the rehearsal database's order (U8 plan Step 34; Workflow 14 step
4, Workflow 19 steps 8–9, BR9.12, BR9.15, BR9.17).

Databases are removed through PlatformControl's `platform.database.remove` on the
composed realm's store and realm driver: a disposable database of the test's own in the
realm's instance, dropped through the scheduler's stand-in login. The backup volume's
pass is the agent's `dispose-due`, recorded by a stand-in that answers as the agent
does, so every report category is seen. The rehearsal database's fixed order (profile,
database, then sets) runs end to end: the realm's backup agent writes a real rehearsal
set of the test's own rehearsal database onto the journey's stand-in volume and deletes
it on its own catalogue's terms once the database is gone.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from uuid import uuid4

import pytest
from psycopg import sql

from backend.modules.operations.incidents import Incidents
from backend.modules.operations.recovery import RecoveryRequests
from backend.modules.operations.retained_copies import RetainedCopies
from backend.u8_policy import SYNTHETIC_OPERATIONS
from docsuri_ops.arrangement.paths import DatabaseNames
from docsuri_ops.cutover.disposal import DisposalPass, DisposalPlatform
from docsuri_ops.cutover.preconditions import SwitchEvidence
from docsuri_ops.cutover.tool import CutoverPlatform, CutoverTool, StepFailed, run_word
from docsuri_ops.platform_control import enums
from docsuri_ops.u8_platform.recovery_words import realm_procedures
from docsuri_ops.u8_platform.u8_protocols import (
    PreconditionRefused,
    ReceiptReader,
    realm_facts,
    realm_operator,
)
from tests.u8_service_operations_integration import cutover_flows as cf
from tests.u8_service_operations_integration import platform_flows as pf
from tests.u8_service_operations_integration import recovery_flows as rf

DAY = 86400
NAMES = DatabaseNames("docsuri_u8")


@pytest.fixture
def ledger(tmp_path, clock):
    value = rf.open_ledger(tmp_path, clock)
    yield value
    value.close()


class Agent:
    """The agent's `dispose-due`, recorded: it answers with the report it is given."""

    def __init__(self, report: dict | None = None, *, fail: bool = False):
        self.report, self.fail, self.documents = report or {}, fail, []

    def __call__(self, document: dict) -> dict:
        self.documents.append(document)
        if self.fail:
            raise RuntimeError("backup-volume-unavailable")
        return {"disposed": [], "held": [], "released": [], "unrecorded": [],
                "mismatched": [], "refused": [], "refusedClaims": [], "swept": 0,
                **self.report}


def realm_databases(realm) -> set[str]:
    with rf.admin(realm) as conn:
        return {row[0] for row in conn.execute("SELECT datname FROM pg_database").fetchall()}


def disposable(realm, kind: str, names: DatabaseNames = NAMES) -> str:
    name = names.new(kind)
    with rf.admin(realm) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER docsuri_disposable TEMPLATE template1")
                     .format(sql.Identifier(name)))
    return name


def operator_for(tmp_path, realm, ledger, clock, *, names: DatabaseNames = NAMES,
                 rehearsal: str | None = None, role: str = "scheduler", **config):
    """The realm's standing authority (the scheduler's grants), as the standing job runs
    the pass; `role="operator"` for the cutover tool's in-person steps."""
    journey = pf.journey(tmp_path, realm, rehearsal=rehearsal, **config)
    base = realm_facts(journey.profile, ledger, clock=clock,
                       databases=lambda: realm_databases(realm))

    def facts():
        current = base()
        current.names = names
        return current

    return journey, facts, realm_operator(journey.profile, role, ledger, clock=clock,
                                          facts=facts)


def disposal(ledger, clock, operator, facts, agent, *, copy_paths=None) -> DisposalPass:
    # Where the standing job serves (L1-65): live when the journey's mode is live,
    # otherwise rehearsal, as `realm_parts` binds it.
    platform = DisposalPlatform(operator=operator, names=facts().names,
                                current_rehearsal=lambda: facts().current_rehearsal,
                                dispose_due=agent, via="standing",
                                environment=lambda: "live" if facts().mode == "live"
                                else "rehearsal",
                                copy_paths=copy_paths or (lambda record: []))
    return DisposalPass(ledger, SYNTHETIC_OPERATIONS, platform, clock=clock)


def test_the_pass_is_refused_while_the_live_exclusion_is_held(tmp_path, realm, ledger, clock):
    _, facts, operator = operator_for(tmp_path, realm, ledger, clock)
    agent = Agent()
    cutover, _ = cf.switching(ledger, clock)
    assert disposal(ledger, clock, operator, facts, agent).run() == {
        "ran": False, "reason": "live-exclusion-held"}
    cutover.abort(reason="operator-abort")
    assert disposal(ledger, clock, operator, facts, agent).run()["reason"] == (
        "live-exclusion-held")
    cutover.aborted()
    # A production restore holds it too, from its admission until it ends.
    requests = RecoveryRequests(ledger, SYNTHETIC_OPERATIONS, clock=clock,
                                mfa_current=lambda *_: True)
    backup = rf.set_record(ledger, now=clock())
    request = requests.request(origin="administrator", operation="restore.production",
                               environment="live", target_id=backup["backupId"],
                               expected_revision=1, submission_id=uuid4(),
                               requested_by=uuid4(), mfa_verified_at=rf.utc_text(clock()))
    approval = rf.approval_record(ledger, "production-restore", request["recoveryRequestId"],
                                  now=clock())
    requests.admit(request["recoveryRequestId"], approval_id=approval["approvalId"])
    assert disposal(ledger, clock, operator, facts, agent).run()["reason"] == (
        "production-restore-active")
    assert agent.documents == []  # nothing was asked of the agent


@pytest.mark.parametrize("kind", ["import", "scratch", "rehearsal"])
def test_a_database_at_its_backstop_is_removed_by_the_standing_authority(
    tmp_path, realm, ledger, clock, kind
):
    """BR9.17: at its backstop date, unattended, through the scheduler's grant and the
    scheduler's database login; the receipt is the standing actor's."""
    _, facts, operator = operator_for(tmp_path, realm, ledger, clock)
    assert operator.standing is True
    copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
    name = disposable(realm, kind)
    copy_kind = {"import": "import-database", "scratch": "scratch-restore",
                 "rehearsal": "rehearsal-database"}[kind]
    copy = copies.record(copy_kind, "run:fixture", [f"database/{name}"])
    try:
        report = disposal(ledger, clock, operator, facts, Agent()).run()
        assert report["databases"] == [] and name in realm_databases(realm)  # not yet due
        if kind == "scratch":
            # A left-behind scratch copy is kept a second before its one-day backstop.
            created = dt.datetime.fromisoformat(copy["createdAt"].replace("Z", "+00:00"))
            clock.now = created + dt.timedelta(seconds=86_399)
            report = disposal(ledger, clock, operator, facts, Agent()).run()
            assert report["databases"] == [] and name in realm_databases(realm)
            clock.now = created + dt.timedelta(seconds=86_401)
        else:
            clock.now = copies.backstop_of(copy) + dt.timedelta(seconds=1)
        report = disposal(ledger, clock, operator, facts, Agent()).run()
        assert report["databases"] == [copy["copyId"]], report
        assert name not in realm_databases(realm)
        disposed = copies.get(copy["copyId"])
        assert "disposedAt" in disposed and "disposalPendingSince" not in disposed
        facts_record = ledger.get("receipt-facts", disposed["disposalReceiptRef"])
        assert facts_record["operation"] == "platform.database.remove"
        assert facts_record["targetId"] == f"database-{kind}"
        removal = operator.authorities[enums.CLASS_DESTRUCTIVE]
        receipt = operator.store.call_committed(
            "read_receipt_named", (operator.actor, removal, facts_record["operationId"]))
        assert ReceiptReader.outcome(receipt) == "succeeded"
        assert receipt["operation"] == "platform.database.remove"
        assert receipt["targetId"] == f"database-{kind}"
    finally:
        rf.drop_database(realm, name)


class FailOnce:
    """The realm's operator, with its first database removal failed through U7's injected
    permission fault: a failed receipt bound under the pass's fixed key."""

    def __init__(self, operator):
        self.operator, self.failed = operator, []

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key, **options):
        if operation == "platform.database.remove" and not self.failed:
            self.failed.append(key)
            return self.operator.execute(operation, target, inputs, key=key,
                                         injected_fault="permission", **options)
        return self.operator.execute(operation, target, inputs, key=key, **options)


def test_a_kept_scratch_copy_whose_removal_failed_is_removed_by_the_next_pass(
    tmp_path, realm, ledger, clock
):
    """A verification kept its scratch database (its drop failed): its copy holds NFR8.15's
    one scratch slot. At its 1-day backstop the pass's removal fails once (a failed
    receipt bound under `disposal:<copyId>:<name>`); the next pass runs it again under its
    next retry key, removes it and frees the slot, with no in-person word."""
    from docsuri_ops.u8_platform.u8_protocols import database_limit_reason

    _, facts, operator = operator_for(tmp_path, realm, ledger, clock)
    copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
    name = disposable(realm, "scratch")
    copy = copies.record("scratch-restore", f"verification:{uuid4()}", [f"database/{name}"])
    try:
        assert database_limit_reason("scratch", ledger, NAMES) == "scratch-database-limit"
        clock.now = copies.backstop_of(copy) + dt.timedelta(seconds=1)
        failing = FailOnce(operator)
        report = disposal(ledger, clock, failing, facts, Agent()).run()
        assert failing.failed == [f"disposal:{copy['copyId']}:{name}"]
        assert report["pending"] == [copy["copyId"]] and report["databases"] == []
        assert name in realm_databases(realm)
        assert "disposalPendingSince" in copies.get(copy["copyId"])
        # The failed removal is a failed attempt (Step 64(i)).
        assert copies.get(copy["copyId"])["lastDisposalFailedAt"] == rf.utc_text(clock())
        assert database_limit_reason("scratch", ledger, NAMES) == "scratch-database-limit"
        # The next pass: the failure is replayed, then retried under the next key.
        report = disposal(ledger, clock, failing, facts, Agent()).run()
        assert report["databases"] == [copy["copyId"]], report
        assert name not in realm_databases(realm)
        disposed = copies.get(copy["copyId"])
        assert "disposedAt" in disposed and "disposalPendingSince" not in disposed
        assert database_limit_reason("scratch", ledger, NAMES) is None  # the slot is free
        # A third pass finds nothing left to do.
        assert disposal(ledger, clock, operator, facts, Agent()).run()["databases"] == []
    finally:
        rf.drop_database(realm, name)


def test_the_volume_is_disposed_only_by_the_agent_and_each_record_follows(tmp_path, realm,
                                                                          ledger, clock):
    _, facts, operator = operator_for(tmp_path, realm, ledger, clock)
    copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
    backup = rf.set_record(ledger, now=clock())
    kept = rf.set_record(ledger, now=clock())
    snapshot = copies.record("v1-final-snapshot", "run:final", ["backup-volume:x:database"],
                             dispose_after=clock() + dt.timedelta(days=30), approval_id=uuid4())
    snapshot_path = "archives/final-snapshot-20261022T120000-x.archive"
    agent = Agent({"disposed": [backup["location"], snapshot_path], "held": [kept["location"]],
                   "unrecorded": ["archives/stray.archive"],
                   "refusedClaims": [kept["location"]]})
    report = disposal(ledger, clock, operator, facts, agent,
                      copy_paths=lambda record: [snapshot_path]).run()
    document = agent.documents[0]
    assert set(document["ledgerPaths"]) == {backup["location"], kept["location"], snapshot_path}
    assert {claim["path"] for claim in document["claims"]} == set(document["ledgerPaths"])
    assert "disposedAt" in ledger.get("backup-set", backup["backupId"])
    assert "heldByFloorSince" in ledger.get("backup-set", kept["backupId"])
    record = copies.get(snapshot["copyId"])
    assert record["disposalAgentRef"] == f"agent-disposed:{snapshot_path}"
    # The journey is in rehearsal mode, so the pass's incident opens there (L1-65).
    incident = Incidents(ledger, environment="rehearsal").open_for("storage.capacity")
    assert Incidents(ledger, environment="live").open_for("storage.capacity") is None
    assert any("stray" in ref for ref in incident["correlationIds"])
    assert any(ref.startswith("backup-volume:refusedClaims") for ref in incident["correlationIds"])
    assert set(report["incidents"]) >= {"unrecorded:archives/stray.archive",
                                        f"refusedClaims:{kept['location']}"}


def test_v1s_stores_go_only_in_person_at_their_point_and_not_before(tmp_path, realm, ledger,
                                                                   clock):
    """Two `v1-stores` copies with the date L1-3 derives, D = admission opening + 90 days
    (a literal here): nothing before D, both listed in person at D and neither disposed
    of by the pass; the in-person deletion is refused before D and accepted at D; past the
    180-day backstop only the copy still in place opens an incident."""
    from backend.modules.operations.errors import OperationsError

    _, facts, operator = operator_for(tmp_path, realm, ledger, clock)
    copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
    clock.now = dt.datetime(2026, 12, 1, 0, 0, tzinfo=dt.UTC)  # admission opening
    point = dt.datetime(2027, 3, 1, 0, 0, tzinfo=dt.UTC)  # opening + 90 days
    first, second = (copies.record("v1-stores", "cutover:fixture", [f"v1-stores/{name}"],
                                   dispose_after=point, approval_id=uuid4())
                     for name in ("database", "uploads"))
    clock.now = point - dt.timedelta(seconds=1)
    assert disposal(ledger, clock, operator, facts, Agent()).run()["inPerson"] == []
    check = rf.receipt("platform.copy.dispose", "copies", now=clock())
    with pytest.raises(OperationsError) as early:
        copies.disposed_in_person(first["copyId"], check, "check:v1-stores")
    assert early.value.current == {"reasonKey": "before-approved-date"}
    clock.now = point
    report = disposal(ledger, clock, operator, facts, Agent()).run()
    assert sorted(report["inPerson"]) == sorted([first["copyId"], second["copyId"]])
    assert all("disposedAt" not in copies.get(item["copyId"]) for item in (first, second))
    copies.disposed_in_person(first["copyId"], rf.receipt("platform.copy.dispose", "copies",
                                                          now=clock()), "check:v1-stores")
    created = dt.datetime(2026, 12, 1, 0, 0, tzinfo=dt.UTC)
    clock.now = created + dt.timedelta(days=180, seconds=1)
    report = disposal(ledger, clock, operator, facts, Agent()).run()
    assert report["incidents"] == [f"backstop:{second['copyId']}"]


def test_v1s_stores_are_left_for_the_operator_in_person(tmp_path, realm, ledger, clock):
    _, facts, operator = operator_for(tmp_path, realm, ledger, clock)
    copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
    stores = copies.record("v1-stores", "cutover:fixture", ["v1-stores/database"],
                           dispose_after=clock() + dt.timedelta(days=90), approval_id=uuid4())
    clock.advance(91 * DAY)
    report = disposal(ledger, clock, operator, facts, Agent()).run()
    assert report["inPerson"] == [stores["copyId"]] and report["incidents"] == []
    clock.advance(90 * DAY)  # past the 180-day backstop, still in place
    report = disposal(ledger, clock, operator, facts, Agent()).run()
    assert report["incidents"] == [f"backstop:{stores['copyId']}"]
    assert "disposedAt" not in copies.get(stores["copyId"])


def test_a_pending_disposal_is_retried_and_opens_an_incident_past_its_backstop(
    tmp_path, realm, ledger, clock
):
    _, facts, operator = operator_for(tmp_path, realm, ledger, clock)
    backup = rf.set_record(ledger, now=clock())
    clock.advance(15 * DAY)
    unreachable = Agent(fail=True)
    report = disposal(ledger, clock, operator, facts, unreachable).run()
    assert report["volume"] == {"refused": "RuntimeError"}
    assert report["pending"] == [backup["backupId"]]
    pending = ledger.get("backup-set", backup["backupId"])["disposalPendingSince"]
    # Each failed pass records its own time; `disposalPendingSince` keeps the first.
    assert ledger.get("backup-set", backup["backupId"])["lastDisposalFailedAt"] == pending
    clock.advance(DAY + 1)
    report = disposal(ledger, clock, operator, facts, unreachable).run()
    assert ledger.get("backup-set", backup["backupId"])["disposalPendingSince"] == pending
    second = rf.utc_text(clock())
    assert ledger.get("backup-set", backup["backupId"])["lastDisposalFailedAt"] == second
    assert report["incidents"] == [f"pending:{backup['backupId']}"]
    retried = disposal(ledger, clock, operator, facts,
                       Agent({"disposed": [backup["location"]]})).run()
    assert retried["ran"]
    record = ledger.get("backup-set", backup["backupId"])
    assert "disposedAt" in record and "disposalPendingSince" not in record
    assert record["lastDisposalFailedAt"] == second  # a later disposal keeps it


def test_a_rehearsal_database_the_profile_names_is_never_removed_at_its_backstop(
    tmp_path, realm, ledger, clock
):
    name = disposable(realm, "rehearsal")
    try:
        _, facts, operator = operator_for(tmp_path, realm, ledger, clock, rehearsal=name)
        cutover, _ = cf.rehearsing(ledger, clock)
        copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
        copy = copies.record("rehearsal-database", "run:fixture", [f"database/{name}"])
        clock.advance(61 * DAY)
        report = disposal(ledger, clock, operator, facts, Agent()).run()
        assert report["pending"] == [copy["copyId"]] and name in realm_databases(realm)
        assert cutover.current()["state"] == "preparing"  # back to preparing (BR9.12)
        assert Incidents(ledger, environment="rehearsal").open_for("storage.capacity")
        # Still in use at its backstop is no failed attempt (Step 64(i)).
        assert "lastDisposalFailedAt" not in copies.get(copy["copyId"])
    finally:
        rf.drop_database(realm, name)


def test_a_refused_dispose_due_marks_only_the_failed_disposals(tmp_path, realm, ledger, clock):
    _, facts, operator = operator_for(tmp_path, realm, ledger, clock)
    copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
    removed = NAMES.new("rehearsal")
    copy = copies.record("rehearsal-database", "run:fixture", [f"database/{removed}"])
    copies.disposed_by_agent(copy["copyId"], f"agent-disposed:{removed}")
    live = rf.set_record(ledger, now=clock())
    waiting = rf.set_record(ledger, environment="rehearsal", now=clock(), database=removed)
    clock.advance(15 * DAY)
    report = disposal(ledger, clock, operator, facts, Agent(fail=True)).run()
    assert waiting["backupId"] in report["waitingSets"]
    failed = ledger.get("backup-set", live["backupId"])
    assert failed["lastDisposalFailedAt"] == rf.utc_text(clock())
    left = ledger.get("backup-set", waiting["backupId"])
    assert "disposalPendingSince" in left and "lastDisposalFailedAt" not in left


def test_the_pass_opens_its_incidents_where_the_standing_job_serves(tmp_path, realm, ledger,
                                                                     clock):
    """L1-65: on a journey in rehearsal mode the pass's storage incidents open in
    rehearsal; after the switch to live they open on live, and the rehearsal incident
    stays on the rehearsal list."""
    journey, facts, operator = operator_for(tmp_path, realm, ledger, clock)
    copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
    backup = rf.set_record(ledger, now=clock())
    snapshot = copies.record("dry-run-snapshot", "run:fixture", ["backup-volume:x:database"])
    clock.advance(15 * DAY)
    report = disposal(ledger, clock, operator, facts, Agent(fail=True)).run()
    assert backup["backupId"] in report["pending"]
    assert f"backstop:{snapshot['copyId']}" in report["incidents"]
    clock.advance(DAY + 1)
    stray = Agent({"unrecorded": ["archives/stray.archive"]})
    disposal(ledger, clock, operator, facts, stray).run()
    expected = {f"retained-copy:{snapshot['copyId']}:backstop",
                f"backup-set:{backup['backupId']}:pending",
                "backup-volume:unrecorded:archives/stray.archive"}
    rehearsal = Incidents(ledger, environment="rehearsal").open_for("storage.capacity")
    assert expected <= set(rehearsal["correlationIds"])
    assert Incidents(ledger, environment="live").open_for("storage.capacity") is None
    journey.set_profile(mode="live")
    disposal(ledger, clock, operator, facts, stray).run()
    live = Incidents(ledger, environment="live").open_for("storage.capacity")
    assert expected <= set(live["correlationIds"])
    still = Incidents(ledger, environment="rehearsal").open_for("storage.capacity")
    assert still["incidentId"] == rehearsal["incidentId"]
    assert expected <= set(still["correlationIds"])


class Recording:
    """The realm's operator, with each bound operation's name recorded in order."""

    def __init__(self, operator):
        self.operator, self.order = operator, []

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key, **options):
        self.order.append(operation.removeprefix("platform."))
        return self.operator.execute(operation, target, inputs, key=key, **options)


def test_the_rehearsal_order_is_profile_then_database_then_sets(tmp_path, realm, ledger, clock):
    database = rf.JourneyDatabase(realm).create()
    rehearsal = disposable(realm, "rehearsal", database.names)
    with rf.admin(realm) as conn:
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO docsuri_backup_agent").format(
            sql.Identifier(rehearsal)))
    with rf.admin(realm, rehearsal) as conn:
        conn.execute("CREATE TABLE rehearsal_rows(id int PRIMARY KEY)")
        conn.execute("INSERT INTO rehearsal_rows VALUES (1)")
    try:
        agent = rf.journey_agent(tmp_path, realm, database, clock)
        # The cutover tool's in-person steps: the operator's grants.
        journey, facts, operator = operator_for(tmp_path, realm, ledger, clock,
                                                names=database.names, rehearsal=rehearsal,
                                                role="operator", agentFolder=str(agent))
        rf.cutover_record(ledger, "preparing")
        procedures = realm_procedures(journey.profile, ledger, clock=clock, ready=lambda: True,
                                      names=database.names).procedures
        requests = procedures.requests
        request = requests.request(origin="schedule", operation="backup.create",
                                   environment="rehearsal", target_id=rehearsal,
                                   expected_revision=0, submission_id=uuid4())
        requests.admit(request["recoveryRequestId"])
        assert procedures.backup(request["recoveryRequestId"],
                                 via="in-person")["state"] == "succeeded"
        backup = next(item for item in ledger.records("backup-set")
                      if item["environment"] == "rehearsal")
        copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
        copies.record("rehearsal-database", "run:fixture", [f"database/{rehearsal}"])
        recording = Recording(operator)
        evidence = SwitchEvidence(lambda run: None, lambda: None, lambda cutover: None,
                                  lambda: {}, lambda: "stand-in", None, lambda: rehearsal)
        tool = CutoverTool(ledger, SYNTHETIC_OPERATIONS, CutoverPlatform(
            operator=recording, production=database.name, v1_labels=(), v2_labels=(),
            v2_ready=lambda: True, v1_ready=lambda: True, public=lambda kind: True,
            evidence=evidence, evidence_folder=tmp_path / "cutover-evidence"), clock=clock)
        record = tool.machine.current()
        set_inputs = {"recordKind": "BackupSet", "recordId": backup["backupId"],
                      "place": "backup-volume", "location": backup["location"],
                      "event": "rehearsal-database-removed"}
        # The sets cannot go first: the profile still names the database.
        with pytest.raises(StepFailed, match="current-rehearsal-database"):
            tool._effect("platform.copy.dispose", "copies", set_inputs, key=f"early-{uuid4()}")
        tool._profile(record, "rehearsalDatabase", None, f"clear-{uuid4()}")
        # Nor before the database is removed.
        with pytest.raises(StepFailed, match="rehearsal-database-not-removed"):
            tool._effect("platform.copy.dispose", "copies", set_inputs, key=f"early-{uuid4()}")
        recording.order.clear()
        result = tool.after_opening(record)
        assert recording.order == ["profile.rehearsal-database", "database.remove",
                                   "copy.dispose"]
        assert result["rehearsalSetsDisposed"] == [backup["backupId"]], result
        assert rehearsal not in realm_databases(realm)
        assert "disposedAt" in ledger.get("backup-set", backup["backupId"])
        assert journey.read_state("profile.json")["rehearsalDatabase"] is None
        assert not (tmp_path / "volume" / "docsuri-v2" / backup["location"]).exists()
    finally:
        rf.drop_database(realm, rehearsal)
        database.drop()


class DisposeFails(Recording):
    """The realm's operator, with every set disposal failed through U7's injected
    permission fault while `failing` is set."""

    failing = True

    def execute(self, operation, target, inputs, *, key, **options):
        self.order.append(operation.removeprefix("platform."))
        if self.failing and operation == "platform.copy.dispose":
            return self.operator.execute(operation, target, inputs, key=key,
                                         injected_fault="permission", **options)
        return self.operator.execute(operation, target, inputs, key=key, **options)


def left_with_a_waiting_set(tmp_path, realm, ledger, clock):
    """A real rehearsal set on the journey's volume (the realm's backup agent wrote it)
    whose database the cutover removed while its set's disposal failed, so the set
    waits: what a rollback's left database (or opening's) leaves after a transient
    failure. Answers what a test needs, and the cleanup."""
    database = rf.JourneyDatabase(realm).create()
    rehearsal = disposable(realm, "rehearsal", database.names)
    with rf.admin(realm) as conn:
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO docsuri_backup_agent").format(
            sql.Identifier(rehearsal)))
    with rf.admin(realm, rehearsal) as conn:
        conn.execute("CREATE TABLE rehearsal_rows(id int PRIMARY KEY)")
        conn.execute("INSERT INTO rehearsal_rows VALUES (1)")

    def cleanup():
        rf.drop_database(realm, rehearsal)
        database.drop()

    agent = rf.journey_agent(tmp_path, realm, database, clock)
    journey, facts, operator = operator_for(tmp_path, realm, ledger, clock,
                                            names=database.names, rehearsal=rehearsal,
                                            role="operator", agentFolder=str(agent))
    rf.cutover_record(ledger, "preparing")
    procedures = realm_procedures(journey.profile, ledger, clock=clock, ready=lambda: True,
                                  names=database.names).procedures
    request = procedures.requests.request(origin="schedule", operation="backup.create",
                                          environment="rehearsal", target_id=rehearsal,
                                          expected_revision=0, submission_id=uuid4())
    procedures.requests.admit(request["recoveryRequestId"])
    assert procedures.backup(request["recoveryRequestId"], via="in-person")["state"] == (
        "succeeded")
    backup = next(item for item in ledger.records("backup-set")
                  if item["environment"] == "rehearsal")
    copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
    copies.record("rehearsal-database", "run:fixture", [f"database/{rehearsal}"])
    failing = DisposeFails(operator)
    evidence = SwitchEvidence(lambda run: None, lambda: None, lambda cutover: None,
                              lambda: {}, lambda: "stand-in", None, lambda: rehearsal)
    tool = CutoverTool(ledger, SYNTHETIC_OPERATIONS, CutoverPlatform(
        operator=failing, production=database.name, v1_labels=(), v2_labels=(),
        v2_ready=lambda: True, v1_ready=lambda: True, public=lambda kind: True,
        evidence=evidence, evidence_folder=tmp_path / "cutover-evidence"), clock=clock)
    result = tool.after_opening(tool.machine.current())
    assert rehearsal not in realm_databases(realm)
    assert [item["backupId"] for item in result["rehearsalSetsWaiting"]] == [
        backup["backupId"]], result
    assert "disposedAt" not in ledger.get("backup-set", backup["backupId"])
    archive = tmp_path / "volume" / "docsuri-v2" / backup["location"]
    assert archive.exists()
    return SimpleNamespace(journey=journey, facts=facts, operator=operator, tool=tool,
                           failing=failing, backup=backup, rehearsal=rehearsal,
                           archive=archive, cleanup=cleanup)


def test_a_standing_pass_reports_a_left_set_and_disposes_of_none(tmp_path, realm, ledger,
                                                                 clock):
    """Your decision of 2026-10-26, "Only in person": the standing disposal pass disposes
    of no left set by event. It reports the set as waiting and marks it pending, binds no
    disposal, leaves its real archive in place, and a set still waiting a day later opens
    the storage incident as built; a set whose database is still there is not reported."""
    left = left_with_a_waiting_set(tmp_path, realm, ledger, clock)
    try:
        standing = Recording(realm_operator(left.journey.profile, "scheduler", ledger,
                                            clock=clock, facts=left.facts))
        kept = rf.set_record(ledger, environment="rehearsal", now=clock(),
                             database=left.facts().current_rehearsal or "docsuri_u8_kept")
        pass_ = disposal(ledger, clock, standing, left.facts, Agent())
        assert left.rehearsal in pass_.removed_rehearsal_databases()
        report = pass_.run()
        assert report["waitingSets"] == [left.backup["backupId"]], report
        assert left.backup["backupId"] in report["pending"]
        assert "copy.dispose" not in standing.order  # nothing bound by event
        record = ledger.get("backup-set", left.backup["backupId"])
        assert "disposalPendingSince" in record and "disposedAt" not in record
        assert left.archive.exists()
        assert "disposalPendingSince" not in ledger.get("backup-set", kept["backupId"])
        # The record is preparing, so the set's in-person retry is `cutover check`.
        assert report["waitingRemedy"] == "cutover-check"
        # Waiting a day: the storage incident opens naming that command, and still nothing
        # is disposed.
        clock.advance(SYNTHETIC_OPERATIONS.staging_file_backstop_seconds + 60)
        later = disposal(ledger, clock, standing, left.facts, Agent()).run()
        assert f"waiting:{left.backup['backupId']}:cutover-check" in later["incidents"], later
        # The journey is in rehearsal mode: the incident opens there (L1-65).
        incident = Incidents(ledger, environment="rehearsal").open_for("storage.capacity")
        assert f"backup-set:{left.backup['backupId']}:waiting:cutover-check" in (
            incident["correlationIds"])
        assert later["waitingSets"] == [left.backup["backupId"]]
        assert left.archive.exists() and "copy.dispose" not in standing.order
    finally:
        left.cleanup()


# --- the in-person retry of each kind of waiting set (review finding, Major, R16) ----------


class Faults(Recording):
    """The realm's operator, with U7's injected permission fault on every database removal
    while `removals` holds (only the databases `only` names, when it names any) and on
    every set disposal while `disposals` holds."""

    removals = disposals = False
    only: frozenset[str] = frozenset()

    def execute(self, operation, target, inputs, *, key, **options):
        self.order.append(operation.removeprefix("platform."))
        if (self.removals and operation == "platform.database.remove" and (
                not self.only or inputs.get("database") in self.only)) or (
                self.disposals and operation == "platform.copy.dispose"):
            return self.operator.execute(operation, target, inputs, key=key,
                                         injected_fault="permission", **options)
        return self.operator.execute(operation, target, inputs, key=key, **options)


def staged(tmp_path, realm, clock):
    """The cutover words' stage (real switch, opening and rollback on the realm's store),
    with the realm's backup agent on its own stand-in volume and one real rehearsal
    database, recorded as a retained copy, whose real rehearsal set lies on that volume.
    Answers the stage, the database, its set, the set's archive and the operator's
    fault wrapper (installed on the cutover tool)."""
    from tests.u8_service_operations_integration.component.test_cutover_words import Stage

    stage = Stage(tmp_path, realm, clock)
    agent = rf.journey_agent(tmp_path, realm, stage.database, clock)
    pf._private_file(stage.journey.profile.effects_root / "driver.json",
                     {**stage.journey.config, "agentFolder": str(agent)})
    name = disposable(realm, "rehearsal", stage.database.names)
    with rf.admin(realm) as conn:
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO docsuri_backup_agent").format(
            sql.Identifier(name)))
    with rf.admin(realm, name) as conn:
        conn.execute("CREATE TABLE rehearsal_rows(id int PRIMARY KEY)")
        conn.execute("INSERT INTO rehearsal_rows VALUES (1)")
    stage.journey.set_profile(rehearsalDatabase=name)
    stage.tool.copies.record("rehearsal-database", f"run:{uuid4()}", [f"database/{name}"])
    procedures = realm_procedures(stage.journey.profile, stage.ledger, clock=clock,
                                  ready=lambda: True, names=stage.database.names).procedures
    request = procedures.requests.request(origin="schedule", operation="backup.create",
                                          environment="rehearsal", target_id=name,
                                          expected_revision=0, submission_id=uuid4())
    procedures.requests.admit(request["recoveryRequestId"])
    assert procedures.backup(request["recoveryRequestId"], via="in-person")["state"] == (
        "succeeded")
    backup = next(item for item in stage.ledger.records("backup-set")
                  if item["environment"] == "rehearsal")
    archive = tmp_path / "volume" / "docsuri-v2" / backup["location"]
    assert archive.exists()
    faults = Faults(stage.operator)
    stage.platform.operator = faults
    return SimpleNamespace(stage=stage, rehearsal=name, backup=backup, archive=archive,
                           faults=faults)


def waiting_ids(result: dict) -> list[str]:
    return [item["backupId"] for item in result["rehearsalSetsWaiting"]]


def standing_pass(stage, clock) -> DisposalPass:
    """The standing disposal pass over the stage's ledger, under the scheduler's grants."""
    facts = stage.operator.facts
    standing = realm_operator(stage.journey.profile, "scheduler", stage.ledger, clock=clock,
                              facts=facts)
    return disposal(stage.ledger, clock, standing, facts, Agent())


def test_cutover_check_in_person_disposes_a_real_rollbacks_left_set(tmp_path, realm, clock):
    """A real rollback's left names: opening's removal of the real rehearsal database
    fails, so it is left pending; the rollback removes it (`_remove_left`, its name kept
    in `rollback-left-<id>.json`) and the set's disposal at the rollback's end fails. The
    standing pass reports the set with `cutover-check`, and a day later the incident names
    that command; `cutover check`, run in person, then disposes of the real archive, and
    the next pass reports nothing waiting."""
    staging = staged(tmp_path, realm, clock)
    stage, backup = staging.stage, staging.backup
    try:
        staging.faults.removals = True
        stage.switched()
        assert staging.rehearsal in realm_databases(realm)  # opening's removal failed
        staging.faults.removals, staging.faults.disposals = False, True
        subject = stage.rollback_subject()
        result = stage.tool.rollback(stage.decide("rollback", subject), subject)
        assert result["state"] == "rolled-back", result
        assert staging.rehearsal in result["rehearsalDatabasesLeft"]
        assert staging.rehearsal not in realm_databases(realm)
        # The soak's stand-in sets (no archive on the volume) wait beside the real one.
        assert backup["backupId"] in waiting_ids(result), result
        report = standing_pass(stage, clock).run()
        assert backup["backupId"] in report["waitingSets"], report
        assert report["waitingRemedy"] == "cutover-check"
        clock.advance(SYNTHETIC_OPERATIONS.staging_file_backstop_seconds + 60)
        later = standing_pass(stage, clock).run()
        assert f"waiting:{backup['backupId']}:cutover-check" in later["incidents"], later
        assert staging.archive.exists()
        staging.faults.disposals = False
        checked = run_word(stage.tool, "check", {})
        assert backup["backupId"] in checked["leftSets"]["rehearsalSetsDisposed"], checked
        assert staging.rehearsal in checked["leftSets"]["rehearsalDatabasesLeft"]
        assert "disposedAt" in stage.ledger.get("backup-set", backup["backupId"])
        assert not staging.archive.exists()
        assert backup["backupId"] not in standing_pass(stage, clock).run()["waitingSets"]
    finally:
        rf.drop_database(realm, staging.rehearsal)
        stage.close()


def test_an_openings_waiting_set_is_reported_with_cutover_open_its_working_remedy(
        tmp_path, realm, clock):
    """A real opening removes the real rehearsal database, and its set's disposal fails:
    the record is switched. The standing pass reports the set with `cutover-open`, the
    command that retries it, and its incident names it a day later; `cutover check` there
    disposes of none and offers `open`; `cutover open` run again disposes of the real
    archive."""
    staging = staged(tmp_path, realm, clock)
    stage, backup = staging.stage, staging.backup
    try:
        staging.faults.disposals = True
        opened = stage.switched()
        assert opened["state"] == "switched", opened
        assert staging.rehearsal not in realm_databases(realm)
        assert backup["backupId"] in waiting_ids(opened), opened
        report = standing_pass(stage, clock).run()
        assert backup["backupId"] in report["waitingSets"], report
        assert report["waitingRemedy"] == "cutover-open"
        clock.advance(SYNTHETIC_OPERATIONS.staging_file_backstop_seconds + 60)
        later = standing_pass(stage, clock).run()
        assert f"waiting:{backup['backupId']}:cutover-open" in later["incidents"], later
        staging.faults.disposals = False
        checked = run_word(stage.tool, "check", {})
        assert checked["leftSets"]["offered"] == ["open"], checked
        assert checked["leftSets"]["rehearsalSetsDisposed"] == []
        assert staging.archive.exists()
        again = run_word(stage.tool, "open", {})
        assert again["state"] == "switched"
        assert backup["backupId"] in again["rehearsalSetsDisposed"], again
        assert "disposedAt" in stage.ledger.get("backup-set", backup["backupId"])
        assert not staging.archive.exists()
        assert backup["backupId"] not in standing_pass(stage, clock).run()["waitingSets"]
    finally:
        rf.drop_database(realm, staging.rehearsal)
        stage.close()


def test_cutover_check_disposes_a_replaced_dry_runs_waiting_set(tmp_path, realm, ledger,
                                                                 clock):
    """A newer accepted dry run replaces the real rehearsal database, which is removed,
    and its real set's disposal fails: no rollback left it, so `rollback-left-<id>.json`
    does not name it. The standing pass reports it with `cutover-check`, and `cutover
    check`'s retry (`retry_left_sets`, which the two tests above reach through the word
    itself) disposes of the real archive."""
    database = rf.JourneyDatabase(realm).create()
    replaced = disposable(realm, "rehearsal", database.names)
    with rf.admin(realm) as conn:
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO docsuri_backup_agent").format(
            sql.Identifier(replaced)))
    with rf.admin(realm, replaced) as conn:
        conn.execute("CREATE TABLE rehearsal_rows(id int PRIMARY KEY)")
        conn.execute("INSERT INTO rehearsal_rows VALUES (1)")
    try:
        agent = rf.journey_agent(tmp_path, realm, database, clock)
        journey, facts, operator = operator_for(tmp_path, realm, ledger, clock,
                                                names=database.names, rehearsal=replaced,
                                                role="operator", agentFolder=str(agent))
        rf.cutover_record(ledger, "preparing")
        procedures = realm_procedures(journey.profile, ledger, clock=clock, ready=lambda: True,
                                      names=database.names).procedures
        request = procedures.requests.request(
            origin="schedule", operation="backup.create", environment="rehearsal",
            target_id=replaced, expected_revision=0, submission_id=uuid4())
        procedures.requests.admit(request["recoveryRequestId"])
        assert procedures.backup(request["recoveryRequestId"],
                                 via="in-person")["state"] == "succeeded"
        backup = next(item for item in ledger.records("backup-set")
                      if item["environment"] == "rehearsal")
        archive = tmp_path / "volume" / "docsuri-v2" / backup["location"]
        RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock).record(
            "rehearsal-database", "run:earlier", [f"database/{replaced}"])
        accepted = database.names.new("rehearsal")
        run = cf.accepted_dry_run(ledger, now=clock(), database=accepted)
        faults = Faults(operator)
        faults.disposals = True
        evidence = SwitchEvidence(lambda run: None, lambda: None, lambda cutover: None,
                                  lambda: {}, lambda: "stand-in", None, lambda: accepted)
        tool = CutoverTool(ledger, SYNTHETIC_OPERATIONS, CutoverPlatform(
            operator=faults, production=database.name, v1_labels=(), v2_labels=(),
            v2_ready=lambda: True, v1_ready=lambda: True, public=lambda kind: True,
            evidence=evidence, evidence_folder=tmp_path / "cutover-evidence"), clock=clock)
        moved = tool.after_dry_run(run["runId"], accepted)
        assert replaced not in realm_databases(realm)
        assert [item["backupId"] for item in moved["rehearsalSetsWaiting"]] == [
            backup["backupId"]], moved
        standing = realm_operator(journey.profile, "scheduler", ledger, clock=clock,
                                  facts=facts)
        report = disposal(ledger, clock, standing, facts, Agent()).run()
        assert report["waitingSets"] == [backup["backupId"]], report
        assert report["waitingRemedy"] == "cutover-check"
        assert archive.exists()
        faults.disposals = False
        checked = tool.retry_left_sets(tool.machine.current())
        assert checked["rehearsalSetsDisposed"] == [backup["backupId"]], checked
        assert "rehearsalDatabasesLeft" not in checked
        assert not archive.exists()
        assert disposal(ledger, clock, standing, facts, Agent()).run()["waitingSets"] == []
    finally:
        rf.drop_database(realm, replaced)
        database.drop()


def test_the_realms_driver_refuses_an_in_person_agent_word_for_a_standing_request(
        tmp_path, realm, ledger, clock):
    """The realm's test driver runs a standing request under the scheduler's identity and
    refuses an in-person agent word for it, as production's `sudo -k` fails unattended.
    A standing disposal by event never reaches it: it is refused before anything is
    bound (the person's decision of 2026-10-26, "Drop it") and the archive stays; the
    same request in person disposes of it."""
    from docsuri_ops.platform_control.errors import ControlError
    from docsuri_ops.u8_platform.drivers import DriverRefused, load_config
    from docsuri_ops.u8_platform.drivers.realm import RealmDriver

    left = left_with_a_waiting_set(tmp_path, realm, ledger, clock)
    try:
        standing = realm_operator(left.journey.profile, "scheduler", ledger, clock=clock,
                                  facts=left.facts)
        inputs = {"recordKind": "BackupSet", "recordId": left.backup["backupId"],
                  "place": "backup-volume", "location": left.backup["location"],
                  "event": "rehearsal-database-removed"}
        with pytest.raises(ControlError, match="disposes of no copy") as caught:
            standing.execute("platform.copy.dispose", "copies", inputs,
                             key=f"standing-{uuid4()}")
        assert caught.value.code == "FORBIDDEN"
        assert left.archive.exists()
        # The driver itself: a scheduler caller is refused every in-person word, and an
        # unknown caller is refused outright.
        config = load_config(left.journey.profile.effects_root)
        scheduler = RealmDriver(config, caller="scheduler")
        for word in ("dispose-event", "stream-back", "snapshot-stream"):
            with pytest.raises(DriverRefused, match="in-person-refused"):
                scheduler._agent_command(word, "in-person")
        assert scheduler._agent_command("status", "standing")[1]["SUDO_UID"] == str(
            config["schedulerUid"])
        with pytest.raises(DriverRefused, match="caller-refused"):
            RealmDriver(config, caller="root")
        receipt = left.operator.execute("platform.copy.dispose", "copies", inputs,
                                        key=f"in-person-{uuid4()}")
        assert receipt["outcome"] == "succeeded", receipt
        assert not left.archive.exists()
    finally:
        left.cleanup()


def test_no_left_set_is_disposed_while_a_release_holds_the_live_exclusion(
        tmp_path, realm, ledger, clock):
    """Review finding (Minor, R13; BR4.4): while an install holds the live exclusion,
    `cutover check`'s retry by event disposes of nothing and reports each waiting set
    with the release's reason, and the disposal's own precondition waits on the release
    record too; once the install ended, the retry disposes the set."""
    from backend.modules.operations.release_records import ReleaseRecords

    left = left_with_a_waiting_set(tmp_path, realm, ledger, clock)
    try:
        tool = left.tool
        record = tool.machine.current()
        tool._write_evidence(tool._left_evidence(record), {
            "cutoverId": record["cutoverId"], "attempts": 1, "names": [left.rehearsal]})
        left.failing.failing = False
        records = ReleaseRecords(ledger, clock=clock)
        records.begin("v2.9.9", "d" * 40, previous_tag=None)
        held = tool.retry_left_sets(record)
        assert held["rehearsalSetsDisposed"] == [], held
        assert held["rehearsalSetsWaiting"] == [{"backupId": left.backup["backupId"],
                                                 "reason": "release-install-active"}]
        assert left.archive.exists()
        assert "disposedAt" not in ledger.get("backup-set", left.backup["backupId"])
        # The disposal's precondition holds it back too, whoever asks.
        inputs = {"recordKind": "BackupSet", "recordId": left.backup["backupId"],
                  "place": "backup-volume", "location": left.backup["location"],
                  "event": "rehearsal-database-removed"}
        with pytest.raises(PreconditionRefused) as caught:
            left.operator.execute("platform.copy.dispose", "copies", inputs,
                                  key=f"during-release-{uuid4()}")
        assert caught.value.reason == "live-exclusion-held" and caught.value.waiting
        assert left.archive.exists()
        records.finish("v2.9.9", "failed", reason="release-step-failed")
        done = tool.retry_left_sets(record)
        assert done["rehearsalSetsDisposed"] == [left.backup["backupId"]], done
        assert not left.archive.exists()
    finally:
        left.cleanup()


def test_a_sets_disposal_never_runs_out_of_keys_in_person(tmp_path, realm, ledger, clock):
    """The re-review's finding of 2026-10-26: each in-person run of a set's disposal is a
    run of its own (counted in `set-disposals-<cutoverId>.json`), so a disposal that
    fails more than STEP_RETRIES + 1 times through `cutover check` still answers its own
    reason, never `step-retries-exhausted`, and a later check, once the fault clears,
    disposes of the real archive."""
    from docsuri_ops.cutover.tool import STEP_RETRIES

    left = left_with_a_waiting_set(tmp_path, realm, ledger, clock)
    try:
        tool = left.tool
        record = tool.machine.current()
        tool._write_evidence(tool._left_evidence(record), {
            "cutoverId": record["cutoverId"], "attempts": 1, "names": [left.rehearsal]})
        for _ in range(STEP_RETRIES + 2):
            held = tool.retry_left_sets(record)
            assert held["rehearsalSetsDisposed"] == []
            [(waiting,)] = [held["rehearsalSetsWaiting"]]
            assert waiting["backupId"] == left.backup["backupId"]
            assert waiting["reason"] != "step-retries-exhausted", waiting
        assert left.archive.exists()
        attempts = tool._read_evidence(tool._set_evidence(record))["attempts"]
        assert attempts[left.backup["backupId"]] == STEP_RETRIES + 3  # opening's run, then each
        left.failing.failing = False
        done = tool.retry_left_sets(record)
        assert done["rehearsalSetsDisposed"] == [left.backup["backupId"]], done
        assert "disposedAt" in ledger.get("backup-set", left.backup["backupId"])
        assert not left.archive.exists()
    finally:
        left.cleanup()


class AppliedThenLost(Recording):
    """The realm's operator, with a set disposal that applied (the agent deleted the
    archive, the receipt succeeded) and whose answer was then lost before the set's
    record was written: what an interruption or a lost connection leaves in flight."""

    def execute(self, operation, target, inputs, *, key, **options):
        self.order.append(operation.removeprefix("platform."))
        receipt = self.operator.execute(operation, target, inputs, key=key, **options)
        if operation == "platform.copy.dispose" and not receipt.get("replayed"):
            from docsuri_ops.platform_control.errors import ControlError

            raise ControlError("DEPENDENCY_UNAVAILABLE", "answer lost")
        return receipt


def test_an_earlier_disposal_that_applied_is_recorded_not_run_again(tmp_path, realm, ledger,
                                                                     clock):
    """The re-review's finding of 2026-10-26: the earlier runs' keys of a set's disposal
    are settled before a new key opens, and the keys are pinned to the cutover's identity,
    so a decision recorded in between changes none. An earlier run whose disposal applied
    but whose answer was lost is taken as done: the next `cutover check` records
    `disposedAt` from that run's receipt instead of running the disposal again against a
    catalogue that no longer holds the archive (`not-catalogued`)."""
    left = left_with_a_waiting_set(tmp_path, realm, ledger, clock)
    try:
        tool = left.tool
        record = tool.machine.current()
        tool._write_evidence(tool._left_evidence(record), {
            "cutoverId": record["cutoverId"], "attempts": 1, "names": [left.rehearsal]})
        tool.platform.operator = AppliedThenLost(left.operator)
        lost = tool.retry_left_sets(record)
        assert lost["rehearsalSetsDisposed"] == []
        assert lost["rehearsalSetsWaiting"][0]["reason"] == "dependency-unavailable", lost
        assert not left.archive.exists()  # applied: the agent deleted it
        assert "disposedAt" not in ledger.get("backup-set", left.backup["backupId"])
        # A decision recorded in between: the keys stay the same.
        record = rf.advance_cutover(ledger, record, record["state"],
                                    approvals=[*record["approvals"], str(uuid4())])
        tool.platform.operator = left.operator
        done = tool.retry_left_sets(record)
        assert done["rehearsalSetsDisposed"] == [left.backup["backupId"]], done
        assert "disposedAt" in ledger.get("backup-set", left.backup["backupId"])
        # Settled from the earlier run's receipt: no third run was opened.
        attempts = tool._read_evidence(tool._set_evidence(record))["attempts"]
        assert attempts[left.backup["backupId"]] == 2
        assert tool.retry_left_sets(record) == {}
    finally:
        left.cleanup()


def test_a_waiting_set_in_a_settled_cutover_is_disposed_by_cutover_check(tmp_path, realm,
                                                                         ledger, clock):
    """The re-review's finding of 2026-10-26: an opening's set still waiting when the
    cutover settles is reported with `cutover-check`, its incident names that command,
    and `cutover check`'s retry disposes of it in the settled state too."""
    from docsuri_ops.cutover.disposal import waiting_remedy

    assert waiting_remedy("settled") == "cutover-check"
    left = left_with_a_waiting_set(tmp_path, realm, ledger, clock)
    try:
        tool = left.tool
        record = tool.machine.current()
        for state in ("rehearsing", "ready-to-switch", "switching", "switched", "settled"):
            record = rf.advance_cutover(ledger, record, state)
        standing = Recording(realm_operator(left.journey.profile, "scheduler", ledger,
                                            clock=clock, facts=left.facts))
        report = disposal(ledger, clock, standing, left.facts, Agent()).run()
        assert report["waitingSets"] == [left.backup["backupId"]], report
        assert report["waitingRemedy"] == "cutover-check"
        clock.advance(SYNTHETIC_OPERATIONS.staging_file_backstop_seconds + 60)
        later = disposal(ledger, clock, standing, left.facts, Agent()).run()
        assert f"waiting:{left.backup['backupId']}:cutover-check" in later["incidents"], later
        left.failing.failing = False
        done = tool.retry_left_sets(record)
        assert done["rehearsalSetsDisposed"] == [left.backup["backupId"]], done
        assert not left.archive.exists()
        assert disposal(ledger, clock, standing, left.facts, Agent()).run()["waitingSets"] == []
    finally:
        left.cleanup()


def test_cutover_check_retries_a_rollbacks_left_set_by_event(tmp_path, realm, ledger, clock):
    """The review's fix of 2026-10-26: once the rollback has ended, `cutover check` reads
    the rollback's left names (`rollback-left-<id>.json`) and disposes their sets still
    waiting, after their database; a set that still fails stays waiting with its reason,
    and a later check disposes the real archive. While the record is switched it disposes
    of none and offers `open` (review finding, Major, R16)."""
    left = left_with_a_waiting_set(tmp_path, realm, ledger, clock)
    try:
        tool = left.tool
        record = tool.machine.current()
        tool._write_evidence(tool._left_evidence(record), {
            "cutoverId": record["cutoverId"], "attempts": 1, "names": [left.rehearsal]})
        # While switched, opening's disposal is the retry: none here, `open` offered.
        for state in ("rehearsing", "ready-to-switch", "switching", "switched"):
            record = rf.advance_cutover(ledger, record, state)
        switched = tool.retry_left_sets(record)
        assert switched["offered"] == ["open"] and switched["rehearsalSetsDisposed"] == []
        assert left.archive.exists()
        # While the record holds the live exclusion, nothing runs.
        record = rf.advance_cutover(ledger, record, "rolling-back")
        assert tool.retry_left_sets(record) == {}
        record = rf.advance_cutover(ledger, record, "rolled-back")
        waiting = tool.retry_left_sets(record)
        assert [item["backupId"] for item in waiting["rehearsalSetsWaiting"]] == [
            left.backup["backupId"]], waiting
        assert left.archive.exists()
        left.failing.failing = False
        done = tool.retry_left_sets(record)
        assert done["rehearsalSetsDisposed"] == [left.backup["backupId"]], done
        assert "disposedAt" in ledger.get("backup-set", left.backup["backupId"])
        assert not left.archive.exists()
        assert tool.retry_left_sets(record) == {}  # nothing waits any more
    finally:
        left.cleanup()


# --- opening's order, database then sets, per database (review finding, Major, R-02) -------


def opening_over(tmp_path, realm, ledger, clock, wrap):
    """A real rehearsal database the profile names, recorded as a retained copy, with a
    real rehearsal set on the journey's volume (the realm's backup agent wrote it), and
    the cutover tool over the operator wrapped by `wrap`, before opening's disposal runs.
    Answers what a test needs, and the cleanup."""
    database = rf.JourneyDatabase(realm).create()
    rehearsal = disposable(realm, "rehearsal", database.names)
    with rf.admin(realm) as conn:
        conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO docsuri_backup_agent").format(
            sql.Identifier(rehearsal)))
    with rf.admin(realm, rehearsal) as conn:
        conn.execute("CREATE TABLE rehearsal_rows(id int PRIMARY KEY)")
        conn.execute("INSERT INTO rehearsal_rows VALUES (1)")

    def cleanup():
        rf.drop_database(realm, rehearsal)
        database.drop()

    agent = rf.journey_agent(tmp_path, realm, database, clock)
    journey, facts, operator = operator_for(tmp_path, realm, ledger, clock,
                                            names=database.names, rehearsal=rehearsal,
                                            role="operator", agentFolder=str(agent))
    rf.cutover_record(ledger, "preparing")
    procedures = realm_procedures(journey.profile, ledger, clock=clock, ready=lambda: True,
                                  names=database.names).procedures
    request = procedures.requests.request(origin="schedule", operation="backup.create",
                                          environment="rehearsal", target_id=rehearsal,
                                          expected_revision=0, submission_id=uuid4())
    procedures.requests.admit(request["recoveryRequestId"])
    assert procedures.backup(request["recoveryRequestId"], via="in-person")["state"] == (
        "succeeded")
    backup = next(item for item in ledger.records("backup-set")
                  if item["environment"] == "rehearsal")
    copies = RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=clock)
    copy = copies.record("rehearsal-database", "run:fixture", [f"database/{rehearsal}"])
    wrapped = wrap(operator)
    evidence = SwitchEvidence(lambda run: None, lambda: None, lambda cutover: None,
                              lambda: {}, lambda: "stand-in", None, lambda: rehearsal)
    tool = CutoverTool(ledger, SYNTHETIC_OPERATIONS, CutoverPlatform(
        operator=wrapped, production=database.name, v1_labels=(), v2_labels=(),
        v2_ready=lambda: True, v1_ready=lambda: True, public=lambda kind: True,
        evidence=evidence, evidence_folder=tmp_path / "cutover-evidence"), clock=clock)
    return SimpleNamespace(journey=journey, facts=facts, operator=operator, wrapped=wrapped,
                           tool=tool, copies=copies, copy=copy, backup=backup,
                           rehearsal=rehearsal, names=database.names,
                           archive=tmp_path / "volume" / "docsuri-v2" / backup["location"],
                           cleanup=cleanup)


def test_at_opening_a_failed_removal_leaves_its_set_and_names_why(tmp_path, realm, ledger,
                                                                   clock):
    """Review finding (Major, R-02): at opening, a set is disposed of only once the
    removal of its own database has applied. Two rehearsal databases: the real one's
    removal fails, a second one's applies. Only the second's set is addressed; the real
    one's database stays, its copy is pending, and its real set waits with the removal's
    reason, its archive untouched (a disposal cannot be undone, BR9.17). `open` run again
    retries in the order database, then sets, and disposes of the real archive."""
    opening = opening_over(tmp_path, realm, ledger, clock, Faults)
    tool, faults = opening.tool, opening.wrapped
    other = disposable(realm, "rehearsal", opening.names)
    try:
        other_copy = opening.copies.record("rehearsal-database", "run:other",
                                           [f"database/{other}"])
        other_set = rf.set_record(ledger, environment="rehearsal", now=clock(), database=other)
        faults.removals, faults.only = True, frozenset({opening.rehearsal})
        record = tool.machine.current()
        result = tool.after_opening(record)
        assert result["rehearsalDatabaseCleared"] is True
        assert result["rehearsalDatabasesRemoved"] == [other_copy["copyId"]], result
        assert result["rehearsalDatabasesPending"] == [
            {"copyId": opening.copy["copyId"], "reason": "rehearsal-database-removal-failed"}]
        assert result["offered"] == ["open"]
        # The real set waits, named with why; no disposal of it was even bound.
        waiting = {item["backupId"]: item["reason"] for item in result["rehearsalSetsWaiting"]}
        assert waiting[opening.backup["backupId"]] == "rehearsal-database-removal-failed"
        assert opening.backup["backupId"] not in result["rehearsalSetsDisposed"]
        assert faults.order.count("copy.dispose") == 1  # the other database's set only
        assert other_set["backupId"] in set(waiting) | set(result["rehearsalSetsDisposed"])
        assert opening.rehearsal in realm_databases(realm) and other not in realm_databases(realm)
        assert "disposalPendingSince" in opening.copies.get(opening.copy["copyId"])
        assert "disposedAt" not in ledger.get("backup-set", opening.backup["backupId"])
        assert opening.archive.exists()
        # Run again, the cause gone: the database first, then its set.
        faults.removals = False
        faults.order.clear()
        again = tool.after_opening(record)
        assert again["rehearsalDatabasesRemoved"] == [opening.copy["copyId"]], again
        assert again["rehearsalDatabasesPending"] == [] and "offered" not in again
        assert opening.backup["backupId"] in again["rehearsalSetsDisposed"], again
        removal = faults.order.index("database.remove")
        assert removal < faults.order.index("copy.dispose"), faults.order
        assert opening.rehearsal not in realm_databases(realm)
        assert "disposedAt" in ledger.get("backup-set", opening.backup["backupId"])
        assert not opening.archive.exists()
    finally:
        rf.drop_database(realm, other)
        opening.cleanup()


def test_at_opening_a_removal_that_applied_disposes_its_set(tmp_path, realm, ledger, clock):
    """Review finding (Major, R-02): the removal's applied receipt is what admits the
    set's disposal. One real rehearsal database, removed at opening: its real set is
    disposed of right after, and the archive is gone."""
    opening = opening_over(tmp_path, realm, ledger, clock, Recording)
    try:
        result = opening.tool.after_opening(opening.tool.machine.current())
        assert result["rehearsalDatabasesRemoved"] == [opening.copy["copyId"]], result
        assert result["rehearsalDatabasesPending"] == [] and "offered" not in result
        assert result["rehearsalSetsDisposed"] == [opening.backup["backupId"]]
        assert result["rehearsalSetsWaiting"] == []
        assert opening.wrapped.order == ["profile.rehearsal-database", "database.remove",
                                         "copy.dispose"]
        assert "disposedAt" in opening.copies.get(opening.copy["copyId"])
        assert "disposedAt" in ledger.get("backup-set", opening.backup["backupId"])
        assert not opening.archive.exists()
    finally:
        opening.cleanup()


def test_at_opening_a_removal_with_an_unknown_receipt_leaves_its_set_until_reconciled(
        tmp_path, realm, ledger, clock):
    """Review finding (Major, R-02): the removal applied on the server, but its outcome
    was reported unknown and the run ended before it reconciled it. Nothing of the set
    was disposed of: it waits, its archive in place. `open` run again settles the same
    key, reconciles the receipt from its target (the database is gone: applied), runs no
    second removal, and only then disposes of the set."""
    from docsuri_ops.platform_control.executor import STATUS_UNKNOWN, EffectOutcome
    from tests.u8_service_operations_integration.operations.test_production_cutover_wiring import (
        Interrupted,
        RemovalEffects,
    )

    opening = opening_over(tmp_path, realm, ledger, clock, Recording)
    bounded = opening.operator.run_effect  # the realm's own run effect

    def unknown(**options):
        applied = bounded(**options)
        return EffectOutcome(STATUS_UNKNOWN, applied.effect_refs)

    removals = RemovalEffects(opening.wrapped, unknown, dies_reconciling=True)
    opening.tool.platform.operator = removals
    try:
        record = opening.tool.machine.current()
        with pytest.raises(Interrupted):
            opening.tool.after_opening(record)
        assert len(removals.ran) == 1
        assert opening.rehearsal not in realm_databases(realm)  # applied on the server
        unresolved = removals.clone._read_named(removals.ran[0])
        assert unresolved["reconciliationState"] == "unresolved", unresolved
        # Until reconciled: the copy is open, the set undisposed, the archive in place.
        assert "disposedAt" not in opening.copies.get(opening.copy["copyId"])
        assert "disposedAt" not in ledger.get("backup-set", opening.backup["backupId"])
        assert "copy.dispose" not in opening.wrapped.order
        assert opening.archive.exists()
        removals.effect, removals.dies_reconciling = None, False
        opening.wrapped.order.clear()
        again = opening.tool.after_opening(record)
        assert again["rehearsalDatabasesRemoved"] == [opening.copy["copyId"]], again
        assert again["rehearsalSetsDisposed"] == [opening.backup["backupId"]], again
        assert len(removals.ran) == 1  # the receipt was replayed and reconciled, not run
        assert opening.wrapped.order.index("database.remove") < (
            opening.wrapped.order.index("copy.dispose"))
        assert "disposedAt" in opening.copies.get(opening.copy["copyId"])
        assert not opening.archive.exists()
    finally:
        opening.cleanup()
