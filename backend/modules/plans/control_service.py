"""U2 policy and administrator control over the existing Usage ledger."""

from __future__ import annotations

from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from docsuri_shared.workspace import wire
from psycopg.types.json import Jsonb

from backend.modules.accounts.control_policy import ControlPolicy
from backend.modules.plans.guarded_repository import GuardedUsageRepository, UsageQuotaExceeded
from backend.modules.summarization.guarded_repository import intent_digest
from backend.transactions import Authority, guard


class ControlUsageService:
    def __init__(self, transactions, policy: ControlPolicy):
        policy.require_realm(transactions.profile.realm)
        self.transactions, self.policy = transactions, policy
        self.repository = GuardedUsageRepository(transactions)

    def _period(self, conn) -> str:
        value = conn.execute(
            "SELECT floor(extract(epoch FROM clock_timestamp())/%s)::bigint AS period",
            (self.policy.period_seconds,),
        ).fetchone()["period"]
        return "u2-period:" + str(value)

    @staticmethod
    def initial_revision(account: UUID) -> UUID:
        return uuid5(NAMESPACE_URL, str(account) + ":assignment-empty:1")

    def assignment(self, actor: Authority, target: UUID) -> dict:
        def read(conn):
            guard(conn, actor, purpose="administration")
            row = conn.execute(
                "SELECT * FROM usage.entitlement WHERE account_id=%s", (target,)
            ).fetchone()
            return {
                "accountId": str(target),
                "revision": str(
                    row["assignment_revision"] if row else self.initial_revision(target)
                ),
                "entitlement": None
                if row is None
                else {
                    "allocation": row["allocation"],
                    "revoked": row["revoked"],
                    "policy": row["policy"],
                    "effectiveAt": row["created_at"].isoformat(),
                },
            }

        return self.transactions.run("usage", read)

    def assign(
        self,
        actor: Authority,
        target: UUID,
        operation: UUID,
        expected: UUID,
        *,
        allocation: int,
        revoked: bool,
        reason: str,
    ) -> dict:
        if (
            type(allocation) is not int
            or not 0 <= allocation <= self.policy.quota
            or type(revoked) is not bool
            or not reason.strip()
            or len(reason.encode()) > 256
        ):
            raise ValueError("finite assignment policy required")
        intent = intent_digest(
            {
                "target": str(target),
                "expectedRevision": str(expected),
                "allocation": allocation,
                "revoked": revoked,
                "reason": reason,
            }
        )

        def write(conn):
            guard(conn, actor, purpose="administration")
            # The target grant is guarded through an accounts-owned narrow
            # status function; app administration never grants operator access.
            if not conn.execute(
                "SELECT accounts.assignment_target_available(%s) AS allowed", (target,)
            ).fetchone()["allowed"]:
                raise PermissionError("assignment target unavailable")
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,24))", (str(target),))
            prior = conn.execute(
                "SELECT * FROM usage.assignment_receipt WHERE actor_id=%s AND key=%s",
                (actor.account_id, operation),
            ).fetchone()
            if prior:
                if prior["intent_hash"] != intent:
                    raise ValueError("assignment operation conflict")
                return prior["outcome"]
            row = conn.execute(
                "SELECT * FROM usage.entitlement WHERE account_id=%s FOR UPDATE", (target,)
            ).fetchone()
            if (row["assignment_revision"] if row else self.initial_revision(target)) != expected:
                raise ValueError("stale assignment revision")
            revision = uuid4()
            assigned = conn.execute(
                "INSERT INTO usage.entitlement(account_id,allocation,policy,revoked,"
                "assignment_revision,period_id) VALUES(%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(account_id) DO UPDATE SET allocation=excluded.allocation,"
                "policy=excluded.policy,revoked=excluded.revoked,"
                "assignment_revision=excluded.assignment_revision,period_id=excluded.period_id,"
                "revision=gen_random_uuid(),created_at=clock_timestamp() RETURNING created_at",
                (target, allocation, self.policy.policy_id, revoked, revision, self._period(conn)),
            ).fetchone()
            outcome = {
                "entitlementId": str(target),
                "accountId": str(target),
                "tierId": "synthetic-free",
                "assignmentSource": "administrative_assignment",
                "policyRef": self.policy.reference,
                "effectiveAt": assigned["created_at"].isoformat(),
                "disposition": "revoked" if revoked else "active",
                "revision": str(revision),
            }
            conn.execute(
                "INSERT INTO usage.assignment_receipt(actor_id,key,target_id,intent_hash,outcome) "
                "VALUES(%s,%s,%s,%s,%s)",
                (actor.account_id, operation, target, intent, Jsonb(outcome)),
            )
            return outcome

        return self.transactions.run("usage", write)

    def records(self, authority: Authority, page: dict, cursor) -> dict:
        limit = page.get("limit", 20)
        if type(limit) is not int or not 1 <= limit <= self.policy.max_page_size:
            raise ValueError("finite ledger page required")

        def read(conn):
            revision = guard(conn, authority, purpose="account-control")
            scope = f"usage-records:{revision}:{limit}:{self.policy.policy_id}"
            position = (
                cursor.decode(authority.account_id, scope, page["cursor"])
                if page.get("cursor")
                else None
            )
            cutoff = (
                datetime.fromisoformat(position["cutoff"])
                if position
                else conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            )
            rows = conn.execute(
                "SELECT * FROM usage.reservation WHERE account_id=%s AND accepted_at<=%s "
                "AND (%s::timestamptz IS NULL OR (accepted_at,id)<(%s::timestamptz,%s::uuid)) "
                "ORDER BY accepted_at DESC,id DESC LIMIT %s",
                (
                    authority.account_id,
                    cutoff,
                    position["time"] if position else None,
                    position["time"] if position else None,
                    position["id"] if position else None,
                    limit + 1,
                ),
            ).fetchall()
            items = rows[:limit]
            next_cursor = (
                cursor.encode(
                    authority.account_id,
                    scope,
                    {
                        "cutoff": cutoff.isoformat(),
                        "time": items[-1]["accepted_at"].isoformat(),
                        "id": str(items[-1]["id"]),
                    },
                )
                if len(rows) > limit
                else None
            )
            return wire.UsageRecordsPage.model_validate(
                {
                    "items": [
                        {
                            "usageRecordId": str(row["id"]),
                            "accountId": str(row["account_id"]),
                            "operation": {
                                "operationId": str(row["operation_id"]),
                                "operationOwner": "PaperAssistance",
                                "inputRevision": row["intent_hash"],
                            },
                            "revision": str(row["revision"]),
                            "periodId": row["period_id"],
                            "policyRef": row["policy_ref"],
                            "disposition": row["disposition"],
                            "quantities": [
                                {"metricId": "paper-assistance", "quantity": row["quantity"]}
                            ],
                            "reasonKey": "accepted-responsibility"
                            if row["disposition"] == "reserved"
                            else "terminal-owner-evidence",
                        }
                        for row in items
                    ],
                    "page": {"nextCursor": next_cursor, "snapshotRevision": cutoff.isoformat()},
                    "appliedLimit": limit,
                    "policyRef": self.policy.reference,
                }
            ).model_dump(mode="json")

        return self.transactions.run("usage", read)

    def reserve(self, authority: Authority, admission: dict) -> dict:
        """Only a registered accepting-owner adapter supplies this bound row."""
        if (
            admission["account_id"] != authority.account_id
            or admission["disposition"] not in ("open", "accepted")
            or admission["quantity"] != 1
            or admission["policy_ref"] != self.policy.reference
        ):
            raise ValueError("bound accepting-owner admission required")

        def write(conn):
            guard(conn, authority)
            row = conn.execute(
                "SELECT * FROM usage.entitlement WHERE account_id=%s FOR UPDATE",
                (authority.account_id,),
            ).fetchone()
            if row is None:
                raise UsageQuotaExceeded("no allocated entitlement")
            prior = conn.execute(
                "SELECT * FROM usage.reservation WHERE operation_id=%s",
                (admission["operation_id"],),
            ).fetchone()
            if prior:
                if (
                    prior["account_id"],
                    prior["intent_hash"],
                    prior["operation_generation"],
                    prior["period_id"],
                ) != (
                    authority.account_id,
                    admission["intent_hash"],
                    admission["generation"],
                    admission["period_id"],
                ):
                    raise ValueError("reservation identity conflict")
                return prior
            if (
                row["revoked"]
                or row["policy"] != self.policy.policy_id
                or admission["period_id"] != self._period(conn)
            ):
                raise UsageQuotaExceeded("current finite assignment unavailable")
            if conn.execute(
                "SELECT 1 FROM usage.rejected_operation WHERE operation_id=%s",
                (admission["operation_id"],),
            ).fetchone():
                raise ValueError("accepting owner closed admission")
            quantity = conn.execute(
                "SELECT coalesce(sum(quantity),0) AS n FROM usage.reservation "
                "WHERE account_id=%s AND period_id=%s AND disposition IN ('reserved','committed')",
                (authority.account_id, admission["period_id"]),
            ).fetchone()["n"]
            if quantity + 1 > row["allocation"]:
                raise UsageQuotaExceeded("finite current period exhausted")
            return conn.execute(
                "INSERT INTO usage.reservation(id,account_id,operation_id,intent_hash,disposition,"
                "operation_generation,period_id,policy_ref,quantity) "
                "VALUES(%s,%s,%s,%s,'reserved',%s,%s,%s,1) RETURNING *",
                (
                    uuid4(),
                    authority.account_id,
                    admission["operation_id"],
                    admission["intent_hash"],
                    admission["generation"],
                    admission["period_id"],
                    Jsonb(self.policy.reference),
                ),
            ).fetchone()

        return self.transactions.run("usage", write)
