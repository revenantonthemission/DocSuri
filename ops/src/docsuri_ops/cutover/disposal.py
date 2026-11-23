"""The disposal pass (U8 plan Step 33; Workflow 14 step 4, Workflow 19 steps 8–9, BR9.12,
BR9.17).

It runs under the standing authority after each scheduled backup and whenever the
volume check passes again (the standing job's lanes, Step 35), never while a switch, an
abort, a rollback or a production restore holds the live environment's exclusion. Each
place has its one path, in the fixed order profile, database, then sets:

1. **Databases** (rehearsal, import and scratch copies whose disposal point, their
   backstop date, has passed) go through PlatformControl's `platform.database.remove`
   under the standing authority's one destructive grant, naming this pass and the copy
   (`pass: disposal`, `copyId`), which the operation checks is recorded there and past
   its backstop. Its precondition also refuses the production database and the rehearsal
   database the profile names, and waits while a backup or verification of it is active;
   the realm drops it through the scheduler's database login, a member of the
   disposable-databases role only. A rehearsal database the profile
   still names at its backstop is not removed: the cutover returns to preparing with an
   incident on storage.capacity until the operator, in person, stops the rehearsal v2,
   clears the profile and removes it (BR9.12).
2. **The backup volume**: the backup agent's unattended `dispose-due` (its fixed
   command) deletes what its catalogue shows due, never on the ledger's word; the pass
   hands it the paths the ledger has records for and the disposal points it claims, only
   to report. Each file the agent reports disposed sets `disposedAt` on its record from
   the agent's receipt; a file the floor holds records `heldByFloorSince`; a due file
   the ledger has no record of, and a claim the catalogue does not show, each open an
   incident on storage.capacity.
3. **v1's stores** are deleted only by the operator in person at the date your decision
   approved; the pass only reports them, and opens an incident once their backstop has
   passed with them still in place.

A disposal that cannot complete keeps `disposalPendingSince`, is retried by the next
pass, and opens an incident on storage.capacity once its backstop has passed; each
failed attempt also records `lastDisposalFailedAt` (U8 plan Step 64(i)).

Every incident the pass opens on storage.capacity opens in the environment the standing
job serves at that moment (`DisposalPlatform.environment`, L1-65): live when the
platform's mode is live, otherwise rehearsal, as its requests and its lone ledger copy
do. During the soak the rehearsal 운영 lists each failed disposal's incident beside its
count, and BR9.3's soak verdict reads it; an incident still open in rehearsal at the
switch stays on the rehearsal list. A rehearsal database still in use at its backstop
keeps its rehearsal incident.

A rehearsal set whose database was removed but which could not be disposed of then (a
rollback's left set, opening's, or a replaced dry run's) is disposed of only in person
(your decision of 2026-10-26, "Only in person"), by the command that retries it
(`waiting_remedy`): `cutover open` run again while the cutover is switched, `cutover
check` otherwise. The pass only reports it as waiting, with that command, and a set
waiting a day opens the storage incident naming it (review finding, Major, R16).
"""

from __future__ import annotations

import datetime as dt
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from backend.modules.operations.errors import LedgerDamaged, OperationsError
from backend.modules.operations.ledger import utc_text
from backend.modules.operations.retained_copies import RetainedCopies, is_open

STORAGE = "storage.capacity"
DATABASE_KINDS = ("rehearsal-database", "import-database", "scratch-restore")
VOLUME_KINDS = ("dry-run-snapshot", "v1-final-snapshot", "rolled-back-v2-database")
SET_KINDS = (("backup-set", "backupId"), ("ledger-copy", "ledgerCopyId"))
CLOSED = ("disposedAt", "retiredWithVolumeAt")


def _parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


# The in-person command that retries a waiting rehearsal set's disposal by event.
REMEDY_OPEN, REMEDY_CHECK = "cutover-open", "cutover-check"


