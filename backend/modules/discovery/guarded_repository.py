"""Read-only Corpus projection access and Discovery-owned execution/relay facts."""

from __future__ import annotations

from uuid import UUID

from backend.transactions import Authority, OwnerTransactions, guard
from psycopg.types.json import Jsonb


class GuardedDiscoveryRepository:
    def __init__(self, transactions: OwnerTransactions):
        self.transactions = transactions

    def admit(self, authority: Authority, execution: UUID, query_hash: str) -> int:
        """Persist U2 admission before search work, serialized with history clear."""
        if self.transactions.profile.realm != "account-controls" or len(query_hash) != 64:
            raise ValueError("U2 admission binding required")

        def write(conn):
            revision = guard(conn, authority)
            conn.execute(
                "INSERT INTO discovery.owner_admission(account_id) VALUES(%s) "
                "ON CONFLICT DO NOTHING",
                (authority.account_id,),
            )
            row = conn.execute(
                "SELECT sequence FROM discovery.owner_admission WHERE account_id=%s FOR UPDATE",
                (authority.account_id,),
            ).fetchone()
            prior = conn.execute(
                "SELECT * FROM discovery.admission WHERE execution_id=%s", (execution,)
            ).fetchone()
            if prior:
                if (
                    prior["account_id"] != authority.account_id
                    or prior["query_hash"] != query_hash
                    or prior["authority_revision"] != revision
                ):
                    raise ValueError("search admission conflict")
                return prior["sequence"]
            sequence = row["sequence"] + 1
            conn.execute(
                "UPDATE discovery.owner_admission SET sequence=%s WHERE account_id=%s",
                (sequence, authority.account_id),
            )
            conn.execute(
                "INSERT INTO discovery.admission(execution_id,account_id,sequence,"
                "authority_revision,query_hash) VALUES(%s,%s,%s,%s,%s)",
                (execution, authority.account_id, sequence, revision, query_hash),
            )
            return sequence

        return self.transactions.run("discovery", write)

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
                # Match all submitted terms within one immutable paper version.
                # Chunk boundaries must not turn a matching paper into no-match.
                "WITH ranked AS MATERIALIZED ("
                "SELECT c.version_id,ts_rank_cd(setweight(to_tsvector('simple',p.title),'A') "
                "|| to_tsvector('simple',string_agg(c.text_content,' ' ORDER BY c.ordinal)),"
                "plainto_tsquery('simple',%s)) AS paper_score "
                "FROM corpus.projection c JOIN corpus.version v ON v.id=c.version_id "
                "JOIN corpus.paper p ON p.id=v.paper_id WHERE v.eligible AND NOT p.withdrawn "
                "GROUP BY c.version_id,p.title) "
                "SELECT c.*,v.paper_id,v.source_hash,v.version_label,p.title,p.authors,"
                "p.published_on,v.source_url,v.eligibility_revision,"
                "CASE WHEN p.id=%s OR v.id=%s THEN 1.0 ELSE ranked.paper_score "
                "END AS lexical_score "
                "FROM corpus.projection c JOIN corpus.version v ON "
                "v.id=c.version_id JOIN ranked ON ranked.version_id=v.id "
                "JOIN corpus.paper p ON p.id=v.paper_id WHERE v.eligible AND "
                "NOT p.withdrawn ORDER BY v.id,c.ordinal LIMIT 257",
                (query, query.strip(), query.strip()),
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
                revision = guard(conn, authority)
                if self.transactions.profile.realm == "account-controls":
                    admitted = conn.execute(
                        "SELECT * FROM discovery.admission WHERE execution_id=%s",
                        (execution,),
                    ).fetchone()
                    if (
                        not admitted
                        or admitted["account_id"] != authority.account_id
                        or admitted["authority_revision"] != revision
                        or admitted["query_hash"] != query_hash
                        or admitted["sequence"] != generation
                    ):
                        raise PermissionError("missing or changed search admission")
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
