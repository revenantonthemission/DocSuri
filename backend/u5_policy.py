"""Finite digest allocations; real delivery requires an explicit free allocation.

Owner settings select the calendar zone. Selection, queue and recovery bounds
remain finite; real attempts additionally spend a durable realm-wide allowance
and carry a bounded evidence-retention period (provider receipt). This policy
does not establish external account capacity or authorize a send.
"""

from dataclasses import dataclass

# The approved upper bound for keeping real-send evidence (provider receipt).
# The database enforces the same bound; a policy can choose less, never more.
REAL_EVIDENCE_RETENTION_DAYS_MAX = 30


@dataclass(frozen=True)
class TopicsPolicy:
    policy_id: str = "u5-synthetic-topics"
    revision: str = "1"
    synthetic_only: bool = True
    delivery_timezone: str = "UTC"  # Compatibility only; owner settings select the zone.
    real_send_limit: int = 0
    real_evidence_retention_days: int = 0
    selection_limit: int = 50
    digest_items_max: int = 10
    sends_per_pass: int = 1
    reconcile_batch: int = 10
    orphan_after_seconds: int = 900
    sweep_limit: int = 10
    page_size: int = 50

    def __post_init__(self):
        for name in (
            "selection_limit",
            "digest_items_max",
            "sends_per_pass",
            "reconcile_batch",
            "orphan_after_seconds",
            "sweep_limit",
            "page_size",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"finite positive {name} required")
        if self.sends_per_pass != 1:
            raise ValueError("single-send passes are required")
        if type(self.real_send_limit) is not int or not 0 <= self.real_send_limit <= 100:
            raise ValueError("finite real-send allocation required")
        if self.synthetic_only != (self.real_send_limit == 0):
            raise ValueError("real delivery requires an explicit positive allocation")
        retention = self.real_evidence_retention_days
        if type(retention) is not int or not 0 <= retention <= REAL_EVIDENCE_RETENTION_DAYS_MAX:
            raise ValueError("finite real-send evidence retention required")
        if self.synthetic_only != (retention == 0):
            raise ValueError("real delivery requires an explicit evidence retention period")
        if not self.delivery_timezone:
            raise ValueError("one stated delivery zone required")

    def reference(self) -> dict:
        return {"policyId": self.policy_id, "revision": self.revision}


SYNTHETIC_TOPICS = TopicsPolicy()

# The person's approved bounded demonstration: one real attempt per realm database
# (failures and receipt expiry never replenish it) and 30-day retention of the
# provider receipt. The count is the realm's `topics.send_log_entry` rows with
# `path_kind='real'`, so it is not global: erasing the recipient's account
# cascades those rows away, and a fresh realm starts with its own empty count.
# Either one resets the allocation; an operator must not use either to retry.
# Inert unless an operator composes it with a verified real adapter
# (backend/u5_real_delivery.py).
REAL_DEMONSTRATION_TOPICS = TopicsPolicy(
    policy_id="u5-real-demonstration",
    synthetic_only=False,
    real_send_limit=1,
    real_evidence_retention_days=30,
)
