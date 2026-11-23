"""The migration tool's operator side: the MigrationRun machine (U8 plan Step 31; BR8.3,
BR8.9–BR8.15, BR9.12, Workflow 9, functional-spec.md § State machine — MigrationRun).

Run by you in person through the operator tool. A dry run:

- **starts** on your go-ahead (`dry-run-go-ahead`), with no switch, abort or rollback
  running, the runtime arrangement installed and the latest isolation evidence passed
  within its freshness bound; it records the digest of the decisions current then;
- **preparing**: a new rehearsal database with the composed realm's schema, recorded as
  a retained copy (`rehearsal-database`) before anything is written to it;
- **copying**: the copy of v1 (`snapshot.Snapshot`), recorded before anything is copied
  and given its checksums when it completes;
- **importing**: the import database recorded as a retained copy (`import-database`),
  the disk guard, the snapshot's dump streamed back and restored into it, the
  snapshot's checksums verified again, then the import phases through the owners'
  operations (`backend.modules.operations.migration.phases`);
- **verifying**: the parity report (`parity`), then the idempotency pass over the same
  snapshot, which must import and update nothing (BR8.3);
- **reported**, then your decision: `accepted` or `rejected`.

At every phase boundary, and before the import restore and the import, the isolation
evidence is read again and the disk guard checked: a lapse interrupts the run with its
phase recorded, and `resume` runs exactly that phase again (against a re-verified
snapshot). An error fails the run; you may abandon an interrupted one. A failed,
rejected or abandoned dry run's copies are disposed through their records; an accepted
one's copy of v1 is disposed. Whatever the outcome, the run's import database is
removed through its record once the run ends (BR8.11, BR9.12).
"""

from __future__ import annotations

import datetime as dt
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import psycopg
from backend.modules.operations.errors import OperationsError
from backend.modules.operations.migration import parity
from backend.modules.operations.migration.misfits import Decisions
from backend.modules.operations.migration.phases import MAX_INPUT, ImportRun, Owners
from backend.modules.operations.migration.v1_source import V1Source, split_objects
from backend.modules.operations.migration_records import MigrationRuns
from backend.modules.operations.retained_copies import RetainedCopies, is_open

from docsuri_ops.backup_agent.archives import ArchiveRefused, unpack_bytes
from docsuri_ops.u8_platform.u8_protocols import database_limit_reason

from .disk_guard import CRITICAL, LOW, DiskGuard, DiskStopped
from .isolation_gate import IsolationGate
from .snapshot import Snapshot, SnapshotRefused

# Room the program's header line keeps for what the import program adds to the request
# (the released login and the archives' sizes) within `phases.MAX_INPUT` (64 KiB).
HEADER_ROOM = 1024


def _header_fits(request: dict) -> bool:
    """Whether the import program's header line for `request` stays within its bound."""
    header = {key: value for key, value in request.items() if key != "archives"}
    return len(json.dumps(header).encode()) + HEADER_ROOM <= MAX_INPUT


