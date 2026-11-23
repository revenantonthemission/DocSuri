"""One producer per registered capability (U8 plan Step 15; BR3.3, BR3.5, BR3.6, BR6.6,
BR6.11, BR6.12, O1, O2).

Producers run in the workers process on timers (`ProducerSchedule`), so the host's
request threads never wait for them. Each observes once as soon as its schedule starts,
then every renewal interval of observability-design § 3.2, and a producer that cannot
observe records unknown with its reason (BR3.3). The host's own 5xx rate is the one
producer the host runs itself, from its latency summaries.

- The owners' probes reuse `backend/local_observation.py`'s `probe_owner`.
- Export reads U6's `export.status_counts` and, beside them, the oldest acceptance of an
  effect not yet terminal. Digests read each pending run's `scheduled_at`, the instant U5
  recorded for it, and U5's due deliveries with no run. Each is degraded past its bound
  (24 h; 2 h past the scheduled time) and carries its failed-over-terminal rate for 24 h.
- `storage.capacity` reads A10's footprint, the internal disk's `statvfs`, the backup
  volume as the service account sees it, and the backup agent's latest status through
  PlatformControl's evidence reader, compared with the volume the profile names.
- `operations.ledger` is the ledger check; `background.work` reads the control loop.
- Providers report reachability, allowance and hold. The model runtime's producer
  compares each pinned model's digest from `/api/tags` with its pin and re-pins the
  search model with `keep_alive: -1` every re-pin interval.
- `platform.status` and `platform.isolation` are read-only: an evidence reader that can
  only inspect, and the newest file of the isolation evidence folder (BR3.5).
- `operations.cutover` compares the CutoverRecord with the routing evidence.
- Assistance reads its readiness marker (BR7.7).

Every value an observation carries is a registered key or a count (BR3.4).

Step 58 adds 24-hour counts to platform.status (the agent's writes and disposals),
public.static (the host's 5xx rate), provider.models (failed model jobs),
operations.cutover (the tunnel's failed probes), background.work (failed jobs per lane
and the account-mail sender's failed runs) and storage.capacity (PostgreSQL failures).
Each settles its outcome first and then reads its counts in one guarded step: a count
read that raises is logged (`counts.unread`) and counts 0 of 0, so a count never changes
an outcome (Step 58(i)). background.work also checks the scheduler's pass file.
"""

from __future__ import annotations

import asyncio
import dataclasses
import datetime as dt
import json
import math
import os
import stat
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from backend.u8_registry import CAPABILITY_BY_ID, MODEL_EVIDENCE, timing

from .observations import ObservationRefused, Observations

SEARCH_MODEL = "bge-m3:latest"
PROBE_REASONS = {
    "observation.storeDenied": "store-denied",
    "observation.storeUnavailable": "store-unavailable",
    "observation.allocationExhausted": "store-busy",
}


@dataclass(frozen=True)
class Observed:
    outcome: str
    reason: str | None = None
    limitations: tuple[str, ...] = ()
    error_count: int = 0
    total_count: int = 0
    observed_at: dt.datetime | None = None


AVAILABLE = Observed("available")
# Every producer's error-rate window (L1-29, L1-30, L1-41, L1-47): the 24 hours to now.
COUNT_WINDOW = dt.timedelta(hours=24)


def _window(policy) -> dt.timedelta:
    seconds = getattr(policy, "error_rate_window_seconds", None)
    return COUNT_WINDOW if seconds is None else dt.timedelta(seconds=seconds)


def _unread(state: str) -> None:
    from backend.log_events import current

    current().event("operations", "counts.unread", "warning", state=state)


def read_counts(capability: str, read: Callable[[], tuple[int, int]] | None) -> tuple[int, int]:
    """One count source, read once the outcome is settled (Step 58(i)): a read that
    raises is logged (`counts.unread`, `state` the capability) and counts 0 of 0, so a
    count never changes an outcome; no source counts 0 of 0."""
    if read is None:
        return 0, 0
    try:
        errors, total = read()
        return int(errors), int(total)
    except Exception:  # noqa: BLE001 - a count never changes an outcome
        _unread(capability)
        return 0, 0


def with_counts(outcome: Observed, *counts: tuple[int, int]) -> Observed:
    """The settled outcome, carrying the sum of its sources' counts."""
    return dataclasses.replace(outcome, error_count=sum(item[0] for item in counts),
                               total_count=sum(item[1] for item in counts))


def _moment(value) -> dt.datetime | None:
    """A ledger or evidence time (`...Z`), or None for none."""
    if not value:
        return None
    return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


class Producer:
    """One capability's producer: `observe(now)` gives its outcome."""

    capability: str = ""

    def __init__(self, capability: str):
        if capability not in CAPABILITY_BY_ID:
            raise ValueError("capability outside the registry")
        self.capability = capability
        self.producer = CAPABILITY_BY_ID[capability].producer

    def observe(self, now: dt.datetime) -> Observed:  # pragma: no cover - interface
        raise NotImplementedError


class OwnerProbe(Producer):
    """An owner's bounded store probe, through its own login."""

    def __init__(self, capability: str, owner: str, transactions):
        super().__init__(capability)
        self.owner, self.transactions = owner, transactions

    def observe(self, now: dt.datetime) -> Observed:
        from backend.local_observation import probe_owner

        result = probe_owner(self.transactions, self.owner)
        if result["disposition"] == "available":
            return AVAILABLE
        reason = PROBE_REASONS.get(result["evidence"].get("reasonKey"), "producer-failed")
        return Observed("unavailable", reason)


class ExportProducer(Producer):
    """U6's status counts and, beside them, the oldest acceptance of an effect that is
    not yet terminal: degraded once the oldest unclear or accepted effect is past its
    bound, whichever of the three ages is largest; the error rate is failed over
    terminal effects in 24 hours (BR3.6)."""

    def __init__(self, transactions, policy):
        super().__init__("export")
        self.transactions, self.policy = transactions, policy

    def observe(self, now: dt.datetime) -> Observed:
        def read(conn) -> tuple[dict, int | None]:
            status = conn.execute(
                "SELECT export.status_counts(%s) AS status", (now,)
            ).fetchone()["status"]
            accepted = conn.execute(EXPORT_OLDEST_ACCEPTANCE, {"now": now}).fetchone()
            return status, accepted["oldest"]

        status, accepted_seconds = self.transactions.run("export", read)
        return export_outcome(status, self.policy, accepted_seconds=accepted_seconds)


