"""Finite U2 experiment policy; never a default for public activation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


class PolicyUnavailable(RuntimeError):
    """The required purpose-specific operating evidence is not installed."""


@dataclass(frozen=True)
class ControlPolicy:
    policy_id: str
    realm: Literal["account-controls"]
    max_accounts: int
    max_body_bytes: int
    max_password_bytes: int
    max_value_bytes: int
    max_page_size: int
    max_scopes: int
    max_outstanding: int
    session_seconds: int
    proof_seconds: int
    material_seconds: int
    cursor_seconds: int
    lease_seconds: int
    attempt_seconds: int
    max_attempts: int
    period_seconds: int
    quota: int

    def __post_init__(self) -> None:
        if self.policy_id != "u2-synthetic-v1" or self.realm != "account-controls":
            raise PolicyUnavailable("only the isolated synthetic policy is bound")
        limits = {
            "max_accounts": 20, "max_body_bytes": 65536,
            "max_password_bytes": 1024, "max_value_bytes": 4096,
            "max_page_size": 50, "max_scopes": 32, "max_outstanding": 100,
            "session_seconds": 900, "proof_seconds": 300,
            "material_seconds": 60, "cursor_seconds": 300,
            "lease_seconds": 15, "attempt_seconds": 10, "max_attempts": 3,
            "period_seconds": 900, "quota": 3,
        }
        for name, ceiling in limits.items():
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(f"finite synthetic bound invalid: {name}")
        if self.attempt_seconds >= self.lease_seconds:
            raise ValueError("attempt deadline must precede lease expiry")
        if self.material_seconds > self.proof_seconds:
            raise ValueError("material delivery cannot outlive proof")

    def require_realm(self, realm: str) -> None:
        if realm != self.realm:
            raise PolicyUnavailable("synthetic policy cannot activate another realm")

    @property
    def reference(self) -> dict[str, str]:
        return {"policyId": self.policy_id, "revision": "1"}


SYNTHETIC_POLICY = ControlPolicy(
    policy_id="u2-synthetic-v1", realm="account-controls", max_accounts=20,
    max_body_bytes=65536, max_password_bytes=1024, max_value_bytes=4096,
    max_page_size=50, max_scopes=32, max_outstanding=100,
    session_seconds=900, proof_seconds=300, material_seconds=60,
    cursor_seconds=300, lease_seconds=15, attempt_seconds=10,
    max_attempts=3, period_seconds=900, quota=3,
)


def public_evidence() -> dict[str, str]:
    """Safe capability reasons; synthetic proofs never clear these real gates."""
    return {
        "credentials": "G1-policy-unresolved",
        "google": "G2-provider-evidence-unresolved",
        "orcid": "G2-provider-evidence-unresolved",
        "email": "G2-delivery-evidence-unresolved",
        "mfa-recovery": "G1-recovery-policy-unresolved",
        "lifecycle": "G3-continuity-retention-unresolved",
        "public-quota": "G6-policy-unresolved",
        "public-capacity": "G7-capacity-unresolved",
    }
