"""ResearchWorkspace lifecycle participant (U8 plan Step 17; BR2.3, BR2.4).

It writes only research records, once per request and scope, through the shared
`apply_owner_effect` contract, so a repeated ticket returns the recorded evidence and
writes nothing. Evidence is counts only (`research.lifecycle_counts`).

- **Withdraw.** `pending_work` stops accepted research and novelty work: every open job
  (accepted, running or cancel-requested) ends failed with `CANCELLED`, its fence moved
  so a running worker's completion is refused, and every prepared admission closes,
  which leaves U4's own usage-release obligation for the worker to settle.
  `live_records` and `derived_artifacts` keep every record: the withdrawn account's
  sessions are revoked and its account inactive, so nothing is served, and the counts
  of what is kept are recorded.
- **Reactivate** serves again only what withdrawal kept: nothing is restored or
  resumed, and stopped work stays stopped.
- **Erase.** `pending_work` stops work as withdrawal does; `derived_artifacts` deletes
  the results with their evidence and assessments; `live_records` deletes contexts,
  sessions, turns and jobs, attachments, drafts and the account's admissions and
  receipts, through `research.erase_account_records`. It waits (`ready`) while open
  work or an unsettled usage reservation remains, so the worker settles it first.
"""

from __future__ import annotations

from psycopg.errors import ObjectNotInPrerequisiteState
from psycopg.types.json import Jsonb

from backend.lifecycle_effects import apply_owner_effect

OWNER = "research"
SCOPES = ("derived_artifacts", "live_records", "pending_work")
COUNT_FIELDS = (
    "contexts", "sessions", "jobs", "artifacts", "evidence", "attachments", "drafts",
    "jobs_stopped", "admissions_closed",
)


class ResearchLifecyclePending(RuntimeError):
    """Open work or an unsettled usage reservation remains for the account."""


class ResearchLifecycleParticipant:
    scopes = SCOPES

    def __init__(self, transactions):
        self.transactions = transactions

    def ready(self, request: dict, scope: str) -> bool:
        """An erase's `live_records` waits until no open work or unsettled usage
        remains; every other scope can be claimed at once."""
        if request["action"] != "erase" or scope != "live_records":
            return True
        return not self.transactions.run(OWNER, lambda conn: conn.execute(
            "SELECT EXISTS(SELECT 1 FROM research.job WHERE owner_id=%s AND (state IN "
            "('accepted','running','cancel_requested') OR usage_state='reserved')) AS open",
            (request["account_id"],),
        ).fetchone()["open"])

    def apply(self, ticket: dict) -> dict:
        def effect(conn, action, current):
            scope = current["scope"]
            if scope == "pending_work" and action in ("withdraw", "erase"):
                counts = _stop_work(conn, current["account_id"])
            elif action == "erase":
                counts = _erase(conn, current)
            else:
                counts = _kept(conn, current["account_id"], scope)
            _record_counts(conn, current, action, counts)

        try:
            return apply_owner_effect(self.transactions, OWNER, self.scopes, ticket, effect)
        except ObjectNotInPrerequisiteState:
            from backend.control_worker import PendingLifecycleEvidence

            raise PendingLifecycleEvidence("research-work-settlement-pending") from None


def _stop_work(conn, account) -> dict:
    stopped = conn.execute(
        "UPDATE research.job SET state='failed',error_code='CANCELLED',revision=revision+1,"
        "seq=seq+1,fence=fence+1,lease_until=NULL WHERE owner_id=%s "
        "AND state IN ('accepted','running','cancel_requested') RETURNING id",
        (account,),
    ).fetchall()
    closed = conn.execute(
        "UPDATE research.admission SET state='closed' WHERE owner_id=%s AND state='prepared' "
        "RETURNING operation_id",
        (account,),
    ).fetchall()
    return {"jobs_stopped": len(stopped), "admissions_closed": len(closed)}


def _kept(conn, account, scope: str) -> dict:
    """What withdrawal keeps, or reactivation serves again: counts only."""
    if scope == "derived_artifacts":
        row = conn.execute(
            "SELECT (SELECT count(*) FROM research.artifact WHERE owner_id=%(a)s) AS artifacts,"
            " (SELECT count(*) FROM research.evidence WHERE owner_id=%(a)s) AS evidence",
            {"a": account},
        ).fetchone()
        return dict(row)
    if scope == "pending_work":
        return {}
    row = conn.execute(
        "SELECT (SELECT count(*) FROM research.context WHERE owner_id=%(a)s) AS contexts,"
        " (SELECT count(*) FROM research.session WHERE owner_id=%(a)s) AS sessions,"
        " (SELECT count(*) FROM research.job WHERE owner_id=%(a)s) AS jobs,"
        " (SELECT count(*) FROM research.attachment WHERE owner_id=%(a)s) AS attachments,"
        " (SELECT count(*) FROM research.draft WHERE owner_id=%(a)s) AS drafts",
        {"a": account},
    ).fetchone()
    return dict(row)


def _erase(conn, current: dict) -> dict:
    return conn.execute(
        "SELECT research.erase_account_records(%s,%s,%s,%s,%s,%s) AS counts",
        (
            current["request_id"], current["account_id"], current["scope"],
            current["generation"], Jsonb(current["policy_ref"]), current["manifest_revision"],
        ),
    ).fetchone()["counts"]


def _record_counts(conn, current: dict, action: str, counts: dict) -> None:
    values = [int(counts.get(name, 0)) for name in COUNT_FIELDS]
    conn.execute(
        "INSERT INTO research.lifecycle_counts(request_id,scope,action,"
        + ",".join(COUNT_FIELDS) + ") VALUES(%s,%s,%s," + ",".join(["%s"] * len(COUNT_FIELDS))
        + ")",
        (current["request_id"], current["scope"], action, *values),
    )
