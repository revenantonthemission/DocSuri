"""Usage-owned reservations and idempotent settlement; no PA table writes."""

from __future__ import annotations

from uuid import UUID, uuid4

from backend.transactions import Authority, OwnerTransactions, guard


class UsageQuotaExceeded(ValueError):
    """A definite owner decision; never used for an uncertain commit."""


class GuardedUsageRepository:
    def __init__(self, transactions: OwnerTransactions):
        self.transactions = transactions

    def reserve(self, authority: Authority, operation: UUID, intent_hash: str) -> dict:
        def write(conn):
            guard(conn, authority)
            policy = conn.execute(
                "SELECT * FROM usage.entitlement WHERE account_id=%s FOR UPDATE",
                (authority.account_id,),
            ).fetchone()
            if not policy:
                raise ValueError("usage participant not initialized")
            if conn.execute(
                "SELECT 1 FROM usage.rejected_operation WHERE operation_id=%s", (operation,)
            ).fetchone():
                raise ValueError("original admission was rejected")
            previous = conn.execute(
                "SELECT * FROM usage.reservation WHERE operation_id=%s", (operation,)
            ).fetchone()
            if previous:
                if (
                    previous["account_id"] != authority.account_id
                    or previous["intent_hash"] != intent_hash
                ):
                    raise ValueError("reservation operation conflict")
                return previous
            used = conn.execute(
                "SELECT count(*) AS count FROM usage.reservation WHERE account_id=%s AND "
                "disposition IN ('reserved','committed')",
                (authority.account_id,),
            ).fetchone()["count"]
            if used >= policy["allocation"]:
                raise UsageQuotaExceeded("finite experiment quota exhausted")
            return conn.execute(
                "INSERT INTO usage.reservation(id,account_id,operation_id,intent_hash,"
                "disposition) VALUES(%s,%s,%s,%s,'reserved') RETURNING *",
                (uuid4(), authority.account_id, operation, intent_hash),
            ).fetchone()

        return self.transactions.run("usage", write)

    def reject_operation(self, proof: dict) -> None:
        """Trusted PA no-acceptance proof; fence late reserve and release atomically.

        The entitlement lock serializes reservation and rejection. This does not
        need a live browser session: it completes an existing owner obligation.
        """
        account, operation = UUID(proof["accountId"]), UUID(proof["operationId"])

        def write(conn):
            if not conn.execute(
                "SELECT 1 FROM usage.entitlement WHERE account_id=%s FOR UPDATE", (account,)
            ).fetchone():
                raise ValueError("usage participant not initialized")
            old = conn.execute(
                "SELECT * FROM usage.rejected_operation WHERE operation_id=%s", (operation,)
            ).fetchone()
            expected = (account, proof["intentHash"], proof["proofHash"])
            if old and (old["account_id"], old["intent_hash"], old["proof_hash"]) != expected:
                raise ValueError("rejection identity conflict")
            reservation = conn.execute(
                "SELECT * FROM usage.reservation WHERE operation_id=%s FOR UPDATE", (operation,)
            ).fetchone()
            if reservation:
                if (reservation["account_id"], reservation["intent_hash"]) != expected[:2]:
                    raise ValueError("reservation does not match rejected input")
                if reservation["disposition"] == "committed":
                    raise ValueError("accepted accounting cannot be rejected")
                if (
                    reservation["disposition"] == "released"
                    and reservation["settlement_hash"] != proof["proofHash"]
                ):
                    raise ValueError("settlement conflict")
                if reservation["disposition"] == "reserved":
                    conn.execute(
                        "UPDATE usage.reservation SET disposition='released',settlement_key=%s,"
                        "settlement_hash=%s,revision=gen_random_uuid() WHERE id=%s",
                        (uuid4(), proof["proofHash"], reservation["id"]),
                    )
            if not old:
                conn.execute(
                    "INSERT INTO usage.rejected_operation VALUES(%s,%s,%s,%s)",
                    (operation, *expected),
                )

        self.transactions.run("usage", write)

    def settle(
        self, reservation: UUID, operation: UUID, *, disposition: str, proof_hash: str
    ) -> dict:
        """Trusted PA terminal/rejection evidence only; no timeout-based release.

        Revocation does not erase a previously accepted accounting obligation.
        The business coordinator validates the PA proof before this owner call.
        """
        if disposition not in ("committed", "released") or len(proof_hash) != 64:
            raise ValueError("terminal accounting evidence required")

        def write(conn):
            row = conn.execute(
                "SELECT * FROM usage.reservation WHERE id=%s FOR UPDATE", (reservation,)
            ).fetchone()
            if not row or row["operation_id"] != operation:
                raise ValueError("reservation identity mismatch")
            if row["disposition"] != "reserved":
                if row["disposition"] != disposition or row["settlement_hash"] != proof_hash:
                    raise ValueError("settlement conflict")
            else:
                row = conn.execute(
                    "UPDATE usage.reservation SET disposition=%s,settlement_key=%s,"
                    "settlement_hash=%s,revision=gen_random_uuid() WHERE id=%s RETURNING *",
                    (disposition, uuid4(), proof_hash, reservation),
                ).fetchone()
            return {
                "reservationId": str(row["id"]),
                "operationId": str(row["operation_id"]),
                "disposition": row["disposition"],
                "settlementId": str(row["settlement_key"]),
                "revision": str(row["revision"]),
            }

        return self.transactions.run("usage", write)

    def current(self, authority: Authority) -> dict:
        def read(conn):
            guard(conn, authority)
            policy = conn.execute(
                "SELECT allocation,policy,revision FROM usage.entitlement WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()
            if not policy:
                raise ValueError("usage participant not initialized")
            rows = conn.execute(
                "SELECT disposition,count(*) AS count FROM usage.reservation WHERE "
                "account_id=%s GROUP BY disposition",
                (authority.account_id,),
            ).fetchall()
            return dict(policy, counts={row["disposition"]: row["count"] for row in rows})

        return self.transactions.run("usage", read)

    def reservation(self, authority: Authority, operation: UUID) -> dict | None:
        """Reconcile a known operation without creating or releasing capacity."""

        def read(conn):
            guard(conn, authority)
            return conn.execute(
                "SELECT * FROM usage.reservation WHERE account_id=%s AND operation_id=%s",
                (authority.account_id, operation),
            ).fetchone()

        return self.transactions.run("usage", read)
