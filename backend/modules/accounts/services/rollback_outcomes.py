"""AccountAccess's read for a rollback (U8 plan Step 33; BR9.7, BR9.13).

After v2 has stopped, the operator tool lists, through this read run under trusted
composition authority against the stopped production database, every account whose
lifecycle state changed since the switch with its latest outcome, and the per-kind
count of what AccountAccess holds that v2 made since then (the rollback's report and a
copy waiver's subject). It reads only AccountAccess's own tables, through its own
login, and writes nothing:

- `latest_outcomes(since)`: per account, the latest lifecycle request accepted at or
  after `since` (`withdraw`, `erase` or `reactivate`); an account reactivated after its
  withdrawal is listed as `reactivate`, which v1's own code applies as nothing more than
  its own reactivation;
- `changes_since(since)`: the counts of accounts created and lifecycle requests
  accepted since `since`. Identifiers and counts only, never an email or a name.
"""

from __future__ import annotations

import datetime as dt

OWNER = "accounts"
MAX_ACCOUNTS = 100_000


def _aware(moment: dt.datetime) -> dt.datetime:
    if moment.tzinfo is None:
        raise ValueError("the switch time must be aware")
    return moment


class RollbackOutcomes:
    def __init__(self, transactions):
        self.transactions = transactions

    def latest_outcomes(self, since: dt.datetime) -> list[dict]:
        moment = _aware(since)

        def read(conn):
            return conn.execute(
                "SELECT DISTINCT ON (account_id) account_id::text AS account_id,action "
                "FROM accounts.lifecycle_request WHERE accepted_at>=%s "
                "ORDER BY account_id,accepted_at DESC,id DESC LIMIT %s",
                (moment, MAX_ACCOUNTS + 1),
            ).fetchall()

        rows = self.transactions.run(OWNER, read)
        if len(rows) > MAX_ACCOUNTS:
            raise ValueError("the rollback's outcome list exceeds its bound")
        return [{"accountId": row["account_id"], "outcome": row["action"]} for row in rows]

    def changes_since(self, since: dt.datetime) -> dict[str, int]:
        moment = _aware(since)

        def read(conn):
            created = conn.execute(
                "SELECT count(*) AS n FROM accounts.account WHERE created_at>=%s", (moment,)
            ).fetchone()["n"]
            requests = conn.execute(
                "SELECT count(*) AS n FROM accounts.lifecycle_request WHERE accepted_at>=%s",
                (moment,),
            ).fetchone()["n"]
            return {"accounts-created": int(created), "lifecycle-requests": int(requests)}

        return self.transactions.run(OWNER, read)
