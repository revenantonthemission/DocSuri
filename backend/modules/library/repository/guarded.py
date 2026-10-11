"""Canonical revision/receipt adapter for the isolated owner-schema assembly."""

from __future__ import annotations

from uuid import UUID

from psycopg.types.json import Jsonb

from backend.transactions import Authority, OwnerTransactions, guard


class GuardedLibraryRepository:
    def __init__(self, transactions: OwnerTransactions):
        self.transactions = transactions

    def save(
        self, authority: Authority, paper: str, version: str, key: UUID, expected: UUID | None
    ) -> dict:
        return self.transactions.run(
            "library",
            lambda conn: conn.execute(
                "SELECT library.save_paper(%s,%s,%s,%s,%s,%s) AS receipt",
                (authority.account_id, authority.session_id, paper, version, key, expected),
            ).fetchone()["receipt"],
        )

    def list_saved(self, authority: Authority, *, limit: int = 20) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("invalid page bound")

        def read(conn):
            guard(conn, authority)
            rows = conn.execute(
                "SELECT * FROM library.saved_paper WHERE account_id=%s ORDER BY saved_at DESC,"
                "paper_id LIMIT %s",
                (authority.account_id, limit),
            ).fetchall()
            for row in rows:
                # Deny the protected read on withdrawal; a later presenter can
                # expose only an unavailable identity through a separate contract.
                guard(conn, authority, version=row["version_id"])
            return rows

        return self.transactions.run("library", read)

    def history_boundary(self, authority: Authority) -> dict:
        def read(conn):
            guard(conn, authority)
            row = conn.execute(
                "SELECT * FROM library.history_boundary WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()
            if row is None:
                raise ValueError("account library participant not initialized")
            return row

        return self.transactions.run("library", read)

    def clear_history(self, authority: Authority, key: UUID, expected: UUID) -> dict:
        return self.transactions.run(
            "library",
            lambda conn: conn.execute(
                "SELECT library.clear_history(%s,%s,%s,%s) AS receipt",
                (authority.account_id, authority.session_id, key, expected),
            ).fetchone()["receipt"],
        )

    def accept_history(self, authority: Authority, fact: dict) -> bool:
        if fact["account_id"] != authority.account_id:
            raise PermissionError("history owner mismatch")
        return self.transactions.run(
            "library",
            lambda conn: conn.execute(
                "SELECT library.accept_history_fact(%s,%s,%s,%s,%s,%s) AS accepted",
                (
                    authority.account_id,
                    authority.session_id,
                    fact["id"],
                    fact["captured_generation"],
                    fact["completed_at"],
                    Jsonb(fact["query"]),
                ),
            ).fetchone()["accepted"],
        )
