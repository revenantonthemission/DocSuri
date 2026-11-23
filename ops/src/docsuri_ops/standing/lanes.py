"""The standing job's lanes (U8 plan Step 35; reliability-design § 11, R4).

One lane per task, each in a thread of its own, so no lane ever waits for another: a
25-minute backup or a 60-minute verification never delays the heartbeat. A lane's turn
comes when its schedule's latest instant has passed since the lane last started:

| Lane | Schedule (Asia/Seoul) |
|---|---|
| `heartbeat` | every 5-minute slot on the clock |
| `agent-status`, `isolation` | every 5 minutes |
| `backup` | 04:00 daily, then the disposal pass |
| `verification` | 05:00 on Sundays, and at the next 05:00 an erasure waits at |
| `housekeeping` | hourly |

A turn that comes while the lane still runs is skipped and recorded with the reason
`skipped-overlap`, never run twice at once; a skipped backup or verification also pings
its check's `/fail`. At start, the backup and verification lanes catch up a run that is
overdue (`catch_up`), rather than running at every restart. One clock decides every due
time: the scheduler's `tick(now)` is handed the same `now` the lanes run with.

A failing lane never stops the job (logical-components § 2, U8 plan Step 66(c)): a run
that raises, and a schedule (`latest`) or catch-up check (`catch_up`) that raises because
the ledger does not answer, records one failed turn (`lane-failed`) per scheduled turn,
and a checked lane (backup, verification) pings its `/fail` once for it; every other lane
goes on. A catch-up check that raised at start is asked again at each tick, launching
nothing, until it answers once; a schedule that raised at start counts the lane as
started at that turn's instant, so it waits for its next scheduled turn; one that raises
later leaves the lane as it was and is asked again at the next tick.
"""

from __future__ import annotations

import datetime as dt
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")
SLOT_SECONDS = 300
SKIPPED = "skipped-overlap"
FAILED = "lane-failed"
CHECKED_LANES = ("backup", "verification")


def every(seconds: int) -> Callable[[dt.datetime], dt.datetime]:
    """The latest instant on a fixed grid from the epoch (slots on the clock)."""
    if seconds <= 0:
        raise ValueError("a period must be positive")

    def latest(now: dt.datetime) -> dt.datetime:
        epoch = int(now.timestamp())
        return dt.datetime.fromtimestamp(epoch - epoch % seconds, dt.UTC)

    return latest


def slot_of(now: dt.datetime, seconds: int = SLOT_SECONDS) -> dt.datetime:
    """The 5-minute slot `now` falls in (:00, :05 and so on)."""
    return every(seconds)(now)


def daily_at(hour: int) -> Callable[[dt.datetime], dt.datetime]:
    """The latest `hour`:00 in Seoul at or before `now`."""

    def latest(now: dt.datetime) -> dt.datetime:
        local = now.astimezone(SEOUL)
        today = local.replace(hour=hour, minute=0, second=0, microsecond=0)
        return (today if today <= local else today - dt.timedelta(days=1)).astimezone(dt.UTC)

    return latest


def weekly_at(weekday: int, hour: int, *, also: Callable[[dt.datetime], bool] | None = None
              ) -> Callable[[dt.datetime], dt.datetime]:
    """The latest `hour`:00 in Seoul on `weekday` (Monday 0), or the latest `hour`:00 of
    any day when `also(that instant)` holds (an erasure waited at it, L1-42)."""
    daily = daily_at(hour)

    def latest(now: dt.datetime) -> dt.datetime:
        candidate = daily(now)
        if also is not None and also(candidate):
            return candidate
        local = candidate.astimezone(SEOUL)
        back = (local.weekday() - weekday) % 7
        return (local - dt.timedelta(days=back)).astimezone(dt.UTC)

    return latest


@dataclass
class Lane:
    """One task: `latest(now)` is its schedule, `work(now)` its run, and `catch_up(now)`
    whether a run is overdue at start (None: the lane simply waits for its next turn).
    `turn(now)` names the scheduled turn `now` belongs to without reading the ledger
    (None: the schedule itself); a failed turn is recorded once per turn."""

    name: str
    latest: Callable[[dt.datetime], dt.datetime]
    work: Callable[[dt.datetime], object]
    catch_up: Callable[[dt.datetime], bool] | None = None
    turn: Callable[[dt.datetime], dt.datetime] | None = None
    last_started: dt.datetime | None = None
    started_once: bool = False
    catch_up_pending: bool = False
    failed_turn: dt.datetime | None = None
    thread: threading.Thread | None = field(default=None, repr=False)

    def running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()


@dataclass
class Turn:
    lane: str
    at: dt.datetime
    outcome: str
    reason: str | None = None


