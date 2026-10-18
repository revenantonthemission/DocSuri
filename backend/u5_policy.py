"""Finite digest allocations; real delivery requires an explicit free allocation.

Owner settings select the calendar zone. Selection, queue and recovery bounds
remain finite; real attempts additionally spend a durable realm-wide allowance.
This policy does not establish external account capacity or authorize a send.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TopicsPolicy:
    policy_id: str = "u5-synthetic-topics"
    revision: str = "1"
    synthetic_only: bool = True
    delivery_timezone: str = "UTC"  # Compatibility only; owner settings select the zone.
    real_send_limit: int = 0
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
        if not self.delivery_timezone:
            raise ValueError("one stated delivery zone required")

    def reference(self) -> dict:
        return {"policyId": self.policy_id, "revision": self.revision}


SYNTHETIC_TOPICS = TopicsPolicy()
