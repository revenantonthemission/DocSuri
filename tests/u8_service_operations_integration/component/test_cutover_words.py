"""The cutover commands' sequences (U8 plan Step 34; Workflows 13 and 14, BR9.2, BR9.4,
BR9.5, BR9.7, BR9.8, BR9.13, R8).

Each word runs its bound operations through the composed realm's PlatformControl store
and realm driver on the journey's own platform state (services, routing, profile), and a
production stand-in of the test's own in the realm's instance (`recovery_flows.
JourneyDatabase`) is what a recreate empties, never `docsuri_u8`. The parts that belong
to v1 (its health, its public pages, its account code) and the final migration run are
stand-ins here: v1's runtime is a recording program run by the realm driver as it runs
v1's, so the lifecycle outcomes it is handed are checked. The journeys against the
synthetic v1 run from v1's own code are `integration/test_cutover_journeys.py`'s.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from backend.modules.operations.incidents import Incidents
from backend.modules.operations.migration.identities import target_id
from backend.modules.operations.migration.misfits import Decisions
from backend.modules.operations.retained_copies import RetainedCopies
from backend.request_context import window_summaries
from backend.u8_policy import SYNTHETIC_OPERATIONS
from docsuri_ops.cutover import tool as cutover_tool
from docsuri_ops.cutover.preconditions import SwitchEvidence
from docsuri_ops.cutover.tool import CutoverPlatform, CutoverTool, run_word
from docsuri_ops.migration.isolation_gate import IsolationGate
from docsuri_ops.u8_platform.u8_protocols import realm_facts, realm_operator
from tests.u8_service_operations_integration import cutover_flows as cf
from tests.u8_service_operations_integration import platform_flows as pf
from tests.u8_service_operations_integration import recovery_flows as rf

DAY = 86400
V1_ACCOUNT = "v1-account-fixture"


class Probes:
    """The probes. v1's counts its polls and, with `v1_late`, answers ready only after
    that many polls; `on_v1_poll` is called at each poll (Step 71(k))."""

    def __init__(self):
        self.v1 = self.v2 = self.public_answers = True
        self.v1_late: int | None = None
        self.v1_polls = 0
        self.on_v1_poll = None

    def v1_ready(self) -> bool:
        self.v1_polls += 1
        if self.on_v1_poll is not None:
            self.on_v1_poll(self.v1_polls)
        if self.v1_late is not None:
            return self.v1_polls > self.v1_late
        return self.v1

    def public(self, kind: str) -> bool:
        return self.public_answers


class AgentRefused(Exception):
    """The agent's refusal, with its fixed reason (as the drivers raise it)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class Agent:
    """The agent's in-person words: `rollback-copy` writes a copy (or cannot), `status`,
    and `set-date` (U8 plan Step 71(g)): each call recorded, and a date that is not
    earlier than the one the agent already holds for that path refused with
    `decided-date-not-earlier`, as the agent's catalogue does."""

    def __init__(self):
        self.copies, self.available, self.calls = True, True, []
        self.set_dates: list[dict] = []
        self.held: dict[str, dt.datetime] = {}

    def __call__(self, word: str, document: dict, *, via: str) -> dict:
        self.calls.append((word, via))
        if word == "status":
            return {"available": self.available, "freeBytes": 10**15}
        if word == "set-date":
            self.set_dates.append(document)
            date = dt.datetime.fromisoformat(document["decided"]["date"])
            held = self.held.get(document["path"])
            if held is not None and date >= held:
                raise AgentRefused("decided-date-not-earlier")
            self.held[document["path"]] = date
            return {"path": document["path"], "disposeAfter": date.isoformat()}
        if not self.copies:
            raise RuntimeError("backup-volume-unavailable")
        return {"sha256": "d" * 64, "integrity": "passed", "databaseBytes": 4096,
                "location": f"archives/rolled-back-copy-x-{document['recordId']}.archive"}


