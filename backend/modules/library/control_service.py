"""U2 Library controls with stable pages and Discovery-owned admission evidence."""

from __future__ import annotations

from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from docsuri_shared.workspace import wire
from psycopg import sql
from psycopg.types.json import Jsonb

from backend.modules.accounts.control_cursor import ControlCursor
from backend.modules.accounts.control_policy import ControlPolicy
from backend.modules.library.repository.guarded import GuardedLibraryRepository, LibraryConflict
from backend.transactions import Authority, guard


class ControlLibraryService(GuardedLibraryRepository):
    def __init__(self, transactions, policy: ControlPolicy, cursor: ControlCursor):
        policy.require_realm(transactions.profile.realm)
        super().__init__(transactions)
        self.policy, self.cursor = policy, cursor

    @staticmethod
    def _boundary(conn, authority):
        row = conn.execute(
            "SELECT account_id,generation,revision,admission_cutoff "
            "FROM library.history_boundary WHERE account_id=%s",
            (authority.account_id,),
        ).fetchone()
        return row or {
            "account_id": authority.account_id,
            "generation": 0,
            "admission_cutoff": 0,
            "revision": uuid5(NAMESPACE_URL, str(authority.account_id) + ":history-empty:1"),
        }

    def history_boundary(self, authority: Authority) -> dict:
        def read(conn):
            self._guard(conn, authority)
            return self._boundary(conn, authority)

        return self.transactions.run("library", read)

    def clear_history(self, authority: Authority, key: UUID, expected: UUID) -> dict:
        if not isinstance(expected, UUID):
            raise ValueError("exact history revision required")

        def write(conn):
            self._guard(conn, authority, mutation=True)
            digest, prior = self._receipt(
                conn, authority, "clear-history-u2", key, {"expectedRevision": str(expected)}
            )
            if prior is not None:
                return prior
            before = self._boundary(conn, authority)
            if before["revision"] != expected:
                raise LibraryConflict("history boundary changed")
            cutoff = conn.execute(
                "SELECT discovery.history_checkpoint(%s,%s) AS sequence",
                (authority.account_id, authority.session_id),
            ).fetchone()["sequence"]
            row = conn.execute(
                "INSERT INTO library.history_boundary(account_id,generation,revision,"
                "admission_cutoff,eligible_after) "
                "VALUES(%s,%s,%s,%s,clock_timestamp()) ON CONFLICT(account_id) DO UPDATE SET "
                "generation=excluded.generation,revision=excluded.revision,"
                "admission_cutoff=excluded.admission_cutoff,eligible_after=excluded.eligible_after "
                "RETURNING generation,revision,admission_cutoff,eligible_after",
                (authority.account_id, before["generation"] + 1, uuid4(), cutoff),
            ).fetchone()
            conn.execute(
                "DELETE FROM library.history WHERE account_id=%s AND admission_sequence<=%s",
                (authority.account_id, cutoff),
            )
            outcome = {
                "generation": row["admission_cutoff"],
                "revision": str(row["revision"]),
                "eligibleAfter": row["eligible_after"].isoformat(),
            }
            return self._record(conn, authority, "clear-history-u2", key, digest, outcome)

        return self.transactions.run("library", write)

    def accept_history(self, authority: Authority, fact: dict) -> bool:
        if fact["account_id"] != authority.account_id:
            raise PermissionError("history owner mismatch")

        def write(conn):
            self._guard(conn, authority, mutation=True)
            # Resolve the actual producer record, never trust a caller's cutoff or payload.
            evidence = conn.execute(
                "SELECT discovery.history_fact(%s,%s,%s) AS value",
                (authority.account_id, authority.session_id, fact["id"]),
            ).fetchone()["value"]
            if (
                not evidence
                or evidence["admissionSequence"]
                <= self._boundary(conn, authority)["admission_cutoff"]
            ):
                return False
            prior = conn.execute(
                "SELECT execution_id FROM library.history WHERE account_id=%s AND execution_id=%s",
                (authority.account_id, fact["id"]),
            ).fetchone()
            if prior:
                return True
            count = conn.execute(
                "SELECT count(*) AS n FROM library.history WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()["n"]
            if count >= self.policy.max_outstanding:
                raise ValueError("finite synthetic history capacity")
            conn.execute(
                "INSERT INTO library.history(account_id,execution_id,query,captured_generation,"
                "completed_at,admission_sequence,completion_sequence) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (
                    authority.account_id,
                    fact["id"],
                    Jsonb(evidence["query"]),
                    evidence["admissionSequence"],
                    evidence["completedAt"],
                    evidence["admissionSequence"],
                    evidence["completionSequence"],
                ),
            )
            return True

        return self.transactions.run("library", write)

    def save(self, authority, paper, version, key, expected=None, *, eligibility=None):
        if not all(
            isinstance(value, str) and 0 < len(value.encode()) <= 160 for value in (paper, version)
        ):
            raise ValueError("bounded stable paper identity required")

        def write(conn):
            self._guard(conn, authority, mutation=True)
            guard(conn, authority, version=version)
            metadata = conn.execute(
                "SELECT corpus.reference_metadata(%s) AS value", (version,)
            ).fetchone()["value"]
            if not metadata or metadata["paperId"] != paper:
                raise PermissionError("paper/version binding mismatch")
            if eligibility is not None and str(eligibility) != str(metadata["eligibilityRevision"]):
                raise LibraryConflict("source eligibility changed")
            intent = {
                "paper": paper,
                "version": version,
                "expected": str(expected) if expected else None,
                "eligibility": str(eligibility) if eligibility else None,
            }
            digest, prior = self._receipt(conn, authority, "save-paper-u2", key, intent)
            if prior is not None:
                return prior
            row = conn.execute(
                "SELECT * FROM library.saved_paper WHERE account_id=%s AND paper_id=%s FOR UPDATE",
                (authority.account_id, paper),
            ).fetchone()
            if row:
                if row["version_id"] != version or (
                    expected is not None and row["revision"] != expected
                ):
                    raise LibraryConflict("saved reference differs; inspect before changing it")
            else:
                if expected is not None:
                    raise LibraryConflict("saved reference unavailable")
                count = conn.execute(
                    "SELECT count(*) AS n FROM library.saved_paper WHERE account_id=%s",
                    (authority.account_id,),
                ).fetchone()["n"]
                if count >= self.policy.max_outstanding:
                    raise ValueError("finite synthetic saved paper capacity")
                row = conn.execute(
                    "INSERT INTO library.saved_paper(account_id,paper_id,version_id,"
                    "eligibility_revision,saved_title) "
                    "VALUES(%s,%s,%s,%s,%s) RETURNING *",
                    (
                        authority.account_id,
                        paper,
                        version,
                        metadata["eligibilityRevision"],
                        metadata["title"],
                    ),
                ).fetchone()
            outcome = {
                "paperId": row["paper_id"],
                "paperVersionId": row["version_id"],
                "revision": str(row["revision"]),
                "savedAt": row["saved_at"].isoformat(),
            }
            return self._record(conn, authority, "save-paper-u2", key, digest, outcome)

        return self.transactions.run("library", write)

    @staticmethod
    def _paper(conn, row):
        if row["eligibility_revision"] is None:
            raise ValueError("saved reference continuity evidence required")
        metadata = conn.execute(
            "SELECT corpus.reference_metadata(%s) AS value", (row["version_id"],)
        ).fetchone()["value"]
        disposition = (metadata or {}).get("disposition", "unavailable")
        saved = {
            "paperId": row["paper_id"],
            "versionId": row["version_id"],
            "eligibilityRevision": str(row["eligibility_revision"]),
        }
        return {
            "savedPaperId": row["paper_id"],
            "accountId": str(row["account_id"]),
            "revision": str(row["revision"]),
            "savedPaper": saved,
            "resolvedPaper": dict(saved, eligibilityRevision=str(metadata["eligibilityRevision"]))
            if disposition == "available"
            else None,
            "savedTitle": row["saved_title"],
            "sourceDisposition": disposition,
            "reasonKey": "source." + disposition,
        }

    @staticmethod
    def _query(row):
        return {
            "savedSearchId": str(row["id"]),
            "accountId": str(row["account_id"]),
            "revision": str(row["revision"]),
            "queryContext": row["query"]["queryContext"],
            "label": row["query"].get("label"),
        }

    @staticmethod
    def _history(row, boundary):
        return {
            "historyId": str(row["execution_id"]),
            "accountId": str(row["account_id"]),
            "searchExecutionId": str(row["execution_id"]),
            "queryContext": row["query"],
            "recordedAt": row["completed_at"].isoformat(),
            "admissionSequence": row["admission_sequence"],
            "completionSequence": row["completion_sequence"],
            "clearBoundary": str(boundary["revision"]),
        }

    def page(
        self, authority: Authority, kind: str, *, limit: int, cursor: str | None = None
    ) -> dict:
        if type(limit) is not int or not 1 <= limit <= self.policy.max_page_size:
            raise ValueError("invalid bounded library page")
        table, time_column, id_column, model = {
            "papers": ("saved_paper", "saved_at", "paper_id", wire.LibraryPaperPage),
            "queries": ("saved_query", "saved_at", "id", wire.LibrarySearchPage),
            "history": ("history", "completed_at", "execution_id", wire.LibraryHistoryPage),
        }[kind]

        def read(conn):
            revision = self._guard(conn, authority)
            boundary = self._boundary(conn, authority)
            scope = f"library:{kind}:{revision}:{limit}" + (
                f":{boundary['revision']}" if kind == "history" else ""
            )
            position = self.cursor.decode(authority.account_id, scope, cursor) if cursor else None
            cutoff = (
                datetime.fromisoformat(position["cutoff"])
                if position
                else conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            )
            query = sql.SQL(
                "SELECT * FROM library.{table} WHERE account_id=%s AND {time}<=%s "
                "AND (%s::timestamptz IS NULL OR "
                "({time},{identifier})<(%s::timestamptz,%s::{id_type})) "
                "ORDER BY {time} DESC,{identifier} DESC LIMIT %s"
            ).format(
                table=sql.Identifier(table),
                time=sql.Identifier(time_column),
                identifier=sql.Identifier(id_column),
                id_type=sql.SQL("text" if kind == "papers" else "uuid"),
            )
            rows = conn.execute(
                query,
                (
                    authority.account_id,
                    cutoff,
                    position["time"] if position else None,
                    position["time"] if position else None,
                    position["id"] if position else None,
                    limit + 1,
                ),
            ).fetchall()
            next_cursor = (
                self.cursor.encode(
                    authority.account_id,
                    scope,
                    {
                        "cutoff": cutoff.isoformat(),
                        "time": rows[limit - 1][time_column].isoformat(),
                        "id": str(rows[limit - 1][id_column]),
                    },
                )
                if len(rows) > limit
                else None
            )
            items = [
                self._paper(conn, row)
                if kind == "papers"
                else self._query(row)
                if kind == "queries"
                else self._history(row, boundary)
                for row in rows[:limit]
            ]
            value = {
                "items": items,
                "page": {"nextCursor": next_cursor, "snapshotRevision": cutoff.isoformat()},
                "appliedLimit": limit,
                "policyRef": self.policy.reference,
            }
            if kind == "history":
                value["clearBoundary"] = str(boundary["revision"])
            return model.model_validate(value).model_dump(mode="json", exclude_none=True)

        return self.transactions.run("library", read)

    def read_record(self, authority: Authority, kind: str, identifier: str) -> dict:
        table, column, model = {
            "papers": ("saved_paper", "paper_id", wire.LibrarySavedPaper),
            "queries": ("saved_query", "id", wire.LibrarySavedSearch),
            "history": ("history", "execution_id", wire.LibraryHistoryRecord),
        }[kind]
        if kind != "papers":
            identifier = UUID(identifier)

        def read(conn):
            self._guard(conn, authority)
            row = conn.execute(
                sql.SQL("SELECT * FROM library.{} WHERE account_id=%s AND {}=%s").format(
                    sql.Identifier(table), sql.Identifier(column)
                ),
                (authority.account_id, identifier),
            ).fetchone()
            if row is None:
                raise PermissionError("library reference unavailable")
            value = (
                self._paper(conn, row)
                if kind == "papers"
                else self._query(row)
                if kind == "queries"
                else self._history(row, self._boundary(conn, authority))
            )
            return model.model_validate(value).model_dump(mode="json", exclude_none=True)

        return self.transactions.run("library", read)
