"""TopicsDigests lifecycle participant; writes only its own tables (BR4.3).

Withdrawal unsubscribes the account's topics and drops queued (prepared) work;
an in-flight sending run finishes its single attempt and records its outcome
normally (BR4.1). Erasure removes the account's topics and every digest fact
through the owner-scoped erasure function; reactivation has nothing to restore
because erasure leaves no rows behind. Disposition evidence is written by the
shared `apply_owner_effect` contract, exactly like every other participant.
"""

from psycopg.types.json import Jsonb

from backend.lifecycle_effects import apply_owner_effect


class TopicsDigestsLifecycleParticipant:
    scopes = ("live_records", "pending_work")

    def __init__(self, transactions):
        self.transactions = transactions

    def apply(self, ticket):
        def effect(conn, action, current):
            account = current["account_id"]
            if action == "reactivate":
                return
            if action == "withdraw":
                conn.execute(
                    "UPDATE topics.followed_topic SET status='unsubscribed',updated_at="
                    "clock_timestamp() WHERE account_id=%s AND status='active'",
                    (account,),
                )
                conn.execute(
                    "UPDATE topics.digest_run SET state='discarded',updated_at="
                    "clock_timestamp() WHERE topic_id IN "
                    "(SELECT id FROM topics.followed_topic WHERE account_id=%s) "
                    "AND state='prepared'",
                    (account,),
                )
                return
            if current["scope"] == "pending_work":
                conn.execute(
                    "UPDATE topics.digest_run SET state='discarded',updated_at="
                    "clock_timestamp() WHERE topic_id IN "
                    "(SELECT id FROM topics.followed_topic WHERE account_id=%s) "
                    "AND state='prepared'",
                    (account,),
                )
                return
            if action == "erase":
                conn.execute(
                    "SELECT topics.erase_private_controls(%s,%s,%s,%s,%s)",
                    (
                        current["request_id"],
                        account,
                        current["generation"],
                        Jsonb(current["policy_ref"]),
                        current["manifest_revision"],
                    ),
                )

        return apply_owner_effect(self.transactions, "topics", self.scopes, ticket, effect)