class Stage:
    def __init__(self, tmp_path: Path, realm, clock):
        self.tmp, self.clock = tmp_path, clock
        self.database = rf.JourneyDatabase(realm).create()
        self.ledger = rf.open_ledger(tmp_path, clock)
        self.seen = tmp_path / "v1-applied.json"
        recorder = (f"import sys; open({str(self.seen)!r}, 'wb')"
                    ".write(sys.stdin.buffer.read())")
        from tests.u8_service_operations_integration.v1_flows import (
            realm_environment,
            write_environment,
        )

        # v1's stores' stand-ins (`v1-stores/*`) and v1's checked environment are this
        # journey's own, under tmp_path.
        environment = write_environment(tmp_path, realm_environment())
        self.journey = pf.journey(tmp_path, realm, v1Runtime=[sys.executable, "-c", recorder],
                                  v1Checkout=str(tmp_path), v1StoresRoot=str(tmp_path),
                                  v1EnvironmentRoot=str(tmp_path),
                                  v1EnvironmentFile=str(environment))
        base = realm_facts(self.journey.profile, self.ledger, clock=clock)

        def facts():
            current = base()
            current.names = self.database.names
            return current

        self.operator = realm_operator(self.journey.profile, "operator", self.ledger,
                                       clock=clock, facts=facts)
        self.isolation = tmp_path / "isolation"
        self.isolation.mkdir()
        self.probes, self.agent = Probes(), Agent()
        self.final_state = "reported"
        # The soak's rehearsal database: a name of the instance's naming that the profile
        # holds once a dry run is accepted onto it (`accept_dry_run`); nothing creates it.
        self.soak_database = self.database.names.new("rehearsal")
        evidence = SwitchEvidence(
            verification=lambda run: {"passed": True, "releaseTag": cf.TAG},
            v1_checkout=lambda: {"commit": "b" * 40, "fingerprint": "f" * 64},
            rehearsal_fingerprint=cutover_tool.rehearsal_fingerprint_reader(
                tmp_path / "evidence"),
            agent_status=lambda: {"available": True, "freeBytes": 10**15},
            service_volume=lambda: "stand-in",
            isolation=IsolationGate(
                self.isolation,
                freshness_seconds=SYNTHETIC_OPERATIONS.isolation_freshness_seconds,
                clock=clock),
            # The profile's rehearsal database, as the operator's facts read it.
            rehearsal_database=lambda: self.operator.facts().current_rehearsal,
        )
        labels = self.journey.profile.labels
        # A rollback's new rehearsal database, recorded instead of created: the realm's
        # instance holds only this journey's own production stand-in.
        self.created_rehearsals: list[str] = []
        # The soak's latency lines: an empty folder of the stage's own (Step 71(i)).
        self.latency = tmp_path / "latency"
        self.latency.mkdir()
        self.platform = CutoverPlatform(
            # Every wait moves the stage's clock and none sleeps (Step 71(k)).
            sleep=clock.advance,
            soak_latency=lambda start, end: window_summaries(
                self.latency, start=start, end=end,
                window_seconds=SYNTHETIC_OPERATIONS.latency_window_seconds),
            snapshot_parts=self.snapshot_parts,
            operator=self.operator, production=self.database.name,
            v1_labels=tuple(item for item in labels if ".v1-" in item),
            v2_labels=tuple(item for item in labels if item.endswith((".host", ".workers",
                                                                      ".scheduler"))),
            v2_ready=lambda: self.probes.v2, v1_ready=self.probes.v1_ready,
            public=self.probes.public, evidence=evidence, evidence_folder=tmp_path / "evidence",
            final_run=self.final_run, first_backup=self.first_backup, agent=self.agent,
            lifecycle_outcomes=lambda since: [
                {"accountId": str(target_id("account", V1_ACCOUNT)), "outcome": "erase"},
                {"accountId": str(uuid4()), "outcome": "withdraw"}],
            v1_accounts=lambda: [V1_ACCOUNT, "v1-other"],
            v1_states=lambda ids: {item: "DEACTIVATED" for item in ids},
            v2_writes=lambda since: {"accounts-created": 2},
            v1_store_present=cutover_tool.store_present(tmp_path),
            create_rehearsal=self.created_rehearsals.append,
        )
        self.tool = CutoverTool(self.ledger, SYNTHETIC_OPERATIONS, self.platform, clock=clock)

    def final_run(self, approval: str, dispose_after: dt.datetime) -> dict:
        """The final run, with its completed final snapshot recorded at the date the
        start computed (Step 71(g))."""
        run_id = str(uuid4())
        copy = cf.final_snapshot(self.ledger, run_id, approval=approval,
                                 dispose_after=dispose_after, now=self.clock())
        return cf.final_run(self.ledger, now=self.clock(), state=self.final_state,
                            runId=run_id, snapshotCopyId=copy["copyId"])

    @staticmethod
    def snapshot_parts(copy_id: str) -> dict:
        """The copy's three part paths, as `Snapshot.verified_parts` answers them."""
        return {part: {"path": f"archives/final-snapshot-{copy_id}-{part}.archive",
                       "sha256": "e" * 64} for part in ("database", "index", "objects")}

    def first_backup(self, key: str) -> dict:
        return cf.first_live(self.ledger, now=self.clock())

    def isolation_passed(self) -> None:
        moment = self.clock()
        (self.isolation / f"{moment:%Y%m%dT%H%M%S%f}.json").write_text(json.dumps(
            {"passed": True, "checkedAt": moment.isoformat(), "items": []}))

    def accept_dry_run(self, database: str | None = None, **fields) -> dict:
        """A dry run accepted onto `database` (the soak's by default): its target copy
        recorded, the profile holding it, and the acceptance on the record. `fields`
        reach the run (`durationSeconds`, `phaseSeconds`, `interruptions`, Step 71(i))."""
        name = database or self.soak_database
        run = cf.accepted_dry_run(self.ledger, now=self.clock(), database=name,
                                  decisionsDigest=Decisions.from_ledger(self.ledger).digest(),
                                  **fields)
        self.journey.set_profile(rehearsalDatabase=name)
        self.tool.machine.dry_run_accepted(run["runId"])
        return run

    def soak_evidence(self, start: dt.datetime, database: str | None = None) -> None:
        """A week of scheduled sets of the soak's database and a verified restore."""
        sets = cf.scheduled_sets(self.ledger, start, 7, database=database or self.soak_database)
        cf.verified_restore(self.ledger, sets[0], now=start + dt.timedelta(hours=2))

    def ready(self) -> dict:
        """Ready to switch on real evidence: every BR9.2 precondition (1)–(9)."""
        machine = self.tool.machine
        machine.begin(cf.TAG)
        self.accept_dry_run()
        machine.verification_passed(uuid4(), cf.TAG)
        record = machine.start_soak()
        start = dt.datetime.fromisoformat(record["soakStartedAt"].replace("Z", "+00:00"))
        self.soak_evidence(start)
        self.clock.advance(7 * DAY + 60)
        # The inventory is taken at the check's clock, after the soak (L1-21).
        machine.inventory_taken(cf.complete_inventory(self.ledger, now=self.clock())[
            "inventoryId"])
        assert self.tool.rehearse_restart(self.decide("v1-restart-rehearsal"))["rehearsed"]
        self.isolation_passed()
        checked = self.tool.check()
        assert checked == {"state": "ready-to-switch", "missing": []}, checked
        return self.tool.machine.current()

    def decide(self, step: str, subject: dict | None = None) -> str:
        record = self.tool.machine.current()
        return cf.decision(self.ledger, step, record["cutoverId"], now=self.clock(),
                           subject=subject)

    def start_subject(self) -> dict:
        """The switch-start subject's rule (L1-3): the final snapshot's backstop."""
        record = self.tool.machine.current()
        return {"cutoverId": record["cutoverId"], "finalSnapshotBackstopSeconds":
                SYNTHETIC_OPERATIONS.final_snapshot_backstop_seconds}

    def opening_subject(self) -> dict:
        record = self.tool.machine.current()
        return {"cutoverId": record["cutoverId"], "providersAcceptedUnavailable": [],
                "v1StoresDisposalSeconds": SYNTHETIC_OPERATIONS.v1_stores_disposal_seconds}

    def start(self) -> dict:
        self.ready()
        subject = self.start_subject()
        return self.tool.start(self.decide("switch-start", subject), subject)

    def switched(self, *, started: bool = False) -> dict:
        if not started:
            self.start()
        run = self.ledger.get("migration-run", self.tool.machine.current()["finalRunId"])
        cf.accept(self.ledger, run, now=self.clock())
        assert self.tool.start()["waiting"] == "maintainer-window"
        subject = self.opening_subject()
        return self.tool.open(self.decide("admission-opening", subject), subject)

    def rollback_subject(self) -> dict:
        record = self.tool.machine.current()
        return {"cutoverId": record["cutoverId"],
                "rolledBackDisposalSeconds": SYNTHETIC_OPERATIONS.rolled_back_disposal_seconds}

    def settlement_subject(self) -> dict:
        record = self.tool.machine.current()
        return {"cutoverId": record["cutoverId"],
                "finalSnapshotDisposalSeconds":
                SYNTHETIC_OPERATIONS.final_snapshot_disposal_seconds,
                "finalSnapshotCopyId": record.get("finalSnapshotCopyId")}

    def close(self) -> None:
        self.ledger.close()
        self.database.drop()


@pytest.fixture
def stage(tmp_path, realm, clock):
    value = Stage(tmp_path, realm, clock)
    yield value
    value.close()


def services(stage) -> dict:
    return {label.rsplit(".", 1)[-1]: stage.journey.read_state("services", f"{label}.json")[
        "state"] for label in (*stage.platform.v1_labels, *stage.platform.v2_labels)}


def test_each_precondition_is_named_when_it_is_missing(stage, clock):
    stage.tool.machine.begin(cf.TAG)
    missing = stage.tool.missing()
    assert missing == ["verification-not-passed", "soak-not-clean", "dry-run-not-accepted",
                       "rehearsal-verification-missing", "inventory-incomplete",
                       "restart-rehearsal-missing", "isolation-evidence-missing"]
    stage.tool.machine.verification_passed(uuid4(), cf.TAG)
    assert stage.tool.missing()[0] == "soak-not-clean"  # it passed on this release
    stage.platform.evidence.verification = lambda run: {"passed": True, "releaseTag": "v9.9.9"}
    assert stage.tool.missing()[0] == "verification-not-passed"
    stage.platform.evidence.agent_status = lambda: {"available": True, "freeBytes": 1}
    assert "backup-volume-unfit" in stage.tool.missing()
    Incidents(stage.ledger, environment="rehearsal").signal("research", "operator")
    assert "incident-unresolved" in stage.tool.missing()


