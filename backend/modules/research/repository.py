"""Owner-scoped research persistence; every access rechecks live authority.

No provider or network work occurs inside these bounded serializable transactions.
Draft storage is an internal primitive: the service must resolve policy before use.
"""

import hashlib
import json
from uuid import uuid4

from psycopg.types.json import Jsonb

from backend.transactions import Authority, OwnerTransactions, guard

from .errors import ResearchError


def digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class ResearchRepository:
    def __init__(self, transactions: OwnerTransactions):
        self.transactions = transactions

    def run(self, authority: Authority, action):
        def guarded(conn):
            guard(conn, authority)
            return action(conn)

        return self.transactions.run("research", guarded)

    @staticmethod
    def context(conn, authority, context_id, *, active=True):
        row = conn.execute(
            "SELECT * FROM research.context WHERE id=%s AND owner_id=%s FOR UPDATE",
            (context_id, authority.account_id),
        ).fetchone()
        if not row:
            raise ResearchError("NOT_FOUND")
        if active and row["lifecycle"] != "active":
            raise ResearchError("NOT_FOUND")
        return row

    @staticmethod
    def session(conn, authority, session_id, *, active=True):
        row = conn.execute(
            "SELECT * FROM research.session WHERE id=%s AND owner_id=%s FOR UPDATE",
            (session_id, authority.account_id),
        ).fetchone()
        if not row:
            raise ResearchError("NOT_FOUND")
        ResearchRepository.context(conn, authority, row["context_id"], active=active)
        if active and row["lifecycle"] != "active":
            raise ResearchError("NOT_FOUND")
        return row

    @staticmethod
    def receipt(conn, authority, operation, value):
        if operation is None:
            return None
        row = conn.execute(
            "SELECT * FROM research.receipt WHERE owner_id=%s AND operation_key=%s",
            (authority.account_id, str(operation)),
        ).fetchone()
        if row and row["input_hash"] != digest(value):
            raise ResearchError("IDEMPOTENCY_CONFLICT")
        return row["response"] if row else None

    @staticmethod
    def save_receipt(conn, authority, operation, value, response):
        if operation is not None:
            conn.execute(
                "INSERT INTO research.receipt(owner_id,operation_key,input_hash,response) "
                "VALUES(%s,%s,%s,%s)",
                (authority.account_id, str(operation), digest(value), Jsonb(response)),
            )

    def create_context(self, authority, purpose, *, operation=None):
        if purpose not in {"research", "novelty"}:
            raise ResearchError("INVALID_ARGUMENT")
        value = {"operation": "create-context", "purpose": purpose}

        def create(conn):
            previous = self.receipt(conn, authority, operation, value)
            if previous:
                return self.context(conn, authority, previous["contextId"])
            row = conn.execute(
                "INSERT INTO research.context(id,owner_id,purpose) VALUES(%s,%s,%s) RETURNING *",
                (uuid4(), authority.account_id, purpose),
            ).fetchone()
            self.save_receipt(conn, authority, operation, value, {"contextId": str(row["id"])})
            return row

        return self.run(authority, create)

    def create_session(self, authority, title, scope, *, operation=None):
        if not isinstance(title, str) or not 1 <= len(title.encode()) <= 1024:
            raise ResearchError("INVALID_ARGUMENT")

        def create(conn):
            self.context(conn, authority, scope["contextId"])
            value = {"operation": "create-session", "title": title, "scope": scope}
            previous = self.receipt(conn, authority, operation, value)
            if previous:
                return self.session(conn, authority, previous["sessionId"])
            row = conn.execute(
                "INSERT INTO research.session(id,owner_id,context_id,title,scope) "
                "VALUES(%s,%s,%s,%s,%s) RETURNING *",
                (uuid4(), authority.account_id, scope["contextId"], title, Jsonb(scope)),
            ).fetchone()
            self.save_receipt(conn, authority, operation, value, {"sessionId": str(row["id"])})
            return row

        return self.run(authority, create)

    def read_session(self, authority, session_id):
        def read(conn):
            row = self.session(conn, authority, session_id)
            jobs = conn.execute(
                "SELECT id,state FROM research.job WHERE session_id=%s AND owner_id=%s ORDER "
                "BY accepted_at,id",
                (session_id, authority.account_id),
            ).fetchall()
            return dict(row, jobs=jobs)

        return self.run(authority, read)

    def list_sessions(self, authority, limit=50):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ResearchError("INVALID_ARGUMENT")
        return self.run(
            authority,
            lambda conn: conn.execute(
                "SELECT s.* FROM research.session s JOIN research.context c ON c.id=s.context_id "
                "WHERE s.owner_id=%s AND s.lifecycle='active' AND c.lifecycle='active' "
                "ORDER BY s.created_at DESC,s.id DESC LIMIT %s",
                (authority.account_id, limit),
            ).fetchall(),
        )

    @staticmethod
    def snapshot_rows(conn, authority):
        rows = conn.execute(
            "SELECT s.* FROM research.session s JOIN research.context c ON c.id=s.context_id "
            "WHERE s.owner_id=%s AND c.lifecycle='active' ORDER BY s.created_at DESC,s.id DESC "
            "LIMIT 1001",
            (authority.account_id,),
        ).fetchall()
        if len(rows) > 1000:
            raise ResearchError("CAPACITY_EXHAUSTED")
        revision = digest(
            {
                "owner": str(authority.account_id),
                "sessions": [[str(r["id"]), r["revision"], r["lifecycle"]] for r in rows],
            }
        )
        return rows, revision

    def session_snapshot(self, authority):
        return self.run(authority, lambda conn: self.snapshot_rows(conn, authority))

    def delete_selection(self, authority, value, *, operation):
        def delete(conn):
            previous = self.receipt(conn, authority, operation, value)
            if previous:
                return previous
            if value["scope"] == "one-session":
                row = self.session(conn, authority, value["sessionId"], active=False)
                current = str(row["revision"])
                rows = [row]
            else:
                rows, current = self.snapshot_rows(conn, authority)
            if current != value["expectedRevision"]:
                raise ResearchError("CONFLICT", current={"revision": current})
            identifiers = [r["id"] for r in rows if r["lifecycle"] == "active"]
            for identifier in identifiers:
                conn.execute(
                    "UPDATE research.session SET lifecycle='deleted',deleted_at=clock_timestamp"
                    "(),revision=revision+1 WHERE id=%s",
                    (identifier,),
                )
                conn.execute(
                    "UPDATE research.artifact SET availability='deleted',eligibility_revision=e"
                    "ligibility_revision+1 "
                    "WHERE availability='ready' AND job_id IN (SELECT id FROM research.job "
                    "WHERE session_id=%s)",
                    (identifier,),
                )
            pending = conn.execute(
                "SELECT id FROM research.job WHERE owner_id=%s AND session_id=ANY(%s::uuid[]) "
                "AND state IN ('accepted','running','cancel_requested')",
                (authority.account_id, identifiers),
            ).fetchall()
            boundary = digest({"before": current, "deleted": [str(i) for i in identifiers]})
            result = {
                "requestId": str(operation),
                "revision": boundary,
                "state": "limited",
                "tombstoneBoundary": boundary,
                "policy": value["policy"],
                "remainingJobIds": [str(r["id"]) for r in pending],
                "limitations": [
                    "Visibility is tombstoned. Policy-defined physical purge and backup "
                    "disposition remain unresolved; deletion is not claimed "
                    "complete."
                ],
            }
            self.save_receipt(conn, authority, operation, value, result)
            return result

        return self.run(authority, delete)

    def delete_session(self, authority, session_id, expected_revision):
        def delete(conn):
            row = self.session(conn, authority, session_id, active=False)
            if str(row["revision"]) != str(expected_revision):
                raise ResearchError("CONFLICT", current={"revision": str(row["revision"])})
            if row["lifecycle"] != "active":
                return row
            result = conn.execute(
                "UPDATE research.session SET lifecycle='deleted',deleted_at=clock_timestamp(),r"
                "evision=revision+1 "
                "WHERE id=%s RETURNING *",
                (session_id,),
            ).fetchone()
            conn.execute(
                "UPDATE research.artifact SET availability='deleted',eligibility_revision=eligi"
                "bility_revision+1 "
                "WHERE job_id IN (SELECT id FROM research.job WHERE session_id=%s) AND "
                "availability='ready'",
                (session_id,),
            )
            return result

        return self.run(authority, delete)

    def save_draft(self, authority, draft_id, context_id, kind, base_revision, text, policy):
        if not isinstance(text, str) or len(text.encode()) > 32768:
            raise ResearchError("INVALID_ARGUMENT")
        if kind not in {
            "research-question",
            "novelty-topic",
            "novelty-manuscript",
            "novelty-discussion",
        }:
            raise ResearchError("INVALID_ARGUMENT")

        def save(conn):
            self.context(conn, authority, context_id)
            row = conn.execute(
                "SELECT * FROM research.draft WHERE id=%s FOR UPDATE", (draft_id,)
            ).fetchone()
            if row and (
                row["owner_id"] != authority.account_id or str(row["context_id"]) != str(context_id)
            ):
                raise ResearchError("NOT_FOUND")
            if row and row["kind"] != kind:
                raise ResearchError("CONFLICT")
            current = row["current_revision"] if row else None
            if (None if base_revision is None else str(base_revision)) != (
                None if current is None else str(current)
            ):
                raise ResearchError(
                    "CONFLICT", current={"revision": str(current) if current else None}
                )
            revision = current + 1 if current else 1
            if row:
                conn.execute(
                    "UPDATE research.draft SET current_revision=%s WHERE id=%s",
                    (revision, draft_id),
                )
            else:
                conn.execute(
                    "INSERT INTO research.draft(id,context_id,owner_id,kind) VALUES(%s,%s,%s,%s)",
                    (draft_id, context_id, authority.account_id, kind),
                )
            return conn.execute(
                "INSERT INTO research.draft_revision(draft_id,revision,parent_revision,content_"
                "hash,text,policy) "
                "VALUES(%s,%s,%s,%s,%s,%s) RETURNING *",
                (
                    draft_id,
                    revision,
                    current,
                    hashlib.sha256(text.encode()).hexdigest(),
                    text,
                    Jsonb(policy),
                ),
            ).fetchone()

        return self.run(authority, save)

    def restore_draft(self, authority, draft_id, context_id):
        def read(conn):
            self.context(conn, authority, context_id)
            row = conn.execute(
                "SELECT r.* FROM research.draft d JOIN research.draft_revision r "
                "ON r.draft_id=d.id AND r.revision=d.current_revision "
                "WHERE d.id=%s AND d.owner_id=%s AND d.context_id=%s",
                (draft_id, authority.account_id, context_id),
            ).fetchone()
            if not row:
                raise ResearchError("NOT_FOUND")
            return row

        return self.run(authority, read)

    def discard_draft(self, authority, draft_id, context_id, expected_revision):
        def discard(conn):
            self.context(conn, authority, context_id)
            row = conn.execute(
                "SELECT * FROM research.draft WHERE id=%s AND owner_id=%s AND context_id=%s "
                "FOR UPDATE",
                (draft_id, authority.account_id, context_id),
            ).fetchone()
            if not row:
                raise ResearchError("NOT_FOUND")
            if str(row["current_revision"]) != str(expected_revision):
                raise ResearchError("CONFLICT", current={"revision": str(row["current_revision"])})
            return conn.execute(
                "UPDATE research.draft_revision SET state='discarded' WHERE draft_id=%s "
                "AND revision=%s AND state='acknowledged' RETURNING *",
                (draft_id, expected_revision),
            ).fetchone()

        return self.run(authority, discard)

    @staticmethod
    def consume_draft(conn, authority, context_id, submitted, job_id):
        """Consume the accepted immutable revision; a newer acknowledged edit survives."""
        if submitted is None:
            return
        row = conn.execute(
            "SELECT r.* FROM research.draft d JOIN research.draft_revision r ON r.draft_id=d.id "
            "WHERE d.id=%s AND d.owner_id=%s AND d.context_id=%s AND r.revision=%s FOR UPDATE "
            "OF d,r",
            (submitted["draftId"], authority.account_id, context_id, submitted["revision"]),
        ).fetchone()
        if not row:
            raise ResearchError("NOT_FOUND")
        if row["content_hash"] != submitted["contentHash"] or row["state"] != "acknowledged":
            raise ResearchError("CONFLICT")
        conn.execute(
            "UPDATE research.draft_revision SET state='consumed',consumed_by=%s WHERE "
            "draft_id=%s AND revision=%s",
            (job_id, submitted["draftId"], submitted["revision"]),
        )
