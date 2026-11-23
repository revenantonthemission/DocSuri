"""A dry run on the synthetic v1 (U8 plan Step 32; BR8.3, BR8.9–BR8.11, BR8.15, BR9.12,
Workflow 9, functional-spec.md § State machine — MigrationRun).

The migration tool runs every phase on the realm: your go-ahead and your decision on the
report through `platform.decision.record`; a rehearsal database of the run's own with
the composed realm's schema; the backup agent's in-person `snapshot` of the synthetic
v1's database and its `snapshot-stream` of the index documents and the document models,
onto a stand-in volume of the test's own; the dump streamed back into the run's import
database; the owners' imports; the parity report; the idempotency pass; and every
disposal through PlatformControl's `platform.copy.dispose`. The free-disk reading is
injected: this Mac's own free space is not the subject.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from backend.modules.operations.migration.misfits import MAPPING_RULES, PROPOSALS
from backend.modules.operations.migration_records import MigrationRuns, MisfitDecisions
from backend.modules.operations.retained_copies import RetainedCopies
from backend.u8_policy import SYNTHETIC_OPERATIONS
from docsuri_ops.arrangement.paths import REALM_DATABASES
from docsuri_ops.backup_agent.config import AgentConfig, Login, write
from docsuri_ops.backup_agent.disposal import prepare_volume
from docsuri_ops.migration.disk_guard import DiskGuard
from docsuri_ops.migration.isolation_gate import IsolationGate
from docsuri_ops.migration.realm import RealmDatabases, owners_for
from docsuri_ops.migration.snapshot import Snapshot
from docsuri_ops.migration.tool import MigrationPlatform, MigrationTool
from docsuri_ops.u8_platform.drivers import load_config
from docsuri_ops.u8_platform.drivers.realm import RealmDriver
from docsuri_ops.u8_platform.u8_protocols import realm_operator
from tests.u8_service_operations_integration import platform_flows as pf
from tests.u8_service_operations_integration import recovery_flows as rf
from tests.u8_service_operations_integration import v1_flows as vf

ROOM = 100 * rf.GIB
COMMIT = "0" * 40
# The isolation reads before the import phase: the start, the preparing and copying
# boundaries, and the boundary once the copy completed.
LAPSE_AFTER_COPY = 4


def v1_agent(tmp_path: Path, realm, v1, clock) -> Path:
    """The agent's own folder and stand-in volume, with its read-only v1 login (the
    realm's agent login, which reads every database it is granted to read)."""
    driver = json.loads((Path(realm.root) / "platform" / "effects" / "driver.json").read_bytes())
    environment = json.loads((Path(realm.root) / "environment.json").read_bytes())
    volume, folder = tmp_path / "volume", tmp_path / "agent"
    for path in (volume, folder):
        path.mkdir(mode=0o700)
    prepare_volume(volume, clock=clock)
    password = rf.credentials(realm, "standin-credentials.json")["roles"]["backupAgent"]
    descriptor = os.open(folder / "v2-login", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(password)
    login = Login("127.0.0.1", realm.database_port, "docsuri_backup_agent", "v2-login")
    write(folder, AgentConfig(
        kind="realm", mount=volume, volume_identity="standin-migration-0001",
        database_prefix="docsuri_u8", v2_login=login, scheduler_uid=driver["schedulerUid"],
        operator_uid=driver["operatorUid"], service_uid=710,
        container=environment["container"], space_floor_bytes=1024**2,
        v1_database=v1.name, v1_login=login,
    ))
    return folder


def seconds_between(start: str, end: str) -> int:
    import datetime as dt

    return int((dt.datetime.fromisoformat(end) - dt.datetime.fromisoformat(start))
               .total_seconds())


class Gate:
    """The real isolation gate, which a test can make lapse after a number of reads."""

    def __init__(self, gate: IsolationGate):
        self.gate, self.lapse_after = gate, None
        self.reads = 0

    def read(self):
        self.reads += 1
        reading = self.gate.read()
        if self.lapse_after is not None and self.reads > self.lapse_after:
            return type(reading)(False, "isolation-stale", reading.checked_at)
        return reading


class Stage:
    def __init__(self, tmp_path, realm, clock, v1):
        self.realm, self.clock, self.v1 = realm, clock, v1
        agent = v1_agent(tmp_path, realm, v1, clock)
        self.journey = pf.journey(tmp_path, realm, mode="rehearsal",
                                  admission="maintainer-only", agentFolder=str(agent))
        self.ledger = rf.open_ledger(tmp_path, clock)
        self.operator = realm_operator(self.journey.profile, "operator", self.ledger,
                                       clock=clock)
        driver = RealmDriver(load_config(self.journey.profile.effects_root))
        self.volume = tmp_path / "volume"
        self.copies = RetainedCopies(self.ledger, SYNTHETIC_OPERATIONS, clock=clock)
        evidence = tmp_path / "evidence" / "migration"
        spool = tmp_path / "spool"
        spool.mkdir(mode=0o700)

        def dump(kind, record, decided):
            document = {"kind": kind, "recordId": record}
            if decided is not None:
                document["decided"] = decided
            return driver.agent_word("snapshot", document, via="in-person")

        self.snapshot = Snapshot(self.copies, dump=dump, stream=driver.snapshot_stream,
                                 index=v1.index_documents, objects=v1.objects,
                                 evidence=evidence)
        self.databases = RealmDatabases.for_realm(Path(realm.root))
        self.free = {"bytes": ROOM}
        # A test may answer the free reading itself (Step 90(e)).
        self.reading = None
        self.gate = Gate(IsolationGate(self.journey.state / "isolation",
                                       freshness_seconds=SYNTHETIC_OPERATIONS
                                       .isolation_freshness_seconds, clock=clock))
        platform = MigrationPlatform(
            operator=self.operator, names=REALM_DATABASES, snapshot=self.snapshot,
            create_rehearsal=self.databases.create_rehearsal,
            create_import=self.databases.create_import,
            restore_import=self.databases.restore_import,
            import_reader=self.databases.import_reader, owners_for=owners_for(realm),
            stream_back=driver.stream_back, isolation=self.gate,
            disk=DiskGuard(lambda: self.reading() if self.reading else self.free["bytes"],
                           SYNTHETIC_OPERATIONS.internal_disk_threshold_bytes),
            spool=spool, evidence=evidence, installed=lambda: True,
            database_bytes=self.databases.database_bytes,
        )
        self.runs = MigrationRuns(self.ledger, clock=clock)
        self.tool = MigrationTool(self.runs, self.copies, platform, clock=clock,
                                  tool_commit=COMMIT)
        self.isolation_passed()
        self.decide_all()

    def isolation_passed(self) -> None:
        receipt = self.operator.execute("platform.isolation.check", "isolation",
                                        {"via": "in-person"}, key=f"isolation-{pf.RUN}-"
                                        f"{self.clock().timestamp()}-{os.urandom(4).hex()}")
        assert receipt["outcome"] == "succeeded", receipt

    def decide_all(self) -> None:
        decisions = MisfitDecisions(self.ledger, clock=self.clock)
        for (kind, reason), decision in PROPOSALS.items():
            approval = rf.approval_record(self.ledger, "misfit-decision", f"{kind}:{reason}",
                                          now=self.clock())
            decisions.decide(kind, reason, decision, approval_id=approval["approvalId"],
                             mapping_rule=MAPPING_RULES.get((kind, reason))
                             if decision == "map" else None)

    def go_ahead(self) -> str:
        return rf.decide(self.operator, self.ledger, self.clock, "dry-run-go-ahead",
                         "synthetic-v1")

    def started(self) -> dict:
        return self.tool.start_dry(self.go_ahead())

    def databases_of(self, run: dict) -> dict:
        return {
            kind: [record["locations"][0].removeprefix("database/")
                   for record in self.copies.ledger.records("retained-copy")
                   if record["kind"] == kind and record["sourceRef"] == f"run:{run['runId']}"]
            for kind in ("rehearsal-database", "import-database")
        }

    def volume_files(self) -> list[str]:
        archives = self.volume / "docsuri-v2" / "archives"
        return sorted(path.name for path in archives.iterdir())

    def cleanup(self) -> None:
        for record in self.ledger.records("retained-copy"):
            for location in record["locations"]:
                if location.startswith("database/"):
                    rf.drop_database(self.realm, location.removeprefix("database/"))
        self.ledger.close()


def parsed(text: str):
    import datetime as dt

    return dt.datetime.fromisoformat(text)


class CopiesFirst:
    """U8 plan Step 90(e) (L1-2, L1-3): delegating spies on the platform's
    `create_rehearsal`, `create_import` and `restore_import` and on the snapshot's dump.
    Each reads the real ledger first, finds the open retained copy of its kind naming its
    database or snapshot with `sourceRef == run:<runId>`, then calls the real part and
    returns its result."""

    def __init__(self, stage: Stage, run_id: str):
        self.stage, self.run_id = stage, run_id
        self.seen: list[tuple[str, str, dict]] = []
        platform = stage.tool.platform
        for name, kind in (("create_rehearsal", "rehearsal-database"),
                           ("create_import", "import-database"),
                           ("restore_import", "import-database")):
            setattr(platform, name, self._wrap(getattr(platform, name), name, kind))
        real_dump = stage.snapshot.dump

        def dump(kind, record_id, decided):
            self.seen.append(("dump", record_id, self._open(
                lambda item: item["copyId"] == record_id
                and item["kind"] in ("dry-run-snapshot", "v1-final-snapshot"))))
            return real_dump(kind, record_id, decided)

        stage.snapshot.dump = dump

    def _open(self, matches) -> dict:
        found = [item for item in self.stage.ledger.records("retained-copy")
                 if matches(item) and item["sourceRef"] == f"run:{self.run_id}"
                 and "disposedAt" not in item]
        assert len(found) == 1, found
        return found[0]

    def _wrap(self, real, name: str, kind: str):
        def spy(database, *args, **kwargs):
            self.seen.append((name, database, self._open(
                lambda item: item["kind"] == kind
                and item["locations"] == [f"database/{database}"])))
            return real(database, *args, **kwargs)

        return spy

    def days(self, name: str) -> list[float]:
        return [(parsed(record["disposeAfter"]) - parsed(record["createdAt"]))
                .total_seconds() / 86400 for part, _, record in self.seen if part == name]


@pytest.fixture(scope="module")
def synthetic_v1(realm):
    v1 = vf.SyntheticV1(realm).create()
    yield v1
    v1.drop()


@pytest.fixture
def stage(tmp_path, realm, clock, synthetic_v1):
    value = Stage(tmp_path, realm, clock, synthetic_v1)
    yield value
    value.cleanup()


def test_the_full_machine_path_to_accepted(stage, realm):
    run = stage.started()
    assert run["state"] == "preparing" and run["decisionsDigest"]
    spies = CopiesFirst(stage, run["runId"])
    reported = stage.tool.run(run["runId"])
    assert reported["state"] == "reported", reported
    # Each copy was recorded before its database or snapshot was made (L1-2), with its
    # kind's backstop as its date.
    assert [part for part, _, _ in spies.seen] == [
        "create_rehearsal", "dump", "create_import", "restore_import"]
    assert spies.days("create_rehearsal") == [60]
    assert spies.days("create_import") == spies.days("restore_import") == [14]
    assert spies.days("dump") == [14]
    assert spies.seen[1][2]["kind"] == "dry-run-snapshot"
    # Its times (Step 68(g), L1-59): the snapshot's start is its copy's `createdAt`.
    snapshot_copy = stage.copies.get(reported["snapshotCopyId"])
    assert reported["snapshotStartedAt"] == snapshot_copy["createdAt"]
    assert set(reported["phaseSeconds"]) == {"preparing", "copying", "importing", "verifying"}
    assert reported["interruptions"] == 0
    assert reported["durationSeconds"] == seconds_between(reported["snapshotStartedAt"],
                                                          reported["reportedAt"])
    approval = rf.decide(stage.operator, stage.ledger, stage.clock, "dry-run-report",
                         run["runId"])
    accepted = stage.tool.decide(run["runId"], approval)
    assert accepted["state"] == "accepted" and accepted["acceptedAt"]
    # Its copy of v1 is disposed; its rehearsal database stays, the soak's database.
    snapshot = stage.copies.get(accepted["snapshotCopyId"])
    assert snapshot["disposedAt"] and snapshot["completedAt"] and snapshot["checksum"]
    assert stage.volume_files() == []
    databases = stage.databases_of(accepted)
    assert rf.database_exists(realm, databases["rehearsal-database"][0])
    assert stage.runs.dry_run_current()


def test_the_idempotency_pass_imports_and_updates_nothing(stage):
    from backend.modules.operations.migration.misfits import Decisions
    from backend.modules.operations.migration.phases import ImportRun
    from backend.modules.operations.migration.v1_source import V1Source

    run = stage.started()
    assert stage.tool.run(run["runId"])["state"] == "reported"
    current = stage.runs.require(run["runId"])
    target = stage.databases_of(current)["rehearsal-database"][0]
    owners, close = owners_for(stage.realm)(target)
    try:
        with stage.v1.connect() as conn:
            tallies = ImportRun(V1Source(conn, index_documents=stage.v1.index_documents(),
                                         objects=stage.v1.objects()),
                                owners, Decisions.from_ledger(stage.ledger),
                                clock=stage.clock).run()
    finally:
        close()
    assert sum(tally.imported + tally.updated for tally in tallies.values()) == 0
    assert tallies["account"].unchanged == 5


def test_the_parity_report_reconciles_and_holds_no_secret_or_content(stage):
    # Step 86(d): every logger captured at DEBUG during the run, as test_log_exposure.py
    # captures it; each logger's level, handlers and propagate flag restored afterwards.
    from tests.u8_service_operations_integration.integration.test_log_exposure import (
        debug_capture,
        record_text,
    )

    with debug_capture() as captured:
        run = stage.started()
        assert stage.tool.run(run["runId"])["state"] == "reported"
    assert captured.records, "the run wrote no record to capture"
    for record in captured.records:
        text = record_text(record)
        for forbidden in ("@", "$argon2", "pbkdf2", vf.V1_PASSWORD, "Paragraph",
                          "google-provider", "Ada Synthetic"):
            assert forbidden not in text, (record.name, forbidden)
    record = stage.ledger.get("parity-report", run["runId"])
    assert record["reconciles"] is True and record["kinds"] >= 10
    path = stage.tool.platform.evidence / Path(record["reportRef"]).name
    assert (path.stat().st_mode & 0o777) == 0o600
    text = path.read_text()
    report = json.loads(text)
    assert all(kind["reconciles"] for kind in report["kinds"])
    for forbidden in ("@", "$argon2", vf.V1_PASSWORD, "Paragraph", "pbkdf2", "google-provider",
                      "Ada Synthetic"):
        assert forbidden not in text, forbidden
    accounts = next(kind for kind in report["kinds"] if kind["kind"] == "account")
    assert accounts["imported"] == 5 and accounts["sourceChecksum"] == accounts["targetChecksum"]
    assert accounts["excluded"] == {"archive-only": 6}
    # The corpus limit record (Step 68(i), L1-79), in the file `migration accept` shows.
    assert record["reportDigest"] == __import__("hashlib").sha256(path.read_bytes()).hexdigest()
    paper = next(kind for kind in report["kinds"] if kind["kind"] == "paper")
    assert paper["reconciles"] is True
    assert paper["limits"] == expected_limits(stage, run)


def expected_limits(stage, run: dict) -> dict:
    """The record a run over the synthetic v1 holds: three chunks at most, 2101.00002
    refused by its chunk count, and the largest stored file of its rehearsal database."""
    import dataclasses

    from backend.modules.corpus.limits import PRODUCTION_LIMITS
    from backend.transactions import OwnerTransactions

    target = stage.databases_of(stage.runs.require(run["runId"]))["rehearsal-database"][0]
    transactions = OwnerTransactions(dataclasses.replace(stage.realm, database_name=target))
    try:
        rows = transactions.run("corpus", lambda conn: conn.execute(
            "SELECT private_path FROM corpus.version").fetchall())
    finally:
        transactions.close()
    folder = Path(stage.realm.root) / "corpus-files"
    largest = max((folder / row["private_path"]).stat().st_size for row in rows)
    return {
        "profile": "production",
        "chunks": {"limit": PRODUCTION_LIMITS.max_chunks, "checked": True, "largest": 3,
                   "refused": 1},
        "sourceBytes": {"limit": 16_777_216, "checked": True, "largest": largest,
                        "refused": 0},
        "elements": {"limit": 250_000, "checked": False, "largest": None, "refused": 0},
        "depth": {"limit": 256, "checked": False, "largest": None, "refused": 0},
    }


def test_a_dry_run_records_a_time_refused_paper_and_reports(stage, monkeypatch):
    """Step 69(h) (L1-75): the paper the database's time limits refuse during `importing`
    is recorded and reported; the idempotency pass, with the spy gone, skips it."""
    import psycopg

    from backend.modules.operations.migration.v1_source import V1Source

    run = stage.started()

    def importing() -> bool:
        return stage.runs.require(run["runId"])["state"] == "importing"

    with vf.refusing("arxiv:2101.00006@v1", "sleep", when=importing):
        reported = stage.tool.run(run["runId"])
    assert reported["state"] == "reported", reported
    assert stage.ledger.get("misfit-record", (run["runId"], "paper", "2101.00006:v1",
                                              "refused-by-database-time-limits")) is not None
    record = stage.ledger.get("parity-report", run["runId"])
    report = json.loads((stage.tool.platform.evidence / Path(record["reportRef"]).name)
                        .read_bytes())
    paper = next(kind for kind in report["kinds"] if kind["kind"] == "paper")
    assert {"kind": "paper", "sourceId": "2101.00006:v1",
            "reasonKey": "refused-by-database-time-limits",
            "newInFinal": False} in paper["misfits"]

    # The idempotency pass ran without the spy and the run still reported: it did not ask
    # again for the refused paper (addition 3). Declined, so the next run may start.
    declined = rf.decide(stage.operator, stage.ledger, stage.clock, "dry-run-report",
                         run["runId"], decision="declined")
    assert stage.tool.decide(run["runId"], declined)["state"] == "rejected"

    # A raise-only database error at a v1 read fails the run and disposes its copies.
    second = stage.started()

    def unreadable(self):
        raise psycopg.OperationalError("stand-in: v1 read refused")

    monkeypatch.setattr(V1Source, "saved", unreadable)
    failed = stage.tool.run(second["runId"])
    assert (failed["state"], failed["reason"]) == ("failed", "OperationalError")
    for item in stage.ledger.records("retained-copy"):
        if item["sourceRef"] == f"run:{second['runId']}":
            assert "disposedAt" in item, item


def test_an_interrupted_run_resumes_only_its_phase_against_a_reverified_snapshot(stage):
    run = stage.started()
    # The isolation evidence lapses at the boundary after the copy completes.
    stage.gate.lapse_after = LAPSE_AFTER_COPY
    interrupted = stage.tool.run(run["runId"])
    assert interrupted["state"] == "interrupted"
    assert interrupted["interruptedPhase"] == "importing", interrupted
    assert interrupted["reason"] == "isolation-stale"
    started_at = interrupted["snapshotStartedAt"]
    stage.gate.lapse_after = None
    copies_before = len(stage.ledger.records("retained-copy"))
    resumed = stage.tool.resume(run["runId"])
    assert resumed["state"] == "reported", resumed
    # The resume keeps the snapshot's start and counts the interruption (Step 68(g)).
    assert resumed["interruptions"] == 1 and resumed["snapshotStartedAt"] == started_at
    # Resuming importing took no new copy of v1: the same snapshot, re-verified.
    snapshots = [item for item in stage.ledger.records("retained-copy")
                 if item["kind"] == "dry-run-snapshot"]
    assert len(snapshots) == 1
    assert len(stage.ledger.records("retained-copy")) == copies_before + 1  # its import DB


def test_a_changed_snapshot_is_refused_when_importing_resumes(stage):
    run = stage.started()
    stage.gate.lapse_after = LAPSE_AFTER_COPY
    interrupted = stage.tool.run(run["runId"])
    assert interrupted["interruptedPhase"] == "importing"
    stage.gate.lapse_after = None
    snapshot = stage.copies.get(stage.runs.require(run["runId"])["snapshotCopyId"])
    parts = stage.snapshot.parts_path(snapshot["copyId"])
    value = json.loads(parts.read_bytes())
    value["index"]["sha256"] = "0" * 64
    parts.write_bytes(json.dumps(value).encode())
    failed = stage.tool.resume(run["runId"])
    assert failed["state"] == "failed" and failed["reason"] == "snapshot-checksum-differs"
    # The failed run's copy of v1 is disposed (Step 90(e)).
    assert_snapshot_disposed(stage, run)


def test_an_abandoned_run_disposes_of_its_copies(stage, realm):
    run = stage.started()
    stage.gate.lapse_after = LAPSE_AFTER_COPY
    stage.tool.run(run["runId"])
    stage.gate.lapse_after = None
    current = stage.runs.require(run["runId"])
    assert current["state"] == "interrupted"
    assert stage.volume_files() != []
    abandoned = stage.tool.abandon(run["runId"])
    assert abandoned["state"] == "failed" and abandoned["reason"] == "abandoned"
    for record in stage.ledger.records("retained-copy"):
        assert record["sourceRef"] != f"run:{run['runId']}" or "disposedAt" in record, record
    assert stage.volume_files() == []
    databases = stage.databases_of(current)
    assert not rf.database_exists(realm, databases["rehearsal-database"][0])


def test_an_isolation_lapse_or_the_disk_guard_interrupts_the_run(stage):
    from backend.modules.operations.errors import OperationsError

    # A stale result refuses the start itself.
    stage.clock.advance(SYNTHETIC_OPERATIONS.isolation_freshness_seconds + 1)
    with pytest.raises(OperationsError) as refused:
        stage.started()
    assert refused.value.current == {"reasonKey": "isolation-stale"}
    stage.clock.advance(-(SYNTHETIC_OPERATIONS.isolation_freshness_seconds + 1))
    # The disk guard (L1-17): the free reading is BASE less what the run's databases hold
    # at the moment the tool reads them. The figure is the one the tool itself read just
    # before it reads the free space (`_held`, a call-through spy), so database growth
    # between two separate readings cannot move the boundary.
    gib = rf.GIB
    assert SYNTHETIC_OPERATIONS.internal_disk_threshold_bytes == 20 * gib
    assert stage.copies.policy.first_rehearsal_estimate_bytes == 4 * gib
    assert stage.runs.latest_accepted("dry") is None
    run = stage.started()
    held_seen: list[int] = []
    real_held = stage.tool._held

    def held_spy(current: dict) -> int:
        value = int(real_held(current))
        held_seen.append(value)
        return value

    stage.tool._held = held_spy

    def base() -> int:
        snapshot = stage.copies.get(stage.runs.require(run["runId"])["snapshotCopyId"])
        return 20 * gib + int(snapshot["sourceDatabaseBytes"]) + 4 * gib

    def papers() -> int:
        [rehearsal] = stage.databases_of(run)["rehearsal-database"]
        with rf.admin(stage.realm, rehearsal) as conn:
            return conn.execute("SELECT count(*) FROM corpus.version").fetchone()[0]

    mode = {"offset": 0, "critical": False}
    # (the tool's figure, both databases measured here, the import database's own size)
    compared: list[tuple[int, int, int]] = []

    def measured() -> None:
        names = stage.databases_of(run)
        if not names["import-database"] or not rf.database_exists(
                stage.realm, names["import-database"][0]):
            return
        sizes = [stage.databases.database_bytes(name) for name in (
            names["rehearsal-database"][0], names["import-database"][0])]
        compared.append((held_seen[-1], sum(sizes), sizes[1]))

    def reading() -> int:
        if mode["critical"] and papers() >= 1:
            return 10 * gib - 1
        measured()
        return base() + mode["offset"] - held_seen[-1]

    stage.reading = reading
    # At BASE, the run is interrupted at importing, before the import database exists.
    interrupted = stage.tool.run(run["runId"])
    assert (interrupted["state"], interrupted["interruptedPhase"], interrupted["reason"]) == (
        "interrupted", "importing", "internal-disk-low"), interrupted
    assert stage.databases_of(run)["import-database"] == []
    # At BASE + 1, both guards pass: the second only because the import database's
    # holdings are subtracted. Once the rehearsal database holds its first paper version,
    # the reading falls below the critical floor and the run stops before the next paper.
    mode.update(offset=1, critical=True)
    stopped = stage.tool.resume(run["runId"])
    assert (stopped["state"], stopped["interruptedPhase"], stopped["reason"]) == (
        "interrupted", "importing", "internal-disk-critical"), stopped
    [imported] = stage.databases_of(run)["import-database"]
    assert rf.database_exists(stage.realm, imported)
    assert papers() == 1
    # Every figure the tool subtracted once the import database existed held both
    # databases: the import database alone is several MiB, far above any growth between
    # the tool's reading and this one.
    assert compared and all(size > 2 * 1024**2 for _, _, size in compared)
    assert all(abs(tool - here) < 1024**2 for tool, here, _ in compared), compared
    # Back at BASE + 1 less what is held, the run resumes to `reported`.
    mode["critical"] = False
    assert stage.tool.resume(run["runId"])["state"] == "reported"


def test_the_import_database_is_removed_whatever_the_outcome(stage, realm):
    accepted = stage.started()
    stage.tool.run(accepted["runId"])
    approval = rf.decide(stage.operator, stage.ledger, stage.clock, "dry-run-report",
                         accepted["runId"])
    stage.tool.decide(accepted["runId"], approval)
    rejected = stage.started()
    stage.tool.run(rejected["runId"])
    declined = rf.decide(stage.operator, stage.ledger, stage.clock, "dry-run-report",
                         rejected["runId"], decision="declined")
    assert stage.tool.decide(rejected["runId"], declined)["state"] == "rejected"
    for run in (accepted, rejected):
        [name] = stage.databases_of(run)["import-database"]
        assert not rf.database_exists(realm, name)
        [record] = [item for item in stage.ledger.records("retained-copy")
                    if item["kind"] == "import-database"
                    and item["sourceRef"] == f"run:{run['runId']}"]
        assert record["disposedAt"] and record["disposalReceiptRef"]
    # A rejected run's rehearsal database goes with its copy.
    [rehearsal] = stage.databases_of(rejected)["rehearsal-database"]
    assert not rf.database_exists(realm, rehearsal)
    # And its copy of v1 is disposed (Step 90(e)).
    assert_snapshot_disposed(stage, rejected)


def assert_snapshot_disposed(stage, run: dict) -> None:
    [snapshot] = [item for item in stage.ledger.records("retained-copy")
                  if item["kind"] == "dry-run-snapshot"
                  and item["sourceRef"] == f"run:{run['runId']}"]
    assert snapshot["disposedAt"] and snapshot["disposalReceiptRef"]
    assert stage.volume_files() == []


class StandInNames:
    """The realm's names with a production stand-in of the test's own (a database under
    the rehearsal naming, which the owners' imports may reach), never `docsuri_u8`."""

    def __init__(self, production: str):
        self.production, self.prefix = production, "docsuri_u8"

    def kind_of(self, name: str):
        return "production" if name == self.production else REALM_DATABASES.kind_of(name)

    def new(self, kind: str) -> str:
        return REALM_DATABASES.new(kind)

    def pattern(self, kind: str):
        return REALM_DATABASES.pattern(kind)


def test_a_final_run_inside_the_switch_imports_under_the_frozen_decisions(stage, realm):
    from docsuri_ops.u8_platform.u8_protocols import realm_facts

    first = stage.started()
    assert stage.tool.run(first["runId"])["state"] == "reported"
    stage.tool.decide(first["runId"], rf.decide(stage.operator, stage.ledger, stage.clock,
                                                "dry-run-report", first["runId"]))
    # The dry run met (kind, reason)s Workflow 10's table does not list: you decide each,
    # and a dry run under the decisions current now is accepted before the switch.
    current = MisfitDecisions(stage.ledger, clock=stage.clock)
    undecided = current.current().undecided(stage.runs.met_pairs(first["runId"]))
    assert ("saved-paper", "dependency-not-migrated") in undecided
    for kind, reason in undecided:
        decision = rf.approval_record(stage.ledger, "misfit-decision", f"{kind}:{reason}",
                                      now=stage.clock())
        current.decide(kind, reason, "archive-only", approval_id=decision["approvalId"])
    assert not stage.runs.dry_run_current()
    dry = stage.started()
    assert stage.tool.run(dry["runId"])["state"] == "reported"
    stage.tool.decide(dry["runId"], rf.decide(stage.operator, stage.ledger, stage.clock,
                                              "dry-run-report", dry["runId"]))
    assert stage.runs.dry_run_current()
    production = REALM_DATABASES.new("rehearsal")
    stage.databases.create_rehearsal(production)
    names = StandInNames(production)
    base = realm_facts(stage.journey.profile, stage.ledger, clock=stage.clock)

    def facts():
        current = base()
        current.names = names
        return current

    operator = realm_operator(stage.journey.profile, "operator", stage.ledger,
                              clock=stage.clock, facts=facts)
    stage.tool.platform.operator = operator
    stage.tool.platform.names = names
    stage.tool.platform.prepare_production = stage.databases.prepare_production
    cutover = rf.cutover_record(stage.ledger, "preparing")
    for state in ("rehearsing", "ready-to-switch", "switching"):
        cutover = rf.advance_cutover(stage.ledger, cutover, state)
    approval = rf.decide(operator, stage.ledger, stage.clock, "switch-start",
                         cutover["cutoverId"])
    try:
        # L1-3's switch-start date: 120 days on, the final copy's backstop; the injected
        # clock does not move.
        switch_start = stage.clock() + __import__("datetime").timedelta(days=120)
        final = stage.tool.start_final(approval_id=approval, dispose_after=switch_start)
        assert all(item["frozen"] for item in stage.ledger.records("misfit-decision"))
        spies = CopiesFirst(stage, final["runId"])
        reported = stage.tool.run(final["runId"])
        assert reported["state"] == "reported", reported
        assert [part for part, _, _ in spies.seen] == ["dump", "create_import",
                                                       "restore_import"]
        assert spies.days("create_import") == spies.days("restore_import") == [14]
        final_copy = spies.seen[0][2]
        assert final_copy["kind"] == "v1-final-snapshot"
        from backend.modules.operations.ledger import utc_text

        assert final_copy["disposeAfter"] == utc_text(switch_start)
        assert stage.copies.backstop_of(final_copy) == parsed(
            final_copy["createdAt"]) + __import__("datetime").timedelta(days=120)
        assert stage.copies.backstop_of(final_copy) == parsed(final_copy["disposeAfter"])
        assert final_copy["disposalApprovalId"] == approval
        report = stage.ledger.get("parity-report", final["runId"])
        assert report["reconciles"] is True
        # Every (kind, reason) the final run met, the accepted dry run met too.
        assert not any(item["newInFinal"] for item in stage.ledger.records("misfit-record")
                       if item["runId"] == final["runId"])
        accepted = stage.tool.decide(final["runId"], rf.decide(
            operator, stage.ledger, stage.clock, "final-report", final["runId"]))
        assert accepted["state"] == "accepted"
        snapshot = stage.copies.get(accepted["snapshotCopyId"])
        assert snapshot["kind"] == "v1-final-snapshot" and snapshot["completedAt"]
        assert "disposedAt" not in snapshot and snapshot["disposalApprovalId"] == approval
        [imported] = stage.databases_of(accepted)["import-database"]
        assert not rf.database_exists(realm, imported)
        with rf.admin(realm, production) as conn:
            assert conn.execute("SELECT count(*) FROM accounts.account").fetchone()[0] == 5
        # The freeze holds until the cutover aborts or rolls back (BR8.9).
        assert all(item["frozen"] for item in stage.ledger.records("misfit-decision"))
    finally:
        rf.drop_database(realm, production)


def test_the_v1_readers_read_every_document_and_object_within_their_bounds():
    """v1's index through the scroll API on loopback only, and its document models
    through an S3 client, each answered by a stand-in of v1's own store."""
    import httpx

    from docsuri_ops.migration.snapshot import BucketObjects, OpenSearchDocuments, SnapshotRefused

    pages = [[{"_source": {"paperId": "p", "version": 1}}], [{"_source": {"paperId": "q"}}], []]
    seen = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        return httpx.Response(200, json={"_scroll_id": "s", "hits": {"hits": pages.pop(0)}})

    reader = OpenSearchDocuments("http://127.0.0.1:19209", "docsuri-corpus",
                                 transport_factory=lambda: httpx.MockTransport(answer))
    assert reader() == [{"paperId": "p", "version": 1}, {"paperId": "q"}]
    assert seen == [("POST", "/docsuri-corpus/_search"), ("POST", "/_search/scroll"),
                    ("POST", "/_search/scroll")]
    with pytest.raises(SnapshotRefused):
        OpenSearchDocuments("https://search.example.com", "i")
    broken = OpenSearchDocuments("http://127.0.0.1:19209", "i", transport_factory=lambda:
                                 httpx.MockTransport(lambda request: httpx.Response(500)))
    with pytest.raises(SnapshotRefused):
        broken()

    read_sizes: list[int | None] = []

    class Body:
        """A stream: each read answers from where the last one stopped."""

        def __init__(self, payload):
            self.payload, self.offset = payload, 0

        def read(self, size=None):
            read_sizes.append(size)
            end = len(self.payload) if size is None else self.offset + size
            chunk = self.payload[self.offset:end]
            self.offset += len(chunk)
            return chunk

    class StreamCut(Exception):
        """What botocore raises when a body ends before its Content-Length."""

    class ShortBody:
        """A body cut short: its bounded read answers fewer bytes than its length, and
        the read that would check that length raises, as botocore's does."""

        def __init__(self, served: bytes):
            self.served, self.done = served, False

        def read(self, size=None):
            if self.done:
                raise StreamCut("1 of 4 bytes read")
            self.done = True
            return self.served

    from backend.modules.operations.migration.v1_source import split_listing
    from docsuri_ops.backup_agent.archives import pack
    from docsuri_ops.migration import snapshot as snapshot_module

    listed = [
        ("doc-model/a/v1.json", 2), ("doc-model/z/v1.json", 2), ("assets/a/v1/fig1.webp", 2),
        ("uploads/evidence/u/a/a/paper.pdf", 64 * 1024 * 1024),
        ("private/userdoc/u/d/v1.json", 2),
    ]

    class Client:
        """v1's bucket, asked with no `Prefix`: two pages holding five keys."""

        def __init__(self):
            entries = [{"Key": key, "Size": size, "ETag": f'"etag-{index}"'}
                       for index, (key, size) in enumerate(listed)]
            # The page's continuation value, generated per run (L1-36).
            self.continuation = os.urandom(8).hex()
            self.pages = [
                {"Contents": entries[:3], "IsTruncated": True,
                 "NextContinuationToken": self.continuation},
                {"Contents": entries[3:], "IsTruncated": False},
            ]
            self.asked: list[str] = []

        def list_objects_v2(self, **options):
            assert "Prefix" not in options
            assert options.get("ContinuationToken") == (
                None if len(self.pages) == 2 else self.continuation)
            return self.pages.pop(0)

        def get_object(self, *, Bucket, Key):
            self.asked.append(Key)
            return {"Body": Body(Key.encode())}

    client = Client()
    read = BucketObjects(client, "v1-bucket")()
    members = {key: value for key, value in read.items() if key != "v1-object-listing.jsonl"}
    assert members == {"doc-model/a/v1.json": b"doc-model/a/v1.json",
                       "doc-model/z/v1.json": b"doc-model/z/v1.json"}
    expected = sorted(({"key": key, "size": size, "etag": f'"etag-{index}"'}
                       for index, (key, size) in enumerate(listed)), key=lambda item: item["key"])
    assert split_listing(read["v1-object-listing.jsonl"]) == expected
    assert client.asked == ["doc-model/a/v1.json", "doc-model/z/v1.json"]
    # Each member body is read at most one byte past the 16 MiB bound, then finished with
    # one unbounded read, which checks the body against its length.
    assert read_sizes == [16 * 1024 * 1024 + 1, None] * 2
    # A body cut short is not passed as complete: the finishing read raises, so the copy
    # stops and is taken again (BR8.15).
    cut = Client()
    cut.get_object = lambda *, Bucket, Key: {"Body": ShortBody(b"{")}
    with pytest.raises(StreamCut):
        BucketObjects(cut, "v1-bucket")()
    # A member rewritten after the listing (listed at 2 bytes, served longer than 16 MiB)
    # is refused on the bytes read, not passed on the listed size.
    rewritten = Client()
    rewritten.get_object = lambda *, Bucket, Key: {"Body": Body(b"x" * (16 * 1024 * 1024 + 2))}
    with pytest.raises(SnapshotRefused) as refused:
        BucketObjects(rewritten, "v1-bucket")()
    assert refused.value.reason == "v1-objects-exceed-their-bound"
    # A member listed over 16 MiB is refused; the 64 MiB upload, never read, is not.
    huge = Client()
    huge.pages[0]["Contents"][0]["Size"] = 16 * 1024 * 1024 + 1
    with pytest.raises(SnapshotRefused) as refused:
        BucketObjects(huge, "v1-bucket")()
    assert refused.value.reason == "v1-objects-exceed-their-bound"
    original = snapshot_module.MAX_LISTED_OBJECTS
    snapshot_module.MAX_LISTED_OBJECTS = 4
    try:
        with pytest.raises(SnapshotRefused) as refused:
            BucketObjects(Client(), "v1-bucket")()
        assert refused.value.reason == "v1-object-listing-exceeds-its-bound"
    finally:
        snapshot_module.MAX_LISTED_OBJECTS = original
    # The tool hands V1Source the members as `objects` and the entries as `listing`.
    index = pack({"documents.jsonl": b""})
    unpacked = MigrationTool._unpacked({"index": index, "objects": pack(read)})
    assert unpacked["objects"] == members and unpacked["listing"] == expected
    assert MigrationTool._unpacked({"index": index, "objects": pack(members)})[
        "listing"] == []


def test_the_snapshot_lists_v1s_uploads_by_key_and_size():
    """U8 plan Step 90(e) (L1-20): v1's uploads, under `uploads/<module>/...` and under
    `novelty/...`, are listed in the reserved member by key, size and ETag; their bodies
    are never read, and one over `MAX_OBJECT_BYTES` does not refuse the snapshot."""
    from backend.modules.operations.migration.v1_source import LISTING_MEMBER, split_listing
    from docsuri_ops.migration.snapshot import MAX_OBJECT_BYTES, BucketObjects

    stored = {
        "doc-model/2101.00001/v1.json": (b'{"meta": {}}', '"etag-model"'),
        "uploads/evidence/acct-1/attachment-1/attachment-1/paper.pdf": (None, '"etag-ev"'),
        "uploads/research/acct-2/job-1/notes.txt": (None, '"etag-research"'),
        "novelty/acct-3/upload-1/draft.pdf": (None, '"etag-novelty"'),
    }
    sizes = {key: len(body) if body is not None else 1024 for key, (body, _) in stored.items()}
    sizes["novelty/acct-3/upload-1/draft.pdf"] = MAX_OBJECT_BYTES + 1

    class Store:
        """v1's bucket as a stand-in: one page; a body may be asked only for a model."""

        def __init__(self):
            self.asked: list[str] = []

        def list_objects_v2(self, **options):
            return {"Contents": [{"Key": key, "Size": sizes[key], "ETag": etag}
                                 for key, (_, etag) in stored.items()], "IsTruncated": False}

        def get_object(self, *, Bucket, Key):
            self.asked.append(Key)
            body = stored[Key][0]
            assert body is not None, f"an upload's body was read: {Key}"
            return {"Body": __import__("io").BytesIO(body)}

    store = Store()
    read = BucketObjects(store, "v1-bucket")()
    assert store.asked == ["doc-model/2101.00001/v1.json"]
    assert set(read) == {"doc-model/2101.00001/v1.json", LISTING_MEMBER}
    assert split_listing(read[LISTING_MEMBER]) == sorted(
        ({"key": key, "size": sizes[key], "etag": etag} for key, (_, etag) in stored.items()),
        key=lambda item: item["key"])


def test_the_realm_import_builds_its_owners_under_the_migration_gate(realm):
    """Step 52(g) (L1-13): the realm's import runs under the migration tool's gate of 4.
    Nothing connects."""
    owners, close = owners_for(realm)(REALM_DATABASES.new("rehearsal"))
    try:
        transactions = owners.papers.transactions
        assert transactions._process == "migration"
        taken = 0
        while transactions._gate.acquire(blocking=False):
            taken += 1
        for _ in range(taken):
            transactions._gate.release()
        assert taken == 4
    finally:
        close()


def test_the_import_program_keeps_its_fixed_shape(monkeypatch):
    """`ops/bin/docsuri-migration-import`'s entry (D6): one word of its closed set,
    bounded JSON, no caller-set interpreter variable, one JSON result."""
    import io
    import sys

    from backend.modules.operations.migration import phases

    def call(argv, payload=b"{}", environ=None, run=None):
        out = io.StringIO()
        monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(payload)))
        monkeypatch.setattr(sys, "stdout", out)
        for name in list(os.environ):
            if name.startswith(("PYTHON", "DYLD_", "LD_")):
                monkeypatch.delenv(name)
        for name, value in (environ or {}).items():
            monkeypatch.setenv(name, value)
        status = phases.main(argv, run=run)
        return status, json.loads(out.getvalue())

    assert call(["anything"]) == (2, {"ok": False, "reason": "word-refused"})
    assert call(["import", "extra"]) == (2, {"ok": False, "reason": "word-refused"})
    assert call(["import"], b"[]") == (2, {"ok": False, "reason": "input-refused"})
    assert call(["import"], environ={"PYTHONPATH": "/x"}) == (
        2, {"ok": False, "reason": "environment-refused"})
    monkeypatch.delenv("PYTHONPATH")
    assert call(["import"]) == (1, {"ok": False, "reason": "import-runner-unbound"})
    assert call(["idempotency"], b'{"run": "r"}\narchives', run=lambda word, document, payload: {
        "word": word, "run": document["run"], "payload": payload.decode()}) == (
        0, {"ok": True, "word": "idempotency", "run": "r", "payload": "archives"})

    def refusing(word, document, payload):
        raise ValueError("import-database-refused")

    assert call(["import"], b"{}", run=refusing) == (
        1, {"ok": False, "reason": "import-database-refused"})