def round_clock(clock) -> None:
    """The clock at a whole millisecond, so a time the ledger stores (`utc_text`) equals
    the instant it came from and each bound is computed from the stored value."""
    clock.now = clock.now.replace(microsecond=clock.now.microsecond // 1000 * 1000)


def instant(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def take_inventory(stage, *, now: dt.datetime | None = None, seconds: int = 14 * DAY) -> str:
    inventory = cf.complete_inventory(stage.ledger, now=now or stage.clock(), seconds=seconds)
    stage.tool.machine.inventory_taken(inventory["inventoryId"])
    return inventory["inventoryId"]


def start_refused(stage, item: str) -> None:
    """`start` on the ready-to-switch record, with no `check` in between, is refused
    naming `item`; the record stays ready-to-switch and no v1 service stopped."""
    from backend.modules.operations.errors import OperationsError

    subject = stage.start_subject()
    with pytest.raises(OperationsError) as refused:
        stage.tool.start(stage.decide("switch-start", subject), subject)
    assert refused.value.code == "CONFLICT", refused.value.current
    assert refused.value.current["reasonKey"] == "precondition-missing"
    assert item in refused.value.current["missing"]
    assert stage.tool.machine.current()["state"] == "ready-to-switch"
    assert {stage.journey.read_state("services", f"{label}.json")["state"]
            for label in stage.platform.v1_labels} == {"running"}


def test_each_precondition_holds_at_its_bound_and_fails_past_it(stage, clock):
    """Step 71(a), NFR7.14, L1-21: each precondition holds exactly at its bound and is
    named one step past it, where `start` is refused without a `check` in between."""
    round_clock(clock)
    tool, machine = stage.tool, stage.tool.machine

    def fresh() -> None:
        take_inventory(stage)
        stage.isolation_passed()

    def fails(item: str) -> None:
        assert tool.missing() == [item]
        start_refused(stage, item)

    # The soak, before ready-to-switch: a start needs ready-to-switch.
    machine.begin(cf.TAG)
    stage.accept_dry_run()
    machine.verification_passed(uuid4(), cf.TAG)
    soak_start = instant(machine.start_soak()["soakStartedAt"])
    stage.soak_evidence(soak_start)
    clock.now = soak_start + dt.timedelta(seconds=604800 - 1)
    assert tool.rehearse_restart(stage.decide("v1-restart-rehearsal"))["rehearsed"]
    fresh()
    checked = tool.check()
    assert checked["state"] == "rehearsing" and checked["missing"] == ["soak-not-clean"]
    clock.now = soak_start + dt.timedelta(seconds=604800)
    assert tool.check() == {"state": "ready-to-switch", "missing": []}
    # The restart rehearsal: 604,800 s passes, 604,801 s does not.
    rehearsed = instant(machine.current()["v1RestartRehearsedAt"])
    clock.now = rehearsed + dt.timedelta(seconds=604800)
    fresh()
    assert tool.missing() == []
    clock.now = rehearsed + dt.timedelta(seconds=604801)
    fresh()
    fails("restart-rehearsal-expired")
    assert tool.rehearse_restart(stage.decide("v1-restart-rehearsal"))["rehearsed"]
    fresh()
    assert tool.missing() == []
    # The inventory's window: 1,209,600 s passes, 1,209,599 s does not.
    take_inventory(stage, seconds=1209600)
    assert tool.missing() == []
    take_inventory(stage, seconds=1209599)
    fails("inventory-window-short")
    # Its recency: ending exactly 86,400 s before the check passes; 86,401 s before it,
    # or 1 ms after it, does not.
    take_inventory(stage, now=clock() - dt.timedelta(seconds=86400))
    assert tool.missing() == []
    take_inventory(stage, now=clock() - dt.timedelta(seconds=86401))
    fails("inventory-not-recent")
    take_inventory(stage, now=clock() + dt.timedelta(milliseconds=1))
    fails("inventory-not-recent")
    fresh()
    assert tool.missing() == []
    # Free space: the floor plus the accepted run's snapshot parts plus the largest set
    # of its rehearsal database; `sourceDatabaseBytes` no longer counts.
    copies = RetainedCopies(stage.ledger, SYNTHETIC_OPERATIONS, clock=clock)
    snapshot = copies.record("dry-run-snapshot", f"run:{uuid4()}",
                             [f"backup-volume:snapshot:{part}" for part in
                              ("database", "index", "objects")])
    copies.complete(snapshot["copyId"], checksum="c" * 64, source_database_bytes=2**20,
                    part_sizes={"database": 2**10, "index": 2**11, "objects": 2**12})
    stage.accept_dry_run(snapshotCopyId=snapshot["copyId"])
    for size in (2**13, 2**12):
        rf.set_record(stage.ledger, environment="rehearsal", now=clock(),
                      database=stage.soak_database, size_bytes=size)
    rf.set_record(stage.ledger, environment="rehearsal", now=clock(),
                  database=stage.database.names.new("rehearsal"), size_bytes=2**14)
    room = 64 * 2**30 + 2**10 + 2**11 + 2**12 + 2**13
    assert room == 68_719_492_096
    stage.platform.evidence.agent_status = lambda: {"available": True, "freeBytes": room}
    assert tool.check() == {"state": "ready-to-switch", "missing": []}
    stage.platform.evidence.agent_status = lambda: {"available": True, "freeBytes": room - 1}
    fails("backup-volume-unfit")
    stage.platform.evidence.agent_status = lambda: {"available": True, "freeBytes": 10**15}
    # Isolation: checked 900 s before passes; 901 s does not.
    stage.isolation_passed()
    clock.advance(900)
    assert tool.missing() == []
    clock.advance(1)
    fails("isolation-stale")
    # The policies hold the same bounds.
    from backend.u8_policy import PRODUCTION_OPERATIONS

    for policy in (PRODUCTION_OPERATIONS, SYNTHETIC_OPERATIONS):
        assert (policy.soak_clean_seconds, policy.restart_rehearsal_seconds,
                policy.consumer_window_seconds, policy.inventory_recency_seconds,
                policy.isolation_freshness_seconds, policy.backup_volume_floor_bytes) == (
            604800, 604800, 1209600, 86400, 900, 64 * 2**30)


def test_settlement_measures_the_inventory_from_the_switchs_check(stage, clock):
    """Step 71(a), L1-21: settlement reads the inventory's rules from `switchCheckedAt`,
    not from v1's stop 60 s later."""
    from backend.modules.operations.errors import OperationsError

    round_clock(clock)
    stage.ready()
    check = clock()
    own = take_inventory(stage, now=check - dt.timedelta(seconds=86400))
    assert stage.tool.missing() == []

    def steps(name, bound, work):
        if name == "route-maintenance":
            clock.advance(60)
        return work()

    stage.platform.steps = steps
    subject = stage.start_subject()
    assert stage.tool.start(stage.decide("switch-start", subject), subject)[
        "waiting"] == "final-report"
    record = stage.tool.machine.current()
    assert instant(record["switchCheckedAt"]) == check
    assert instant(record["switchStartedAt"]) == check + dt.timedelta(seconds=60)
    stage.platform.steps = cutover_tool._direct
    stage.switched(started=True)
    clock.advance(stage.tool.machine.current()["rollbackWindowSeconds"] + 60)
    subject = stage.settlement_subject()
    approval = stage.decide("settlement", subject)
    for ending, seconds, reason in (
        (check - dt.timedelta(seconds=86400), 14 * DAY - 1, "inventory-window-short"),
        (check - dt.timedelta(seconds=86401), 14 * DAY, "inventory-not-recent"),
        (check + dt.timedelta(seconds=1), 14 * DAY, "inventory-not-recent"),
    ):
        take_inventory(stage, now=ending, seconds=seconds)
        with pytest.raises(OperationsError) as refused:
            stage.tool.settle(approval, subject)
        assert refused.value.current["reasonKey"] == reason
        assert stage.tool.machine.current()["state"] == "switched"
    stage.tool.machine.inventory_taken(own)
    assert stage.tool.settle(approval, subject)["state"] == "settled"


def test_an_inventory_from_a_cloudflare_export_spans_its_non_empty_intervals(stage, clock):
    """Step 71(a): an hourly export's window runs from its first non-empty interval to
    its last one's end, so 336 intervals whose first has no row read 1,206,000 s."""
    from docsuri_ops.migration import cloudflare_export
    from docsuri_ops.migration.inventory import ConsumerInventory

    round_clock(clock)
    stage.ready()
    check = clock()

    def recorded(rows: int) -> dict:
        lines = ["datetimeHour,requests"]
        lines += [f"{(check - dt.timedelta(hours=hour)).isoformat()},5"
                  for hour in range(rows, 0, -1)]
        inventory = ConsumerInventory(
            stage.ledger, window_seconds=SYNTHETIC_OPERATIONS.consumer_window_seconds,
            clock=clock)
        observed = inventory.observe(cloudflare_export.read("\n".join(lines).encode()))
        record = inventory.record(observed)
        stage.tool.machine.inventory_taken(record["inventoryId"])
        return record

    short = recorded(335)  # 336 intervals ending at the check, the first one empty
    assert (instant(short["observedUntil"]) - instant(short["observedFrom"])).total_seconds(
    ) == 1_206_000
    assert stage.tool.missing() == ["inventory-window-short"]
    start_refused(stage, "inventory-window-short")
    recorded(337)
    assert stage.tool.missing() == []


def test_the_switch_runs_to_the_maintainer_window_then_opens(stage, clock):
    first = stage.start()
    assert first["waiting"] == "final-report"
    record = stage.tool.machine.current()
    assert record["state"] == "switching" and "switchStartedAt" in record
    assert stage.journey.tunnel()["origin"] == "maintenance"
    assert set(services(stage).values()) == {"stopped"}
    assert stage.tool.start()["waiting"] == "final-report"  # your decision is awaited
    opened = stage.switched(started=True)
    assert opened["state"] == "switched"
    profile = stage.journey.read_state("profile.json")
    assert profile["mode"] == "live" and profile["admission"] == "open"
    assert stage.journey.tunnel()["origin"] == "v2-host"
    assert services(stage)["host"] == "running" and services(stage)["v1-web"] == "stopped"
    copy = RetainedCopies(stage.ledger, SYNTHETIC_OPERATIONS).get(opened["v1StoresCopyId"])
    assert copy["kind"] == "v1-stores"
    # The soak's rehearsal database is removed once the profile no longer names it, then
    # its sets: they are records of this test only (no file on a volume), so each waits
    # for the disposal pass instead of being marked disposed.
    (soaked,) = [copy for copy in stage.ledger.records("retained-copy")
                 if copy["locations"] == [f"database/{stage.soak_database}"]]
    assert opened["rehearsalDatabaseCleared"] is True
    assert opened["rehearsalDatabasesRemoved"] == [soaked["copyId"]]
    assert opened["rehearsalSetsDisposed"] == []
    assert {item["reason"] for item in opened["rehearsalSetsWaiting"]} == {"copy-dispose-failed"}
    assert stage.journey.read_state("profile.json")["rehearsalDatabase"] is None
    status = run_word(stage.tool, "status", {})
    assert status["state"] == "switched" and status["boundPassed"] is False


def test_a_rejected_final_run_aborts_and_v1_serves_again(stage, clock):
    stage.final_state = "rejected"
    stage.ready()
    subject = stage.start_subject()
    result = stage.tool.start(stage.decide("switch-start", subject), subject)
    assert result["state"] == "rehearsing", result
    record = stage.tool.machine.current()
    assert record["state"] == "rehearsing"
    incident = Incidents(stage.ledger, environment="live").get(record["abortIncidentId"])
    assert incident["openedBy"] == "switch-aborted"
    assert stage.journey.tunnel()["origin"] == "v1-web"
    assert services(stage)["v1-api"] == "running" and services(stage)["host"] == "running"
    profile = stage.journey.read_state("profile.json")
    assert profile["mode"] == "rehearsal" and profile["admission"] == "maintainer-only"
    assert stage.database.tables() == []  # recreated empty, only after v1 serves


def v1_starts(stage, log) -> dict[str, int]:
    """How many `platform.service.control` effects the log holds for each v1 label."""
    return {label: sum(1 for operation, name in log.order
                       if operation == "platform.service.control" and name == label)
            for label in stage.platform.v1_labels}


def test_v1_not_starting_keeps_the_abort_with_the_notice_up(stage, clock):
    stage.start()
    stage.probes.v1 = False
    log = OperationLog(stage.operator)
    stage.platform.operator = log
    polls, started = stage.probes.v1_polls, clock()
    result = run_word(stage.tool, "abort", {"reason": "operator-abort"})
    assert result == {"state": "aborting", "reason": "v1-restart-failed"}
    # The never-ready v1 was polled 121 times over 600 s, and each label started once.
    assert stage.probes.v1_polls - polls == 121
    assert (clock() - started).total_seconds() == 600
    assert v1_starts(stage, log) == {label: 1 for label in stage.platform.v1_labels}
    stage.platform.operator = stage.operator
    assert stage.journey.tunnel()["origin"] == "maintenance"
    assert stage.database.tables() != []  # nothing of v2's is removed
    stage.probes.v1 = True
    result = run_word(stage.tool, "abort", {})
    assert result["state"] == "rehearsing"
    run = stage.ledger.get("migration-run", stage.tool.machine.current()["finalRunId"])
    assert run["state"] == "failed"  # a final run not yet accepted ends failed


def test_the_four_hour_bound_offers_only_the_abort(stage, clock):
    stage.start()
    clock.advance(4 * 3600 + 1)
    assert stage.tool.start() == {"state": "switching", "offered": ["abort"],
                                  "reason": "switch-bound-passed"}
    subject = stage.opening_subject()
    assert stage.tool.open(stage.decide("admission-opening", subject), subject)[
        "state"] == "rehearsing"  # opening past the bound aborts


def test_a_rollback_applies_v2s_outcomes_to_v1_before_it_serves_and_copies(stage, clock):
    stage.switched()
    subject = stage.rollback_subject()
    result = stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert result["state"] == "rolled-back", result
    applied = json.loads(stage.seen.read_bytes())
    # Only the account matched by BR8.3's derivation, and every v1 session.
    assert applied == {"outcomes": [{"v1AccountId": V1_ACCOUNT, "outcome": "erase"}],
                       "accounts": [V1_ACCOUNT, "v1-other"]}
    record = stage.tool.machine.current()
    assert "rollbackV1ServingAt" in record and record["state"] == "rolled-back"
    assert stage.journey.tunnel()["origin"] == "v1-web"
    profile = stage.journey.read_state("profile.json")
    assert profile["mode"] == "rehearsal" and profile["admission"] == "maintainer-only"
    copies = RetainedCopies(stage.ledger, SYNTHETIC_OPERATIONS)
    assert "returnedToServiceAt" in copies.get(record["v1StoresCopyId"])
    rolled = copies.undisposed("rolled-back-v2-database")
    assert len(rolled) == 1 and "completedAt" in rolled[0]
    assert stage.database.tables() == []
    report = json.loads((stage.tmp / "evidence" /
                         f"rollback-writes-{record['cutoverId']}.json").read_bytes())
    assert report["perKind"] == {"accounts-created": 2}


def test_a_rollback_whose_copy_waits_then_is_retried_or_waived(stage, clock):
    stage.switched()
    stage.agent.copies = False
    subject = stage.rollback_subject()
    waiting = stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert waiting["copyPending"] is True
    record = stage.tool.machine.current()
    assert record["state"] == "rolling-back" and "rollbackCopyPendingSince" in record
    assert stage.database.tables() != []  # stopped and untouched while the copy waits
    stage.agent.available = False
    assert run_word(stage.tool, "retry-copy", {})["reason"] == "backup-volume-unfit"
    waiver_subject = {"cutoverId": record["cutoverId"], "perKind": {"accounts-created": 2}}
    done = run_word(stage.tool, "waive-copy", {
        "approvalId": stage.decide("rollback-copy-waiver", waiver_subject),
        "subject": waiver_subject})
    assert done["state"] == "rolled-back"
    incident = Incidents(stage.ledger, environment="live").get(
        record["rollbackCopyIncidentId"])
    assert incident["resolutionKind"] == "rollback-copy-settled"
    assert stage.database.tables() == []


def test_a_retried_copy_completes_the_rollback(stage, clock):
    stage.switched()
    stage.agent.copies = False
    subject = stage.rollback_subject()
    stage.tool.rollback(stage.decide("rollback", subject), subject)
    stage.agent.copies = True
    done = run_word(stage.tool, "retry-copy", {})
    assert done["state"] == "rolled-back", done


def test_a_rollback_is_cancelled_when_v1_does_not_start(stage, clock):
    stage.switched()
    stage.probes.v1 = False
    log = OperationLog(stage.operator)
    stage.platform.operator = log
    polls, started = stage.probes.v1_polls, clock()
    subject = stage.rollback_subject()
    waiting = stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert waiting == {"state": "rolling-back", "reason": "v1-restart-failed",
                       "offered": ["cancel-rollback"]}
    assert stage.probes.v1_polls - polls == 121
    assert (clock() - started).total_seconds() == 600
    assert v1_starts(stage, log) == {label: 1 for label in stage.platform.v1_labels}
    stage.platform.operator = stage.operator
    assert stage.database.tables() != []
    cancelled = run_word(stage.tool, "cancel-rollback",
                         {"approvalId": stage.decide("rollback-cancel")})
    assert cancelled == {"state": "switched"}
    assert stage.journey.tunnel()["origin"] == "v2-host"
    assert services(stage)["host"] == "running" and services(stage)["v1-api"] == "stopped"


def late_v1(stage, log) -> dict:
    """v1 not ready to its first three polls; the log's length at the fourth poll."""
    seen: dict = {}
    stage.probes.v1_polls, stage.probes.v1_late = 0, 3

    def polled(count: int) -> None:
        if count == 4:
            seen["at"] = len(log.order)

    stage.probes.on_v1_poll = polled
    return seen


def test_an_abort_waits_for_a_v1_that_answers_late_and_starts_it_once(stage, clock):
    """Step 71(k), L1-59: the abort polls v1's health every 5 s, routes to v1 only after
    it answers, and starts each v1 label once."""
    stage.start()
    log = OperationLog(stage.operator)
    stage.platform.operator = log
    seen, started = late_v1(stage, log), clock()
    result = run_word(stage.tool, "abort", {"reason": "operator-abort"})
    assert result["state"] == "rehearsing", result
    assert (clock() - started).total_seconds() == 15
    route = log.order.index(("platform.tunnel.route", "v1-web"))
    assert route >= seen["at"]
    assert v1_starts(stage, log) == {label: 1 for label in stage.platform.v1_labels}


def test_a_rollback_waits_for_a_v1_that_answers_late_and_starts_it_once(stage, clock):
    stage.switched()
    log = OperationLog(stage.operator)
    stage.platform.operator = log
    seen, started = late_v1(stage, log), clock()
    subject = stage.rollback_subject()
    result = stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert result["state"] == "rolled-back", result
    assert (clock() - started).total_seconds() == 15
    steps = [operation for operation, _ in log.order]
    assert steps.index("platform.v1.lifecycle.apply") >= seen["at"]
    assert v1_starts(stage, log) == {label: 1 for label in stage.platform.v1_labels}


def test_a_failed_v1_start_ends_the_abort_without_a_wait(stage, clock):
    stage.start()
    failing = stage.platform.v1_labels[0]
    log = OperationLog(stage.operator, fail_label=failing)
    stage.platform.operator = log
    polls, started = stage.probes.v1_polls, clock()
    result = run_word(stage.tool, "abort", {"reason": "operator-abort"})
    assert result == {"state": "aborting", "reason": "v1-restart-failed"}
    assert stage.probes.v1_polls == polls and clock() == started
    first = [key for (operation, label), key in zip(log.order, log.keys, strict=True)
             if label == failing]
    assert len(first) == 1
    # Run again: that label's start is asked for once more, under the next retry key.
    again = run_word(stage.tool, "abort", {})
    assert again["state"] == "rehearsing", again
    keys = [key for (operation, label), key in zip(log.order, log.keys, strict=True)
            if label == failing and operation == "platform.service.control"]
    assert keys[0] == first[0] and len(set(keys)) == 2


class OperationLog:
    """The operator, with each effect it is asked for recorded in order (operation and
    its target's key facts), and one named operation's first effect failed through U7's
    injected permission fault (a failed receipt bound under its key). `fail_label` fails
    the first effect on that label the same way (Step 71(k)); `keys` keeps each effect's
    key."""

    def __init__(self, operator, *, fail_once: str | None = None,
                 fail_label: str | None = None):
        self.operator, self.fail_once, self.order = operator, fail_once, []
        self.fail_label, self.keys = fail_label, []

    def execute(self, operation, target, inputs, *, key, **options):
        self.order.append((operation, inputs.get("label") or inputs.get("origin")
                           or inputs.get("action") or inputs.get("database")))
        self.keys.append(key)
        if operation == self.fail_once or (
                self.fail_label is not None and inputs.get("label") == self.fail_label):
            if operation == self.fail_once:
                self.fail_once = None
            else:
                self.fail_label = None
            return self.operator.execute(operation, target, inputs, key=key,
                                         injected_fault="permission", **options)
        return self.operator.execute(operation, target, inputs, key=key, **options)

    def __getattr__(self, name):
        return getattr(self.operator, name)


def soak_again(stage, clock, database: str) -> dict:
    """After a rollback: a dry run accepted onto `database`, the soak started on the
    verification already passed, and BR9.2 holding again on fresh evidence."""
    stage.accept_dry_run(database)
    assert stage.tool.soak_after_verification() == "started"
    record = stage.tool.machine.current()
    start = dt.datetime.fromisoformat(record["soakStartedAt"].replace("Z", "+00:00"))
    stage.soak_evidence(start, database)
    clock.advance(7 * DAY + 60)
    # A fresh inventory at the check's clock (L1-21).
    stage.tool.machine.inventory_taken(cf.complete_inventory(stage.ledger, now=clock())[
        "inventoryId"])
    assert stage.tool.rehearse_restart(stage.decide("v1-restart-rehearsal"))["rehearsed"]
    stage.isolation_passed()
    checked = stage.tool.check()
    # The first soak's stand-in sets (no archive on the volume) are retried by event and
    # still wait (`leftSets`; review finding, Major, R16); that holds back no switch.
    assert {name: checked[name] for name in ("state", "missing")} == {
        "state": "ready-to-switch", "missing": []}, checked
    assert set(checked) <= {"state", "missing", "leftSets"}, checked
    return stage.tool.machine.current()


def test_a_second_switch_after_a_rollback_rolls_back_through_every_step(stage, clock):
    """Switch, roll back, soak again, switch again, roll back again: the second rollback
    runs its own steps (maintenance, v2 stopped, v1 started, v2's outcomes applied to v1,
    v1's public check) before anything of v2's changes, and the production database is
    untouched until its copy (BR9.7, BR9.13; the CutoverRecord rows for `rolled-back`)."""
    stage.switched()
    subject = stage.rollback_subject()
    first = stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert first["state"] == "rolled-back", first
    second_database = stage.database.names.new("rehearsal")
    record = soak_again(stage, clock, second_database)
    # Leaving rolled-back left the first rollback's own facts behind.
    for name in ("rollbackV1ServingAt", "rollbackCopyIncidentId", "rollbackCopyPendingSince"):
        assert name not in record, name
    start_subject = stage.start_subject()
    started = stage.tool.start(stage.decide("switch-start", start_subject), start_subject)
    assert started["waiting"] == "final-report", started
    assert stage.switched(started=True)["state"] == "switched"
    stage.database.create()  # what v2 wrote while serving after the second opening
    stage.database.add_owner()
    log = OperationLog(stage.operator)
    stage.platform.operator = log
    stage.seen.unlink()
    stage.agent.copies = False  # the copy waits: nothing of v2's may change before it
    subject = stage.rollback_subject()
    waiting = stage.tool.rollback(stage.decide("rollback", subject), subject)
    assert waiting["copyPending"] is True, waiting
    steps = [operation for operation, _ in log.order]
    assert "platform.database.recreate" not in steps
    assert log.order[0] == ("platform.tunnel.route", "maintenance")
    started_v1 = steps.index("platform.service.control", steps.index(
        "platform.service.control") + len(stage.platform.v2_labels))
    assert log.order[started_v1][1] in stage.platform.v1_labels
    assert steps.index("platform.v1.lifecycle.apply") > started_v1
    assert ("platform.tunnel.route", "v1-web") in log.order
    assert stage.seen.exists()  # v2's outcomes reached v1 through v1's own code again
    assert stage.journey.tunnel()["origin"] == "v1-web"
    assert services(stage)["v1-api"] == "running" and services(stage)["host"] == "stopped"
    assert stage.database.tables() != []  # the production database is untouched
    record = stage.tool.machine.current()
    assert record["state"] == "rolling-back" and "rollbackV1ServingAt" in record
    assert record["rollbackV1ServingAt"] >= record["admissionOpenedAt"]
    # The retried copy completes it, and only then is the database recreated.
    stage.agent.copies = True
    done = run_word(stage.tool, "retry-copy", {})
    assert done["state"] == "rolled-back", done
    steps = [operation for operation, _ in log.order]
    assert steps.index("platform.database.recreate") > steps.index(
        "platform.v1.lifecycle.apply")
    assert stage.database.tables() == []


def test_a_failed_clear_at_opening_answers_and_open_run_again_completes_the_disposal(
        stage, clock):
    """The opening's clear of the profile's rehearsal database fails (a failed receipt
    bound under its key): `open` answers with the reason, removes nothing, and run again
    on the switched record it retries the clear, then removes the database (BR9.17)."""
    stage.start()
    run = stage.ledger.get("migration-run", stage.tool.machine.current()["finalRunId"])
    cf.accept(stage.ledger, run, now=clock())
    assert stage.tool.start()["waiting"] == "maintainer-window"
    log = OperationLog(stage.operator, fail_once="platform.profile.rehearsal-database")
    stage.platform.operator = log
    subject = stage.opening_subject()
    opened = stage.tool.open(stage.decide("admission-opening", subject), subject)
    assert opened["state"] == "switched", opened
    assert opened["rehearsalDatabaseCleared"] is False and opened["offered"] == ["open"]
    assert opened["reason"] == "profile-rehearsal-database-failed"
    assert opened["rehearsalDatabasesRemoved"] == []
    assert "platform.database.remove" not in [operation for operation, _ in log.order]
    assert stage.journey.read_state("profile.json")["rehearsalDatabase"] == stage.soak_database
    # Run again: the failed clear runs again under its next key, then the removal.
    again = run_word(stage.tool, "open", {})
    assert again["state"] == "switched" and again["rehearsalDatabaseCleared"] is True, again
    (soaked,) = [copy for copy in stage.ledger.records("retained-copy")
                 if copy["locations"] == [f"database/{stage.soak_database}"]]
    assert again["rehearsalDatabasesRemoved"] == [soaked["copyId"]]
    assert stage.journey.read_state("profile.json")["rehearsalDatabase"] is None
    # Run a third time, everything replays: nothing is removed twice.
    assert run_word(stage.tool, "open", {})["rehearsalDatabasesRemoved"] == []


class Killed(BaseException):
    """The operator's process ended mid-effect (killed, Ctrl-C, a closed terminal): the
    receipt is bound and the operation marked executing, and nothing settles it."""


class Unsettled:
    """The operator, with one named operation's first call ended as `how` says, through
    a second operator on the same store whose effect never runs: `killed` raises after
    `mark_executing` (the operation stays executing in U7's store); `lost` answers
    `unknown` without applying anything (the effect's answer lost before it ran)."""

    def __init__(self, stage, operation: str, how: str):
        from docsuri_ops.platform_control.executor import EffectOutcome

        self.operator, self.operation, self.operations = stage.operator, operation, []

        def never(**request):
            self.operations.append(request["operation_id"])
            if how == "killed":
                raise Killed()
            return EffectOutcome("unknown", [], {"kind": "internal", "message": "deadline"})

        self.unsettled = realm_operator(stage.journey.profile, "operator", stage.ledger,
                                        clock=stage.clock, facts=stage.operator.facts,
                                        run_effect=never)

    def __getattr__(self, name):
        return getattr(self.operator, name)

    def execute(self, operation, target, inputs, *, key, **options):
        if operation == self.operation and not self.operations:
            return self.unsettled.execute(operation, target, inputs, key=key, **options)
        return self.operator.execute(operation, target, inputs, key=key, **options)


def opening(stage, clock) -> tuple[dict, dict]:
    """The switch run to the maintainer window, and the opening's decision and subject."""
    stage.start()
    run = stage.ledger.get("migration-run", stage.tool.machine.current()["finalRunId"])
    cf.accept(stage.ledger, run, now=clock())
    assert stage.tool.start()["waiting"] == "maintainer-window"
    subject = stage.opening_subject()
    return stage.decide("admission-opening", subject), subject


def lease_passed(realm, operation_id: str) -> None:
    """The interrupted operation's lease deadline moved into the past, as time would."""
    with rf.admin(realm, "docsuri_u8_platform") as conn:
        conn.execute("UPDATE platform_control.target_lease SET deadline_at=clock_timestamp()"
                     "-interval '1 hour' WHERE operation_id=%s", (operation_id,))


def operation_state(realm, operation_id: str) -> tuple[str, str | None]:
    with rf.admin(realm, "docsuri_u8_platform") as conn:
        row = conn.execute(
            "SELECT o.state, r.reconciliation_state FROM platform_control.operation o JOIN "
            "platform_control.receipt r USING (operation_id) WHERE o.operation_id=%s",
            (operation_id,)).fetchone()
    return row[0], row[1]


def test_an_interrupted_step_is_reconciled_and_the_word_run_again_completes_it_once(
        stage, clock, realm):
    """`open`'s clear of the rehearsal database is interrupted after its receipt was bound
    (the operation left executing in U7's store). Run again within the lease it answers
    `effect-in-progress` and runs nothing beside it; once the lease has passed the same
    word promotes it, reconciles it from its target (not applied), runs the clear under
    its next retry key and completes the disposal; a third run replays everything."""
    approval, subject = opening(stage, clock)
    unsettled = Unsettled(stage, "platform.profile.rehearsal-database", "killed")
    stage.platform.operator = unsettled
    with pytest.raises(Killed):
        stage.tool.open(approval, subject)
    (interrupted,) = unsettled.operations
    assert operation_state(realm, interrupted)[0] == "executing"
    assert stage.tool.machine.current()["state"] == "switched"
    within = run_word(stage.tool, "open", {})
    assert within["rehearsalDatabaseCleared"] is False, within
    assert within["reason"] == "effect-in-progress" and within["offered"] == ["open"]
    assert stage.journey.read_state("profile.json")["rehearsalDatabase"] == stage.soak_database
    lease_passed(realm, interrupted)
    again = run_word(stage.tool, "open", {})
    assert again["rehearsalDatabaseCleared"] is True, again
    assert operation_state(realm, interrupted) == ("unknown", "reconciled-not-applied")
    assert stage.journey.read_state("profile.json")["rehearsalDatabase"] is None
    (soaked,) = [copy for copy in stage.ledger.records("retained-copy")
                 if copy["locations"] == [f"database/{stage.soak_database}"]]
    assert again["rehearsalDatabasesRemoved"] == [soaked["copyId"]]
    assert run_word(stage.tool, "open", {})["rehearsalDatabasesRemoved"] == []


def test_an_unknown_step_reconciled_not_applied_is_retried_by_the_word_run_again(
        stage, clock, realm):
    """`open`'s clear answers `unknown` and reconciles not applied: the word fails that step
    (`effect-outcome-unknown`). Run again, the replayed receipt (unknown, reconciled not
    applied) is a failure to retry, not a step to fail for ever: the clear runs under its
    next retry key and the disposal completes."""
    approval, subject = opening(stage, clock)
    unsettled = Unsettled(stage, "platform.profile.rehearsal-database", "lost")
    stage.platform.operator = unsettled
    opened = stage.tool.open(approval, subject)
    assert opened["rehearsalDatabaseCleared"] is False, opened
    assert opened["reason"] == "effect-outcome-unknown"
    (lost,) = unsettled.operations
    assert operation_state(realm, lost) == ("unknown", "reconciled-not-applied")
    again = run_word(stage.tool, "open", {})
    assert again["rehearsalDatabaseCleared"] is True, again
    assert stage.journey.read_state("profile.json")["rehearsalDatabase"] is None
    assert len(again["rehearsalDatabasesRemoved"]) == 1


def test_the_realms_rehearsal_creation_completes_a_create_cut_short_or_unanswered(realm):
    """On the realm's own instance: a create cut short (the database made, nothing
    copied) and a create whose answer was lost are each completed by the same create
    again, for the recorded name; a database of that name owned by another role is
    refused and left as it is."""
    from psycopg import sql

    from docsuri_ops.arrangement.paths import REALM_DATABASES
    from docsuri_ops.migration.realm import DISPOSABLE, RealmDatabases

    databases = RealmDatabases.for_realm(Path(realm.root))
    name, foreign = REALM_DATABASES.new("rehearsal"), REALM_DATABASES.new("rehearsal")

    def identity(database: str):
        with databases.admin(database) as conn:
            return conn.execute("SELECT run_id FROM public.docsuri_local_identity").fetchone()

    try:
        with databases.admin() as conn:
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER {} TEMPLATE template1").format(
                sql.Identifier(name), sql.Identifier(DISPOSABLE)))
            conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template1").format(
                sql.Identifier(foreign)))
        databases.create_rehearsal(name)  # cut short before: made again, whole
        assert identity(name) == (realm.run_id,)
        databases.create_rehearsal(name)  # its answer lost: the same create completes
        assert identity(name) == (realm.run_id,)
        with pytest.raises(ValueError, match="not the disposable role"):
            databases.create_rehearsal(foreign)
        with databases.admin() as conn:
            owner = conn.execute("SELECT pg_get_userbyid(datdba) FROM pg_database "
                                 "WHERE datname=%s", (foreign,)).fetchone()
        assert owner == ("postgres",)
    finally:
        rf.drop_database(realm, name)
        rf.drop_database(realm, foreign)