# The oldest effect that is not yet terminal, counted from its acceptance. U6's own age
# for an unknown effect restarts at its latest attempt's deadline; this one never does.
EXPORT_OLDEST_ACCEPTANCE = """
SELECT floor(extract(epoch FROM %(now)s - min(e.accepted_at)))::bigint AS oldest
  FROM export.effect e
 WHERE e.state IN ('accepted','executing','unknown')
"""


def export_outcome(status: dict, policy, *, accepted_seconds: int | None = None) -> Observed:
    """U6's counts (`export.status_counts`) and the oldest acceptance's age to an outcome
    and an error rate: the largest of U6's two ages and the acceptance's decides."""
    effects = status["effects"]
    failed = int(effects["failedLast24h"])
    terminal = failed + sum(int(effects[name]) for name in (
        "succeededLast24h", "cancelledLast24h", "invalidatedLast24h"))
    oldest = max(status.get("oldestAcceptedSeconds") or 0,
                 status.get("oldestUnknownSeconds") or 0,
                 accepted_seconds or 0)
    if oldest > policy.export_degraded_after_seconds:
        return Observed("degraded", "export-effect-late", ("export-effect-late",),
                        failed, terminal)
    return Observed("available", None, (), failed, terminal)


# The pending runs' oldest scheduled instant, the pending runs that have none, and the
# 24-hour counts. A run's scheduled instant is `scheduled_at`: the due instant of the
# occurrence it was prepared for, which U5 records once at preparation and never changes
# (`backend/modules/topics/u5_scheduled_instant.sql`). Nothing else of the run or of its
# topic's settings is read, so no later change of delivery time, cadence or zone moves
# the instant. A pending run with no recorded instant has no age; it is counted in
# `unscheduled`, so it is never hidden. Both counts cover the 24 hours to `now`.
DIGEST_RUNS = """
SELECT
  (SELECT floor(extract(epoch FROM %(now)s - min(r.scheduled_at)))::bigint
     FROM topics.digest_run r
    WHERE r.state IN ('prepared','sending','unknown')) AS oldest,
  (SELECT count(*) FROM topics.digest_run r
    WHERE r.state IN ('prepared','sending','unknown')
      AND r.scheduled_at IS NULL) AS unscheduled,
  (SELECT count(*) FROM topics.digest_run
    WHERE state = 'failed'
      AND updated_at > %(since)s AND updated_at <= %(now)s) AS failed,
  (SELECT count(*) FROM topics.digest_run
    WHERE state IN ('sent','failed','empty')
      AND updated_at > %(since)s AND updated_at <= %(now)s) AS terminal
"""


class DigestProducer(Producer):
    """U5's digest deliveries: degraded once the oldest pending delivery is more than
    2 hours past its scheduled time; failed over terminal runs in 24 hours (BR3.6).

    Two kinds of delivery are pending:
    - a run still prepared, sending or unknown, from the instant U5 recorded for it
      (`DIGEST_RUNS`, `scheduled_at`), whatever happened to its topic's settings or its
      owner's zone afterwards;
    - the oldest due delivery that has no run yet, through U5's own due read
      (`TopicsRepository.due_topics`), so a topics task that fails on every pass shows.

    The due read is scoped as U5's scheduler scopes it: `recipient` gives the delivery's
    one permitted address (rehearsal) or None (live). A pending run with no recorded
    instant cannot be shown on time, so it reads degraded at once. The observation
    carries an age and counts only."""

    def __init__(self, transactions, policy, *, limitation: str | None = None,
                 recipient: Callable[[], str | None] | None = None):
        super().__init__("topics.digest")
        self.transactions, self.policy = transactions, policy
        # Production's rehearsal before the maintainer has an address: every run held
        # (`maintainer-address-pending`, your decision of 2026-10-24).
        self.limitation = limitation
        self.recipient = recipient

    def _oldest_due(self, now: dt.datetime) -> dt.datetime | None:
        """The oldest due delivery with no run, read first in its own transaction, so a
        run prepared between the two reads is counted twice, never missed."""
        from backend.modules.topics.repository import TopicsRepository

        scope = None if self.recipient is None else self.recipient()
        rows = TopicsRepository(self.transactions).due_topics(now, 1, recipient=scope)
        return rows[0]["due_at"] if rows else None

    def observe(self, now: dt.datetime) -> Observed:
        window = dt.timedelta(seconds=self.policy.error_rate_window_seconds)
        due = self._oldest_due(now)
        row = self.transactions.run("topics", lambda conn: conn.execute(
            DIGEST_RUNS, {"now": now, "since": now - window}).fetchone())
        ages = [age for age in (
            row["oldest"],
            None if due is None else math.floor((now - due).total_seconds()),
        ) if age is not None]
        outcome = digest_outcome({**row, "oldest": max(ages) if ages else None}, self.policy)
        if self.limitation is not None:
            return Observed("degraded", self.limitation, (self.limitation,),
                            outcome.error_count, outcome.total_count)
        return outcome


def digest_outcome(row: dict, policy) -> Observed:
    """U5's digest runs (the oldest pending delivery's age, the pending runs with no
    recorded instant, and the 24-hour failed and terminal counts) to an outcome and an
    error rate. A pending run with no instant is late at once: it is never hidden."""
    failed, terminal = int(row["failed"]), int(row["terminal"])
    late = (row["oldest"] or 0) > policy.digest_late_seconds
    if late or int(row.get("unscheduled") or 0) > 0:
        return Observed("degraded", "digest-delivery-late", ("digest-delivery-late",),
                        failed, terminal)
    return Observed("available", None, (), failed, terminal)


class LedgerProducer(Producer):
    def __init__(self, ledger):
        super().__init__("operations.ledger")
        self.ledger = ledger

    def observe(self, now: dt.datetime) -> Observed:
        check = self.ledger.check()
        if check["status"] == "available":
            return AVAILABLE
        return Observed("unavailable", "ledger-damaged")


