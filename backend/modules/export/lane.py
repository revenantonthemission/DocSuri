"""The export lane: the only background caller of Notion (D9, security design §8.1).

One background thread per process, a one-item queue and a bulkhead of one: the worker
pass hands it a due item only while it is idle. For each item the lane runs the write
path of security design §8.2 or one reconciliation scan (§9.4):

1. **Pre-write check** (BR3.3) through the shared binding check, without a gate key: a
   definite change ends the effect (an accepted one invalidated, a resumed one failed);
   a could-not-check leaves it waiting from `waiting_since` and ends it as failed once
   the 24 h bound (or, for a resumed effect, the rate-limit window) has passed.
2. **Pace**: reserve the connection's pace slot and wait for it before claiming, so the
   attempt's deadline is spent only on the request.
3. **Claim**: one compare-and-set that records the attempt and its `deadline_at`.
4. **Write**: outside any transaction (D8), under the session's `asyncio.timeout`
   until `deadlineAt`; the adapter's create includes the read-back of a "saved but busy"
   answer under its own 60 s budget (§8.3).
5. **Record**: the classified outcome with the provider's request id and
   `creator_confirmed`; the store applies the connection facts (decision "Connection
   facts from outcomes"). A rate-limited answer whose stated wait would end after the
   window, or that used the last allowed attempt, fails at once (NFR4.5).

The lane keeps no state outside the database: a lane that stops leaves only records,
which the orphan sweep and the next due time recover. Each store call is its own short
transaction under the lane's own work budget, never the pass's. On shutdown the lane
stops taking items and waits for the one in hand, up to that item's deadline. Nothing
here logs an exception object, a token or provider text: only fixed categories.
"""

import asyncio
import datetime as dt
import logging
import queue
import threading
import time
from dataclasses import dataclass
from uuid import UUID

from backend.control_runtime import work_budget
from backend.u6_policy import ExportPolicy

from .binding import DEPENDENCY_UNAVAILABLE, POLICY_UNRESOLVED, BindingCheck, BoundFacts
from .classification import NOT_CONNECTED
from .lane_store import ClaimRefused, WriteOutcome
from .notion_adapter import ScanRequest, WriteRequest
from .notion_session import StoredConnection

LOGGER = logging.getLogger("docsuri.export.lane")
KINDS = ("resume", "execute", "scan")
# The lane's own work budget for each short store transaction (logical-components: at
# most 5 s per transaction), independent of the worker pass's 10 s budget.
UNIT_SECONDS = 5.0
# How often an idle lane looks at its queue and at the stop signal.
POLL_SECONDS = 0.05
# A write never starts with less than this left before `deadlineAt`.
MIN_WRITE_SECONDS = 0.001
# The source is a U4 export read of a novelty result (C09 A6 `ResultRef.mediaType`).
SOURCE_MEDIA_TYPE = "application/json"
RATE_LIMIT_SPENT = "rate-limit-budget-spent"
# Outcome categories recorded on the lane status record; categories, never text.
SKIPPED = "skipped"
WAITING = "waiting"
STOPPED = "stopped"
FAILED = "error"


@dataclass(frozen=True)
class LaneItem:
    """One due item as the pass hands it over: its kind, effect and expected revision."""

    kind: str
    effect_id: UUID
    revision: int

    def __post_init__(self):
        if self.kind not in KINDS:
            raise ValueError("unknown lane item kind")
        if not isinstance(self.effect_id, UUID):
            raise TypeError("an effect id is required")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("an effect revision is required")


def _unsent_outcome(category: str) -> WriteOutcome:
    """The attempt's record when no create request left because the stored token could
    not be opened after the claim. Like a content mismatch (§8.4), the attempt is
    recorded as refused before sending: a missing token is a connection that changed
    (disconnected or revoked meanwhile), any other is protection unavailable (BR8.3)."""
    reason = "connection-changed" if category == NOT_CONNECTED else POLICY_UNRESOLVED
    return WriteOutcome("refused", reason=reason)