def test_settlement_and_the_words_refusals(stage, clock):
    stage.switched()
    with pytest.raises(Exception, match="INVALID_INPUT"):
        run_word(stage.tool, "settle", {"unknown": 1})
    clock.advance(14 * DAY + 1)
    subject = stage.settlement_subject()
    settled = run_word(stage.tool, "settle", {"approvalId": stage.decide("settlement", subject),
                                              "subject": subject})
    record = stage.tool.machine.current()
    assert settled["state"] == "settled" and settled["finalSnapshotRedated"] is True, settled
    assert settled["finalSnapshotCopyId"] == record["finalSnapshotCopyId"]
    assert len(stage.agent.set_dates) == 3


# --- v1's stores, deleted by hand (the person's decision of 2026-10-22, BR9.17) -----------


def place_v1_stores(stage) -> list[Path]:
    """The journey's stand-ins for v1's stores, one per recorded location."""
    paths = []
    for location in stage.platform.v1_stores:
        path = stage.tmp / location
        path.mkdir(parents=True, exist_ok=True)
        (path / "data.bin").write_bytes(b"v1")
        paths.append(path)
    return paths


def remove_tree(path: Path) -> None:
    for item in path.iterdir():
        item.unlink()
    path.rmdir()


def refusal(stage, document: dict | None = None) -> dict:
    from backend.modules.operations.errors import OperationsError

    with pytest.raises(OperationsError) as raised:
        run_word(stage.tool, "v1-stores-deleted", document or {})
    return {"code": raised.value.code, **(raised.value.current or {})}


