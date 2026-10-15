"""Account-owned profile, consent and immutable mutation receipts."""

from __future__ import annotations

from uuid import UUID, uuid4

from backend.modules.accounts.control_policy import ControlPolicy
from backend.modules.summarization.guarded_repository import intent_digest
from backend.transactions import Authority, OwnerTransactions, guard
from psycopg.types.json import Jsonb


class ControlRepository:
    def __init__(self, transactions: OwnerTransactions, policy: ControlPolicy):
        policy.require_realm(transactions.profile.realm)
        self.transactions, self.policy = transactions, policy

    @staticmethod
    def replay(conn, account: UUID, kind: str, operation: UUID, intent: dict):
        digest = intent_digest(intent)
        prior = conn.execute(
            "SELECT * FROM accounts.control_receipt WHERE account_id=%s AND kind=%s AND key=%s",
            (account, kind, operation),
        ).fetchone()
        if prior and prior["intent_hash"] != digest:
            raise ValueError("operation identity conflict")
        return digest, prior["outcome"] if prior else None

    @staticmethod
    def record(conn, account, kind, operation, digest, outcome):
        conn.execute(
            "INSERT INTO accounts.control_receipt(account_id,kind,key,intent_hash,outcome) VALUES(%s,%s,%s,%s,%s)",
            (account, kind, operation, digest, Jsonb(outcome)),
        )
        return outcome

    def profile(self, authority: Authority) -> dict:
        def read(conn):
            guard(conn, authority, purpose="account-control")
            row = conn.execute(
                "SELECT id,display_name,profile,profile_revision,lifecycle_revision,role,email "
                "FROM accounts.account WHERE id=%s",
                (authority.account_id,),
            ).fetchone()
            return {
                "accountId": str(row["id"]),
                "displayName": row["display_name"],
                "profile": row["profile"],
                "revision": str(row["profile_revision"]),
                "lifecycleRevision": str(row["lifecycle_revision"]),
                "role": row["role"],
                "email": row["email"],
            }

        return self.transactions.run("accounts", read)

    def consents(self, authority: Authority) -> list[dict]:
        def read(conn):
            guard(conn, authority, purpose="account-control")
            return [
                dict(
                    row, revision=str(row["revision"]), effective_at=row["effective_at"].isoformat()
                )
                for row in conn.execute(
                    "SELECT purpose,granted,revision,effective_at FROM accounts.consent WHERE account_id=%s ORDER BY purpose",
                    (authority.account_id,),
                ).fetchall()
            ]

        return self.transactions.run("accounts", read)

    def update_profile(
        self, authority: Authority, operation: UUID, expected: UUID, changes: dict
    ) -> dict:
        if not changes or set(changes) - {"displayName", "affiliation", "biography"}:
            raise ValueError("unsupported profile change")
        for key, value in changes.items():
            maximum = 256 if key == "displayName" else self.policy.max_value_bytes
            if (
                not isinstance(value, str)
                or len(value.encode()) > maximum
                or (key == "displayName" and not value.strip())
            ):
                raise ValueError("profile value outside policy")
        intent = {"expectedRevision": str(expected), "changes": changes}

        def write(conn):
            guard(conn, authority, purpose="account-control")
            row = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR UPDATE", (authority.account_id,)
            ).fetchone()
            digest, prior = self.replay(conn, authority.account_id, "profile", operation, intent)
            if prior is not None:
                return prior
            if row["profile_revision"] != expected:
                raise ValueError("stale profile revision")
            profile = dict(row["profile"])
            profile.update({key: value for key, value in changes.items() if key != "displayName"})
            revision = uuid4()
            conn.execute(
                "UPDATE accounts.account SET display_name=%s,profile=%s,profile_revision=%s WHERE id=%s",
                (
                    changes.get("displayName", row["display_name"]),
                    Jsonb(profile),
                    revision,
                    authority.account_id,
                ),
            )
            return self.record(
                conn,
                authority.account_id,
                "profile",
                operation,
                digest,
                {
                    "accountId": str(authority.account_id),
                    "revision": str(revision),
                    "displayName": changes.get("displayName", row["display_name"]),
                    "profile": profile,
                    "lifecycleRevision": str(row["lifecycle_revision"]),
                    "email": row["email"],
                    "role": row["role"],
                },
            )

        return self.transactions.run("accounts", write)

    def update_consent(
        self, authority: Authority, operation: UUID, expected: UUID, purpose: str, granted: bool
    ) -> dict:
        if purpose not in ("personalization", "local-research") or type(granted) is not bool:
            raise ValueError("registered consent purpose and decision required")
        intent = {"expectedRevision": str(expected), "purpose": purpose, "granted": granted}

        def write(conn):
            guard(conn, authority, purpose="account-control")
            conn.execute(
                "SELECT id FROM accounts.account WHERE id=%s FOR UPDATE", (authority.account_id,)
            )
            digest, prior = self.replay(conn, authority.account_id, "consent", operation, intent)
            if prior is not None:
                return prior
            row = conn.execute(
                "SELECT * FROM accounts.consent WHERE account_id=%s AND purpose=%s FOR UPDATE",
                (authority.account_id, purpose),
            ).fetchone()
            if not row or row["revision"] != expected:
                raise ValueError("stale consent revision")
            revision, authority_revision = uuid4(), uuid4()
            changed = conn.execute(
                "UPDATE accounts.consent SET granted=%s,revision=%s,effective_at=clock_timestamp() WHERE account_id=%s AND purpose=%s RETURNING effective_at",
                (granted, revision, authority.account_id, purpose),
            ).fetchone()
            conn.execute(
                "UPDATE accounts.account SET authority_revision=%s WHERE id=%s",
                (authority_revision, authority.account_id),
            )
            conn.execute(
                "UPDATE accounts.session SET revoked=true WHERE account_id=%s AND id<>%s",
                (authority.account_id, authority.session_id),
            )
            conn.execute(
                "UPDATE accounts.session SET authority_revision=%s WHERE id=%s",
                (authority_revision, authority.session_id),
            )
            conn.execute(
                "INSERT INTO accounts.consent_obligation(id,account_id,purpose,consent_revision,authority_revision,granted) VALUES(%s,%s,%s,%s,%s,%s)",
                (operation, authority.account_id, purpose, revision, authority_revision, granted),
            )
            return self.record(
                conn,
                authority.account_id,
                "consent",
                operation,
                digest,
                {
                    "consentId": purpose,
                    "accountId": str(authority.account_id),
                    "purposeId": purpose,
                    "decision": "granted" if granted else "revoked",
                    "revision": str(revision),
                    "effectiveAt": changed["effective_at"].isoformat(),
                    "policyRef": self.policy.reference,
                },
            )

        return self.transactions.run("accounts", write)

    def pending_consents(self, *, limit: int = 20, purpose: str | None = None) -> list[dict]:
        if type(limit) is not int or not 1 <= limit <= self.policy.max_page_size:
            raise ValueError("finite consent obligation page required")
        if purpose not in (None, "personalization", "local-research"):
            raise ValueError("unknown consent obligation purpose")
        return self.transactions.run(
            "accounts",
            lambda conn: conn.execute(
                "SELECT * FROM accounts.consent_obligation WHERE disposition='pending' "
                "AND (%s::text IS NULL OR purpose=%s) ORDER BY accepted_at,id LIMIT %s",
                (purpose, purpose, limit),
            ).fetchall(),
        )

    def acknowledge_consent(self, identifier: UUID, revision: UUID, evidence: UUID) -> None:
        def write(conn):
            row = conn.execute(
                "SELECT * FROM accounts.consent_obligation WHERE id=%s FOR UPDATE", (identifier,)
            ).fetchone()
            if (
                not row
                or row["consent_revision"] != revision
                or (row["evidence_ref"] and row["evidence_ref"] != evidence)
            ):
                raise ValueError("consent obligation evidence conflict")
            conn.execute(
                "UPDATE accounts.consent_obligation SET disposition='complete',evidence_ref=%s WHERE id=%s",
                (evidence, identifier),
            )

        self.transactions.run("accounts", write)
