"""Library lifecycle participant; external restore evidence belongs to Operations."""

from psycopg.types.json import Jsonb

from backend.lifecycle_effects import apply_owner_effect


class LibraryLifecycleParticipant:
    scopes = ("live_records",)

    def __init__(self, transactions):
        self.transactions = transactions

    def apply(self, ticket):
        def effect(conn, action, current):
            restriction = conn.execute(
                "SELECT disposition FROM library.restriction WHERE account_id=%s FOR UPDATE",
                (current["account_id"],),
            ).fetchone()
            if action == "reactivate" and restriction and restriction["disposition"] == "erased":
                raise PermissionError("erased library cannot be restored")
            if action == "erase":
                conn.execute(
                    "SELECT library.erase_private_controls(%s,%s,%s,%s,%s)",
                    (
                        current["request_id"],
                        current["account_id"],
                        current["generation"],
                        Jsonb(current["policy_ref"]),
                        current["manifest_revision"],
                    ),
                )
            disposition = {"withdraw": "withdrawn", "erase": "erased", "reactivate": "active"}[
                action
            ]
            conn.execute(
                "INSERT INTO library.restriction(account_id,lifecycle_revision,disposition) "
                "VALUES(%s,%s,%s) ON CONFLICT(account_id) DO UPDATE SET "
                "lifecycle_revision=excluded.lifecycle_revision,disposition=excluded.disposition,"
                "updated_at=clock_timestamp()",
                (current["account_id"], current["lifecycle_revision"], disposition),
            )

        return apply_owner_effect(self.transactions, "library", self.scopes, ticket, effect)
