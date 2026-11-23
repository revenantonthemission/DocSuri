"""`docsuri-standing`: the scheduler account's one long-running job (U8 plan Step 35;
reliability-design § 11, R4, BR4.2, BR6.12, BR9.17).

It holds the standing operator authority, and nothing in person. It reaches the
platform only through PlatformControl's bound operations and the fixed programs:

- **heartbeat** (`heartbeat.Heartbeat`): the probe pair, the availability record and the
  heartbeat ping, every 5-minute slot;
- **agent-status** (`AgentStatus`): the backup agent's unattended `status`, recorded as
  PlatformControl evidence for the backup volume (which `storage.capacity` reads
  through the service account's bounded evidence reader); when the volume check passes
  again after failing, the disposal pass runs;
- **isolation**: `platform.isolation.check` through PlatformControl, every 5 minutes;
- **backup** (`ScheduledRecovery.backup`): at 04:00, after settling what an interrupted
  turn left open, a `backup.create` request from the schedule, admitted and run as
  Workflow 5 (its set, then its ledger copy), the backup ping, then the disposal pass; a
  day without a passed set takes a lone ledger copy and pings `/backup/fail` (NFR4.3,
  L1-5, L1-48), then runs the disposal pass when it ran the backup; it catches up at
  start when the newest passed set is older than 24 hours;
- **verification** (`ScheduledRecovery.verification`): at 05:00 on Sundays and at the
  next 05:00 after an erasure (L1-42), a `restore.verify` of the newest passed set
  (Workflow 6) and the verification ping; it catches up at start when the latest
  Sunday's run, or the verification of an erasure that waited at the latest 05:00, is
  missing;
- **housekeeping** (`housekeeping.Housekeeping`), hourly.

At each start the start watch (`heartbeat.StartWatch`) writes the start record (NFR8.6),
and the agent's status is recorded compared with the ledger (L1-51).

A scheduled request's submission is derived from its lane and its scheduled instant, so
a run retried after a restart recovers the same request (BR4.9). The composed realm's
wiring (`realm_parts`) uses its own ledger, scheduler grant, realm driver and stand-in
check addresses; production's (`production_wiring.production_parts`, Step 37) the
scheduler account's credentials and check files the installer wrote.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from .healthchecks import Healthchecks
from .heartbeat import Heartbeat, StartWatch
from .housekeeping import Housekeeping
from .lanes import SEOUL, SLOT_SECONDS, Lane, Lanes, Turn, daily_at, every, slot_of, weekly_at

TICK_SECONDS = 1.0
HOUR = 3600
# The targets the 04:00 turn settles the scheduler's interrupted operations on (Step
# 66(b), Step 64(j)).
INTERRUPTED_TARGETS = ("ledger-copy", "database-production", "database-rehearsal")


def _parse(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


MAX_UNRECORDED = 32


def ledger_identities(ledger) -> Callable[[], set[str]]:
    """The record identities the ledger carries for volume files: every BackupSet's,
    LedgerCopy's and RetainedCopy's (U8 plan Step 66(f))."""

    def identities() -> set[str]:
        found = {str(item["backupId"]) for item in ledger.records("backup-set")}
        found |= {str(item["ledgerCopyId"]) for item in ledger.records("ledger-copy")}
        found |= {str(item["copyId"]) for item in ledger.records("retained-copy")}
        return found

    return identities


def compared(observed: dict, identities: Callable[[], set[str]] | None) -> dict:
    """The status with its `catalogued` list replaced by `unrecordedFiles` (at most 32,
    the latest disposal points first), `unrecordedCount` and `cataloguedCount` (L1-51).
    A ledger read that fails leaves the comparison out: the status is recorded without
    `catalogued` and without the three fields, which the backups evidence treats as
    unusable (Step 64(f)). A status without a list is recorded as it came."""
    if "catalogued" not in observed:
        return observed
    status = {name: value for name, value in observed.items() if name != "catalogued"}
    if identities is None:
        return status
    try:
        recorded = identities()
    except Exception:  # noqa: BLE001 - the agent-status lane never depends on the ledger
        return status
    catalogued = list(observed.get("catalogued") or [])
    unrecorded = [entry for entry in catalogued
                  if str(entry.get("recordId")) not in recorded]
    unrecorded.sort(key=lambda entry: str(entry.get("disposeAfter") or ""), reverse=True)
    return {**status, "unrecordedFiles": unrecorded[:MAX_UNRECORDED],
            "unrecordedCount": len(unrecorded), "cataloguedCount": len(catalogued)}


class AgentStatus:
    """The agent's status recorded as evidence, its catalogue compared with the ledger's
    record identities (`identities`, L1-51); a volume check that passes again after
    failing runs the disposal pass (BR9.17)."""

    def __init__(self, status: Callable[[], dict], record: Callable[[dict], object],
                 disposal: Callable[[], dict], *,
                 identities: Callable[[], set[str]] | None = None):
        self.status, self.record_evidence, self.disposal = status, record, disposal
        self.identities = identities
        self.available: bool | None = None

    def run(self, now: dt.datetime) -> str:
        try:
            observed = self.status()
        except Exception:  # noqa: BLE001 - an agent that cannot answer is unavailable
            observed = {"available": False, "findings": ["backup-agent-unreachable"]}
        else:
            observed = compared(observed, self.identities)
        self.record_evidence(observed)
        available = bool(observed.get("available"))
        passed_again = available and self.available is False
        self.available = available
        if passed_again:
            self.disposal()
            return "volume-check-passed-again"
        return "volume-available" if available else "volume-unavailable"


class ScheduledRecovery:
    """The schedule's backups and verifications as RecoveryRequests (BR4.2)."""

    def __init__(self, requests, procedures, checks: Healthchecks, *,
                 environment: Callable[[], str], disposal: Callable[[], dict],
                 policy):
        self.requests, self.procedures, self.checks = requests, procedures, checks
        self.environment, self.disposal, self.policy = environment, disposal, policy
        self.ledger = requests.ledger
        # The 05:00 candidate the schedule last took a fresh view for (review fix, batch
        # 4): each candidate is decided on a read made at or after it.
        self._fresh_for: dt.datetime | None = None
        self._fresh_lock = threading.Lock()

    def fresh(self) -> None:
        """Make the next ledger read a current one (review fix, batch 4). Production's
        `LedgerClient` keeps a local copy refreshed only after its own writes, so what
        another process records (the release's pre-release set, an administrator's
        backup, a tombstone, a profile receipt) would stay out of view until the job's
        next write; `invalidate()` drops that copy, and the next read takes a fresh one.
        A ledger read directly (the realm's `Ledger`) is always current."""
        invalidate = getattr(self.ledger, "invalidate", None)
        if invalidate is not None:
            invalidate()

    def _submission(self, lane: str, environment: str, instant: dt.datetime):
        return uuid5(NAMESPACE_URL, f"docsuri-standing:{lane}:{environment}:{instant:%Y%m%dT%H}")

    def _admitted(self, request: dict) -> bool:
        from backend.modules.operations.errors import OperationsError

        if request["state"] in ("awaiting-operator", "running"):
            return True
        if request["state"] != "requested":
            return False
        try:
            return self.requests.admit(request["recoveryRequestId"])["state"] == (
                "awaiting-operator")
        except OperationsError:
            return False  # a switch, a restore or a conflicting request holds it

    def settle_unknown(self) -> list[str]:
        """A scheduled request left `unknown` (its effect's outcome unknown, its
        PlatformControl operation bound by the scheduler) is settled here, under the
        standing job's own operator, before the lane's next request (review finding,
        Minor, R16): the store refuses the in-person word for the scheduler's operations,
        as it refuses the scheduler yours, so only the standing job can reconcile them.
        Answers the requests it settled; one the store or the ledger still refuses stays
        unknown for the next turn, and an in-person request is never touched."""
        from backend.modules.operations.errors import OperationsError

        from docsuri_ops.platform_control.errors import ControlError

        settled = []
        # Both environments (Step 66(b)): a switch, an abort or a rollback changes the
        # mode between two turns, and only the standing job settles its own operations.
        for request in self.requests.unknown():
            if request["origin"] != "schedule":
                continue
            try:
                after = self.procedures.reconcile(request["recoveryRequestId"])
            except (OperationsError, ControlError):
                continue
            if after["state"] != "unknown":
                settled.append(request["recoveryRequestId"])
        return settled

    def settle_interrupted(self, instant: dt.datetime) -> None:
        """What an interrupted turn left open, settled before the 04:00 turn files
        anything (Step 66(b)): the scheduler's own operations a stopped process left
        pending on the lone copy's and the databases' targets (a store that refuses is
        caught, and the turn goes on), then each scheduled `backup.create` an earlier
        day's turn left `running`, run again through `procedures.backup` under its
        unchanged key, so its receipt replays and the request settles."""
        from backend.modules.operations.errors import OperationsError

        from docsuri_ops.platform_control.errors import ControlError

        try:
            self.procedures.reconcile_interrupted(INTERRUPTED_TARGETS)
        except (OperationsError, ControlError):
            pass
        for request in self.requests.active():
            if (request["origin"], request["operation"], request["state"]) != (
                    "schedule", "backup.create", "running"):
                continue
            today = str(self._submission("backup", request["environment"], instant))
            if request["submissionId"] == today:
                continue  # this turn's own request: the turn below runs it
            try:
                self.procedures.backup(request["recoveryRequestId"], via="standing")
            except (OperationsError, ControlError):
                continue

    def backup(self, now: dt.datetime) -> str:
        """The 04:00 turn (Step 66(b)): a passed set pings ok, then the disposal pass.
        Any other turn takes the lone ledger copy of that day, pings `/backup/fail` once
        whatever the copy's outcome, and then runs the disposal pass when it ran
        `procedures.backup`. A copy that does not complete answers `ledger-copy-failed`.

        The turn reads a fresh view first, so its mode and its expected revision are
        current, and a request whose filing the ledger refuses (a set another process
        recorded since, CONFLICT) is a backup not admitted: the lone copy is still taken
        (review fix, batch 4). A backup run that raises still takes the lone copy and runs
        the disposal pass."""
        from backend.modules.operations.errors import OperationsError
        from backend.modules.operations.recovery_procedures import OutcomeUnknown, ProcedureFailed

        self.fresh()
        self.settle_unknown()
        instant = daily_at(self.policy.backup_hour_seoul)(now)
        self.settle_interrupted(instant)
        environment = self.environment()
        ran = False
        try:
            target = self.procedures.platform.database_of(environment)
        except ProcedureFailed as failure:
            if failure.reason != "no-rehearsal-database":
                raise
            result = "no-rehearsal-database"
        else:
            try:
                request = self.requests.request(
                    origin="schedule", operation="backup.create", environment=environment,
                    target_id=target,
                    expected_revision=self.requests.backup_revision(environment),
                    submission_id=self._submission("backup", environment, instant))
            except OperationsError:
                request = None  # the ledger refused the filing: not admitted
            if request is None or not self._admitted(request):
                result = "backup-not-admitted"
            else:
                ran = True
                try:
                    done = self.procedures.backup(request["recoveryRequestId"],
                                                  via="standing")
                except Exception:  # noqa: BLE001 - the day still gets its lone copy
                    done = {"state": "raised"}
                if done["state"] == "succeeded":
                    self.checks.ping("backup", ok=True)
                    self.disposal()
                    return "backup-succeeded"
                result = "backup-failed"
        owner = f"standing-ledger-copy:{environment}:{instant.astimezone(SEOUL):%Y%m%d}"
        try:
            self.procedures.ledger_copy_alone(environment, owner_key=owner, via="standing")
        except (ProcedureFailed, OutcomeUnknown):
            result = "ledger-copy-failed"  # its storage.capacity signal is already sent
        self.checks.fail("backup")
        if ran:
            self.disposal()
        return result

    def newest_passed(self, environment: str) -> dict | None:
        sets = [item for item in self.ledger.records("backup-set")
                if item["environment"] == environment and item.get("integrity") == "passed"
                and not any(name in item for name in ("disposedAt", "retiredWithVolumeAt"))]
        return max(sets, key=lambda item: item["takenAt"], default=None)

    def verification(self, now: dt.datetime) -> str:
        self.fresh()
        self.settle_unknown()
        environment = self.environment()
        backup = self.newest_passed(environment)
        if backup is None:
            self.checks.fail("verification")
            return "no-passed-set"
        instant = daily_at(self.policy.verification_hour_seoul)(now)
        request = self.requests.request(
            origin="schedule", operation="restore.verify", environment=environment,
            target_id=backup["backupId"],
            expected_revision=self.ledger.revision("backup-set", backup["backupId"]),
            submission_id=self._submission("verification", environment, instant))
        if not self._admitted(request):
            self.checks.fail("verification")
            return "verification-not-admitted"
        done = self.procedures.verify(request["recoveryRequestId"], via="standing")
        ok = done["state"] == "succeeded"
        self.checks.ping("verification", ok=ok)
        return "verification-succeeded" if ok else "verification-failed"

    # --- catch-up at start (R4) ----------------------------------------------------------

    def backup_overdue(self, now: dt.datetime) -> bool:
        newest = self.newest_passed(self.environment())
        return newest is None or now - _parse(newest["takenAt"]) > dt.timedelta(
            seconds=self.policy.backup_catch_up_seconds)

    def erasure_waits(self, at: dt.datetime) -> bool:
        """An uncovered tombstone appended at or before `at` (L1-42): the verification
        lane asks it at each 05:00, so a tombstone appended after a day's 05:00 is
        verified at the next day's 05:00, within 24 hours. Each new candidate is decided
        on a fresh view, read once per candidate (review fix, batch 4): a tombstone
        another process appended before 05:00 is seen at that 05:00."""
        from backend.modules.operations.lifecycle import covering_verification

        with self._fresh_lock:
            if at != self._fresh_for:
                self.fresh()
                self._fresh_for = at
        return any(_parse(tombstone["appendedAt"]) <= at
                   and covering_verification(self.ledger, tombstone) is None
                   for tombstone in self.ledger.records("restore-tombstone"))

    def _started_since(self, environment: str, since: dt.datetime) -> bool:
        return any(item["environment"] == environment and _parse(item["startedAt"]) >= since
                   for item in self.ledger.records("restore-verification"))

    def verification_due(self, now: dt.datetime) -> bool:
        """Due at start (R4) when no verification of the environment started at or after
        the latest Sunday 05:00, or when an erasure waited at the latest 05:00 and none has
        started since: a restart catches up only an erasure a missed 05:00 left waiting."""
        environment = self.environment()
        sunday = weekly_at(self.policy.verification_weekday,
                           self.policy.verification_hour_seoul)(now)
        if not self._started_since(environment, sunday):
            return True
        latest = daily_at(self.policy.verification_hour_seoul)(now)
        return self.erasure_waits(latest) and not self._started_since(environment, latest)