def test_v1s_stores_deletion_is_recorded_only_after_it_and_only_at_its_date(stage, clock):
    from backend.modules.operations.lifecycle import backups_evidence

    opened = stage.switched()
    copy_id = opened["v1StoresCopyId"]
    stores = place_v1_stores(stage)
    # Before the approved date, nothing is recorded, deleted or not.
    assert refusal(stage)["reasonKey"] == "before-approved-date"
    clock.advance(90 * DAY + 60)
    # While any location is still there, the deletion is refused, naming what remains.
    assert refusal(stage) == {"code": "CONFLICT", "reasonKey": "v1-store-still-present",
                              "locations": list(stage.platform.v1_stores)}
    for path in stores[:-1]:
        remove_tree(path)
    assert refusal(stage)["locations"] == [stage.platform.v1_stores[-1]]
    copies = RetainedCopies(stage.ledger, SYNTHETIC_OPERATIONS)
    assert "disposedAt" not in copies.get(copy_id)
    assert all(path.exists() for path in stores[-1:])  # the tool never deletes them
    counted = backups_evidence(stage.ledger, SYNTHETIC_OPERATIONS,
                               schedule_active=True)["copiesCounted"]
    remove_tree(stores[-1])
    result = run_word(stage.tool, "v1-stores-deleted", {"copyId": copy_id})
    record = copies.get(copy_id)
    assert result["disposedAt"] == record["disposedAt"]
    assert record["disposalCheckRef"] == result["checkRef"]
    facts = stage.ledger.get("receipt-facts", record["disposalReceiptRef"])
    assert facts["operation"] == "platform.copy.dispose" and facts["outcome"] == "succeeded"
    name = f"v1-stores-deleted-{copy_id}.json"
    check = json.loads((stage.tmp / "evidence" / name).read_bytes())
    assert check["locations"] == [{"location": location, "present": False}
                                  for location in stage.platform.v1_stores]
    assert check["receiptId"] == record["disposalReceiptRef"]
    # Erase evidence stops counting the copy, and a second record is refused.
    assert backups_evidence(stage.ledger, SYNTHETIC_OPERATIONS,
                            schedule_active=True)["copiesCounted"] == counted - 1
    assert refusal(stage, {"copyId": copy_id})["reasonKey"] == "v1-stores-closed"