def removed_rehearsal_databases(ledger) -> set[str]:
    """The rehearsal databases removed so far, read from the ledger: every disposed
    `rehearsal-database` copy's database (opening's, a replaced dry run's and a
    rollback's left names alike)."""
    return {location.removeprefix("database/")
            for copy in ledger.records("retained-copy")
            if copy.get("kind") == "rehearsal-database" and "disposedAt" in copy
            for location in copy.get("locations", []) if location.startswith("database/")}


def set_database(backup: dict) -> str:
    """The database a backup set was taken of (its incarnation names it)."""
    return str(backup.get("databaseIncarnation", "")).split(":", 1)[0]


def waiting_rehearsal_sets(ledger) -> list[dict]:
    """The open rehearsal sets of a removed rehearsal database: sets the cutover could not
    dispose of when their database was removed. Each has an in-person retry
    (`waiting_remedy`)."""
    removed = removed_rehearsal_databases(ledger)
    if not removed:
        return []
    return [backup for backup in ledger.records("backup-set")
            if backup.get("environment") == "rehearsal"
            and not any(name in backup for name in CLOSED)
            and set_database(backup) in removed]


def waiting_remedy(state: str | None) -> str:
    """The in-person command that disposes of a waiting set in the cutover's state: while
    switched, `cutover open` run again (it re-runs opening's disposal, `after_opening`);
    in any other state the pass runs in, `cutover check` (`retry_left_sets`)."""
    return REMEDY_OPEN if state == "switched" else REMEDY_CHECK


@dataclass
class DisposalPlatform:
    """What the pass needs from the platform side."""

    operator: object
    names: object
    current_rehearsal: Callable[[], str | None]
    dispose_due: Callable[[dict], dict]
    # The environment the standing job serves now: live when the platform's mode is
    # live, otherwise rehearsal (L1-65). The pass opens its incidents there.
    environment: Callable[[], str]
    copy_paths: Callable[[dict], list[str]] = field(default=lambda record: [])
    via: str = "standing"