class Interrupted(Exception):
    """A phase boundary found a reason to stop: the run is interrupted, not failed."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass
class MigrationPlatform:
    """What the tool needs from the platform side (the realm's wiring, or production's
    with the production environment tool, Step 37)."""

    operator: object
    names: object
    snapshot: Snapshot
    create_rehearsal: Callable[[str], None]
    create_import: Callable[[str], None]
    restore_import: Callable[[str, Path], None]
    import_reader: Callable[[str], AbstractContextManager]
    owners_for: Callable[[str], tuple[Owners, Callable[[], None]]]
    stream_back: Callable[[dict, Path], dict]
    isolation: IsolationGate
    disk: DiskGuard
    spool: Path
    evidence: Path
    installed: Callable[[], bool]
    database_bytes: Callable[[str], int]
    # A final run: the composed schema in the production database just recreated empty
    # (the production environment tool's `migrate`, Step 37; the realm's schema copy).
    prepare_production: Callable[[str], None] | None = None
    # Production's import phases run as the service account through
    # `ops/bin/docsuri-migration-import` (`production.ProgramImporter`): `importer(word,
    # request)` answers what `production_wiring.production_import` answers. Without it
    # the owners' imports run in this process through `owners_for` (the composed realm).
    importer: Callable[[str, dict], dict] | None = None


class MigrationTool:
    def __init__(self, runs: MigrationRuns, copies: RetainedCopies, platform: MigrationPlatform,
                 *, clock: Callable[[], dt.datetime], tool_commit: str):
        self.runs, self.copies, self.platform = runs, copies, platform
        self.ledger = runs.ledger
        self.clock, self.tool_commit = clock, tool_commit
        self.last_report: dict | None = None

    # --- starting ---------------------------------------------------------------------

    def _dry_precondition(self, view) -> str | None:
        cutovers = view.records("cutover-record")
        if cutovers and cutovers[-1]["state"] in ("switching", "aborting", "rolling-back"):
            return "switch-abort-or-rollback-running"
        if cutovers and cutovers[-1]["state"] == "switched":
            # v2 serves live: a dry run has nothing to rehearse for, and a rollback must
            # never meet a rehearsal database it did not leave (BR9.7, BR9.15).
            return "cutover-switched"
        if not self.platform.installed():
            return "arrangement-not-installed"
        reading = self.platform.isolation.read()
        if not reading.passed:
            return reading.reason
        # NFR8.15: the run creates a rehearsal database, so it starts only while fewer
        # than two are open, counted from the ledger's open retained copies; refused here,
        # nothing is written.
        return database_limit_reason("rehearsal", view, self.platform.names)

    def start_dry(self, go_ahead) -> dict:
        return self.runs.start("dry", tool_commit=self.tool_commit, go_ahead=go_ahead,
                               precondition=self._dry_precondition)

    def start_final(self, *, approval_id, dispose_after: dt.datetime) -> dict:
        """A final run, inside the switch (BR8.12): `approval_id` is the decision that
        approved the final snapshot's disposal date (`dispose_after`, BR9.12)."""
        run = self.runs.start("final", tool_commit=self.tool_commit)
        self._write_private(self._final_path(run["runId"]), {
            "approvalId": str(approval_id), "disposeAfter": dispose_after.isoformat()})
        return run

    def _final_path(self, run_id: str) -> Path:
        return self.platform.evidence / f"final-{run_id}.json"

    def _final(self, run: dict) -> dict:
        value = json.loads(self._final_path(run["runId"]).read_bytes())
        approval = self.ledger.get("maintainer-approval", value["approvalId"])
        if approval is None or approval["decision"] != "approved":
            raise OperationsError("FORBIDDEN", current={"reasonKey": "decision-required"})
        return {"approval": approval,
                "disposeAfter": dt.datetime.fromisoformat(value["disposeAfter"])}

    @staticmethod
    def _write_private(path: Path, value: dict) -> None:
        import os

        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                             0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, sort_keys=True)

    # --- the phases -------------------------------------------------------------------

    def _boundary(self, run: dict | None = None) -> None:
        """A dry run's isolation evidence, read again at the boundary (BR8.11)."""
        if run is not None and run["kind"] == "final":
            return
        reading = self.platform.isolation.read()
        if not reading.passed:
            raise Interrupted(reading.reason)

    def run(self, run_id) -> dict:
        """Drive the run from its current phase to `reported`, or until it is
        interrupted or fails."""
        steps = {"preparing": self._prepare, "copying": self._copy,
                 "importing": self._import, "verifying": self._verify}
        while True:
            current = self.runs.require(run_id)
            phase = current["state"]
            if phase not in steps:
                return current
            try:
                self._boundary(current)
                steps[phase](current)
            except Interrupted as stop:
                self.runs.interrupt(run_id, phase)
                return {**self.runs.require(run_id), "reason": stop.reason}
            except (OperationsError, SnapshotRefused, ArchiveRefused, ValueError,
                    RuntimeError, psycopg.Error) as error:
                # Any other database error fails the run through `fail()`, which disposes
                # its copies (Step 68(h), addition 4).
                return self.fail(run_id, getattr(error, "reason", None) or
                                 getattr(error, "code", None) or type(error).__name__)

    def _prepare(self, run: dict) -> None:
        if run["kind"] == "final":
            self._prepare_production(run)
            return
        name = self.platform.names.new("rehearsal")
        copy = self.copies.record("rehearsal-database", f"run:{run['runId']}",
                                  [f"database/{name}"])
        self.platform.create_rehearsal(name)
        self.runs.move(run["runId"], "copying", targetCopyId=copy["copyId"])

    def _prepare_production(self, run: dict) -> None:
        """The production database recreated empty, then given the composed schema, so
        the final run imports into a database that holds nothing else (BR6.3)."""
        from docsuri_ops.u8_platform.u8_protocols import EffectUnsettled, execute_settled

        production = self.platform.names.production
        try:
            # A recreate an earlier attempt of this run left with nothing applied runs
            # again under its next retry key (`execute_settled`).
            execute_settled(self.platform.operator, "platform.database.recreate",
                            "database-production", {"database": production},
                            key=f"final-recreate:{run['runId']}")
        except EffectUnsettled:
            raise OperationsError("CONFLICT", current={"reasonKey": "recreate-failed"}) from None
        if self.platform.prepare_production is None:
            raise OperationsError("DEPENDENCY_UNAVAILABLE")
        self.platform.prepare_production(production)
        self.runs.move(run["runId"], "copying")

    def _copy(self, run: dict) -> None:
        snapshot = self.platform.snapshot
        prior = run.get("snapshotCopyId")
        if prior is not None:
            record = self.copies.get(prior)
            if record is not None and "completedAt" in record:
                # The copy completed before the interruption: importing comes next.
                self.runs.move(run["runId"], "importing")
                return
            # A copy cut short is disposed through its record and taken again anew.
            if record is not None:
                self._dispose(record)
        if run["kind"] == "final":
            final = self._final(run)
            record = snapshot.record("v1-final-snapshot", run["runId"],
                                     dispose_after=final["disposeAfter"],
                                     approval_id=final["approval"]["approvalId"])
            decided = {"date": final["disposeAfter"].isoformat(),
                       "receipt": final["approval"]["operatorReceiptRef"],
                       "subjectDigest": final["approval"]["subjectDigest"]}
        else:
            record, decided = snapshot.record("dry-run-snapshot", run["runId"]), None
        # The copy is recorded before anything is copied, so its `createdAt` is the
        # snapshot's start, NFR8.8's start of a run's duration (Step 68(g)).
        self.runs.move(run["runId"], "copying", snapshotCopyId=record["copyId"],
                       snapshotStartedAt=record["createdAt"])
        snapshot.take(record, decided=decided)
        self._boundary(run)
        self.runs.move(run["runId"], "importing", snapshotCopyId=record["copyId"])

    def _target(self, run: dict) -> str:
        if run["kind"] == "final":
            return self.platform.names.production
        copy = self.copies.get(run["targetCopyId"])
        return copy["locations"][0].removeprefix("database/")

    def target_of(self, run: dict) -> str:
        """The database a run imported into: a dry run's rehearsal database, or the
        production database for a final run (the cutover's moves read it)."""
        return self._target(run)

    def target_disposed(self, run: dict) -> bool:
        """Whether a dry run's rehearsal database is gone (its retained copy disposed,
        retired or returned): such a run can no longer be accepted, since the profile
        would then name a database that does not exist."""
        if run["kind"] != "dry" or not run.get("targetCopyId"):
            return False
        copy = self.copies.get(run["targetCopyId"])
        return copy is None or any(name in copy for name in (
            "disposedAt", "retiredWithVolumeAt", "returnedToServiceAt"))

    def _import_database(self, run: dict) -> tuple[str, dict]:
        existing = [item for item in self.copies.undisposed("import-database")
                    if item["sourceRef"] == f"run:{run['runId']}"]
        if existing:
            return existing[0]["locations"][0].removeprefix("database/"), existing[0]
        name = self.platform.names.new("import")
        copy = self.copies.record("import-database", f"run:{run['runId']}",
                                  [f"database/{name}"])
        return name, copy

    def _estimate(self) -> int:
        """The rehearsal database a run builds (L1-17): the latest accepted dry run's
        rehearsal database while its copy is open, otherwise the policy's first-rehearsal
        estimate (4 GiB). Rejected, failed and final runs never count."""
        accepted = self.runs.latest_accepted("dry")
        if accepted is not None and accepted.get("targetCopyId") and not self.target_disposed(
                accepted):
            return int(self.platform.database_bytes(self._target(accepted)))
        return int(self.copies.policy.first_rehearsal_estimate_bytes)

    def _to_write(self, snapshot: dict) -> int:
        return int(snapshot.get("sourceDatabaseBytes", 0)) + self._estimate()

    def _held(self, run: dict) -> int:
        """What the run's databases already hold (BR6.6): its target, and its import
        database once that copy is recorded (read from the open copy, never recorded
        here)."""
        held = int(self.platform.database_bytes(self._target(run)))
        for record in self.copies.undisposed("import-database"):
            if record["sourceRef"] == f"run:{run['runId']}":
                held += int(self.platform.database_bytes(
                    record["locations"][0].removeprefix("database/")))
                break
        return held

    def _guard(self, run: dict, snapshot: dict) -> int:
        """Both figures read again at every call; the figure still to write is returned."""
        to_write = self._to_write(snapshot)
        if not self.platform.disk.room(to_write=to_write, written=self._held(run)):
            raise Interrupted(LOW)
        return to_write

    def _import(self, run: dict) -> None:
        snapshot_record = self.copies.get(run["snapshotCopyId"])
        parts = self.platform.snapshot.verified_parts(snapshot_record)
        self._guard(run, snapshot_record)
        name, _ = self._import_database(run)
        raw = self._read_back(name, parts)
        to_write = self._guard(run, snapshot_record)
        self._boundary(run)
        final = run["kind"] == "final"
        if self.platform.importer is not None:
            misfits, fresh, report = self._import_through_program(run, name, raw, final,
                                                                  to_write=to_write)
        else:
            misfits, fresh, report = self._import_here(run, name, raw, final,
                                                       to_write=to_write)
        self.runs.record_misfits(run["runId"], misfits, new_in_final=fresh)
        self._store_report(run, report)
        self.runs.move(run["runId"], "verifying")

    def _import_here(self, run: dict, name: str, raw: dict, final: bool, *, to_write: int):
        """The owners' import operations in this process (the composed realm), stopping
        at the disk guard's next boundary (S3)."""
        decisions = Decisions.from_ledger(self.ledger)
        if final:
            # The frozen decisions; anything met for the first time takes archive-only.
            decisions = decisions.for_final_run()
        boundary = self.platform.disk.boundary(to_write=to_write,
                                               held=lambda: self._held(run))
        owners, close = self.platform.owners_for(self._target(run))
        try:
            with self.platform.import_reader(name) as conn:
                try:
                    tallies = ImportRun(V1Source(conn, **self._unpacked(raw)), owners,
                                        decisions, clock=self.clock, boundary=boundary).run()
                except DiskStopped as stopped:
                    raise Interrupted(stopped.reason) from None
                misfits = [item for tally in tallies.values() for item in tally.misfits]
                fresh = ({(kind, reason) for kind, _, reason in misfits}
                         - self.runs.required_pairs()) if final else set()
                report = parity.build(run["runId"], tallies, owners, now=self.clock(),
                                      new_in_final=fresh)
        finally:
            close()
        return misfits, fresh, report

    def _request(self, run: dict, name: str, raw: dict, final: bool, *,
                 to_write: int | None = None) -> dict:
        """What the import program is handed: the run's two databases, the decisions
        current now, the pairs a final run's accepted dry run met, the figure the disk
        guard gave when the request was made (`toWrite`), and the archives."""
        request = {"runId": run["runId"], "importDatabase": name,
                   "targetDatabase": self._target(run),
                   "decisions": self.ledger.records("misfit-decision"), "archives": raw}
        if to_write is not None:
            request["toWrite"] = int(to_write)
        if final:
            request["final"] = True
            request["required"] = sorted([list(pair) for pair in self.runs.required_pairs()])
        return request

    def _import_through_program(self, run: dict, name: str, raw: dict, final: bool, *,
                                to_write: int):
        """The import phase as the service account (`docsuri-migration-import import`)."""
        answer = self.platform.importer("import", self._request(run, name, raw, final,
                                                                to_write=to_write))
        if isinstance(answer, dict) and "interrupted" in answer:
            # The program stopped at a boundary (S3): an interruption with its reason.
            if answer["interrupted"] in (LOW, CRITICAL):
                raise Interrupted(answer["interrupted"])
            raise OperationsError("CONFLICT", current={"reasonKey": "import-answer-refused"})
        try:
            misfits = [tuple(item) for item in answer["misfits"]]
            fresh = {tuple(pair) for pair in answer["newInFinal"]}
            report = answer["report"]
        except (KeyError, TypeError):
            raise OperationsError("CONFLICT", current={"reasonKey": "import-answer-refused"}) \
                from None
        if not all(len(item) == 3 for item in misfits) or not isinstance(report, dict):
            raise OperationsError("CONFLICT", current={"reasonKey": "import-answer-refused"})
        return misfits, fresh, report

    def _read_back(self, name: str, parts: dict) -> dict:
        """The snapshot streamed back: the dump restored into a fresh import database
        (a resumed import restores it again), and the two archives checked against
        their manifests before use."""
        spool = self.platform.spool / f"{uuid4().hex}.dump"
        try:
            self.platform.stream_back(parts["database"], spool)
            self.platform.create_import(name)
            self.platform.restore_import(name, spool)
        finally:
            spool.unlink(missing_ok=True)
        return self._archive_bytes(parts)

    def _store_report(self, run: dict, report: dict) -> None:
        reference, digest = parity.write(self.platform.evidence, report)
        self.runs.record_report(run["runId"], reference=reference, digest=digest,
                                kinds=len(report["kinds"]), reconciles=report["reconciles"])
        self.last_report = report

    def _verify(self, run: dict) -> None:
        """A dry run's idempotency pass over the same snapshot: nothing imported,
        nothing updated (BR8.3). A final run reports at once."""
        if run["kind"] == "final":
            self.runs.move(run["runId"], "reported")
            return
        snapshot_record = self.copies.get(run["snapshotCopyId"])
        parts = self.platform.snapshot.verified_parts(snapshot_record)
        name, _ = self._import_database(run)
        raw = self._archive_bytes(parts)
        skipped = self._time_refused(run)
        if self.platform.importer is not None:
            request = self._request(run, name, raw, False)
            if skipped and _header_fits({**request, "skipPapers": skipped}):
                request["skipPapers"] = skipped
            answer = self.platform.importer("idempotency", request)
            changed = answer.get("changed")
            if type(changed) is not int:
                raise OperationsError("CONFLICT", current={"reasonKey": "import-answer-refused"})
        else:
            owners, close = self.platform.owners_for(self._target(run))
            try:
                with self.platform.import_reader(name) as conn:
                    tallies = ImportRun(V1Source(conn, **self._unpacked(raw)), owners,
                                        Decisions.from_ledger(self.ledger),
                                        clock=self.clock, skip_papers=skipped).run()
            finally:
                close()
            changed = sum(tally.imported + tally.updated for tally in tallies.values())
        if changed:
            raise OperationsError("CONFLICT", current={"reasonKey": "idempotency-pass-changed"})
        self.runs.move(run["runId"], "reported")

    def _time_refused(self, run: dict) -> list[str]:
        """The source ids of the papers this run recorded as refused by the database's
        time limits, sorted (Step 68(h), addition 3): the idempotency pass does not ask
        CorpusContent again for them."""
        from backend.modules.corpus.paper_import import TIME_REFUSED

        return sorted({item["sourceId"] for item in self.ledger.records("misfit-record")
                       if item["runId"] == run["runId"] and item["kind"] == "paper"
                       and item["reasonKey"] == TIME_REFUSED})

    def _archive_bytes(self, parts: dict) -> dict[str, bytes]:
        """The index and objects archives streamed back, each digest-checked by the
        stream and its members checked against the manifest before use."""
        archives = {}
        for part in ("index", "objects"):
            spool = self.platform.spool / f"{uuid4().hex}.{part}"
            try:
                self.platform.stream_back(parts[part], spool)
                archives[part] = spool.read_bytes()
            finally:
                spool.unlink(missing_ok=True)
            unpack_bytes(archives[part])  # refuses a member whose checksum differs
        return archives

    @staticmethod
    def _unpacked(raw: dict[str, bytes]) -> dict:
        index, objects = unpack_bytes(raw["index"]), unpack_bytes(raw["objects"])
        documents = [json.loads(line) for line in index.get(
            "documents.jsonl", b"").splitlines() if line.strip()]
        # The bucket's listing travels as the objects part's reserved member (L1-37).
        members, listing = split_objects(objects)
        return {"index_documents": documents, "objects": members, "listing": listing}

    # --- endings -------------------------------------------------------------------------

    def decide(self, run_id, approval_id) -> dict:
        """Your decision on the report; an accepted dry run's copy of v1 is disposed, a
        rejected one's copies all are. A final run's completed snapshot stays under its
        decided date (BR8.12); its abort is the cutover's (Step 33)."""
        decided = self.runs.decide_report(run_id, approval_id)
        if decided["kind"] == "dry":
            if decided["state"] == "accepted":
                self._dispose_snapshot(decided)
            else:
                self._dispose_run(decided)
        self._remove_import(decided)
        return self.runs.require(run_id)

    def fail(self, run_id, reason: str) -> dict:
        current = self.runs.require(run_id)
        if current["state"] not in ("failed", "accepted", "rejected"):
            self.runs.move(run_id, "failed")
        ended = self.runs.require(run_id)
        self._dispose_run(ended)
        self._remove_import(ended)
        return {**self.runs.require(run_id), "reason": reason}

    def abandon(self, run_id) -> dict:
        """You abandon an interrupted dry run: it fails, and its copies are disposed."""
        current = self.runs.require(run_id)
        if current["state"] != "interrupted" or current["kind"] != "dry":
            raise OperationsError("CONFLICT", current={"state": current["state"]})
        return self.fail(run_id, "abandoned")

    def resume(self, run_id) -> dict:
        self.runs.resume(run_id)
        return self.run(run_id)

    def interrupt(self, run_id, phase: str) -> dict:
        """The process stopped mid-phase: the run is interrupted with that phase."""
        return self.runs.interrupt(run_id, phase)

    # --- disposal through each copy's record -------------------------------------------------

    def _dispose_run(self, run: dict) -> None:
        if run["kind"] == "final":
            # A final snapshot whose copy never completed is disposed; a completed one
            # stays under its disposal date (BR9.12).
            record = self.copies.get(run["snapshotCopyId"]) if run.get(
                "snapshotCopyId") else None
            if record is not None and "completedAt" not in record:
                self._dispose(record)
            return
        self._dispose_snapshot(run)
        if run.get("targetCopyId"):
            record = self.copies.get(run["targetCopyId"])
            if record is not None:
                self._dispose(record)

    def _dispose_snapshot(self, run: dict) -> None:
        if run.get("snapshotCopyId"):
            record = self.copies.get(run["snapshotCopyId"])
            if record is not None:
                self._dispose(record)

    def _remove_import(self, run: dict) -> None:
        for record in self.copies.undisposed("import-database"):
            if record["sourceRef"] == f"run:{run['runId']}":
                self._dispose(record)

    def _dispose(self, record: dict) -> None:
        """Dispose one copy through its one path: every location, then the record."""
        if not is_open(record):
            return
        receipt = None
        for location in record["locations"]:
            receipt = self._dispose_location(record, location) or receipt
        if receipt is None:
            self.copies.disposal_pending(record["copyId"])
            return
        self.copies.disposed(record["copyId"], receipt)

    def _dispose_location(self, record: dict, location: str) -> dict | None:
        """One location's disposal run to a settled outcome (`execute_settled`): one an
        earlier attempt left with nothing applied runs again under its next retry key,
        so a later disposal retries it instead of replaying the failure."""
        from docsuri_ops.u8_platform.u8_protocols import execute_settled

        operator = self.platform.operator
        if location.startswith("database/"):
            # A database's one path is PlatformControl's database removal (BR9.17), which
            # a switch's own steps may take too.
            name = location.removeprefix("database/")
            operation, target = ("platform.database.remove",
                                 f"database-{self.platform.names.kind_of(name)}")
            inputs = {"database": name, "via": "in-person"}
        else:
            part = location.rsplit(":", 1)[-1]
            parts_file = self.platform.snapshot.parts_path(record["copyId"])
            try:
                path = json.loads(parts_file.read_bytes())[part]["path"]
            except (OSError, ValueError, KeyError):
                return None
            operation, target = "platform.copy.dispose", "copies"
            inputs = {"recordKind": "RetainedCopy", "recordId": record["copyId"],
                      "place": "backup-volume", "location": path, "event": "run-ended"}
        try:
            return execute_settled(operator, operation, target, inputs,
                                   key=f"dispose:{record['copyId']}:{location}")
        except Exception:  # noqa: BLE001 - a disposal that cannot complete stays pending
            return None