class CapacityProducer(Producer):
    """The footprint against the budget, the internal disk against its floors, the
    backup volume as the service account sees it, and the backup agent's status
    (scalability-design § 3; BR6.6)."""

    def __init__(self, transactions, policy, *, disk_path: Path,
                 volume_state: Callable[[], str], agent_status: Callable[[], dict] | None,
                 expected_volume: str | None, footprint: Callable[[], int] | None = None,
                 free_bytes: Callable[[], int] | None = None,
                 counts: Callable[[dt.datetime], tuple[int, int]] | None = None):
        super().__init__("storage.capacity")
        from backend.u8_capacity import CapacityBudget

        self.budget = CapacityBudget(policy, disk_path)
        self.policy, self.transactions = policy, transactions
        self.volume_state, self.agent_status = volume_state, agent_status
        self.expected_volume = expected_volume
        self._footprint = footprint or self._read_footprint
        self._free = free_bytes or self.budget.free_bytes
        # Step 58(g) (L1-29): every process's 24-hour PostgreSQL failure counts.
        self.counts = counts

    def _read_footprint(self) -> int:
        row = self.transactions.run(
            "operations",
            lambda conn: conn.execute("SELECT * FROM operations.capacity_footprint()").fetchone(),
        )
        return int(row["database_bytes"]) + int(row["wal_bytes"])

    def observe(self, now: dt.datetime) -> Observed:
        outcome = self._outcome()
        read = None if self.counts is None else (lambda: self.counts(now))
        return with_counts(outcome, read_counts(self.capability, read))

    def _outcome(self) -> Observed:
        state, reason = self.budget.judge(self._footprint(), self._free())
        if state == "unavailable":
            return Observed("unavailable", reason)
        found = [reason] if reason else []
        if self.volume_state() == "unavailable":
            found.append("backup-volume-unavailable")
        if self.agent_status is not None:
            found.extend(self._agent_findings())
        found = list(dict.fromkeys(found))
        if found:
            return Observed("degraded", found[0], tuple(found))
        return AVAILABLE

    def _agent_findings(self) -> list[str]:
        try:
            status = self.agent_status()
        except Exception:  # noqa: BLE001 - an unreadable status is an unavailable volume
            return ["backup-volume-unavailable"]
        found = []
        if status.get("volumeIdentity") != self.expected_volume:
            found.append("backup-volume-mismatch")
        if not status.get("available", False):
            found.append("backup-volume-unavailable")
        if int(status.get("freeBytes", 0)) < self.policy.backup_volume_floor_bytes:
            found.append("backup-volume-low")
        if status.get("sharedCleanupMarker"):
            found.append("backup-volume-shared-cleanup")
        if status.get("catalogue") != "intact":
            found.append("backup-catalogue-damaged")
        if status.get("lastGoodHeldPastRetention"):
            found.append("last-backup-held")
        return found


# The account-mail sender's beat may be at most this old: three of § 10's 30 s sends.
SENDER_LATE_SECONDS = 90.0
# The scheduler's pass may be at most this old: 3 x its 30 s pass (`SCHEDULER_SECONDS`,
# `u8_host.py`), Step 58(f), L1-41.
SCHEDULER_PASS_LATE_SECONDS = 90.0
SCHEDULER_PASS_FILE = "scheduler-pass.json"
BEHIND = Observed("degraded", "lane-behind-deadline", ("lane-behind-deadline",))


class BackgroundWorkProducer(Producer):
    """The control loop's status: degraded while a pass is behind its deadline.

    - `scheduler_pass` (Step 58(f), L1-41): the scheduler's last pass time, checked after
      the loop's own rules when they give available and before the sender's beat: no
      pass 90 s after the first observation is unknown `scheduler-pass-unrecorded`, a
      pass older than 90 s degraded `lane-behind-deadline`, both on the wall clock.
    - `lane_counts` and `sender_counts` (Step 58(f), L1-70): the six lanes' failed jobs
      and the account-mail sender's failed runs over 24 hours, read after the outcome
      (Step 58(i)) and carried on every outcome."""

    def __init__(self, status: Callable[[], dict] | None = None, *,
                 sender_beat: Callable[[], dt.datetime | None] | None = None,
                 wall_clock: Callable[[], dt.datetime] | None = None,
                 scheduler_pass: Callable[[], dt.datetime | None] | None = None,
                 lane_counts=None,
                 sender_counts: Callable[[dt.datetime], tuple[int, int]] | None = None):
        super().__init__("background.work")
        self.status = status
        self._timeouts = None
        # The account-mail sender's beat (U8 plan Step 53(h), L1-69), read through a
        # callable so the producer imports nothing of AccountAccess, and timed on the
        # wall clock in every profile (L1-68's exception to "One clock").
        self.sender_beat = sender_beat
        self.wall_clock = wall_clock or (lambda: dt.datetime.now(dt.UTC))
        self.scheduler_pass = scheduler_pass
        self.lane_counts, self.sender_counts = lane_counts, sender_counts
        self._first_seen: dt.datetime | None = None
        self._beat_unread_logged = False

    def observe(self, now: dt.datetime) -> Observed:
        outcome = self._outcome()
        lanes = None if self.lane_counts is None else (
            lambda: lane_sum(self.lane_counts.read(now)))
        sender = None if self.sender_counts is None else (lambda: self.sender_counts(now))
        return with_counts(outcome, read_counts(self.capability, lanes),
                           read_counts(self.capability, sender))

    def _outcome(self) -> Observed:
        if self.status is None:
            return Observed("unknown", "evidence-unavailable")
        status = dict(self.status())
        timeouts, previous = status.get("timeouts", 0), self._timeouts
        self._timeouts = timeouts
        if self._first_seen is None:
            self._first_seen = self.wall_clock()
        if status.get("state") == "stopped":
            return Observed("unknown", "evidence-unavailable")
        if status.get("state") == "deadline" or (previous is not None and timeouts > previous):
            return BEHIND
        late_pass = self._pass_outcome()
        if late_pass is not None:
            return late_pass
        if self._sender_late():
            return BEHIND
        return AVAILABLE

    def _pass_outcome(self) -> Observed | None:
        """The scheduler pass check; None keeps the loop's outcome."""
        if self.scheduler_pass is None:
            return None
        try:
            passed = self.scheduler_pass()
        except Exception:  # noqa: BLE001 - an unreadable pass is no pass
            passed = None
        since = self._first_seen if passed is None else max(passed, self._first_seen)
        if (self.wall_clock() - since).total_seconds() <= SCHEDULER_PASS_LATE_SECONDS:
            return None
        if passed is None:
            return Observed("unknown", "scheduler-pass-unrecorded")
        return BEHIND

    def _sender_late(self) -> bool:
        """A beat more than `SENDER_LATE_SECONDS` old, counted from the later of the beat
        and this producer's first observation. No beat, or a read that raises (logged
        once), keeps the loop's outcome."""
        if self.sender_beat is None:
            return False
        try:
            beat = self.sender_beat()
        except Exception:  # noqa: BLE001 - the check never makes background.work unknown
            if not self._beat_unread_logged:
                self._beat_unread_logged = True
                from backend.log_events import current

                current().event("operations", "sender.unread", "warning")
            return False
        if beat is None:
            return False
        since = max(beat, self._first_seen)
        return (self.wall_clock() - since).total_seconds() > SENDER_LATE_SECONDS


