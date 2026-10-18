"""Finite synthetic digest allocations; unresolved real-data policy stays shut.

One stated delivery zone keeps every window bound and day boundary in one
comparable timezone (BR1.2: timezone ambiguity is resolved by one stated zone,
never by mixed-zone comparison). The recorded values are the bounded limits the
readiness evidence names: selection budget, digest size and recovery bounds.
No paid provider is part of this policy.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TopicsPolicy:
    policy_id: str = "u5-synthetic-topics"
    revision: str = "1"
    synthetic_only: bool = True
    delivery_timezone: str = "Asia/Seoul"
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
        if not self.synthetic_only or self.sends_per_pass != 1:
            raise ValueError("only the bounded single-send synthetic profile is enabled")
        if not self.delivery_timezone:
            raise ValueError("one stated delivery zone required")

    def reference(self) -> dict:
        return {"policyId": self.policy_id, "revision": self.revision}


SYNTHETIC_TOPICS = TopicsPolicy()
