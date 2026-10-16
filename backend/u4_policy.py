"""Finite synthetic research allocations; unresolved real-data policy stays shut."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchPolicy:
    policy_id: str = "u4-synthetic-research"
    revision: str = "1"
    synthetic_only: bool = True
    durable_drafts: bool = False
    private_attachments: bool = False
    upload_bytes: int = 2_097_152
    text_bytes: int = 32_768
    queue_depth: int = 16
    concurrency: int = 1
    retries: int = 2
    lease_seconds: int = 30
    artifact_seconds: int = 3600
    page_size: int = 50

    def __post_init__(self):
        for name in (
            "upload_bytes",
            "text_bytes",
            "queue_depth",
            "concurrency",
            "retries",
            "lease_seconds",
            "artifact_seconds",
            "page_size",
        ):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"finite positive {name} required")
        if not self.synthetic_only or self.concurrency != 1:
            raise ValueError("only the bounded serial synthetic profile is enabled")

    def reference(self) -> dict:
        return {"policyId": self.policy_id, "revision": self.revision}


SYNTHETIC_RESEARCH = ResearchPolicy()
