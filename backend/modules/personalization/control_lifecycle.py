"""Explicit Personalization live, derived and pending-work lifecycle scopes."""

from psycopg.types.json import Jsonb

from backend.lifecycle_effects import apply_owner_effect


class PersonalizationLifecycleParticipant:
    scopes = ("live_records", "derived_artifacts", "pending_work")

    def __init__(self, transactions):
        self.transactions = transactions

    def apply(self, ticket):
        def effect(conn, action, current):
            owner = current["account_id"]
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,22))", (str(owner),))
            if action != "erase":
                # AccountAccess already gates all publication/processing. Retained
                # explicit state is not reconstructed by withdraw/reactivate.
                return
            if current["scope"] == "live_records":
                conn.execute(
                    "SELECT personalization.erase_private_controls(%s,%s,%s,%s,%s)",
                    (
                        current["request_id"],
                        owner,
                        current["generation"],
                        Jsonb(current["policy_ref"]),
                        current["manifest_revision"],
                    ),
                )
            elif current["scope"] == "derived_artifacts":
                conn.execute("DELETE FROM personalization.behavior WHERE account_id=%s", (owner,))
                conn.execute("DELETE FROM personalization.projection WHERE account_id=%s", (owner,))
            else:
                conn.execute(
                    "UPDATE personalization.reset_scope s SET generation=generation+1,"
                    "lease_until=NULL,attempts=3,disposition='blocked',reason_key='account-erased',"
                    "updated_at=clock_timestamp() FROM personalization.reset_responsibility r "
                    "WHERE s.reset_id=r.id AND r.account_id=%s AND s.disposition<>'complete'",
                    (owner,),
                )
                conn.execute(
                    "UPDATE personalization.reset_responsibility "
                    "SET status_revision=status_revision+1,disposition='blocked',"
                    "reason_key='account-erased' WHERE account_id=%s AND disposition<>'complete'",
                    (owner,),
                )

        return apply_owner_effect(self.transactions, "personalization", self.scopes, ticket, effect)
