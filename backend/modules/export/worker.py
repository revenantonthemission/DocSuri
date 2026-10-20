"""U6's step inside the shared worker pass, shaped like `TopicsWorker` (D9, §8.1).

`ExportWorker(inherited, export_pass)` runs the inherited bounded pass, then U6's pass
step. The pass step touches only the database, on bounded batches, and never calls
Notion; the export lane is the only background caller (D9). Each pass:

1. **Orphan sweep** (BR4.6): an attempt still outstanding past the orphan threshold
   turns its effect unknown and records the evidence gap.
2. **Housekeeping** (§10, BR2.6, BR3.4, NFR1.5, NFR4.9):
   - D4: an approval whose approving session ended is invalidated (authority-revoked)
     and trimmed in the same transaction;
   - while the session is current, an approval whose source U4 definitely reports
     absent, changed or not exportable is invalidated (source-changed) and trimmed in
     one transaction. U4 unreachable or policy unresolved, or a session check that could
     not complete, leaves it approved, to be checked again on the next pass;
   - every preview revision that can no longer lead to a write is trimmed;
   - unapproved previews are purged after the retention period;
   - stale pending reservations are swept.
3. **Hand-over**: when the lane is idle, the next due item in §8.1's order goes to it.
   A scan's `next_check_at` first moves past the scan budget plus one minute, so no
   second worker starts the same scan.

Approval batches walk a keyset; the step passes each batch's `resumeAfter` back on its
next pass and starts over from the oldest when it is None. A failing step does not stop
the others: the pass runs every step, then raises `ExportPassIncomplete` naming the
failed steps, so the shared loop counts the pass as failed. No exception object, token or
provider text is logged or kept.
"""

import logging

from backend.transactions import Authority
from backend.u6_policy import ExportPolicy

from .binding import check_source
from .lane import LaneItem

LOGGER = logging.getLogger("docsuri.export.worker")


class ExportPassIncomplete(RuntimeError):
    """One or more pass steps failed; holds only their fixed step names."""

    def __init__(self, steps: tuple[str, ...]):
        super().__init__("export pass steps failed: " + ",".join(steps))
        self.steps = steps


class ExportWorker:
    """One inherited bounded pass plus U6's database-only pass step."""

    def __init__(self, inherited, export_pass):
        self.inherited = inherited
        self.export_pass = export_pass

    def run_once(self, limit=1):
        result = self.inherited.run_once(limit=limit)
        self.export_pass.run_once()
        return result


class ExportPass:
    def __init__(self, repository, research, lane, *, policy: ExportPolicy, clock):
        if not isinstance(policy, ExportPolicy):
            raise TypeError("an ExportPolicy is required")
        self._repository = repository
        self._research = research
        self._lane = lane
        self._policy = policy
        self._clock = clock
        self._session_after = None
        self._source_after = None
        self._handed: set = set()

    def run_once(self) -> dict:
        """One pass; every due-time decision compares against this one `now`."""
        now = self._clock()
        result = {
            "orphans": 0,
            "sessionInvalidated": 0,
            "sessionUnchecked": 0,
            "sourceInvalidated": 0,
            "sourceUnchecked": 0,
            "trimmed": 0,
            "purged": 0,
            "pendingSwept": 0,
            "handedOver": None,
        }
        steps = (
            ("orphans", lambda: self._orphans(now, result)),
            ("sessions", lambda: self._sessions(now, result)),
            ("sources", lambda: self._sources(now, result)),
            ("trim", lambda: result.update(trimmed=self._repository.trim_settled_revisions(now))),
            (
                "purge",
                lambda: result.update(purged=self._repository.purge_unapproved_previews(now)),
            ),
            (
                "pending",
                lambda: result.update(pendingSwept=self._repository.sweep_stale_pending(now)),
            ),
            ("hand-over", lambda: result.update(handedOver=self._hand_over(now))),
        )
        failed = tuple(name for name, step in steps if not self._run_step(name, step))
        if failed:
            raise ExportPassIncomplete(failed)
        return result

    @staticmethod
    def _run_step(name: str, step) -> bool:
        failure = None
        try:
            step()
        except Exception as error:  # noqa: BLE001 - reduced to its class name below
            failure = type(error).__name__
        if failure is None:
            return True
        LOGGER.warning("export pass step %s failed (%s)", name, failure)
        return False

    # -- the steps --------------------------------------------------------------------------

    def _orphans(self, now, result: dict) -> None:
        result["orphans"] = len(self._repository.sweep_orphans(now))

    def _sessions(self, now, result: dict) -> None:
        """D4: one bounded batch of open approvals checked against AccountAccess."""
        swept = self._repository.invalidate_ended_sessions(now, after=self._session_after)
        self._session_after = swept["resumeAfter"]
        result["sessionInvalidated"] = len(swept["invalidated"])
        result["sessionUnchecked"] = swept["unchecked"]

    def _sources(self, now, result: dict) -> None:
        """NFR4.9: U4's export read for each open approval of a current session, outside
        any transaction; only a definite answer invalidates."""
        batch = self._repository.approvals_for_source_check(after=self._source_after)
        self._source_after = batch["resumeAfter"]
        for approval in batch["approvals"]:
            verdict = check_source(
                self._research,
                Authority(approval["account_id"], approval["approving_session"]),
                {
                    "artifactId": str(approval["artifact_id"]),
                    "revision": approval["source_revision"],
                    "contentHash": approval["source_content_hash"],
                },
                approval["source_eligibility_revision"],
            )
            if verdict is None:
                continue
            if not verdict.changed:
                result["sourceUnchecked"] += 1
                continue
            if self._repository.invalidate_open_approval(approval["id"], verdict.reason, now=now):
                result["sourceInvalidated"] += 1

    def _hand_over(self, now) -> str | None:
        """The next due item in §8.1's order, only while the lane is idle.

        An effect left waiting by a could-not-check keeps its revision and stays first in
        that order, so items already handed at their current revision go behind the
        batch's others until every due item has had its turn. This round-robin is a
        fairness hint held in memory only; the records stay the only state."""
        if not self._lane.idle:
            return None
        rows = self._repository.due_items(now, limit=self._policy.pass_batch)
        # Only items still due at the same revision keep their place behind the others.
        self._handed &= {(row["id"], row["revision"]) for row in rows}
        fresh = [row for row in rows if (row["id"], row["revision"]) not in self._handed]
        if not fresh:
            self._handed.clear()
            fresh = rows
        for row in fresh:
            revision = row["revision"]
            if row["kind"] == "scan":
                revision = self._repository.push_next_check(row["id"], revision, now=now)
                if revision is None:
                    continue
            item = LaneItem(row["kind"], row["id"], revision)
            if not self._lane.offer(item):
                return None
            self._handed.add((row["id"], row["revision"]))
            return item.kind
        return None