class ExportLane:
    def __init__(
        self,
        repository,
        adapter,
        binding: BindingCheck,
        *,
        policy: ExportPolicy,
        clock,
    ):
        if not isinstance(policy, ExportPolicy):
            raise TypeError("an ExportPolicy is required")
        self._repository = repository
        self._adapter = adapter
        self._binding = binding
        self._policy = policy
        self._clock = clock
        self._path_kind = "synthetic" if policy.synthetic_only else "real"
        self._queue: queue.Queue = queue.Queue(maxsize=1)
        self._lock = threading.Lock()
        self._busy = False
        self._hand_deadline: float | None = None
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None

    # -- lifecycle -------------------------------------------------------------------

    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive() and not self._stopping.is_set()

    @property
    def idle(self) -> bool:
        """True while the lane runs and holds no item, queued or in hand."""
        with self._lock:
            return self.running and not self._busy

    def start(self) -> None:
        if self._thread is not None:
            raise ValueError("export lane already started")
        self._thread = threading.Thread(target=self._loop, name="docsuri-export-lane", daemon=True)
        self._thread.start()

    def stop(self, timeout: float | None = None) -> bool:
        """Stop taking items and wait for the one in hand, up to its deadline (or
        `timeout`). True when the lane thread has ended."""
        self._stopping.set()
        thread = self._thread
        if thread is None:
            return True
        if timeout is None:
            with self._lock:
                deadline = self._hand_deadline
            timeout = POLL_SECONDS * 2
            if deadline is not None:
                timeout += max(0.0, deadline - time.monotonic())
        thread.join(timeout)
        return not thread.is_alive()

    def item_seconds(self, kind: str) -> float:
        """The longest an item of this kind can take: its reads, pace waits, the write
        deadline and the read-back budget, plus one store unit for each record."""
        policy = self._policy
        if kind == "scan":
            return policy.scan_budget_seconds + 2 * UNIT_SECONDS
        return (
            2 * policy.page_read_budget_seconds
            + policy.write_deadline_seconds
            + policy.read_back_budget_seconds
            + 6 * UNIT_SECONDS
        )

    def offer(self, item: LaneItem) -> bool:
        """Hand the lane one item. False, and nothing queued, unless it runs and is idle."""
        if not isinstance(item, LaneItem):
            raise TypeError("a lane item is required")
        with self._lock:
            if not self.running or self._busy:
                return False
            self._busy = True
            self._hand_deadline = time.monotonic() + self.item_seconds(item.kind)
        self._queue.put_nowait(item)
        return True

    def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                item = self._queue.get(timeout=POLL_SECONDS)
            except queue.Empty:
                continue
            try:
                if not self._stopping.is_set():
                    self.run_item(item)
            finally:
                with self._lock:
                    self._busy = False
                    self._hand_deadline = None

    # -- one item -------------------------------------------------------------------

    def run_item(self, item: LaneItem) -> str:
        """Run one item to its record and return its outcome category. Never raises for
        the item's own failures: a store or adapter fault leaves the records as they
        are, for the orphan sweep and the next due time to recover."""
        outcome, failure = FAILED, None
        try:
            outcome = self._dispatch(item)
        except Exception as error:  # noqa: BLE001 - reduced to its class name below
            failure = type(error).__name__
        if failure is not None:
            LOGGER.warning("export lane %s item ended early (%s)", item.kind, failure)
        self._record_status(outcome)
        return outcome

    def _unit(self, call, *args, **kwargs):
        """One short store transaction under the lane's own work budget."""
        with work_budget(UNIT_SECONDS):
            return call(*args, **kwargs)

    def _record_status(self, outcome: str) -> None:
        failure = None
        try:
            self._unit(self._repository.record_lane_status, outcome)
        except Exception as error:  # noqa: BLE001 - the status record is best effort
            failure = type(error).__name__
        if failure is not None:
            LOGGER.warning("export lane status not recorded (%s)", failure)

    def _dispatch(self, item: LaneItem) -> str:
        binding = self._unit(self._repository.effect_binding, item.effect_id)
        if binding is None or binding["effect"]["revision"] != item.revision:
            return SKIPPED
        if item.kind == "scan":
            return self._scan(binding)
        return self._write(item, binding)

    # -- the write path (§8.2) ------------------------------------------------------------

    def _write(self, item: LaneItem, binding: dict) -> str:
        effect, attempts = binding["effect"], binding["attempts"]
        now = self._clock()
        resume = item.kind == "resume"
        if effect["state"] != ("executing" if resume else "accepted"):
            return SKIPPED
        if resume:
            if not self._resumable(effect, attempts, now):
                return SKIPPED
            if self._window_spent(effect, len(attempts), now):
                reason = DEPENDENCY_UNAVAILABLE if effect["waiting_since"] else RATE_LIMIT_SPENT
                return self._end(effect, reason, now)
        verdict = self._binding.check(self._facts(binding))
        if verdict.changed:
            return self._end(effect, verdict.reason, now)
        if not verdict.unchanged:
            return self._could_not_check(effect, verdict.reason, attempts, now, resume=resume)
        slot = self._unit(
            self._repository.reserve_pace_slot,
            binding["revision"]["connection_id"],
            remaining_seconds=float(self._policy.page_read_budget_seconds),
        )
        if slot is None or not slot.within_budget:
            return self._could_not_check(
                effect, DEPENDENCY_UNAVAILABLE, attempts, now, resume=resume
            )
        if self._stopping.wait(slot.wait_seconds):
            return STOPPED
        claimed = self._unit(
            self._repository.claim,
            effect["id"],
            effect["revision"],
            now=self._clock(),
            path_kind=self._path_kind,
        )
        if claimed is None:
            return SKIPPED
        if isinstance(claimed, ClaimRefused):
            if claimed.reason == "connection-unavailable":
                # BR1.6: an unopenable token is could-not-check, never a change.
                return self._could_not_check(
                    effect, POLICY_UNRESOLVED, attempts, now, resume=resume
                )
            return self._end(effect, claimed.reason, now)
        return self._send(binding, claimed)

    @staticmethod
    def _resumable(effect: dict, attempts: list, now: dt.datetime) -> bool:
        """A resumed effect waits after a rate-limited answer with nothing outstanding."""
        latest = attempts[-1] if attempts else None
        return (
            latest is not None
            and latest["ended_at"] is not None
            and latest["response_class"] == "rate-limited"
            and effect["next_attempt_at"] is not None
            and effect["next_attempt_at"] <= now
        )

    def _window_spent(self, effect: dict, attempt_count: int, now: dt.datetime) -> bool:
        """NFR4.5: at most `rate_limit_max_attempts` within the window that starts at the
        first rate-limited answer."""
        started = effect["rate_limit_started_at"]
        if started is None:
            return False
        window_end = started + dt.timedelta(seconds=self._policy.rate_limit_window_seconds)
        return attempt_count >= self._policy.rate_limit_max_attempts or now >= window_end

    @staticmethod
    def _facts(binding: dict) -> BoundFacts:
        approval, effect = binding["approval"], binding["effect"]
        return BoundFacts.of(
            binding["revision"],
            account_id=approval["account_id"],
            approving_session=approval["approving_session"],
            artifact_id=effect["artifact_id"],
            destination_id=effect["destination_id"],
        )

    def _end(self, effect: dict, reason: str, now: dt.datetime) -> str:
        ended = self._unit(
            self._repository.end_unwritten, effect["id"], effect["revision"], reason, now=now
        )
        return SKIPPED if ended is None else ended["state"]

    def _could_not_check(
        self, effect: dict, reason: str, attempts: list, now: dt.datetime, *, resume: bool
    ) -> str:
        """BR3.3: nothing is written; the effect waits from its first could-not-check and
        is checked again on later passes. An accepted effect fails with the reason once
        the 24 h bound passes; a resumed one fails as dependency-unavailable once its
        rate-limit window is spent (NFR4.5)."""
        waiting = self._unit(
            self._repository.mark_waiting, effect["id"], effect["revision"], now=now
        )
        if waiting is None:
            return SKIPPED
        if resume:
            if self._window_spent(waiting, len(attempts), now):
                return self._end(waiting, DEPENDENCY_UNAVAILABLE, now)
            return WAITING
        bound = dt.timedelta(seconds=self._policy.could_not_check_wait_seconds)
        if waiting["waiting_since"] + bound <= now:
            return self._end(waiting, reason, now)
        return WAITING

    def _send(self, binding: dict, claimed) -> str:
        effect, attempt = claimed.effect, claimed.attempt
        revision = binding["revision"]
        connection_id = revision["connection_id"]
        request = WriteRequest(
            effect_id=effect["id"],
            approval_id=effect["approval_id"],
            connection_id=connection_id,
            destination_id=effect["destination_id"],
            artifact={
                "resultId": str(effect["artifact_id"]),
                "revision": revision["source_revision"],
                "contentHash": revision["source_content_hash"],
                "mediaType": SOURCE_MEDIA_TYPE,
            },
            preview_hash=effect["binding_hash"],
            writer_identity=attempt["writer_identity"],
        )
        remaining = (attempt["deadline_at"] - self._clock()).total_seconds()
        result = asyncio.run(
            self._adapter.create_page(
                StoredConnection(effect["account_id"], connection_id),
                request,
                deadline_seconds=max(MIN_WRITE_SECONDS, remaining),
            )
        )
        outcome = result.outcome or _unsent_outcome(result.category)
        now = self._clock()
        recorded = self._unit(
            self._repository.record_write_outcome,
            effect["id"],
            attempt["id"],
            effect["revision"],
            outcome,
            now=now,
        )
        if recorded is None:
            return SKIPPED
        if outcome.response_class != "rate-limited":
            return recorded["state"]
        if self._wait_past_window(recorded, attempt["attempt_number"], outcome.retry_at):
            return self._end(recorded, RATE_LIMIT_SPENT, now)
        return "rate-limited"

    def _wait_past_window(self, effect: dict, attempt_number: int, retry_at) -> bool:
        """NFR4.5: the last allowed attempt was rate-limited, or Notion's stated wait
        would end after the window; either fails the effect at once."""
        window_end = effect["rate_limit_started_at"] + dt.timedelta(
            seconds=self._policy.rate_limit_window_seconds
        )
        return attempt_number >= self._policy.rate_limit_max_attempts or retry_at > window_end

    # -- reconciliation (§9.4) ------------------------------------------------------------

    def _scan(self, binding: dict) -> str:
        """One scan for the effect's marker by the writer identities recorded on its
        attempts (not the current connection's), recorded by compare-and-set (BR4.4)."""
        effect = binding["effect"]
        if effect["state"] != "unknown" or binding["firstAttemptAt"] is None:
            return SKIPPED
        request = ScanRequest(
            effect_id=effect["id"],
            destination_id=effect["destination_id"],
            marker=effect["marker"],
            writer_identities=frozenset(binding["writerIdentities"]),
            first_attempt_started_at=binding["firstAttemptAt"],
        )
        target = StoredConnection(effect["account_id"], binding["revision"]["connection_id"])
        outcome = asyncio.run(self._adapter.scan(target, request))
        recorded = self._unit(
            self._repository.record_check,
            effect["id"],
            effect["revision"],
            outcome.check,
            now=self._clock(),
        )
        return SKIPPED if recorded is None else f"scan-{outcome.result}"