@dataclass
class StandingParts:
    heartbeat: Heartbeat
    checks: Healthchecks
    agent: AgentStatus
    isolation: Callable[[dt.datetime], object]
    recovery: ScheduledRecovery
    housekeeping: Housekeeping
    policy: object
    slot_seconds: int = SLOT_SECONDS
    # The start record's watch (NFR8.6, Step 66(e)), started before `run_forever`.
    start_watch: StartWatch | None = None


def build_lanes(parts: StandingParts, *, record: Callable[[Turn], None] | None = None) -> Lanes:
    """The lane table. A failed backup or verification turn is identified by that day's
    04:00 or 05:00 candidate, which needs no ledger read (Step 66(c))."""
    policy, recovery = parts.policy, parts.recovery
    return Lanes([
        Lane("heartbeat", every(parts.slot_seconds), parts.heartbeat.run),
        Lane("agent-status", every(parts.slot_seconds), parts.agent.run),
        Lane("isolation", every(parts.slot_seconds), parts.isolation),
        Lane("backup", daily_at(policy.backup_hour_seoul), recovery.backup,
             catch_up=recovery.backup_overdue, turn=daily_at(policy.backup_hour_seoul)),
        Lane("verification", weekly_at(policy.verification_weekday,
                                       policy.verification_hour_seoul,
                                       also=recovery.erasure_waits),
             recovery.verification, catch_up=recovery.verification_due,
             turn=daily_at(policy.verification_hour_seoul)),
        Lane("housekeeping", every(HOUR), parts.housekeeping.run),
    ], record=record, fail=parts.checks.fail)