def test_v1s_stores_storage_incident_resolves_only_once_their_deletion_is_recorded(
    stage, clock
):
    from types import SimpleNamespace

    from backend.modules.operations.errors import OperationsError
    from docsuri_ops.cutover.disposal import DisposalPass, DisposalPlatform

    opened = stage.switched()
    copy_id = opened["v1StoresCopyId"]
    stores = place_v1_stores(stage)
    # The switch's final snapshot (recorded since Step 71(g)) is disposed of at its own
    # date by the agent's pass, long before 181 days: only v1's stores are left here.
    RetainedCopies(stage.ledger, SYNTHETIC_OPERATIONS, clock=clock).disposed_by_agent(
        stage.tool.machine.current()["finalSnapshotCopyId"], "agent:final-snapshot-disposed")
    clock.advance(181 * DAY)  # past the 180-day backstop, still in place
    # Where the standing job serves (L1-65): the stage is switched, so live.
    platform = DisposalPlatform(operator=stage.operator, names=stage.database.names,
                                current_rehearsal=lambda: None,
                                dispose_due=lambda document: {},
                                environment=lambda: "live" if stage.operator.facts().mode
                                == "live" else "rehearsal")
    report = DisposalPass(stage.ledger, SYNTHETIC_OPERATIONS, platform, clock=clock).run()
    assert f"backstop:{copy_id}" in report["incidents"]
    incidents = Incidents(stage.ledger, environment="live")
    incident = incidents.open_for("storage.capacity")
    assert f"retained-copy:{copy_id}:backstop" in incident["correlationIds"]
    available = {"storage.capacity": SimpleNamespace(state="available")}
    with pytest.raises(OperationsError) as kept:
        incidents.resolve(incident["incidentId"], "capability-available",
                          ["observation:storage.capacity"], states=available)
    assert kept.value.code == "EVIDENCE_REQUIRED"
    for path in stores:
        remove_tree(path)
    run_word(stage.tool, "v1-stores-deleted", {})
    again = DisposalPass(stage.ledger, SYNTHETIC_OPERATIONS, platform, clock=clock).run()
    assert f"backstop:{copy_id}" not in again["incidents"]
    resolved = incidents.resolve(incident["incidentId"], "capability-available",
                                 ["observation:storage.capacity"], states=available)
    assert resolved["state"] == "resolved"


