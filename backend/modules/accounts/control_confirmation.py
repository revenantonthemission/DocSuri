"""Finite owner/session-bound confirmations for destructive settings controls."""

from __future__ import annotations

from uuid import UUID, uuid4

from backend.modules.summarization.guarded_repository import intent_digest
from backend.transactions import Authority, guard
from psycopg.types.json import Jsonb


class ResetConfirmationService:
    def __init__(self, transactions, policy, entry):
        policy.require_realm(transactions.profile.realm)
        self.transactions, self.policy, self.entry = transactions, policy, entry

    def prepare(
        self,
        authority: Authority,
        operation: UUID,
        *,
        action: str,
        expected: UUID,
        proof: str,
    ) -> dict:
        if action not in ("delete_behavior", "reset_profile"):
            raise ValueError("invalid reset action")
        self.entry.reauthenticate(authority, proof)
        fingerprint = intent_digest(
            {"action": action, "expected": str(expected), "policy": self.policy.reference}
        )

        def write(conn):
            revision = guard(conn, authority, purpose="account-control")
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,26))",
                (str(authority.account_id),),
            )
            previous = conn.execute(
                "SELECT * FROM accounts.reset_confirmation WHERE account_id=%s AND prepare_key=%s",
                (authority.account_id, operation),
            ).fetchone()
            if previous:
                if (
                    previous["intent_hash"] != fingerprint
                    or previous["session_id"] != authority.session_id
                    or previous["authority_revision"] != revision
                ):
                    raise ValueError("confirmation operation conflict")
                return previous["public_value"]
            pending = conn.execute(
                "SELECT count(*) AS n FROM accounts.reset_confirmation WHERE account_id=%s "
                "AND consumed_operation IS NULL AND expires_at>clock_timestamp()",
                (authority.account_id,),
            ).fetchone()["n"]
            if pending >= self.policy.max_outstanding:
                raise ValueError("finite confirmation limit")
            identifier = uuid4()
            expiry = conn.execute(
                "SELECT clock_timestamp()+(%s*interval '1 second') AS expiry",
                (self.policy.proof_seconds,),
            ).fetchone()["expiry"]
            value = {
                "confirmationRef": str(identifier),
                "action": action,
                "revision": str(expected),
                "expiresAt": expiry.isoformat(),
            }
            conn.execute(
                "INSERT INTO accounts.reset_confirmation(id,account_id,session_id,authority_revision,"
                "action,settings_revision,policy_ref,prepare_key,intent_hash,expires_at,public_value) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    identifier,
                    authority.account_id,
                    authority.session_id,
                    revision,
                    action,
                    expected,
                    Jsonb(self.policy.reference),
                    operation,
                    fingerprint,
                    expiry,
                    Jsonb(value),
                ),
            )
            return value

        return self.transactions.run("accounts", write)