def start_watch(parts: StandingParts) -> None:
    """The start record's watch, when the parts carry one (Step 66(e))."""
    if getattr(parts, "start_watch", None) is not None:
        parts.start_watch.start()


def isolation_lane(operator) -> Callable[[dt.datetime], str]:
    """`platform.isolation.check` through PlatformControl, one per 5-minute slot."""

    def run(now: dt.datetime) -> str:
        key = f"standing-isolation:{slot_of(now):%Y%m%dT%H%M}"
        receipt = operator.execute("platform.isolation.check", "isolation", {"via": "standing"},
                                   key=key)
        return "isolation-checked" if receipt.get("outcome") == "succeeded" else (
            "isolation-not-checked")

    return run


def evidence_recorder(store, *, environment: str, max_age_seconds: int):
    """The agent's status as PlatformControl evidence for the backup volume."""

    def record(observations: dict) -> object:
        digest = hashlib.sha256(json.dumps(observations, sort_keys=True).encode()).hexdigest()
        return store.record_evidence(target="backup-volume", input_hash=digest,
                                     environment=environment, observations=observations,
                                     max_age_seconds=max_age_seconds)

    return record


def run_forever(lanes: Lanes, clock: Callable[[], dt.datetime], stopping: threading.Event,
                *, tick_seconds: float = TICK_SECONDS) -> None:
    lanes.start(clock())
    while not stopping.wait(tick_seconds):
        lanes.tick(clock())