def test_v1s_stores_deletion_is_recorded_only_in_person(stage, clock):
    from backend.modules.operations.errors import OperationsError
    from docsuri_ops.platform_control.errors import ControlError

    opened = stage.switched()
    clock.advance(90 * DAY + 60)
    standing = realm_operator(stage.journey.profile, "scheduler", stage.ledger, clock=clock,
                              facts=stage.operator.facts)
    stage.platform.operator = standing
    assert refusal(stage)["reasonKey"] == "in-person-required"
    # Below the tool, the standing authority's grant cannot bind it either.
    copy = RetainedCopies(stage.ledger, SYNTHETIC_OPERATIONS).get(opened["v1StoresCopyId"])
    inputs = {"recordKind": "RetainedCopy", "recordId": copy["copyId"], "place": "v1-stores",
              "locations": copy["locations"], "via": "in-person"}
    with pytest.raises(ControlError, match="only unattended"):
        standing.execute("platform.copy.dispose", "copies", inputs, key=f"v1s-{uuid4()}")
    # A standing request is refused by the standing scope first (no standing disposal of
    # any copy; the person's decision of 2026-10-26, "Drop it"), and A6's own
    # precondition refuses it too.
    with pytest.raises(ControlError, match="disposes of no copy"):
        standing.execute("platform.copy.dispose", "copies", {**inputs, "via": "standing"},
                         key=f"v1s-{uuid4()}")
    from docsuri_ops.u8_platform.u8_protocols import PreconditionRefused, check, load_revision

    with pytest.raises(PreconditionRefused, match="v1-stores-in-person-only"):
        check(load_revision().by_name("platform.copy.dispose"), "copies",
              {**inputs, "via": "standing"}, standing.facts())
    stage.platform.operator = stage.operator
    # Nothing was recorded, and the in-person path still works afterwards.
    assert "disposedAt" not in RetainedCopies(stage.ledger, SYNTHETIC_OPERATIONS).get(
        copy["copyId"])
    assert run_word(stage.tool, "v1-stores-deleted", {})["copyId"] == copy["copyId"]
    with pytest.raises(OperationsError):
        run_word(stage.tool, "v1-stores-deleted", {"unknown": 1})


