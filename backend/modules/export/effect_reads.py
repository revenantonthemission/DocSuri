"""Read units of the export store: one effect, and the owner's export history (A2, A4).

Both derive `settlementOffered` from the effect, its latest attempt and check and the
caller's `now` (BR4.5), and carry the latest marker-found check's other marked pages
as possible duplicates (BR4.4). History is keyset-ordered by (approvedAt, approvalId),
newest first; `continuable` comes from AccountAccess's session guard, run in a
savepoint for each approved, unconsumed entry (BR3.7).
"""

import base64
import binascii
import datetime as dt
import json
from uuid import UUID

from .store_support import (
    APPROVAL_COLUMNS,
    CHECK_COLUMNS,
    EFFECT_COLUMNS,
    invalid,
    latest_check,
    not_found,
    require_now,
    require_uuid,
    session_current,
    settlement_offered,
)

_CURSOR_LIMIT = 512


def encode_cursor(approved_at: dt.datetime, approval_id: UUID) -> str:
    raw = json.dumps([approved_at.isoformat(), str(approval_id)], separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor) -> tuple[dt.datetime, UUID]:
    """The opaque cursor's keyset position; anything else is INVALID_ARGUMENT."""
    if not isinstance(cursor, str) or not 1 <= len(cursor) <= _CURSOR_LIMIT:
        invalid("cursor")
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        approved_at, approval_id = json.loads(raw)
        position = (dt.datetime.fromisoformat(approved_at), UUID(approval_id))
    except (binascii.Error, ValueError, TypeError, UnicodeDecodeError):
        invalid("cursor")
    if position[0].tzinfo is None:
        invalid("cursor")
    return position


def possible_duplicates(conn, effect_id: UUID) -> list:
    """The other marked pages of the latest marker-found check, bounded at ten."""
    row = conn.execute(
        f"SELECT {CHECK_COLUMNS} FROM export.reconciliation_check WHERE effect_id=%s "
        "AND result='marker-found' ORDER BY checked_at DESC,id DESC LIMIT 1",
        (effect_id,),
    ).fetchone()
    return list(row["other_marked_pages"]) if row else []


def effect_view(conn, effect, now: dt.datetime, policy) -> dict:
    return {
        "effect": effect,
        "latestCheck": latest_check(conn, effect["id"]),
        "possibleDuplicates": possible_duplicates(conn, effect["id"]),
        "settlementOffered": settlement_offered(conn, effect, now, policy),
    }


class EffectReadUnits:
    def read_effect(self, authority, effect_id: UUID, *, now: dt.datetime) -> dict:
        """The owner's effect with its derived settlement and duplicate facts."""
        require_uuid(effect_id, "effectId")
        require_now(now)

        def read(conn):
            effect = conn.execute(
                f"SELECT {EFFECT_COLUMNS} FROM export.effect WHERE id=%s AND account_id=%s",
                (effect_id, authority.account_id),
            ).fetchone()
            if effect is None:
                not_found()
            return effect_view(conn, effect, now, self.policy)

        return self.run(authority, read)

    def history(
        self, authority, *, limit: int = 20, cursor: str | None = None, now: dt.datetime
    ) -> dict:
        """One page of the owner's approvals, newest first, with their effects."""
        if type(limit) is not int or not 1 <= limit <= self.policy.history_page_max:
            invalid("limit")
        position = None if cursor is None else decode_cursor(cursor)
        require_now(now)

        def read(conn):
            after_at, after_id = position if position else (None, None)
            rows = conn.execute(
                f"SELECT {', '.join('a.' + c for c in APPROVAL_COLUMNS.split(','))},"
                "r.source_title,r.destination,r.prepared_at,e.id AS effect_id "
                "FROM export.approval a JOIN export.preview_revision r "
                "ON r.preview_id=a.preview_id AND r.revision=a.preview_revision "
                "LEFT JOIN export.effect e ON e.approval_id=a.id WHERE a.account_id=%s "
                "AND (%s::timestamptz IS NULL OR (a.approved_at,a.id)<(%s::timestamptz,%s::uuid)) "
                "ORDER BY a.approved_at DESC,a.id DESC LIMIT %s",
                (authority.account_id, after_at, after_at, after_id, limit + 1),
            ).fetchall()
            entries = [self._history_entry(conn, row, now) for row in rows[:limit]]
            last = rows[limit - 1] if len(rows) > limit else None
            next_cursor = encode_cursor(last["approved_at"], last["id"]) if last else None
            return {"entries": entries, "nextCursor": next_cursor}

        return self.run(authority, read)

    def _history_entry(self, conn, row, now: dt.datetime) -> dict:
        approval = {key: row[key] for key in APPROVAL_COLUMNS.split(",")}
        entry = {
            "approval": approval,
            "sourceTitle": row["source_title"],
            "destination": row["destination"],
            "preparedAt": row["prepared_at"],
            "effect": None,
            "continuable": False,
        }
        if row["effect_id"] is not None:
            effect = conn.execute(
                f"SELECT {EFFECT_COLUMNS} FROM export.effect WHERE id=%s", (row["effect_id"],)
            ).fetchone()
            entry["effect"] = effect_view(conn, effect, now, self.policy)
        elif approval["state"] == "approved":
            entry["continuable"] = session_current(
                conn, approval["account_id"], approval["approving_session"]
            )
        return entry