def realm_parts(environment_file: Path, ledger, *, clock: Callable[[], dt.datetime],
                transactions=None, send=None, checks: Healthchecks | None = None,
                record_folder: Path | None = None) -> StandingParts:
    """The standing job over the composed realm: its scheduler grant (routine only), the
    realm driver's agent words as the scheduler, the realm's ledger, and the check
    addresses its tool writes to `scheduler/healthchecks.json` (a local stand-in)."""
    import ssl

    from backend.modules.operations.observation_store import ObservationStore
    from backend.u8_policy import SYNTHETIC_OPERATIONS as policy

    from docsuri_ops.arrangement.paths import DatabaseNames
    from docsuri_ops.cutover.disposal import DisposalPass, DisposalPlatform
    from docsuri_ops.u8_platform.drivers import load_config
    from docsuri_ops.u8_platform.drivers.realm import RealmDriver
    from docsuri_ops.u8_platform.platform_profile import U8PlatformProfile
    from docsuri_ops.u8_platform.recovery_words import realm_procedures
    from docsuri_ops.u8_platform.u8_protocols import realm_facts, realm_operator

    from .availability import AvailabilityRecord
    from .healthchecks import load_addresses
    from .heartbeat import REALM_LOCAL, REALM_PUBLIC, probe
    from .housekeeping import starts_pruner

    profile = U8PlatformProfile.realm(environment_file.parent)
    run_root = profile.run_root
    facts = realm_facts(profile, ledger, clock=clock)
    operator = realm_operator(profile, "scheduler", ledger, clock=clock, facts=facts)
    driver = RealmDriver(load_config(profile.effects_root), caller="scheduler")
    procedures = realm_procedures(profile, ledger, clock=clock, role="scheduler",
                                  policy=policy).procedures
    if checks is None:
        options = {} if send is None else {"send": send}
        checks = Healthchecks(load_addresses(run_root / "scheduler", production=False),
                              **options)
    record = AvailabilityRecord(record_folder or run_root / "availability",
                                slot_seconds=policy.availability_slot_seconds)
    certificate = run_root / "service-operations-tls.crt"
    context = ssl.create_default_context(cafile=str(certificate)) if certificate.exists() else None
    heartbeat = Heartbeat(
        record, checks,
        public=lambda: probe(REALM_PUBLIC, seconds=policy.probe_limit_seconds, context=context),
        local=lambda: probe(REALM_LOCAL, seconds=policy.probe_limit_seconds))
    def serving() -> str:
        """The environment the standing job serves now (L1-65): the disposal pass's
        incidents and the standing job's requests read this one function."""
        return "live" if facts().mode == "live" else "rehearsal"

    disposal = DisposalPass(ledger, policy, DisposalPlatform(
        operator=operator, names=DatabaseNames("docsuri_u8"), environment=serving,
        current_rehearsal=lambda: facts().current_rehearsal,
        dispose_due=lambda document: driver.agent_word("dispose-due", document,
                                                       via="standing")), clock=clock).run
    agent = AgentStatus(lambda: driver.agent_word("status", {}, via="standing"),
                        evidence_recorder(operator.store, environment=profile.environment,
                                          max_age_seconds=policy.provider_stale_seconds),
                        disposal, identities=ledger_identities(ledger))
    recovery = ScheduledRecovery(
        procedures.requests, procedures, checks, environment=serving,
        disposal=disposal, policy=policy)
    starts = run_root / "scheduler" / "evidence" / "starts"
    housekeeping = Housekeeping(
        expire_requests=procedures.requests.expire_due,
        delete_observations=(lambda now: 0) if transactions is None
        else ObservationStore(transactions).delete_old,
        prune_availability=record.prune, prune_starts=starts_pruner(starts))
    watch = StartWatch(starts, lambda: probe(REALM_LOCAL, seconds=policy.probe_limit_seconds),
                       clock)
    return StandingParts(heartbeat, checks, agent, isolation_lane(operator), recovery,
                         housekeeping, policy, slot_seconds=policy.availability_slot_seconds,
                         start_watch=watch)


