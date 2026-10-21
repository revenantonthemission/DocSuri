"""Housekeeping units of the export store, run by the worker pass on bounded batches.

- D4: an approved, unconsumed approval whose approving session ended is invalidated
  (authority-revoked) and trimmed in the same transaction.
- NFR4.9: while the session is current, an approval whose source U4 definitely no
  longer exports is invalidated (source-changed) and trimmed in its own transaction;
  the worker asks U4 outside any transaction, between the two units here.
- Decision "Rendered copies" (BR2.6): every preview revision that can no longer lead
  to a write loses its tree and text; its summary stays.
- NFR1.5: unapproved previews are purged after the retention period; R-02: stale
  pending reservations are swept by compare-and-set on their observed holder.

Approval batches walk a keyset (`after`) so approvals whose sessions stay current
cannot starve newer ones; the worker passes the returned `resumeAfter` to its next
pass and starts over from the oldest when it is None.
"""

import datetime as dt
from uuid import UUID

import psycopg

from .store_support import (
    APPROVAL_COLUMNS,
    INVALIDATION_REASONS,
    invalid,
    require_now,
    require_uuid,
    session_current,
    trim_revision,
)

_OPEN_APPROVALS = (
    f"SELECT {', '.join('a.' + c for c in APPROVAL_COLUMNS.split(','))},"
    "p.artifact_id,p.destination_id,r.source_revision,r.source_content_hash,"
    "r.source_eligibility_revision FROM export.approval a "
    "JOIN export.preview_revision r ON r.preview_id=a.preview_id "
    "AND r.revision=a.preview_revision JOIN export.preview_pair p ON p.preview_id=a.preview_id "
    "WHERE a.state='approved' AND NOT EXISTS (SELECT 1 FROM export.effect e "
    "WHERE e.approval_id=a.id) AND (%s::timestamptz IS NULL OR "
    "(a.approved_at,a.id)>(%s::timestamptz,%s::uuid)) "
    "ORDER BY a.approved_at,a.id LIMIT %s FOR UPDATE OF a SKIP LOCKED"
)
# A revision that can no longer lead to a write: never approved and superseded, or
# approved and ended (cancelled or invalidated before binding, or bound to a settled
# effect). An approved, unconsumed approval keeps its tree; so does the current
# never-approved revision until the retention purge.
_TRIMMABLE = (
    "WITH candidates AS (SELECT r.preview_id,r.revision FROM export.preview_revision r "
    "JOIN export.preview_pair p ON p.preview_id=r.preview_id "
    "LEFT JOIN export.approval a ON a.preview_id=r.preview_id AND a.preview_revision=r.revision "
    "LEFT JOIN export.effect e ON e.approval_id=a.id WHERE r.trimmed_at IS NULL AND ("
    "(a.id IS NULL AND r.revision<p.current_revision) "
    "OR (a.state IN ('cancelled','invalidated') AND e.id IS NULL) "
    "OR (e.state IN ('succeeded','failed','cancelled','invalidated'))) "
    "ORDER BY r.prepared_at,r.preview_id,r.revision LIMIT %s FOR UPDATE OF r SKIP LOCKED) "
    "UPDATE export.preview_revision r SET rendered_blocks=NULL,rendered_text=NULL,trimmed_at=%s "
    "FROM candidates c WHERE r.preview_id=c.preview_id AND r.revision=c.revision "
    "RETURNING r.preview_id,r.revision"
)


def _resume_after(rows, limit: int):
    if len(rows) < limit:
        return None
    return (rows[-1]["approved_at"], rows[-1]["id"])


def _check_after(after):
    if after is None:
        return None, None
    if (
        not isinstance(after, tuple)
        or len(after) != 2
        or not isinstance(after[0], dt.datetime)
        or not isinstance(after[1], UUID)
    ):
        invalid("after")
    return after


