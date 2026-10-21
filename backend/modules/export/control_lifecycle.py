"""ApprovedExport lifecycle participant (U6; BR6.1-BR6.5, BR7.2, NFR1.4, A8).

It writes only this module's records, through the shared `apply_owner_effect`
contract, so evidence is written once per (request, scope) and a repeated ticket
returns the recorded evidence. It never defers: no ticket is left blocked by this
participant (BR6.5).

- **Withdraw** (`live_records`, `pending_work`), in one transaction: approved
  approvals and accepted effects become invalidated (account-withdrawn) and their
  rendered copies are trimmed, the envelope is cleared and the connection set
  disconnected, the pending reservation is released through
  `export.lifecycle_release_pending`, and the counts are recorded. An executing export
  finishes on its own and an unknown one is kept (BR6.1).
- **Reactivate** records evidence and changes nothing (BR6.3).
- **Erase** runs the withdraw step, records count-only evidence (including the pages
  exported and possibly created), then `export.erase_account_records` deletes every
  record of the account. Only the `live_records` ticket may erase (BR6.2).
- **external_copies** reports the owner's Notion pages, which are never touched,
  under `external-copies-retained-by-owner` (BR6.4), overriding the reason key as
  `UsageLifecycleParticipant` does; AccountAccess reports it as retained by policy.

The report never depends on scope order. The withdraw step's counts are the request's:
a later sibling scope adds only what it changed itself to what the first one recorded.
External copies count the account's rows, or, once `live_records` has erased them for
the same request, that request's recorded page counts. Evidence holds numbers only and
no account column, so it survives erasure (BR7.2).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable

from psycopg.types.json import Jsonb

from backend.lifecycle_effects import apply_owner_effect

from .store_support import require_now

OWNER = "export"
SCOPES = ("live_records", "pending_work", "external_copies")
WITHDRAW_SCOPES = ("live_records", "pending_work")
COMPLETE_REASON = "owner-scope-complete"
EXTERNAL_COPIES_REASON = "external-copies-retained-by-owner"
WITHDRAWN = "account-withdrawn"
COUNT_FIELDS = (
    "approvals_invalidated",
    "effects_invalidated",
    "exports_in_flight",
    "exports_unknown",
    "pages_exported",
    "pages_possibly_created",
)


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class ExportLifecycleParticipant:
    """The `ApprovedExport` participant. `clock` gives the one aware `now` per ticket."""

    scopes = SCOPES

    def __init__(self, transactions, *, clock: Callable[[], dt.datetime] = _utc_now):
        self.transactions = transactions
        self.clock = clock

    def apply(self, ticket: dict) -> dict:
        now = require_now(self.clock())

        def effect(conn, action, current):
            if current["scope"] == "external_copies":
                counts = _external_copies(conn, current)
            elif action == "reactivate":
                counts = {}
            else:
                counts = _withdraw(conn, current, now)
                if action == "erase" and current["scope"] == "live_records":
                    counts.update(_page_counts(conn, current["account_id"]))
                    _erase(conn, current)
            _record_counts(conn, current, action, counts)

        result = apply_owner_effect(self.transactions, OWNER, self.scopes, ticket, effect)
        if ticket["scope"] == "external_copies":
            result["reasonKey"] = EXTERNAL_COPIES_REASON
        return result


def _guard_arguments(current: dict) -> tuple:
    return (
        current["request_id"],
        current["account_id"],
        current["scope"],
        current["generation"],
        Jsonb(current["policy_ref"]),
        current["manifest_revision"],
    )


def _withdraw(conn, current: dict, now: dt.datetime) -> dict:
    """BR6.1 in the ticket's transaction; returns the request's withdraw counts."""
    account = current["account_id"]
    conn.execute(
        "SELECT export.lifecycle_release_pending(%s,%s,%s,%s,%s,%s)", _guard_arguments(current)
    )
    _disconnect(conn, account)
    effects = conn.execute(
        "UPDATE export.effect SET state='invalidated',revision=revision+1,outcome_reason=%s,"
        "ended_at=%s,updated_at=clock_timestamp() WHERE account_id=%s AND state='accepted' "
        "RETURNING approval_id",
        (WITHDRAWN, now, account),
    ).fetchall()
    approvals = conn.execute(
        "UPDATE export.approval SET state='invalidated',invalidation_reason=%s "
        "WHERE account_id=%s AND state='approved' RETURNING id",
        (WITHDRAWN, account),
    ).fetchall()
    _trim(conn, [row["approval_id"] for row in effects] + [row["id"] for row in approvals], now)
    open_work = conn.execute(
        "SELECT count(*) FILTER (WHERE state='executing') AS in_flight,"
        "count(*) FILTER (WHERE state='unknown') AS unknown "
        "FROM export.effect WHERE account_id=%s",
        (account,),
    ).fetchone()
    own = {
        "approvals_invalidated": len(approvals),
        "effects_invalidated": len(effects),
        "exports_in_flight": open_work["in_flight"],
        "exports_unknown": open_work["unknown"],
    }
    return _with_sibling(conn, current, own)


def _disconnect(conn, account) -> None:
    """Clear the envelope and set the connection disconnected (NFR3.7). A disconnected
    or revoked connection already holds no envelope and stays as it is."""
    row = conn.execute(
        "SELECT id,revision,state FROM export.connection WHERE account_id=%s FOR UPDATE",
        (account,),
    ).fetchone()
    if row is None or row["state"] not in ("connected", "unavailable"):
        return
    cleared = conn.execute(
        "SELECT export.clear_token_envelope(%s,%s,%s,'disconnected') AS revision",
        (account, row["id"], row["revision"]),
    ).fetchone()["revision"]
    if cleared is None:
        raise RuntimeError("export connection moved while locked")


def _trim(conn, approval_ids: list, now: dt.datetime) -> None:
    """The rendered copies of withdrawn work can no longer lead to a write (BR2.6)."""
    if not approval_ids:
        return
    conn.execute(
        "UPDATE export.preview_revision r SET rendered_blocks=NULL,rendered_text=NULL,"
        "trimmed_at=%s FROM export.approval a WHERE a.preview_id=r.preview_id "
        "AND a.preview_revision=r.revision AND a.id=ANY(%s) AND r.trimmed_at IS NULL",
        (now, approval_ids),
    )


def _with_sibling(conn, current: dict, own: dict) -> dict:
    """The first withdraw scope of a request records its counts; a later sibling adds
    only what it changed itself, so the report is the same in either order."""
    sibling = conn.execute(
        "SELECT approvals_invalidated,effects_invalidated,exports_in_flight,exports_unknown "
        "FROM export.lifecycle_counts WHERE request_id=%s AND scope=ANY(%s) AND scope<>%s",
        (current["request_id"], list(WITHDRAW_SCOPES), current["scope"]),
    ).fetchone()
    if sibling is None:
        return own
    return {
        "approvals_invalidated": sibling["approvals_invalidated"] + own["approvals_invalidated"],
        "effects_invalidated": sibling["effects_invalidated"] + own["effects_invalidated"],
        "exports_in_flight": sibling["exports_in_flight"],
        "exports_unknown": sibling["exports_unknown"],
    }


def _page_counts(conn, account) -> dict:
    """Pages in the owner's Notion: written ones, and ones an executing or unknown export
    may have created. An accepted export has written nothing."""
    row = conn.execute(
        "SELECT count(*) FILTER (WHERE state='succeeded') AS exported,"
        "count(*) FILTER (WHERE state IN ('executing','unknown')) AS possibly "
        "FROM export.effect WHERE account_id=%s",
        (account,),
    ).fetchone()
    return {"pages_exported": row["exported"], "pages_possibly_created": row["possibly"]}


def _external_copies(conn, current: dict) -> dict:
    """BR6.4: nothing in Notion changes. Once live_records has erased the rows for this
    request, its recorded page counts stand for them."""
    erased = conn.execute(
        "SELECT pages_exported,pages_possibly_created FROM export.lifecycle_counts "
        "WHERE request_id=%s AND scope='live_records' AND action='erase'",
        (current["request_id"],),
    ).fetchone()
    if erased is not None:
        return dict(erased)
    return _page_counts(conn, current["account_id"])


def _erase(conn, current: dict) -> None:
    conn.execute(
        "SELECT export.erase_account_records(%s,%s,%s,%s,%s)",
        (
            current["request_id"],
            current["account_id"],
            current["generation"],
            Jsonb(current["policy_ref"]),
            current["manifest_revision"],
        ),
    )


def _record_counts(conn, current: dict, action: str, counts: dict) -> None:
    """Count-only evidence: integers and fixed categories, no account column (BR7.2)."""
    values = [int(counts.get(field, 0)) for field in COUNT_FIELDS]
    reason = EXTERNAL_COPIES_REASON if current["scope"] == "external_copies" else COMPLETE_REASON
    conn.execute(
        "INSERT INTO export.lifecycle_counts(request_id,scope,action,reason_key,"
        + ",".join(COUNT_FIELDS)
        + ") VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (current["request_id"], current["scope"], action, reason, *values),
    )
