"""Canonical revision/receipt adapter for the isolated owner-schema assembly."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID, uuid4

from docsuri_shared.workspace import wire
from psycopg import sql
from psycopg.types.json import Jsonb

from backend.transactions import Authority, OwnerTransactions, guard


class LibraryConflict(ValueError):
    """A fresh revision or changed operation needs deliberate reconciliation."""


def query_reference(query: dict, label: str | None = None) -> dict:
    """Preserve submitted context, including its vocabulary, without rerunning it."""
    context = wire.LibraryQueryContext.model_validate(query).model_dump(mode="json")
    if not context["query"].strip() or len(context["query"].encode()) > 2048:
        raise ValueError("saved query outside finite policy")
    if label is not None and (not isinstance(label, str) or not label.strip() or len(label) > 100):
        raise ValueError("saved query label outside finite policy")
    value = {"queryContext": context}
    if label is not None:
        value["label"] = label
    if len(json.dumps(value).encode()) > 16384:
        raise ValueError("saved query context outside finite policy")
    return value


class GuardedLibraryRepository:
    def __init__(self, transactions: OwnerTransactions):
        self.transactions = transactions
        self.purpose = (
            "account-control"
            if transactions.profile.realm == "account-controls"
            else "local-research"
        )

    def _guard(self, conn, authority, *, mutation=False):
        revision = guard(conn, authority, purpose=self.purpose)
        if mutation:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,23))",
                (str(authority.account_id),),
            )
        return revision

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
            self._guard(conn, authority)
            rows = conn.execute(
                "SELECT * FROM library.saved_paper WHERE account_id=%s ORDER BY saved_at DESC,"
                "paper_id LIMIT %s",
                (authority.account_id, limit),
            ).fetchall()
            for row in rows:
                # The saved reference remains the owner's data after withdrawal.
                # This narrow corpus function grants disposition, never content.
                row["availability"] = conn.execute(
                    "SELECT corpus.reference_availability(%s) AS disposition",
                    (row["version_id"],),
                ).fetchone()["disposition"]
            return rows

        return self.transactions.run("library", read)

    def ensure_boundary(self, authority: Authority) -> None:
        """Owner-side participant initialization; runs before the first history effect."""

        def write(conn):
            self._guard(conn, authority, mutation=True)
            conn.execute(
                "INSERT INTO library.history_boundary(account_id) VALUES(%s) "
                "ON CONFLICT (account_id) DO NOTHING",
                (authority.account_id,),
            )

        self.transactions.run("library", write)

    def history_boundary(self, authority: Authority) -> dict:
        def read(conn):
            self._guard(conn, authority)
            # The fresh boundary defaults to '-infinity', which is not a Python
            # datetime; callers need only the generation and revision tokens.
            row = conn.execute(
                "SELECT account_id, generation, revision FROM library.history_boundary "
                "WHERE account_id=%s",
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

    @staticmethod
    def _receipt(conn, authority: Authority, kind: str, key: UUID, intent: dict):
        digest = hashlib.sha256(
            json.dumps(intent, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        prior = conn.execute(
            "SELECT intent_hash,outcome FROM library.receipt "
            "WHERE account_id=%s AND kind=%s AND key=%s",
            (authority.account_id, kind, key),
        ).fetchone()
        if prior and prior["intent_hash"] != digest:
            raise LibraryConflict("operation identity changed")
        return digest, prior["outcome"] if prior else None

    @staticmethod
    def _record(conn, authority, kind, key, digest, outcome):
        conn.execute(
            "INSERT INTO library.receipt(account_id,kind,key,intent_hash,outcome) "
            "VALUES(%s,%s,%s,%s,%s)",
            (authority.account_id, kind, key, digest, Jsonb(outcome)),
        )
        return outcome

    def save_query(
        self, authority: Authority, key: UUID, query: dict, *, label: str | None = None
    ) -> dict:
        value = query_reference(query, label)

        def write(conn):
            self._guard(conn, authority, mutation=True)
            digest, previous = self._receipt(conn, authority, "save-query", key, value)
            if previous is not None:
                return previous
            count = conn.execute(
                "SELECT count(*) AS count FROM library.saved_query WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()["count"]
            if count >= 100:
                raise ValueError("synthetic saved query allocation reached")
            row = conn.execute(
                "INSERT INTO library.saved_query(account_id,id,query) "
                "VALUES(%s,%s,%s) RETURNING id,revision",
                (authority.account_id, uuid4(), Jsonb(value)),
            ).fetchone()
            outcome = {"savedSearchId": str(row["id"]), "revision": str(row["revision"])}
            return self._record(conn, authority, "save-query", key, digest, outcome)

        return self.transactions.run("library", write)

    def remove_paper(self, authority: Authority, paper: str, key: UUID, expected: UUID) -> dict:
        return self._remove(authority, "paper", paper, key, expected)

    def remove_query(self, authority: Authority, query: UUID, key: UUID, expected: UUID) -> dict:
        return self._remove(authority, "query", query, key, expected)

    def _remove(self, authority, kind, resource, key, expected):
        if not isinstance(expected, UUID):
            raise ValueError("removal requires an exact revision")
        # Identifiers are selected only from this fixed internal vocabulary.
        table, column = {"paper": ("saved_paper", "paper_id"), "query": ("saved_query", "id")}[kind]
        operation = "remove-" + kind
        intent = {"resource": str(resource), "expectedRevision": str(expected)}

        def write(conn):
            self._guard(conn, authority, mutation=True)
            digest, previous = self._receipt(conn, authority, operation, key, intent)
            if previous is not None:
                return previous
            row = conn.execute(
                sql.SQL(
                    "SELECT revision FROM library.{} WHERE account_id=%s AND {}=%s FOR UPDATE"
                ).format(sql.Identifier(table), sql.Identifier(column)),
                (authority.account_id, resource),
            ).fetchone()
            if not row or row["revision"] != expected:
                raise LibraryConflict("reference unavailable or revision changed")
            conn.execute(
                sql.SQL("DELETE FROM library.{} WHERE account_id=%s AND {}=%s").format(
                    sql.Identifier(table), sql.Identifier(column)
                ),
                (authority.account_id, resource),
            )
            outcome = {"removed": True, "resourceId": str(resource)}
            return self._record(conn, authority, operation, key, digest, outcome)

        return self.transactions.run("library", write)

    def list_queries(self, authority: Authority, *, limit: int = 20) -> list[dict]:
        return self._read_records(authority, "queries", limit)

    def read_query(self, authority: Authority, query: UUID) -> dict:
        def read(conn):
            self._guard(conn, authority)
            row = conn.execute(
                "SELECT * FROM library.saved_query WHERE account_id=%s AND id=%s",
                (authority.account_id, query),
            ).fetchone()
            if row is None:
                raise PermissionError("saved query unavailable")
            return row

        return self.transactions.run("library", read)

    def list_history(self, authority: Authority, *, limit: int = 20) -> list[dict]:
        return self._read_records(authority, "history", limit)

    def _read_records(self, authority, kind, limit):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("invalid page bound")
        query = {
            "queries": "SELECT * FROM library.saved_query WHERE account_id=%s "
            "ORDER BY saved_at DESC,id DESC LIMIT %s",
            "history": "SELECT * FROM library.history WHERE account_id=%s "
            "ORDER BY completed_at DESC,execution_id DESC LIMIT %s",
        }[kind]

        def read(conn):
            self._guard(conn, authority)
            return conn.execute(query, (authority.account_id, limit)).fetchall()

        return self.transactions.run("library", read)
