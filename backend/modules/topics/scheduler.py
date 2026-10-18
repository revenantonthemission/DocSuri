"""Bounded digest passes: due-topic evaluation, preparation, send attempts and
the orphan sweep, one responsibility per bounded pass.

Every pass runs the same finite sequence: the restart sweep moves orphaned
`sending` runs to `unknown` (BR3.4), the reconciliation check resolves unknown
outcomes from send-log evidence (BR3.2), due topics are prepared idempotently
in the one stated zone (BR1.2/BR2.4) with consent-stopped queued work dropped
(BR4.2), and at most one send attempt starts per pass behind the checked
transition guards (BR3.1/BR4.1). Failed runs are never auto-resent (BR3.3):
the next scheduled window is the only automatic follow-up.
"""

import datetime as dt
from zoneinfo import ZoneInfo

from backend.u5_policy import SYNTHETIC_TOPICS

from .errors import TopicsError
from .repository import TopicsRepository

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class TopicsScheduler:
    def __init__(self, transactions, preparation, delivery, *, policy=SYNTHETIC_TOPICS):
        self.repository = TopicsRepository(transactions)
        self.preparation = preparation
        self.delivery = delivery
        self.policy = policy
        self.zone = ZoneInfo(policy.delivery_timezone)

    def run_once(self, limit=1):
        if type(limit) is not int or not 1 <= limit <= 10:
            raise ValueError("finite scheduler bound required")
        result = {
            "recovered": 0,
            "reconciled": 0,
            "prepared": 0,
            "sent": 0,
            "failed": 0,
            "unknown": 0,
        }
        self._sweep_orphans(result)
        self._reconcile(result)
        self._drop_consent_stopped(result)
        self._evaluate_due(result, limit)
        self._send_prepared(result)
        return result

    def _sweep_orphans(self, result):
        """Orphaned `sending` past the bound moves to `unknown` (BR3.4)."""
        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(
            seconds=self.policy.orphan_after_seconds
        )
        for orphan in self.repository.orphaned_sending(cutoff, self.policy.sweep_limit):
            if self.repository.retire_orphan(orphan["id"]) is not None:
                result["recovered"] += 1

    def _reconcile(self, result):
        """Send-log evidence reconciles unknown outcomes; silence never does (BR3.2)."""
        for row in self.repository.unknown_runs(self.policy.reconcile_batch):
            decision = self.delivery.reconcile_decision(row)
            if decision is None:
                continue
            if self.repository.reconcile_run(row["id"], decision) is not None:
                result["reconciled"] += 1

    def _now(self):
        """One stated zone for every boundary decision; tests pin this clock."""
        return dt.datetime.now(self.zone)

    def _due_window(self, topic):
        """The next chronological window, or None while the topic is not due (BR1.2).

        The window is the rolling bound the settings name: [today-(days-1), today]
        in the one stated zone. The watermark, not window tiling, prevents
        repeats (BR2.2), so a failed window's content stays re-deliverable by a
        later window while it remains inside that window's bounds (BR3.3).
        """
        now_local = self._now()
        today = now_local.date()
        scheduled = topic["delivery_time_local"]
        if topic["cadence"] == "weekly":
            if WEEKDAYS[now_local.weekday()] != topic["delivery_day"]:
                return None
        elif now_local.time() < scheduled:
            return None
        latest = self.repository.latest_window(topic["id"])
        if latest is not None and latest >= today:
            return None
        start = today - dt.timedelta(days=topic["content_window_days"] - 1)
        return start, today

    def _drop_consent_stopped(self, result):
        """Consent-stopped delivery drops queued work like an unsubscribe (BR4.2)."""
        for row in self.repository.consent_stopped_runs(self.policy.reconcile_batch):
            discarded = self.repository.discard_prepared_runs(row["topic_id"])
            result["recovered"] += len(discarded)

    def _evaluate_due(self, result, limit):
        due = self.repository.due_topics(self.policy.delivery_timezone, self.policy.page_size)
        for topic in due:
            if result["prepared"] >= limit:
                return
            recipient = self.repository.digest_recipient(topic["account_id"])
            if not recipient["granted"]:
                # Consent-stopped delivery behaves as unsubscribed until consent
                # is restored: queued work is dropped, nothing sends (BR4.2).
                self.repository.discard_prepared_runs(topic["id"])
                continue
            window = self._due_window(topic)
            if window is None:
                continue
            try:
                _, adopted = self.preparation.prepare(
                    topic["id"], window, topic["settings_revision"]
                )
            except TopicsError as error:
                # A revision change (BR1.3) or window-order refusal re-fires on
                # the next pass with fresh state; later topics keep their turn.
                if error.code in ("WINDOW_ORDER", "CONFLICT"):
                    continue
                raise
            if not adopted:
                result["prepared"] += 1

    def _send_prepared(self, result):
        attempted = 0
        for run in self.repository.prepared_runs(self.policy.sends_per_pass + 5):
            if attempted >= self.policy.sends_per_pass:
                return
            sending = self.repository.begin_send(run["id"], self.delivery.path_kind())
            if sending is None:
                # Blocked (unsubscribed, consent-stopped, paused, single-flight):
                # skipped without consuming the pass's send budget (BR3.1/4.1/4.2).
                continue
            attempted += 1
            terminal = self.delivery.attempt(sending, run)
            if terminal is not None:
                result[terminal["state"]] += 1
