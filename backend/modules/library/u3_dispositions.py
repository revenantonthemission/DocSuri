"""U3 Library: consume ordered corpus change facts into explicit dispositions.

The Library owner — not CorpusContent — records the saved reference's
disposition. Consumption is ordered by fact position, replay-safe (a duplicate
delivery re-applies the same disposition), and never deletes owner data.
"""

from __future__ import annotations

from backend.transactions import OwnerTransactions, guard
from backend.u3_policy import bounded_int


class SavedReferenceDispositions:
    def __init__(self, transactions: OwnerTransactions):
        self.transactions = transactions

    def consume(self, limit: int = 50) -> dict:
        limit = bounded_int(limit, low=1, high=100, name="disposition page bound")
        facts = self.transactions.run(
            "library",
            lambda conn: conn.execute(
                "SELECT position FROM library.disposition_cursor WHERE singleton"
            ).fetchone()["position"],
        )
        pending = self.transactions.run(
            "corpus",
            lambda conn: conn.execute(
                "SELECT * FROM corpus.read_change_facts(%s,%s)", (facts, limit)
            ).fetchall(),
        )
        applied = 0
        for fact in pending:
            applied += self._apply(fact)
        return {"consumedPosition": facts + len(pending), "applied": applied}

    def _apply(self, fact: dict) -> int:
        """One fact, one owner transaction, ordered by its position."""

        def write(conn):
            cursor = conn.execute(
                "SELECT * FROM library.disposition_cursor WHERE singleton FOR UPDATE"
            ).fetchone()
            if fact["fact_position"] <= cursor["position"]:
                return 0  # duplicate delivery is harmless
            detail = fact["detail"] or {}
            disposition = detail.get("disposition")
            if fact["change_kind"] == "withdrawal":
                target = "unavailable"
            elif fact["change_kind"] == "canonicalization":
                target = "canonicalized"
            elif fact["change_kind"] == "version-change":
                target = "version-superseded"
            elif disposition in ("restricted", "unavailable", "withdrawn"):
                target = "unavailable"
            else:
                target = None
            changed = 0
            if target == "version-superseded" and fact["version_id"] is not None:
                changed = conn.execute(
                    "UPDATE library.saved_paper SET disposition='version-superseded',"
                    "disposition_revision=%s,disposition_position=%s "
                    "WHERE paper_id=%s AND version_id<>%s AND disposition<>'version-superseded'",
                    (
                        fact["eligibility_revision"],
                        fact["fact_position"],
                        fact["paper_id"],
                        fact["version_id"],
                    ),
                ).rowcount
            elif target is not None:
                changed = conn.execute(
                    "UPDATE library.saved_paper SET disposition=%s,disposition_revision=%s,"
                    "disposition_position=%s WHERE paper_id=%s AND disposition<>%s",
                    (
                        target,
                        fact["eligibility_revision"],
                        fact["fact_position"],
                        fact["paper_id"],
                        target,
                    ),
                ).rowcount
            conn.execute(
                "UPDATE library.disposition_cursor SET position=%s,"
                "revision=gen_random_uuid() WHERE singleton",
                (fact["fact_position"],),
            )
            return changed

        return self.transactions.run("library", write)

    def dispositions(self, authority) -> list[dict]:
        """Owner-bound read of saved references plus their current disposition."""

        def read(conn):
            guard(conn, authority)
            return conn.execute(
                "SELECT paper_id,version_id,disposition,disposition_position FROM "
                "library.saved_paper WHERE account_id=%s ORDER BY saved_at,paper_id LIMIT 100",
                (authority.account_id,),
            ).fetchall()

        return self.transactions.run("library", read)