# --- failed jobs per lane (Step 58(f), L1-41) ------------------------------------------

LANES = ("research", "assistance", "topics", "export", "corpus", "lifecycle")
# A lifecycle scope's built attempt limit (`accounts.lifecycle_scope.attempts`, 0 to 3).
LIFECYCLE_ATTEMPTS = 3


def lane_sum(lanes: dict) -> tuple[int, int]:
    """The lanes' summed `(failed, terminal)`; a lane answered None counts 0 of 0."""
    present = [value for value in lanes.values() if value is not None]
    return sum(item[0] for item in present), sum(item[1] for item in present)


class LaneCounts:
    """Each lane's failed and terminal jobs over (now − 24 h, now], each lane read
    through its owner's login in one short transaction; each job counts once, whichever
    runner ran it. A lane whose read raises is logged (`counts.unread`, `state` the lane)
    and answered None."""

    def __init__(self, transactions, policy=None):
        self.transactions, self.policy = transactions, policy

    def read(self, now: dt.datetime, *, lanes=LANES) -> dict[str, tuple[int, int] | None]:
        since = now - _window(self.policy)
        answers: dict[str, tuple[int, int] | None] = {}
        for lane in lanes:
            if lane not in LANES:
                raise ValueError("unknown lane")
            # Looked up at call time, so a test may replace one lane's read.
            reader = getattr(self, f"_{lane}")
            try:
                answers[lane] = reader(now, since)
            except Exception:  # noqa: BLE001 - one lane's read never hides the others
                _unread(lane)
                answers[lane] = None
        return answers

    def _counted(self, owner: str, sql: str, now: dt.datetime,
                 since: dt.datetime) -> tuple[int, int]:
        row = self.transactions.run(
            owner, lambda conn: conn.execute(sql, {"now": now, "since": since}).fetchone())
        return int(row["failed"]), int(row["terminal"])

    def _research(self, now, since):
        return self._counted("research", (
            "SELECT count(*) FILTER (WHERE state='failed') AS failed,"
            " count(*) FILTER (WHERE state IN ('succeeded','failed','cancelled')) AS terminal"
            " FROM research.job WHERE updated_at > %(since)s AND updated_at <= %(now)s"),
            now, since)

    def _assistance(self, now, since):
        return self._counted("assistance", (
            "SELECT count(*) FILTER (WHERE state='failed') AS failed,"
            " count(*) FILTER (WHERE state IN ('succeeded','failed')) AS terminal"
            " FROM assistance.job WHERE updated_at > %(since)s AND updated_at <= %(now)s"),
            now, since)

    def _topics(self, now, since):
        return self._counted("topics", (
            "SELECT count(*) FILTER (WHERE state='failed') AS failed,"
            " count(*) FILTER (WHERE state IN ('sent','failed','empty')) AS terminal"
            " FROM topics.digest_run WHERE updated_at > %(since)s AND updated_at <= %(now)s"),
            now, since)

    def _export(self, now, since):
        # U6's own counts, as `export_outcome` reads them; never a read of its tables.
        outcome = export_outcome(self.transactions.run(
            "export",
            lambda conn: conn.execute(
                "SELECT export.status_counts(%s) AS status", (now,)).fetchone()["status"],
        ), _NO_LATENESS)
        return outcome.error_count, outcome.total_count

    def _corpus(self, now, since):
        return self._counted("corpus", (
            "SELECT count(*) FILTER (WHERE state='failed') AS failed,"
            " count(*) FILTER (WHERE state IN ('completed','failed')) AS terminal"
            " FROM corpus.run WHERE completed_at > %(since)s AND completed_at <= %(now)s"),
            now, since)

    def _lifecycle(self, now, since):
        # A scope that used its attempts and is not complete failed, at the later of its
        # last acknowledgement and its last claim's lease end: a claim sets lease_until
        # and never updated_at, so a third attempt still inside its lease waits.
        return self._counted("accounts", (
            "WITH s AS (SELECT disposition, attempts, updated_at,"
            " greatest(updated_at, coalesce(lease_until, updated_at)) AS ended"
            " FROM accounts.lifecycle_scope),"
            " f AS (SELECT count(*) FILTER (WHERE disposition<>'complete'"
            f" AND attempts>={LIFECYCLE_ATTEMPTS}"
            " AND ended > %(since)s AND ended <= %(now)s) AS failed,"
            " count(*) FILTER (WHERE disposition='complete'"
            " AND updated_at > %(since)s AND updated_at <= %(now)s) AS complete FROM s)"
            " SELECT failed, failed + complete AS terminal FROM f"),
            now, since)


@dataclass(frozen=True)
class _NoLateness:
    """A policy that never degrades: `LaneCounts` reads only `export_outcome`'s counts."""

    export_degraded_after_seconds: float = float("inf")


_NO_LATENESS = _NoLateness()


# --- the scheduler's pass (Step 58(f), L1-41) -----------------------------------------

