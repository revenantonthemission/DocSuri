"""AccountAccess's lifecycle service in the two complete realms (U8 plan Step 17; BR2.5).

`CompleteLifecycleService` is U2's `ControlLifecycleService` with one part (the
person's decisions of 2026-10-22 and 2026-10-24): a part retained by policy (the
backups part of an erase among them) may carry the date it is gone. The date is stored
with the scope's first evidence, in U2's `_acknowledge_in` step, so a replay never
changes it, and the status reports it as `retainedUntil`. The column exists only on
U8's composed chain (`u8_lifecycle_retention.sql`).
"""

from __future__ import annotations

import datetime as dt
from uuid import UUID

from backend.modules.accounts.services.control_lifecycle import (
    RETAINED_BY_POLICY,
    ControlLifecycleService,
)
from docsuri_shared.workspace import wire


class CompleteLifecycleService(ControlLifecycleService):
    def __init__(self, entry, manifest: tuple[tuple[str, str], ...], *, revision: str):
        if not callable(getattr(ControlLifecycleService, "_acknowledge_in", None)):
            raise TypeError("U2's ControlLifecycleService lacks its acknowledgement step")
        super().__init__(entry, manifest, revision=revision)

    def acknowledge(
        self, ticket: dict, *, evidence: UUID | None, reason: str,
        retained_until: dt.datetime | None = None,
    ) -> dict:
        """Record one scope's evidence; `retained_until`, the date a part retained by
        policy is gone, is stored beside complete evidence with a retention reason key."""
        if retained_until is None:
            return super().acknowledge(ticket, evidence=evidence, reason=reason)
        if (
            evidence is None
            or reason not in RETAINED_BY_POLICY
            or getattr(retained_until, "tzinfo", None) is None
        ):
            raise ValueError("a retention date belongs only to evidence retained by policy")

        def recorded(conn):
            conn.execute(
                "UPDATE accounts.lifecycle_scope SET retained_until=%s "
                "WHERE request_id=%s AND participant=%s AND scope=%s",
                (retained_until, ticket["request_id"], ticket["participant"], ticket["scope"]),
            )

        return self._acknowledge_in(ticket, evidence, reason, recorded=recorded)

    def _status(self, conn, request: dict, account: dict) -> dict:
        value = super()._status(conn, request, account)
        dates = {
            (row["participant"], row["scope"]): row["retained_until"]
            for row in conn.execute(
                "SELECT participant,scope,retained_until FROM accounts.lifecycle_scope "
                "WHERE request_id=%s AND disposition='complete' AND retained_until IS NOT NULL",
                (request["id"],),
            ).fetchall()
        }
        if not dates:
            return value
        for participant in value["participants"]:
            for scope in participant["scopes"]:
                date = dates.get((participant["participantId"], scope["scope"]))
                if date is not None:
                    scope["retainedUntil"] = date.isoformat()
        return wire.LifecycleRequest.model_validate(value).model_dump(
            mode="json", exclude_none=True
        )
