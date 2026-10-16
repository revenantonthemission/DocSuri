"""Research admission fencing around the separate UsageEntitlements owner."""

from uuid import NAMESPACE_URL, uuid5

from backend.transactions import UnknownCommit

from .errors import ResearchError
from .repository import ResearchRepository, digest


class ResearchAdmission(ResearchRepository):
    def prepare(self, authority, key, value):
        operation = uuid5(NAMESPACE_URL, f"ResearchWorkspace:{authority.account_id}:{key}")
        input_hash = digest(value)

        def prepare(conn):
            conn.execute(
                "INSERT INTO research.admission(operation_id,owner_id,operation_key,input_hash)"
                " VALUES(%s,%s,%s,%s) ON CONFLICT(operation_id) DO "
                "NOTHING",
                (operation, authority.account_id, key, input_hash),
            )
            row = conn.execute(
                "SELECT * FROM research.admission WHERE operation_id=%s FOR UPDATE", (operation,)
            ).fetchone()
            if row["input_hash"] != input_hash:
                raise ResearchError("IDEMPOTENCY_CONFLICT")
            if row["state"] == "closed":
                raise ResearchError("CONFLICT")
            return row

        return self.run(authority, prepare)

    def close(self, authority, operation):
        def close(conn):
            row = conn.execute(
                "SELECT * FROM research.admission WHERE operation_id=%s AND owner_id=%s FOR UPDATE",
                (operation, authority.account_id),
            ).fetchone()
            if not row or row["state"] == "accepted":
                raise ResearchError("CONFLICT")
            conn.execute(
                "UPDATE research.admission SET state='closed' WHERE operation_id=%s", (operation,)
            )
            proof = {
                "accountId": str(authority.account_id),
                "operationId": str(operation),
                "intentHash": row["input_hash"],
            }
            return dict(proof, proofHash=digest(dict(proof, state="closed")))

        return self.run(authority, close)

    def accept_with_usage(self, authority, key, value, kind, usage, jobs, *, queue_limit):
        admission = self.prepare(authority, key, value)
        operation = admission["operation_id"]
        try:
            reservation = usage.reserve(authority, operation, admission["input_hash"])
            return jobs.accept(
                authority,
                kind=kind,
                operation_key=key,
                value=value,
                usage_id=reservation["id"],
                operation_id=operation,
                queue_limit=queue_limit,
            )
        except UnknownCommit:
            # Preserve both obligations: a retry resolves this exact admission.
            raise
        except (ResearchError, ValueError):
            proof = self.close(authority, operation)
            usage.reject_operation(proof)
            raise
