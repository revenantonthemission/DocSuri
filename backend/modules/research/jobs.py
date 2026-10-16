"""Durable acceptance and read-only rediscovery in the research owner store."""

from uuid import uuid4

from psycopg.types.json import Jsonb

from .errors import ResearchError
from .repository import ResearchRepository, digest


class ResearchJobs(ResearchRepository):
    def accept(
        self, authority, *, kind, operation_key, value, usage_id, queue_limit=16, operation_id=None
    ):
        """Internal acceptance only; mounted dispatch remains gated on codec readiness.

        The caller supplies the UsageEntitlements reservation identity. Acceptance,
        submitted-draft consumption and dispatch obligation commit together.
        """
        input_hash = digest(value)
        scope = value["scope"]

        def accept(conn):
            if operation_id is not None:
                admission = conn.execute(
                    "SELECT * FROM research.admission WHERE operation_id=%s AND owner_id=%s "
                    "FOR UPDATE",
                    (operation_id, authority.account_id),
                ).fetchone()
                if (
                    not admission
                    or admission["state"] == "closed"
                    or admission["input_hash"] != input_hash
                ):
                    raise ResearchError("CONFLICT")
                if admission["state"] == "prepared" and conn.execute(
                    "SELECT %s<=clock_timestamp() AS expired", (admission["accept_before"],)
                ).fetchone()["expired"]:
                    raise ResearchError("CONFLICT")
            self.context(conn, authority, scope["contextId"])
            session_id = value.get("sessionId")
            if session_id:
                session = self.session(conn, authority, session_id)
                if str(session["context_id"]) != scope["contextId"]:
                    raise ResearchError("NOT_FOUND")
                # Each new turn chooses its own authorized source scope. The
                # session binds owner/context; accepted job snapshots stay immutable.
            prior = conn.execute(
                "SELECT * FROM research.job WHERE owner_id=%s AND operation_key=%s FOR UPDATE",
                (authority.account_id, operation_key),
            ).fetchone()
            if prior:
                if prior["input_hash"] != input_hash or prior["kind"] != kind:
                    raise ResearchError("IDEMPOTENCY_CONFLICT")
                return prior
            count = conn.execute(
                "SELECT count(*) AS count FROM research.job j JOIN research.admission a ON "
                "a.operation_id=j.id "
                "WHERE a.state='accepted' AND j.state IN ('accepted','running','cancel_requested')"
            ).fetchone()["count"]
            if count >= queue_limit:
                raise ResearchError("CAPACITY_EXHAUSTED")
            row = conn.execute(
                "INSERT INTO research.job(id,owner_id,context_id,session_id,authority_session,k"
                "ind,operation_key,input_hash,input,scope,policy,usage_id) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (
                    operation_id or uuid4(),
                    authority.account_id,
                    scope["contextId"],
                    session_id,
                    authority.session_id,
                    kind,
                    operation_key,
                    input_hash,
                    Jsonb(value),
                    Jsonb(scope),
                    Jsonb(value["policy"]),
                    usage_id,
                ),
            ).fetchone()
            self.consume_draft(
                conn, authority, scope["contextId"], value.get("submittedDraft"), row["id"]
            )
            conn.execute("INSERT INTO research.dispatch(job_id) VALUES(%s)", (row["id"],))
            if operation_id is not None:
                conn.execute(
                    "UPDATE research.admission SET state='accepted' WHERE operation_id=%s",
                    (operation_id,),
                )
            return row

        return self.run(authority, accept)

    def read_job(self, authority, job_id, context_id, kind):
        def read(conn):
            self.context(conn, authority, context_id)
            row = conn.execute(
                "SELECT * FROM research.job WHERE id=%s AND owner_id=%s AND context_id=%s AND "
                "kind=%s",
                (job_id, authority.account_id, context_id, kind),
            ).fetchone()
            if not row:
                raise ResearchError("NOT_FOUND")
            if row["session_id"]:
                self.session(conn, authority, row["session_id"])
            return row

        return self.run(authority, read)

    def cancel(self, authority, job_id, context_id, expected_revision):
        def cancel(conn):
            self.context(conn, authority, context_id)
            row = conn.execute(
                "SELECT * FROM research.job WHERE id=%s AND owner_id=%s AND context_id=%s AND "
                "kind='novelty-analysis' FOR UPDATE",
                (job_id, authority.account_id, context_id),
            ).fetchone()
            if not row:
                raise ResearchError("NOT_FOUND")
            if str(row["revision"]) != str(expected_revision):
                raise ResearchError("CONFLICT", current={"revision": str(row["revision"])})
            if row["state"] not in {"accepted", "running"}:
                return row
            return conn.execute(
                "UPDATE research.job SET state='cancel_requested',revision=revision+1,seq=seq+1"
                " WHERE id=%s RETURNING *",
                (job_id,),
            ).fetchone()

        return self.run(authority, cancel)

    def read_artifact(self, authority, reference):
        def read(conn):
            row = conn.execute(
                "SELECT a.*,j.session_id FROM research.artifact a JOIN research.job j ON "
                "j.id=a.job_id "
                "WHERE a.id=%s AND a.owner_id=%s",
                (reference["artifactId"], authority.account_id),
            ).fetchone()
            if not row:
                raise ResearchError("NOT_FOUND")
            self.context(conn, authority, row["context_id"])
            if row["session_id"]:
                self.session(conn, authority, row["session_id"])
            if (
                str(row["revision"]) != str(reference["revision"])
                or row["content_hash"] != reference["contentHash"]
            ):
                raise ResearchError("CONFLICT")
            expired = conn.execute(
                "SELECT %s <= clock_timestamp() AS expired", (row["expires_at"],)
            ).fetchone()["expired"]
            return dict(
                row,
                availability="expired"
                if expired and row["availability"] == "ready"
                else row["availability"],
            )

        return self.run(authority, read)

    def expire_artifacts(self):
        return self.transactions.run(
            "research",
            lambda conn: conn.execute(
                "UPDATE research.artifact SET availability='expired',eligibility_revision=eligi"
                "bility_revision+1 "
                "WHERE availability='ready' AND expires_at<=clock_timestamp() RETURNING id"
            ).fetchall(),
        )