class Lanes:
    """The scheduler: each tick starts every due lane in its own thread."""

    def __init__(self, lanes: list[Lane], *, record: Callable[[Turn], None] | None = None,
                 fail: Callable[[str], None] | None = None):
        names = [lane.name for lane in lanes]
        if len(names) != len(set(names)):
            raise ValueError("each task has one lane")
        self.lanes = {lane.name: lane for lane in lanes}
        self.record = record or (lambda turn: None)
        self.fail = fail or (lambda check: None)
        self.turns: list[Turn] = []
        self.failures: dict[str, str] = {}

    def _note(self, turn: Turn) -> None:
        self.turns.append(turn)
        self.turns = self.turns[-1000:]
        self.record(turn)

    # --- failed turns ---------------------------------------------------------------

    def _turn_of(self, lane: Lane, now: dt.datetime) -> dt.datetime:
        """The scheduled turn `now` belongs to, read without the ledger."""
        if lane.turn is not None:
            return lane.turn(now)
        try:
            return lane.latest(now)
        except Exception:  # noqa: BLE001 - a schedule that cannot answer: the instant
            return now

    def _ping_fail(self, lane: Lane) -> None:
        """A checked lane's `/fail`, which never raises into the tick thread (review fix,
        batch 4): a ping that cannot be sent is undelivered, and the lanes go on."""
        if lane.name not in CHECKED_LANES:
            return
        try:
            self.fail(lane.name)
        except Exception:  # noqa: BLE001 - a failing ping never stops the job
            pass

    def _failed(self, lane: Lane, now: dt.datetime, error: Exception) -> None:
        """One failed turn per scheduled turn, and a checked lane's `/fail` once for it."""
        self.failures[lane.name] = type(error).__name__
        turn = self._turn_of(lane, now)
        if lane.failed_turn == turn:
            return
        lane.failed_turn = turn
        self._note(Turn(lane.name, now, "failed", FAILED))
        self._ping_fail(lane)

    def _settle_start(self, lane: Lane, now: dt.datetime) -> str | None:
        """The start's decision for one lane: launch an overdue run, or count the lane as
        started at its latest instant (at its turn's instant when the schedule raises).
        A catch-up check that raises leaves the decision for the next tick."""
        try:
            due = lane.catch_up is not None and lane.catch_up(now)
        except Exception as error:  # noqa: BLE001 - asked again at the next tick
            lane.catch_up_pending = True
            self._failed(lane, now, error)
            return None
        lane.catch_up_pending = False
        if due:
            return self._launch(lane, now)
        try:
            lane.last_started = lane.latest(now)
        except Exception as error:  # noqa: BLE001 - started at this turn's instant
            lane.last_started = self._turn_of(lane, now)
            self._failed(lane, now, error)
        return None

    # --- the scheduler --------------------------------------------------------------

    def start(self, now: dt.datetime) -> list[str]:
        """The first tick: lanes with a run overdue catch up; every other lane counts as
        started at its latest instant, so it runs at its next one."""
        started = []
        for lane in self.lanes.values():
            lane.started_once = True
            launched = self._settle_start(lane, now)
            if launched is not None:
                started.append(launched)
        return started

    def tick(self, now: dt.datetime) -> list[str]:
        started = []
        for lane in self.lanes.values():
            if not lane.started_once:
                lane.started_once = True
                try:
                    lane.last_started = lane.latest(now)
                except Exception as error:  # noqa: BLE001 - started at this turn's instant
                    lane.last_started = self._turn_of(lane, now)
                    self._failed(lane, now, error)
                continue
            if lane.catch_up_pending:
                launched = self._settle_start(lane, now)
                if launched is not None:
                    started.append(launched)
                continue
            try:
                latest = lane.latest(now)
            except Exception as error:  # noqa: BLE001 - asked again at the next tick
                self._failed(lane, now, error)
                continue
            if lane.last_started is not None and lane.last_started >= latest:
                continue
            if lane.running():
                lane.last_started = latest  # this turn is spent, not queued
                self._note(Turn(lane.name, now, "skipped", SKIPPED))
                self._ping_fail(lane)
                continue
            started.append(self._launch(lane, now, latest))
        return started

    def _launch(self, lane: Lane, now: dt.datetime, latest: dt.datetime | None = None) -> str:
        if latest is None:
            try:
                latest = lane.latest(now)
            except Exception:  # noqa: BLE001 - an overdue run still launches
                latest = self._turn_of(lane, now)
        lane.last_started = max(latest, lane.last_started or latest)

        def run() -> None:
            try:
                outcome = lane.work(now)
            except Exception as error:  # noqa: BLE001 - a lane failure never stops the job
                self.failures[lane.name] = type(error).__name__
                self._note(Turn(lane.name, now, "failed", FAILED))
                self._ping_fail(lane)
                return
            reason = outcome if isinstance(outcome, str) else None
            self._note(Turn(lane.name, now, "ran", reason))

        lane.thread = threading.Thread(target=run, name=f"standing-{lane.name}", daemon=True)
        lane.thread.start()
        return lane.name

    def join(self, seconds: float = 5.0) -> None:
        for lane in self.lanes.values():
            if lane.thread is not None:
                lane.thread.join(seconds)