def test_v1s_stores_deletion_follows_the_operations_own_refusals():
    """`platform.copy.dispose` at place `v1-stores`: only a v1-stores copy, in person, its
    recorded locations, at its approved date, and never during a switch, abort or
    rollback; no event brings it forward."""
    from docsuri_ops.u8_platform.u8_protocols import PreconditionRefused, check

    copy = {"copyId": "c-v1", "kind": "v1-stores", "locations": ["v1-stores/database"],
            "disposeAfter": "2026-10-22T11:00:00Z"}
    records = pf.Records(retained_copy=[copy])
    inputs = {"recordKind": "RetainedCopy", "recordId": "c-v1", "place": "v1-stores",
              "locations": ["v1-stores/database"], "via": "in-person"}
    protocol = pf.protocol("platform.copy.dispose")
    check(protocol, "copies", inputs, pf.facts(ledger=records))

    def reason(changes: dict, facts=None) -> str:
        with pytest.raises(PreconditionRefused) as refused:
            check(protocol, "copies", {**inputs, **changes}, facts or pf.facts(ledger=records))
        return refused.value.reason

    assert reason({"via": "standing"}) == "v1-stores-in-person-only"
    assert reason({"event": "settlement"}) == "v1-stores-input-refused"
    assert reason({"locations": ["v1-stores/objects"]}) == "v1-stores-locations-differ"
    early = pf.Records(retained_copy=[{**copy, "disposeAfter": "2026-10-23T00:00:00Z"}])
    assert reason({}, pf.facts(ledger=early)) == "disposal-point-not-reached"
    other = pf.Records(retained_copy=[{**copy, "kind": "dry-run-snapshot"}])
    assert reason({}, pf.facts(ledger=other)) == "v1-stores-input-refused"
    returned = pf.Records(retained_copy=[{**copy, "returnedToServiceAt": "2026-10-01"}])
    assert reason({}, pf.facts(ledger=returned)) == "copy-not-recorded"
    rolling = records.with_record("cutover-record", {"cutoverId": "x", "state": "rolling-back"})
    assert reason({}, pf.facts(ledger=rolling)) == "live-exclusion-held"


def test_the_realm_wiring_names_its_labels_probes_and_evidence(tmp_path, realm, clock,
                                                              monkeypatch):
    import backend.request_context as request_context

    journey = pf.journey(tmp_path, realm)
    ledger = rf.open_ledger(tmp_path, clock)
    read: list = []
    monkeypatch.setattr(request_context, "window_summaries",
                        lambda folder, **window: read.append((folder, window)) or {})
    try:
        platform = cutover_tool.realm_platform(journey.profile, ledger, clock=clock,
                                               policy=SYNTHETIC_OPERATIONS)
        assert platform.v1_labels == ("dev.docsuri.u8.run.v1-api", "dev.docsuri.u8.run.v1-web")
        assert platform.v2_labels == tuple(f"dev.docsuri.u8.run.{name}"
                                           for name in ("host", "workers", "scheduler"))
        assert platform.production == "docsuri_u8" and platform.first_backup is not None
        assert platform.create_rehearsal is not None  # a rollback's new rehearsal database
        # The realm's v2 and public address do not serve in this test: their probes answer
        # "not there". v1's probe answers exactly as the synthetic v1 does (`v1-up` runs
        # it for the integration-carrying phases).
        assert platform.v2_ready() is False and platform.public("v1-health") is False
        assert platform.v1_ready() is (cutover_tool.http_probe(
            f"{cutover_tool.REALM_V1_API}/health") == 200)
        assert platform.capabilities_missing() == ["readiness-unreadable"]
        assert platform.evidence.verification(str(uuid4())) is None
        assert platform.evidence.service_volume() == "stand-in"
        assert platform.evidence.isolation.read().passed is False
        assert platform.evidence.rehearsal_database() is None
        # The realm's own volume check, read through the agent's status word.
        status = platform.evidence.agent_status()
        assert "available" in status and "freeBytes" in status
        # The soak's latency lines are the run root's (Step 71(i)), and a snapshot's
        # parts are read from the migration's evidence folder (Step 70(a)).
        start = clock()
        platform.soak_latency(start, start + dt.timedelta(days=7))
        assert read == [(journey.profile.run_root / "evidence" / "latency",
                         {"start": start, "end": start + dt.timedelta(days=7),
                          "window_seconds": SYNTHETIC_OPERATIONS.latency_window_seconds})]
        assert platform.snapshot_parts is not None
    finally:
        ledger.close()


def test_the_cutover_word_reaches_the_tool_through_the_operator_cli(monkeypatch, capsys):
    import io

    from docsuri_ops.u8_platform import operator_tool as cli

    monkeypatch.setattr(sys, "stdin", type("In", (), {"buffer": io.BytesIO(b"[]")})())
    assert cli.main(["cutover", "status", "--environment-file", "/tmp/none/environment.json"]) == 1
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "INVALID_INPUT"


def test_the_realm_main_refuses_production(monkeypatch, capsys):
    import io

    monkeypatch.setattr(sys, "stdin", type("In", (), {"buffer": io.BytesIO(b"{}")})())
    assert cutover_tool.main(["status", "--production"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_the_v1_checkout_reader_reads_its_commit_and_fingerprint(tmp_path):
    calls = []

    class Done:
        def __init__(self, out: bytes, code: int = 0):
            self.stdout, self.returncode = out, code

    def run(argv, **options):
        calls.append(argv[3:])
        return Done(b"a" * 40 + b"\n") if "rev-parse" in argv else Done(b"")

    definition = tmp_path / "dev.docsuri.api.plist"
    definition.write_text("<plist/>")
    reader = cutover_tool.V1Checkout(tmp_path, (definition, tmp_path / "missing.plist"), run)
    first = reader()
    assert first["commit"] == "a" * 40 and first["clean"] is True
    definition.write_text("<plist changed/>")
    assert reader()["fingerprint"] != first["fingerprint"]
    failing = cutover_tool.V1Checkout(tmp_path, (), lambda argv, **o: Done(b"", 128))
    assert failing() is None
    assert os.path.exists(definition)