def write_scheduler_pass(folder: Path, passed_at: dt.datetime) -> None:
    """`scheduler-pass.json` holding exactly `passedAt`, at mode 0600, through a temporary
    file renamed over the old one; a link at the path, or a linked folder, is refused."""
    text = passed_at.astimezone(dt.UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    payload = json.dumps({"passedAt": text}, sort_keys=True).encode()
    directory = os.open(folder, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = f".{SCHEDULER_PASS_FILE}.{os.getpid()}.tmp"
    try:
        try:
            if stat.S_ISLNK(os.stat(SCHEDULER_PASS_FILE, dir_fd=directory,
                                    follow_symlinks=False).st_mode):
                raise ValueError("the scheduler pass file cannot be a link")
        except FileNotFoundError:
            pass
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
        try:
            os.fchmod(descriptor, 0o600)
            view = memoryview(payload)
            while view:
                view = view[os.write(descriptor, view):]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, SCHEDULER_PASS_FILE, src_dir_fd=directory, dst_dir_fd=directory)
    finally:
        os.close(directory)


def read_scheduler_pass(folder: Path) -> dt.datetime | None:
    """The pass's `passedAt`, or None for a file that is missing, a link, unreadable or
    malformed."""
    try:
        descriptor = os.open(Path(folder) / SCHEDULER_PASS_FILE,
                             os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        value = json.loads(os.read(descriptor, 4096))
        if not isinstance(value, dict) or set(value) != {"passedAt"}:
            return None
        moment = _moment(value["passedAt"])
        return moment if moment is not None and moment.tzinfo is not None else None
    except (OSError, ValueError, TypeError):
        return None
    finally:
        os.close(descriptor)


def marker_ready(profile, purpose: str) -> bool:
    """The reviewed real-model evidence for `purpose` (BR7.7): the one readiness marker
    in production (`u8_outward.model_readiness`); earlier realms keep
    `assistance-readiness.json`."""
    if getattr(profile, "is_production", False):
        from backend.u8_outward import model_readiness

        return model_readiness(profile, purpose)
    from backend.local_host import assistance_readiness

    return purpose == "assistance" and assistance_readiness(profile)


class AssistanceProducer(Producer):
    """PaperAssistance waits for its readiness evidence (BR7.7) and for the model
    runtime (`provider.models`)."""

    def __init__(self, capability: str, profile, models_state: Callable[[], str] | None = None):
        super().__init__(capability)
        self.profile, self.models_state = profile, models_state

    def observe(self, now: dt.datetime) -> Observed:
        if self.models_state is not None and self.models_state() == "unavailable":
            return Observed("unavailable", "model-runtime-unavailable")
        if marker_ready(self.profile, "assistance"):
            return AVAILABLE
        return Observed("degraded", "assistance-readiness-pending",
                        ("assistance-readiness-pending",))


class ResearchProducer(Producer):
    """Research and novelty in production (Step 21): the owner's store probe, then
    degraded with `model-runtime-waiting` while the marker lacks `research` or
    `provider.models` is unavailable, so new requests wait for the runtime (BR3.2)."""

    def __init__(self, capability: str, transactions, profile,
                 models_state: Callable[[], str] | None = None):
        if capability not in ("research", "novelty"):
            raise ValueError("the research producer observes research and novelty")
        super().__init__(capability)
        self.probe = OwnerProbe(capability, "research", transactions)
        self.profile, self.models_state = profile, models_state

    def observe(self, now: dt.datetime) -> Observed:
        probed = self.probe.observe(now)
        if probed.outcome != "available":
            return probed
        waiting = Observed("degraded", "model-runtime-waiting", ("model-runtime-waiting",))
        if self.models_state is not None and self.models_state() == "unavailable":
            return waiting
        return AVAILABLE if marker_ready(self.profile, "research") else waiting


def latest_state(store, capability: str) -> Callable[[], str]:
    """The latest recorded outcome of a capability (`unknown` when none or unreadable),
    one short read: how the model producers learn `provider.models`."""

    def state() -> str:
        try:
            row = store.latest([capability]).get(capability)
        except Exception:  # noqa: BLE001 - an unreadable store is unknown, never available
            return "unknown"
        return "unknown" if row is None else row["outcome"]

    return state


class PlatformStatusProducer(Producer):
    """PlatformControl's status, through a reader that can only inspect (BR3.5), with
    the backup agent's status beside it (Step 58(b), NFR9.7's backup-agent row): an
    agent status with findings is degraded with the first as its reason and all as
    limitations; no recorded status (`LookupError`) is unknown while inspect passed.
    Every outcome carries the agent's failed writes and disposals over 24 hours, from
    the ledger alone (`platform_counts`)."""

    def __init__(self, inspect: Callable[[], dict] | None, *,
                 agent_status: Callable[[], dict] | None = None, ledger=None,
                 environment: str | None = None, policy=None):
        super().__init__("platform.status")
        self.inspect, self.agent_status = inspect, agent_status
        self.ledger, self.environment, self.policy = ledger, environment, policy

    def observe(self, now: dt.datetime) -> Observed:
        outcome = self._outcome()
        read = None if self.ledger is None or self.environment is None else (
            lambda: platform_counts(self.ledger, self.environment, now, _window(self.policy)))
        return with_counts(outcome, read_counts(self.capability, read))

    def _outcome(self) -> Observed:
        if self.inspect is None:
            return Observed("unknown", "evidence-unavailable")
        evidence = self.inspect().get("outcome")
        if evidence not in ("pass", "available", "degraded"):
            return Observed("unknown", "evidence-unavailable")
        passed = evidence != "degraded"
        inspected = AVAILABLE if passed else Observed("degraded", "evidence-unavailable")
        if self.agent_status is None:
            return inspected
        try:
            status = self.agent_status()
        except LookupError:  # no status recorded: never available, never producer-failed
            return Observed("unknown", "evidence-unavailable") if passed else inspected
        findings = tuple(dict.fromkeys(status.get("findings") or ()))
        if findings:
            return Observed("degraded", findings[0], findings)
        return inspected


def platform_counts(ledger, environment: str, now: dt.datetime,
                    window: dt.timedelta) -> tuple[int, int]:
    """The backup agent's failed writes and disposals over (now − window, now], from the
    ledger's records (Step 58(b)); never through a receipt reader.

    - Writes: each settled `backup.create` request at its `updatedAt` (its own set part
      of it), each set no such request owns at its `takenAt`, and each lone ledger copy
      at its `takenAt`, failed when recorded without `verifiedAt`.
    - Disposals on the backup volume: sets, ledger copies and the volume's retained
      copies, at `disposedAt`, or failed at `lastDisposalFailedAt` while undisposed; a
      waiting rehearsal set's disposal waits for an in-person command and is left out.
    - A set and a request carry their environment; a ledger copy takes its set's; a lone
      copy and a retained copy belong to this machine, so to `environment`."""
    from docsuri_ops.cutover.disposal import waiting_rehearsal_sets

    from .retained_copies import CLOSED, VOLUME_KINDS

    start = now - window

    def inside(value) -> bool:
        moment = _moment(value)
        return moment is not None and start < moment <= now

    creates = {record["recoveryRequestId"]: record
               for record in ledger.records("recovery-request")
               if record.get("operation") == "backup.create"}
    sets = ledger.records("backup-set")
    set_environment = {record["backupId"]: record.get("environment") for record in sets}
    copies = ledger.records("ledger-copy")
    outcomes: list[bool] = []
    for request_id, request in creates.items():
        if (request.get("environment") == environment
                and request.get("state") in ("succeeded", "failed")
                and inside(request.get("updatedAt"))):
            own_failed = any(record.get("recoveryRequestId") == request_id
                             and record.get("integrity") == "failed" for record in sets)
            outcomes.append(request["state"] == "failed" or own_failed)
    for record in sets:
        if (record.get("environment") == environment
                and record.get("recoveryRequestId") not in creates
                and inside(record.get("takenAt"))):
            outcomes.append(record.get("integrity") == "failed")
    for copy in copies:
        if "backupId" not in copy and inside(copy.get("takenAt")):
            outcomes.append("verifiedAt" not in copy)
    waiting = {record["backupId"] for record in waiting_rehearsal_sets(ledger)}
    disposable = [record for record in sets
                  if record.get("environment") == environment
                  and record["backupId"] not in waiting]
    disposable += [
        copy for copy in copies
        if (set_environment.get(copy["backupId"]) if "backupId" in copy else environment)
        == environment
    ]
    disposable += [record for record in ledger.records("retained-copy")
                   if record.get("kind") in VOLUME_KINDS]
    # A failed disposal counts only for a record still open: retired with its volume or
    # returned to service closes it as disposal does (retained_copies.CLOSED).
    for record in disposable:
        if record.get("disposedAt"):
            if inside(record["disposedAt"]):
                outcomes.append(False)
        elif (not any(record.get(name) for name in CLOSED)
              and inside(record.get("lastDisposalFailedAt"))):
            outcomes.append(True)
    return sum(outcomes), len(outcomes)


class IsolationProducer(Producer):
    """The newest result of the root isolation check (BR6.12, observability-design § 8).
    Its time is the check's own, so an old result derives as stale."""

    def __init__(self, folder: Path):
        super().__init__("platform.isolation")
        self.folder = folder

    def observe(self, now: dt.datetime) -> Observed:
        try:
            candidates = sorted(
                path for path in self.folder.iterdir()
                if path.suffix == ".json" and path.is_file() and not path.is_symlink()
            )
        except FileNotFoundError:
            candidates = []
        if not candidates:
            return Observed("unknown", "evidence-unavailable")
        value = json.loads(candidates[-1].read_bytes()[:65536])
        checked = dt.datetime.fromisoformat(str(value["checkedAt"]).replace("Z", "+00:00"))
        if value.get("passed") is True and all(item.get("passed") for item in value["items"]):
            return Observed("available", observed_at=checked)
        failed = tuple(
            f"isolation-{item['item']}" for item in value["items"] if not item.get("passed")
        )
        return Observed("unavailable", "runtime-isolation-lapsed", failed, observed_at=checked)


# Where the public address is routed in each cutover state (the CutoverRecord machine).
EXPECTED_ROUTE = {
    "preparing": "v1-web", "rehearsing": "v1-web", "ready-to-switch": "v1-web",
    "switching": "maintenance", "switched": "v2-host", "settled": "v2-host",
    "aborting": "v1-web", "rolling-back": "v1-web", "rolled-back": "v1-web",
}


class CutoverProducer(Producer):
    """The CutoverRecord against PlatformControl's routing and service evidence."""

    def __init__(self, ledger, routing: Callable[[], dict] | None, *,
                 availability: Path | None = None):
        super().__init__("operations.cutover")
        self.ledger, self.routing = ledger, routing
        # Step 58(e) (L1-30): the heartbeat's availability record, for its failed probes.
        self.availability = availability

    def observe(self, now: dt.datetime) -> Observed:
        outcome = self._outcome()
        read = None if self.availability is None else (
            lambda: heartbeat_counts(self.availability, now))
        return with_counts(outcome, read_counts(self.capability, read))

    def _outcome(self) -> Observed:
        records = self.ledger.records("cutover-record")
        if not records:
            return AVAILABLE  # nothing moves between versions yet
        if self.routing is None:
            return Observed("unknown", "evidence-unavailable")
        evidence = self.routing()
        if int(evidence.get("unknownEffects", 0)):
            return Observed("unavailable", "cutover-effect-unknown")
        state = records[-1]["state"]
        if evidence.get("route") != EXPECTED_ROUTE[state]:
            return Observed("unavailable", "cutover-route-differs")
        return AVAILABLE


# The tunnel's own failures: the public path failed while the host answered (L1-30).
TUNNEL_REASONS = frozenset({"public-unreachable", "public-timeout"})


def heartbeat_counts(folder: Path, now: dt.datetime) -> tuple[int, int]:
    """The heartbeat slots recorded in (now − 24 h, now], across the current and previous
    Seoul month files, the first line per slot kept: the tunnel's failed probes over
    every recorded slot."""
    from docsuri_ops.standing.availability import AvailabilityRecord, month_of
    from docsuri_ops.standing.lanes import SEOUL

    local = now.astimezone(SEOUL)
    first = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    months = (month_of(now), month_of(first - dt.timedelta(days=1)))
    record, start = AvailabilityRecord(folder), now - COUNT_WINDOW
    slots: dict[str, dict] = {}
    for month in reversed(months):  # older month first; the first line per slot kept
        for line in record.lines(month):
            slots.setdefault(line["slot"], line)
    inside = [line for slot, line in slots.items() if start < _moment(slot) <= now]
    return sum(1 for line in inside if line["reason"] in TUNNEL_REASONS), len(inside)


PROVIDERS = {
    "provider.google": ("google", False), "provider.orcid": ("orcid", False),
    "provider.resend": ("resend", True), "provider.notion": ("notion", True),
}


class ProviderProducer(Producer):
    """Reachability, allowance and hold: a held outward provider is degraded with
    first-effect-pending, a held sign-in provider with sign-in-unverified (BR3.11).

    - `probe` (Step 56(a), L1-11): the production profile's uncredentialed check, read
      first; a failed probe is unavailable `provider-unreachable` at once. The adapter's
      passive `reachable` stays the second input.
    - `counts` (Step 56(d), L1-12): a reader of the provider's 24-hour `(errors, total)`,
      read only once the outcome is settled and carried on every outcome. A read that
      raises is logged (`counts.unread`, `state` the capability) and counts 0 of 0, so a
      count never changes an outcome; without a reader every outcome counts 0 of 0."""

    def __init__(self, capability: str, ledger, *, allowance=None,
                 reachable: Callable[[], bool] | None = None,
                 probe: Callable[[], bool] | None = None,
                 counts: Callable[[], tuple[int, int]] | None = None):
        super().__init__(capability)
        self.ledger, self.allowance, self.reachable = ledger, allowance, reachable
        self.probe, self.counts = probe, counts
        self.provider, self.outward = PROVIDERS[capability]

    def observe(self, now: dt.datetime) -> Observed:
        outcome = self._outcome()
        errors, total = self._read_counts()
        return dataclasses.replace(outcome, error_count=errors, total_count=total)

    def _read_counts(self) -> tuple[int, int]:
        if self.counts is None:
            return 0, 0
        try:
            errors, total = self.counts()
            return int(errors), int(total)
        except Exception:  # noqa: BLE001 - a count never changes an outcome
            from backend.log_events import current

            current().event("operations", "counts.unread", "warning", state=self.capability)
            return 0, 0

    def _outcome(self) -> Observed:
        if self.probe is not None and not self.probe():
            return Observed("unavailable", "provider-unreachable")
        if self.reachable is not None and not self.reachable():
            return Observed("unavailable", "provider-unreachable")
        activation = self.ledger.get("provider-activation", self.provider)
        if activation is not None and activation["state"] == "held":
            reason = "first-effect-pending" if self.outward else "sign-in-unverified"
            return Observed("degraded", reason, (reason,))
        if activation is not None and activation["state"] == "unavailable":
            return Observed("unavailable", "provider-unreachable")
        # At either limit (the day's for digests, or the month's) the provider is
        # degraded: digests wait for the reset (security-design § 13).
        if self.allowance is not None and self.allowance.exhausted("digest"):
            return Observed("degraded", "allowance-exhausted", ("allowance-exhausted",))
        return AVAILABLE


class ModelsProducer(Producer):
    """Each pinned model's digest from `/api/tags` against its pin; the search model is
    re-pinned with `keep_alive: -1` every re-pin interval (BR6.11, performance-design
    § 3.3)."""

    MODEL_LANES = ("research", "assistance")

    def __init__(self, source, policy, *, pins: Iterable = MODEL_EVIDENCE, lane_counts=None):
        super().__init__("provider.models")
        self.source, self.policy = source, policy
        self.pins = {model: digest for model, _, digest in pins}
        self._repinned: dt.datetime | None = None
        # Step 58(d): the research and assistance lanes' failed model jobs over 24 hours.
        self.lane_counts = lane_counts

    def observe(self, now: dt.datetime) -> Observed:
        outcome = self._outcome(now)
        read = None if self.lane_counts is None else (
            lambda: lane_sum(self.lane_counts.read(now, lanes=self.MODEL_LANES)))
        return with_counts(outcome, read_counts(self.capability, read))

    def _outcome(self, now: dt.datetime) -> Observed:
        if self.source is None:
            return Observed("unknown", "evidence-unavailable")
        try:
            tags = {item["name"]: item for item in self.source.tags()}
        except Exception:  # noqa: BLE001 - an unreachable runtime is its own outcome
            return Observed("unavailable", "runtime-unreachable")
        for model, digest in self.pins.items():
            tag = tags.get(model)
            if tag is None or tag.get("digest") != digest or tag.get("remote_host"):
                return Observed("unavailable", "model-evidence-mismatch")
        if (
            self._repinned is None
            or (now - self._repinned).total_seconds() >= self.policy.search_model_repin_seconds
        ):
            try:
                self.source.repin(SEARCH_MODEL, keep_alive=self.policy.search_model_keep_alive)
                self._repinned = now
            except Exception:  # noqa: BLE001 - a failed re-pin is retried next interval
                return Observed("unavailable", "runtime-unreachable")
        return AVAILABLE


class OllamaTags:
    """The shared model runtime on its loopback address, for the production profile.

    Each call runs through `u8_provider_probes.run_bounded` under its own whole deadline,
    with an httpx timeout of the same length (Step 56(b)): `tags()` under `PROBE_SECONDS`
    (5.0 s), `repin()` under `REPIN_SECONDS` (10.0 s), which covers the search model's
    measured first load of 1.7 to 4.9 s. A call past its deadline raises, so
    `ModelsProducer` reads unavailable `runtime-unreachable` at once. The clock and the
    waiter default to production's."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434", *, transport=None,
                 clock: Callable[[], float] | None = None, waiter=None):
        self.base_url, self.transport = base_url, transport
        self.clock, self.waiter = clock, waiter

    def _client(self, seconds: float):
        import httpx

        from backend.modules.summarization import model_runtime

        # The shared runtime's one network transport, read as a module attribute at call
        # time, so the test-wide guard replaces it as it does the runtime's own client.
        transport = self.transport if self.transport is not None else (
            model_runtime.network_transport())
        return httpx.Client(base_url=self.base_url, timeout=seconds, transport=transport,
                            trust_env=False)

    def _bounded(self, seconds: float, work: Callable):
        from backend.u8_provider_probes import run_bounded

        def call(client):
            with client:
                return work(client)

        return run_bounded(lambda: self._client(seconds), call, seconds=seconds,
                           clock=self.clock, waiter=self.waiter)

    def tags(self) -> list[dict]:
        from backend.u8_provider_probes import PROBE_SECONDS

        def read(client) -> list[dict]:
            response = client.get("/api/tags")
            response.raise_for_status()
            return list(response.json()["models"])

        return self._bounded(PROBE_SECONDS, read)

    def repin(self, model: str, *, keep_alive: int) -> None:
        from backend.u8_provider_probes import REPIN_SECONDS

        def post(client) -> None:
            client.post("/api/embed", json={"model": model, "input": "",
                                            "keep_alive": keep_alive}).raise_for_status()

        self._bounded(REPIN_SECONDS, post)


class HostErrorRateProducer(Producer):
    """The host's own 5xx rate over 24 hours, from its latency summaries
    (observability-design § 6; Step 58(c), L1-47): the route class with the highest
    share; `public.static` stays available while the host serves."""

    def __init__(self, folder: Path):
        super().__init__("public.static")
        self.folder = folder

    def observe(self, now: dt.datetime) -> Observed:
        return with_counts(AVAILABLE, read_counts(self.capability,
                                                  lambda: host_error_rate(self.folder, now)))


def host_error_rate(folder: Path, now: dt.datetime) -> tuple[int, int]:
    """The latency lines of `now`'s UTC day file and the day before, whose window started
    in (now − 24 h, now], summed per route class: the class with the highest share among
    those with a count above 0, equal shares going to the larger count; 0 of 0 when every
    count is 0 or no file is there. A linked day file is not read, and a line that is not
    a whole latency line (a write cut short) is skipped, as the dashboard's reader skips
    it; an unreadable file still raises, which `read_counts` reads as 0 of 0."""
    utc = now.astimezone(dt.UTC)
    start = now - COUNT_WINDOW
    sums: dict[str, list[int]] = {}
    for day in (utc - dt.timedelta(days=1), utc):
        path = folder / f"{day:%Y-%m-%d}.jsonl"
        if not path.is_file() or path.is_symlink():
            continue
        for raw in path.read_text().splitlines():
            line = _host_line(raw)
            if line is None or not start < line[0] <= now:
                continue
            counted = sums.setdefault(line[1], [0, 0])
            counted[0] += line[2]
            counted[1] += line[3]
    best = (0, 0)
    for errors, count in sums.values():
        if count <= 0:
            continue
        # A higher share (errors / count, compared without division), then a larger count.
        if best[1] == 0 or (errors * best[1], count) > (best[0] * count, best[1]):
            best = (errors, count)
    return best


def _host_line(raw: str) -> tuple[dt.datetime, str, int, int] | None:
    """One latency line's window, class, 5xx count and count; None for a line that is not
    a whole latency line."""
    try:
        line = json.loads(raw)
        window = _moment(line["window"])
        errors, count = line["errors5xx"], line["count"]
        route_class = line["class"]
    except (ValueError, TypeError, KeyError):
        return None
    if (window is None or window.tzinfo is None or not isinstance(route_class, str)
            or type(errors) is not int or type(count) is not int
            or not 0 <= errors <= count):
        return None
    return window, route_class, errors, count


@dataclass
class ProducerSchedule:
    """Runs each producer once at start, then whenever its renewal interval has passed
    since its last observation (BR3.3), on the injected clock or on elapsed real time.

    Observations are stamped on the one injected clock. Renewal is also paced on the
    monotonic source, so a clock that stands still (the composed realm's fixture clock
    held ahead of real time) or steps backward never stops renewals being written (your
    decision of 2026-11-13, "Renew on real time too").

    `ObservationStore.latest` breaks a tie on `observed_at` by revision, and
    `Observations` seeds each capability's revisions from the newest stored one before
    its first write in a process, so a renewal stamped at the same held instant replaces
    the row readiness, the dashboard and the incidents read, after a process restart as
    well. Limit: a renewal stamped earlier, after a backward step, does not. Readiness
    ages the row it reads at no less than 0 s."""

    producers: list[Producer]
    observations: Observations
    policy: object
    clock: Callable[[], dt.datetime]
    monotonic: Callable[[], float] = time.monotonic
    last: dict[str, dt.datetime] = field(default_factory=dict)
    stamps: dict[str, float] = field(default_factory=dict)
    refused: int = 0

    def interval(self, producer: Producer) -> int:
        renewal, _, _ = timing(CAPABILITY_BY_ID[producer.capability], self.policy)
        return renewal or self.policy.required_renewal_seconds

    def due(self, now: dt.datetime, moment: float | None = None) -> list[Producer]:
        moment = self.monotonic() if moment is None else moment
        return [producer for producer in self.producers if self._due(producer, now, moment)]

    def _due(self, producer: Producer, now: dt.datetime, moment: float) -> bool:
        capability = producer.capability
        if capability not in self.last:
            return True
        interval = self.interval(producer)
        if (now - self.last[capability]).total_seconds() >= interval:
            return True
        stamp = self.stamps.get(capability)
        return stamp is not None and moment - stamp >= interval

    def run_due(self, now: dt.datetime | None = None) -> list[str]:
        now = now or self.clock()
        moment = self.monotonic()
        observed = []
        for producer in self.due(now, moment):
            try:
                result = producer.observe(now)
            except Exception:  # noqa: BLE001 - a producer that cannot observe says so
                result = Observed("unknown", "producer-failed")
            try:
                row = self.observations.make(
                    producer.capability, producer.producer, result.outcome,
                    observed_at=result.observed_at or now, reason=result.reason,
                    limitations=result.limitations, error_count=result.error_count,
                    total_count=result.total_count,
                )
            except ObservationRefused:
                self.refused += 1
                continue
            finally:
                self.last[producer.capability] = now
                self.stamps[producer.capability] = moment
            self.observations.record(producer.producer, [row])
            observed.append(producer.capability)
        return observed

    async def run(self, stopping: asyncio.Event, *, tick: float = 1.0) -> None:
        while not stopping.is_set():
            await asyncio.to_thread(self.run_due)
            try:
                await asyncio.wait_for(stopping.wait(), tick)
            except TimeoutError:
                pass


def owner_probes(transactions, active: Callable[[str], bool]) -> list[Producer]:
    """The owners' probes for every capability whose contribution is active."""
    pairs = (
        ("account.entry", "accounts"), ("account.controls", "accounts"),
        ("library.saved-work", "library"), ("personalization.settings", "personalization"),
        ("usage.wallet", "usage"), ("corpus.content", "corpus"),
        ("discovery.search", "discovery"), ("research", "research"), ("novelty", "research"),
    )
    return [OwnerProbe(cap, owner, transactions) for cap, owner in pairs if active(cap)]


def isolation_folder(profile, arrangement=None) -> Path:
    """The isolation evidence folder: the arrangement's in production (the composition's
    one arrangement value, U8 plan Step 11), the run root's stand-in in the composed
    realm."""
    if getattr(profile, "is_production", False):
        if arrangement is None:
            from docsuri_ops.arrangement.paths import ArrangementPaths

            arrangement = ArrangementPaths()
        return arrangement.isolation_evidence
    return profile.root / "evidence" / "isolation"


def disk_path(profile) -> Path:
    return Path(os.fspath(profile.root))
