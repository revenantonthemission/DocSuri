"""Read-only Corpus projection access and Discovery-owned execution/relay facts."""

from __future__ import annotations

from uuid import UUID

from backend.transactions import Authority, OwnerTransactions, guard
from psycopg.types.json import Jsonb


class GuardedDiscoveryRepository:
    def __init__(self, transactions: OwnerTransactions):
        self.transactions = transactions

    def candidates(self, authority: Authority | None) -> list[dict]:
        return self.snapshot(authority)["candidates"]

    def snapshot(self, authority: Authority | None, *, query: str = "") -> dict:
        if len(query.encode()) > 2048:
            raise ValueError("search query exceeds finite allocation")

        def read(conn):
            if authority:
                guard(conn, authority)
            publication = conn.execute("SELECT * FROM corpus.guard_publication()").fetchone()
            rows = conn.execute(
                "SELECT c.*,v.paper_id,v.source_hash,v.version_label,p.title,p.authors,"
                "p.published_on,v.source_url,v.eligibility_revision,"
                "ts_rank_cd(setweight(to_tsvector('simple',p.title),'A') || c.lexical,"
                "plainto_tsquery('simple',%s)) AS lexical_score "
                "FROM corpus.projection c JOIN corpus.version v ON "
                "v.id=c.version_id JOIN corpus.paper p ON p.id=v.paper_id WHERE v.eligible AND "
                "NOT p.withdrawn ORDER BY v.id,c.ordinal LIMIT 257",
                (query,),
            ).fetchall()
            if len(rows) > 256:
                raise ValueError("corpus projection exceeds declared allocation")
            for version in sorted({row["version_id"] for row in rows}):
                conn.execute("SELECT corpus.guard_version(%s,%s)", (version, "local-research"))
            return {"publication": publication, "candidates": rows}

        return self.transactions.run("discovery", read)

    def record(
        self,
        authority: Authority | None,
        execution: UUID,
        query: dict,
        query_hash: str,
        results: list[dict],
        generation: int | None,
    ) -> dict:
        def write(conn):
            if authority:
                guard(conn, authority)
            return conn.execute(
                "INSERT INTO discovery.execution(id,account_id,query,query_hash,"
                "captured_generation,results,relay_state) VALUES(%s,%s,%s,%s,%s,%s,%s) "
                "RETURNING *",
                (
                    execution,
                    authority.account_id if authority else None,
                    Jsonb(query),
                    query_hash,
                    generation,
                    Jsonb(results),
                    "pending" if authority else "none",
                ),
            ).fetchone()

        return self.transactions.run("discovery", write)

    def pending_history(self, authority: Authority) -> list[dict]:
        def read(conn):
            guard(conn, authority)
            return conn.execute(
                "SELECT * FROM discovery.execution WHERE account_id=%s AND "
                "relay_state='pending' ORDER BY completed_at,id LIMIT 20",
                (authority.account_id,),
            ).fetchall()

        return self.transactions.run("discovery", read)

    def acknowledge_history(
        self, authority: Authority, execution: UUID, *, delivered: bool
    ) -> None:
        def write(conn):
            guard(conn, authority)
            conn.execute(
                "UPDATE discovery.execution SET relay_state=%s WHERE id=%s AND account_id=%s "
                "AND relay_state='pending'",
                ("delivered" if delivered else "suppressed", execution, authority.account_id),
            )

        self.transactions.run("discovery", write)