def production_main(stopping: threading.Event) -> int:
    """The standing job on this Mac (Step 37's wiring): the scheduler account's
    credentials and check files the installer wrote, the ledger through `docsuri-ledger`
    (`sudo -n`), its logs in `scheduler/logs/`."""
    from backend.log_events import configure

    from docsuri_ops.arrangement.paths import ArrangementPaths
    from docsuri_ops.production_wiring import LedgerClient, production_parts

    def clock() -> dt.datetime:
        return dt.datetime.now(dt.UTC)

    paths = ArrangementPaths()
    log = configure("standing", paths.scheduler / "logs", production=True)
    ledger = LedgerClient(via="standing", clock=clock, paths=paths)
    try:
        parts = production_parts(ledger, clock=clock, paths=paths)
        lanes = build_lanes(parts, record=lambda turn: log.event(
            "standing", f"lane.{turn.outcome}", state=turn.lane,
            **({"reason": turn.reason} if turn.reason else {})))
        start_watch(parts)
        run_forever(lanes, clock, stopping)
    except KeyboardInterrupt:
        pass
    finally:
        ledger.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    """The installed program's entry: production's standing job, or `--realm-environment`
    for the composed realm's."""
    import os
    import signal

    if any(name.startswith(("PYTHON", "DYLD_", "LD_")) for name in os.environ):
        print(json.dumps({"ok": False, "reason": "environment-refused"}))
        return 2
    parser = argparse.ArgumentParser(prog="docsuri-standing")
    parser.add_argument("--realm-environment", type=Path)
    args = parser.parse_args(argv)
    if args.realm_environment is None:
        stopping = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stopping.set())
        return production_main(stopping)
    from backend.local_profile import LocalProfile
    from backend.log_events import configure
    from backend.modules.operations.ledger import Ledger
    from backend.transactions import OwnerTransactions

    def clock() -> dt.datetime:
        return dt.datetime.now(dt.UTC)

    local = LocalProfile.load(args.realm_environment)
    log = configure("standing", local.root / "logs", production=False)
    ledger = Ledger.open(local.root / "ledger", clock=clock)
    transactions = OwnerTransactions(local, process="worker")
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopping.set())
    try:
        parts = realm_parts(args.realm_environment, ledger, clock=clock,
                            transactions=transactions)
        lanes = build_lanes(parts, record=lambda turn: log.event(
            "standing", f"lane.{turn.outcome}", state=turn.lane,
            **({"reason": turn.reason} if turn.reason else {})))
        start_watch(parts)
        run_forever(lanes, clock, stopping)
    except KeyboardInterrupt:
        pass
    finally:
        transactions.close()
        ledger.close()
    return 0
