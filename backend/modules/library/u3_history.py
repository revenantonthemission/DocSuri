"""U3 Library history handoff over Discovery's admitted search facts.

The Library owner — not Discovery — records accepted history. Producer evidence
is re-verified through Discovery's narrow SECURITY DEFINER projection, never
trusted from the caller, and a clear boundary suppresses facts admitted at or
before it. Replay executes no search and writes no duplicate row.
"""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from backend.transactions import Authority, OwnerTransactions, guard


class U3HistoryConsumer:
    def __init__(self, transactions: OwnerTransactions):
        self.transactions = transactions

    def ensure_boundary(self, authority: Authority) -> None:
        def write(conn):
            guard(conn, authority)
            conn.execute(
                "INSERT INTO library.history_boundary(account_id,generation,revision,"
                "admission_cutoff) VALUES(%s,0,%s,0) ON CONFLICT (account_id) DO NOTHING",
                (
                    authority.account_id,
                    uuid5(NAMESPACE_URL, str(authority.account_id) + ":history-empty:1"),
                ),
            )

        self.transactions.run("library", write)

    def boundary(self, authority: Authority) -> dict:
        def read(conn):
            guard(conn, authority)
            row = conn.execute(
                "SELECT account_id,generation,revision,admission_cutoff,"
                "CASE WHEN eligible_after='-infinity' THEN NULL ELSE eligible_after END "
                "AS eligible_after FROM library.history_boundary WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()
            if row is None:
                return {
                    "account_id": authority.account_id,
                    "generation": 0,
                    "admission_cutoff": 0,
                    "revision": None,
                }
            return row

        return self.transactions.run("library", read)

    def accept_history(self, authority: Authority, fact: dict) -> bool:
        if fact["account_id"] != authority.account_id:
            raise PermissionError("history owner mismatch")

        def write(conn):
            guard(conn, authority)
            evidence = conn.execute(
                "SELECT discovery.history_fact(%s,%s,%s) AS value",
                (authority.account_id, authority.session_id, fact["id"]),
            ).fetchone()["value"]
            if not evidence:
                return False
            boundary = conn.execute(
                "SELECT admission_cutoff FROM library.history_boundary "
                "WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()
            if boundary is None:
                conn.execute(
                    "INSERT INTO library.history_boundary(account_id,generation,revision,"
                    "admission_cutoff) VALUES(%s,0,%s,0)",
                    (
                        authority.account_id,
                        uuid5(NAMESPACE_URL, str(authority.account_id) + ":history-empty:1"),
                    ),
                )
                boundary = {"admission_cutoff": 0}
            if evidence["admissionSequence"] <= boundary["admission_cutoff"]:
                return False
            prior = conn.execute(
                "SELECT 1 FROM library.history WHERE account_id=%s AND execution_id=%s",
                (authority.account_id, fact["id"]),
            ).fetchone()
            if prior:
                return True
            conn.execute(
                "INSERT INTO library.history(account_id,execution_id,query,captured_generation,"
                "completed_at,admission_sequence,completion_sequence) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (
                    authority.account_id,
                    fact["id"],
                    _jsonb(fact["query"]),
                    evidence["admissionSequence"],
                    fact["completed_at"],
                    evidence["admissionSequence"],
                    evidence["completionSequence"],
                ),
            )
            return True

        return self.transactions.run("library", write)

    def history(self, authority: Authority, limit: int = 20) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("invalid history bound")

        def read(conn):
            guard(conn, authority)
            return conn.execute(
                "SELECT * FROM library.history WHERE account_id=%s "
                "ORDER BY completed_at DESC, execution_id LIMIT %s",
                (authority.account_id, limit),
            ).fetchall()

        return self.transactions.run("library", read)


def _jsonb(value):
    from psycopg.types.json import Jsonb

    return Jsonb(value)