class DisposalPass:
    def __init__(self, ledger, policy, platform: DisposalPlatform, *,
                 clock: Callable[[], dt.datetime], incidents=None, cutover=None):
        from backend.modules.operations.cutover import Cutover
        from backend.modules.operations.incidents import Incidents
        from backend.modules.operations.recovery import RecoveryRequests

        self.ledger, self.policy, self.platform, self.clock = ledger, policy, platform, clock
        self.copies = RetainedCopies(ledger, policy, clock=clock)
        self.incidents = incidents or Incidents(ledger, environment="live")
        self.cutover = cutover or Cutover(ledger, policy, clock=clock, incidents=self.incidents)
        self.requests = RecoveryRequests(ledger, policy, clock=clock)
        # One run at a time (review fix, batch 4): the backup lane and the agent-status
        # lane share this pass from their own threads, and a run keeps its per-run state
        # (`_serving`, `_gone`, `_remedies`) on the pass while it holds this lock.
        self._running = threading.Lock()

    # --- when it may run --------------------------------------------------------------

    def blocked(self) -> str | None:
        """Why the pass may not run now, or None (BR9.17)."""
        if self.cutover.holds_live_exclusion():
            return "live-exclusion-held"
        if self.requests.production_restore_active("live") is not None:
            return "production-restore-active"
        from backend.modules.operations.release_records import release_blocker

        # An install, or a release rollback, holds it too (cicd-pipeline § 5.1, § 6).
        return release_blocker(self.ledger)

    def run(self) -> dict:
        """One pass; a second caller waits for a pass in progress, then runs on what it
        left, so two passes never dispose of the same file or reset each other's state."""
        with self._running:
            return self._run()

    def fresh(self) -> None:
        """Make this pass read a current ledger (review fix, batch 4, re-review): the
        standing job's `LedgerClient` keeps a local copy refreshed only after its own
        writes, and the agent-status lane's passed-again pass can come up to a day after
        the job's last fresh read. A switch, a production restore or an install another
        process began since then must hold the pass (BR9.17), and a switch's profile
        receipt must move its incidents (L1-65). A ledger read directly (the realm's
        `Ledger`) has no `invalidate` and is always current."""
        invalidate = getattr(self.ledger, "invalidate", None)
        if invalidate is not None:
            invalidate()

    def _run(self) -> dict:
        self.fresh()
        reason = self.blocked()
        if reason is not None:
            return {"ran": False, "reason": reason}
        # Where the standing job serves at this moment (L1-65): read once, after
        # `blocked()`, through the same facts the pass reads first.
        self._serving = self.platform.environment()
        now = self.clock()
        self._gone: set[str] = set()
        self._remedies: dict[str, str] = {}
        report = {"ran": True, "databases": [], "pending": [], "volume": {}, "inPerson": [],
                  "incidents": [], "waitingSets": []}
        self._databases(now, report)
        self._waiting_sets(report)
        self._volume(now, report)
        self._in_person(now, report)
        self._backstops(now, report)
        return report

    # --- 1. databases -----------------------------------------------------------------

    def _databases(self, now: dt.datetime, report: dict) -> None:
        current = self.platform.current_rehearsal()
        for record in self.copies.due(now):
            if record["kind"] not in DATABASE_KINDS:
                continue
            names = [item.removeprefix("database/") for item in record["locations"]
                     if item.startswith("database/")]
            if record["kind"] == "rehearsal-database" and current in names:
                self._backstop_in_use(record, report)
                continue
            receipt = None
            for name in names:
                receipt = self._remove(record, name)
                if receipt is None:
                    break
            if receipt is None:
                # A removal that did not settle applied: a failed attempt (Step 64(i)).
                self.copies.disposal_pending(record["copyId"], failed=True)
                report["pending"].append(record["copyId"])
                continue
            self.copies.disposed(record["copyId"], receipt)
            report["databases"].append(record["copyId"])

    def _backstop_in_use(self, record: dict, report: dict) -> None:
        """A rehearsal database the soak still uses at its backstop: back to preparing,
        with the incident, until the operator removes it in person."""
        self.copies.disposal_pending(record["copyId"])
        report["pending"].append(record["copyId"])
        cutover = self.cutover.current()
        if cutover is not None and cutover["state"] in ("rehearsing", "ready-to-switch"):
            self.cutover.rehearsal_backstop()
        else:
            self._incident(f"retained-copy:{record['copyId']}:in-use", "rehearsal")
        report["incidents"].append(f"rehearsal-backstop:{record['copyId']}")

    def _remove(self, record: dict, name: str) -> dict | None:
        """One database's removal run to a settled outcome (`execute_settled`): a removal
        an earlier pass left with nothing applied (a failed drop, an interrupted one
        reconciled not applied) runs again under its next retry key, so the next pass
        retries it instead of replaying the failure."""
        from docsuri_ops.platform_control.errors import ControlError
        from docsuri_ops.u8_platform.u8_protocols import (
            EffectUnsettled,
            PreconditionRefused,
            execute_settled,
        )

        kind = self.platform.names.kind_of(name)
        if kind not in ("rehearsal", "import", "scratch"):
            return None
        inputs = {"database": name, "via": self.platform.via}
        if self.platform.via == "standing":
            # The standing authority's one removal: this pass, at the copy's backstop.
            inputs.update({"pass": "disposal", "copyId": record["copyId"]})
        try:
            return execute_settled(self.platform.operator, "platform.database.remove",
                                   f"database-{kind}", inputs,
                                   key=f"disposal:{record['copyId']}:{name}")
        except (PreconditionRefused, ControlError, EffectUnsettled):
            return None  # waits (a backup or verification active), not this grant, or failed

    # --- 1b. sets waiting for their disposal by event, in person ----------------------------

    def removed_rehearsal_databases(self) -> set[str]:
        return removed_rehearsal_databases(self.ledger)

    def waiting_sets(self) -> list[dict]:
        return waiting_rehearsal_sets(self.ledger)

    def _waiting_sets(self, report: dict) -> None:
        """A waiting set is disposed of only in person (your decision of 2026-10-26, "Only
        in person"): its disposal by event is the agent's in-person `dispose-event`, which
        no standing grant reaches. So the pass disposes of none by event and only reports
        each set still waiting (`waitingSets`) with the in-person command that disposes
        of it (`waitingRemedy`: `cutover-open` while the cutover is switched,
        `cutover-check` otherwise; review finding, Major, R16), marking it
        `disposalPendingSince` the first time; a set waiting a day opens the storage
        incident naming that command (`_backstops`)."""
        waiting = self.waiting_sets()
        if not waiting:
            return
        current = self.cutover.current()
        remedy = waiting_remedy(None if current is None else current["state"])
        report["waitingRemedy"] = remedy
        for backup in waiting:
            self._pending("backup-set", backup, report)
            report["waitingSets"].append(backup["backupId"])
            self._remedies[backup["backupId"]] = remedy

    # --- 2. the backup volume ------------------------------------------------------------

    def _volume_records(self) -> dict[str, tuple[str, dict]]:
        """Every open ledger record with a file on the volume, by catalogue path."""
        paths: dict[str, tuple[str, dict]] = {}
        for kind, _ in SET_KINDS:
            for record in self.ledger.records(kind):
                if not any(name in record for name in CLOSED):
                    paths[record["location"]] = (kind, record)
        for record in self.copies.undisposed():
            if record["kind"] in VOLUME_KINDS:
                for path in self.platform.copy_paths(record):
                    paths[path] = ("retained-copy", record)
        return paths

    @staticmethod
    def _claim(kind: str, record: dict) -> str:
        return record["retainUntil"] if kind != "retained-copy" else record["disposeAfter"]

    def _volume(self, now: dt.datetime, report: dict) -> None:
        records = self._volume_records()
        document = {
            "ledgerPaths": sorted(records),
            "claims": [{"path": path, "disposeAfter": self._claim(kind, record)}
                       for path, (kind, record) in sorted(records.items())],
        }
        try:
            result = self.platform.dispose_due(document)
        except Exception as error:  # noqa: BLE001 - the agent refused or is unreachable
            report["volume"] = {"refused": getattr(error, "reason", type(error).__name__)}
            # A refused or unreachable `dispose-due` is a failed attempt, except for a
            # waiting rehearsal set, which only an in-person command disposes of.
            waiting = {item["backupId"] for item in self.waiting_sets()}
            for kind, record in records.values():
                if _parse(self._claim(kind, record)) <= now:
                    self._pending(kind, record, report,
                                  failed=record.get("backupId") not in waiting
                                  or kind != "backup-set")
            return
        report["volume"] = {name: result.get(name, []) for name in (
            "disposed", "held", "released", "unrecorded", "mismatched", "refused",
            "refusedClaims")}
        for path in result.get("disposed", []):
            entry = records.get(path)
            if entry is not None:
                self._disposed(*entry, path)
        for path in result.get("held", []):
            entry = records.get(path)
            if entry is not None and entry[0] != "retained-copy":
                self._held(*entry, now)
        for path in result.get("released", []):
            entry = records.get(path)
            if entry is not None and entry[0] != "retained-copy":
                self._released(*entry)
        for name in ("unrecorded", "refusedClaims", "mismatched", "held"):
            for path in result.get(name, []):
                self._incident(f"backup-volume:{name}:{path}", self._serving)
                report["incidents"].append(f"{name}:{path}")

    def _version(self, kind: str, record: dict, change: dict) -> None:
        key = record["backupId" if kind == "backup-set" else "ledgerCopyId"]
        current = self.ledger.get(kind, key) or record
        updated = {**current, **change}
        for name in [name for name, value in change.items() if value is None]:
            updated.pop(name, None)
        if updated == current:
            return
        self.ledger.append(kind, updated, expect_revision=self.ledger.revision(kind, key))

    def _disposed(self, kind: str, record: dict, path: str) -> None:
        if kind == "retained-copy":
            current = self.copies.get(record["copyId"])
            if current is not None and is_open(current):
                remaining = [item for item in self.platform.copy_paths(current) if item != path]
                if not remaining or all(item in self._gone for item in remaining):
                    self.copies.disposed_by_agent(record["copyId"], f"agent-disposed:{path}")
                self._gone.add(path)
            return
        self._version(kind, record, {"disposedAt": utc_text(self.clock()),
                                     "disposalPendingSince": None, "heldByFloorSince": None})

    def _held(self, kind: str, record: dict, now: dt.datetime) -> None:
        if "heldByFloorSince" not in record:
            self._version(kind, record, {"heldByFloorSince": utc_text(now)})

    def _released(self, kind: str, record: dict) -> None:
        self._version(kind, record, {"heldByFloorSince": None})

    def _pending(self, kind: str, record: dict, report: dict, *, failed: bool = False) -> None:
        """The disposal could not complete: `disposalPendingSince` keeps the first time,
        and a failed attempt (`failed`) records `lastDisposalFailedAt` at each attempt
        (U8 plan Step 64(i)); a later disposal keeps it."""
        if kind == "retained-copy":
            self.copies.disposal_pending(record["copyId"], failed=failed)
            report["pending"].append(record["copyId"])
            return
        key = record["backupId" if kind == "backup-set" else "ledgerCopyId"]
        current = self.ledger.get(kind, key) or record
        change = {}
        if "disposalPendingSince" not in current:
            change["disposalPendingSince"] = utc_text(self.clock())
        if failed:
            change["lastDisposalFailedAt"] = utc_text(self.clock())
        if change:
            self._version(kind, record, change)
        report["pending"].append(key)

    # --- 3. v1's stores and the backstops ------------------------------------------------

    def _in_person(self, now: dt.datetime, report: dict) -> None:
        for record in self.copies.due(now):
            if record["kind"] == "v1-stores":
                report["inPerson"].append(record["copyId"])

    def _backstops(self, now: dt.datetime, report: dict) -> None:
        """Every copy still in place after its backstop, and every pending disposal of a
        set or ledger copy still pending a day after it was first attempted (one daily
        pass later; sets have no backstop row of their own in NFR3.12, so the one-day
        staging backstop bounds the wait), opens an incident on storage.capacity. A
        waiting rehearsal set's incident names the in-person command that disposes of it
        (`<kind>:<id>:waiting:<command>`), never only the pass's own retry."""
        for record in self.copies.past_backstop(now):
            self._incident(f"retained-copy:{record['copyId']}:backstop", self._serving)
            report["incidents"].append(f"backstop:{record['copyId']}")
        backstop = dt.timedelta(seconds=self.policy.staging_file_backstop_seconds)
        for kind, key in SET_KINDS:
            for record in self.ledger.records(kind):
                since = record.get("disposalPendingSince")
                if since is None or any(name in record for name in CLOSED) or (
                    now - _parse(since) <= backstop
                ):
                    continue
                remedy = self._remedies.get(record[key]) if kind == "backup-set" else None
                if remedy is not None:
                    self._incident(f"{kind}:{record[key]}:waiting:{remedy}", self._serving)
                    report["incidents"].append(f"waiting:{record[key]}:{remedy}")
                    continue
                self._incident(f"{kind}:{record[key]}:pending", self._serving)
                report["incidents"].append(f"pending:{record[key]}")

    def _incident(self, correlation: str, environment: str) -> None:
        try:
            self.incidents.signal(STORAGE, "tolerance-exceeded", correlation=correlation,
                                  environment=environment)
        except (LedgerDamaged, OperationsError):
            pass  # a damaged ledger shows as operations.ledger unavailable (BR6.10)