def _invalidate_and_trim(conn, approval, reason: str, now: dt.datetime) -> bool:
    moved = conn.execute(
        "UPDATE export.approval SET state='invalidated',invalidation_reason=%s "
        "WHERE id=%s AND state='approved' AND NOT EXISTS "
        "(SELECT 1 FROM export.effect e WHERE e.approval_id=export.approval.id)",
        (reason, approval["id"]),
    ).rowcount
    if moved != 1:
        return False
    trim_revision(conn, approval["preview_id"], approval["preview_revision"], now)
    return True


class HousekeepingUnits:
    def invalidate_ended_sessions(self, now: dt.datetime, *, after=None) -> dict:
        """D4: check each open approval's approving session with AccountAccess's guard.
        A definite "not current" invalidates it (authority-revoked) and trims it in this
        transaction; a check that could not complete leaves it approved."""
        require_now(now)
        after_at, after_id = _check_after(after)
        limit = self.policy.housekeeping_batch

        def sweep(conn):
            rows = conn.execute(_OPEN_APPROVALS, (after_at, after_at, after_id, limit)).fetchall()
            invalidated, unchecked = [], 0
            for row in rows:
                try:
                    current = session_current(conn, row["account_id"], row["approving_session"])
                except psycopg.Error:
                    unchecked += 1
                    continue
                if not current and _invalidate_and_trim(conn, row, "authority-revoked", now):
                    invalidated.append(row["id"])
            return {
                "checked": len(rows) - unchecked,
                "unchecked": unchecked,
                "invalidated": invalidated,
                "resumeAfter": _resume_after(rows, limit),
            }

        return self.system(sweep)

    def approvals_for_source_check(self, *, after=None) -> dict:
        """NFR4.9: open approvals whose approving session is current, with the source
        facts the worker re-reads through U4 outside any transaction."""
        after_at, after_id = _check_after(after)
        limit = self.policy.housekeeping_batch

        def read(conn):
            rows = conn.execute(_OPEN_APPROVALS, (after_at, after_at, after_id, limit)).fetchall()
            current = []
            for row in rows:
                try:
                    if session_current(conn, row["account_id"], row["approving_session"]):
                        current.append(row)
                except psycopg.Error:
                    continue
            return {"approvals": current, "resumeAfter": _resume_after(rows, limit)}

        return self.system(read)

    def invalidate_open_approval(self, approval_id: UUID, reason: str, *, now: dt.datetime):
        """Invalidate one approved, unconsumed approval and trim its revision in this one
        transaction. False when it moved on (consumed, cancelled or already ended)."""
        require_uuid(approval_id, "approvalId")
        if reason not in INVALIDATION_REASONS:
            invalid("invalidationReason")
        require_now(now)

        def invalidate(conn):
            approval = conn.execute(
                "SELECT id,preview_id,preview_revision FROM export.approval WHERE id=%s FOR UPDATE",
                (approval_id,),
            ).fetchone()
            return approval is not None and _invalidate_and_trim(conn, approval, reason, now)

        return self.system(invalidate)

    def trim_settled_revisions(self, now: dt.datetime) -> int:
        """Trim, in one bounded batch, every revision that can no longer lead to a write."""
        require_now(now)
        return self.system(
            lambda conn: len(
                conn.execute(_TRIMMABLE, (self.policy.housekeeping_batch, now)).fetchall()
            )
        )

    def purge_unapproved_previews(self, now: dt.datetime) -> int:
        """Remove never-approved revisions past retention, and pairs left empty."""
        require_now(now)
        return self.system(
            lambda conn: conn.execute(
                "SELECT export.purge_unapproved_previews(%s,%s,%s) AS removed",
                (now, self.policy.preview_retention_days, self.policy.housekeeping_batch),
            ).fetchone()["removed"]
        )

    def sweep_stale_pending(self, now: dt.datetime) -> int:
        """Remove reservations still held by the observed holder past the takeover time."""
        require_now(now)
        return self.system(
            lambda conn: conn.execute(
                "SELECT export.sweep_stale_pending(%s,%s,%s) AS removed",
                (now, self.policy.pending_takeover_seconds, self.policy.housekeeping_batch),
            ).fetchone()["removed"]
        )
