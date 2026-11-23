"""AccountAccess's control policies for the two complete realms (U8 plan Step 19; D1,
security-design § 3.1): the composed realm's `u8-synthetic-v1` and production's
`docsuri-production-v1`.

U2's `ControlPolicy` binds only `u2-synthetic-v1` to U2's realm. `CompletePolicy` binds
each complete policy to its one realm and refuses U2's id and every other realm, so
neither the synthetic policies nor production's can run in another's place. It adds D1's
full session lengths by role, both required, and keeps every ceiling and order check of
the built policy (the person's decision of 2026-10-24, "Move, scope tools, test U2").
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from backend.modules.accounts.control_policy import ControlPolicy, PolicyUnavailable

ADMISSIONS = ("maintainer-only", "open")


@dataclass(frozen=True)
class Admission:
    """Who may enter (security-design § 3.5, C02 4.0.0 `AccessAdmission`): a policy input
    the host passes from the profile, never a browser input.

    `maintainer-only` admits only administrators to sign-in. `open` admits every account,
    which with registration closed are the migrated ones. Registration stays closed in
    both until the public-activation evidence is recorded and the maintainer's decision
    opens it (`registration_open`); the policy's account cap then applies."""

    state: str
    registration_open: bool = False

    def __post_init__(self) -> None:
        if self.state not in ADMISSIONS or type(self.registration_open) is not bool:
            raise ValueError("admission outside its vocabulary")
        if self.state == "maintainer-only" and self.registration_open:
            raise ValueError("maintainer-only admission keeps registration closed")

    @classmethod
    def from_profile(cls, profile) -> Admission | None:
        """The production profile's admission; a synthetic profile states none, so its
        realm keeps the built entry rules."""
        if not getattr(profile, "is_production", False):
            return None
        return cls(profile.admission)

    def admits(self, role: str) -> bool:
        return self.state == "open" or role == "administrator"


def remaining_seconds(expires_at: str | dt.datetime, now: dt.datetime) -> int:
    """A session cookie's `Max-Age` under D1: the issued session's remaining length,
    from its `expiresAt` (security-design § 3.1, "Cookies")."""
    if isinstance(expires_at, str):
        expires_at = dt.datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("session times must be aware")
    return max(0, int((expires_at - now).total_seconds()))


# Each complete policy and the one realm it is bound to (C02 4.0.0, A3).
BOUND_REALMS = {
    "u8-synthetic-v1": "service-operations",
    "docsuri-production-v1": "production",
}

# The bound every synthetic policy keeps (U2's finite experiment), field by field.
SYNTHETIC_CEILINGS = {
    "max_accounts": 20, "max_body_bytes": 65536,
    "max_password_bytes": 1024, "max_value_bytes": 4096,
    "max_page_size": 50, "max_scopes": 32, "max_outstanding": 100,
    "session_seconds": 900, "proof_seconds": 300,
    "material_seconds": 60, "cursor_seconds": 300,
    "lease_seconds": 15, "attempt_seconds": 10, "max_attempts": 3,
    "period_seconds": 900, "quota": 3,
    "member_session_seconds": 900, "administrator_session_seconds": 900,
    # Account emails per account a UTC day (U8 plan Step 53(i), L1-71): the composed
    # realm's own value, the realm ledger's 90 places a day.
    "account_mail_per_day": 90,
}
# D1: production's own ceilings. A member's session lasts 12 hours, an administrator's
# 1 hour, a purpose-limited one 15 minutes (`session_seconds`); the account cap is 500
# (NFR1.3). Every other ceiling is the synthetic one.
PRODUCTION_CEILINGS = {
    **SYNTHETIC_CEILINGS,
    "max_accounts": 500,
    "member_session_seconds": 12 * 3600,
    "administrator_session_seconds": 3600,
    # Five account emails per account a UTC day (Step 53(i), L1-71), your choice.
    "account_mail_per_day": 5,
}
CEILINGS = {
    "u8-synthetic-v1": SYNTHETIC_CEILINGS,
    "docsuri-production-v1": PRODUCTION_CEILINGS,
}
ROLES = ("member", "administrator")


@dataclass(frozen=True)
class CompletePolicy(ControlPolicy):
    """One complete realm's account policy.

    `session_seconds` is the purpose-limited session's length (lifecycle status,
    consent-pending). D1's shape adds a full session's length by role:
    `member_session_seconds` (a member who uses a second factor included) and
    `administrator_session_seconds`. The second factor must come within `proof_seconds`
    of the password."""

    member_session_seconds: int | None = None
    administrator_session_seconds: int | None = None
    # Account emails per account a UTC day, every kind together (Step 53(i), L1-71).
    account_mail_per_day: int | None = None

    def __post_init__(self) -> None:
        # Replaces the built check, which binds only U2's policy; every guard it holds
        # is kept below.
        if BOUND_REALMS.get(self.policy_id) != self.realm:
            raise PolicyUnavailable("a policy runs only in the realm it is bound to")
        if self.member_session_seconds is None or self.administrator_session_seconds is None:
            raise ValueError("the complete realms' policies carry D1's lengths by role")
        for name, ceiling in CEILINGS[self.policy_id].items():
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(f"finite policy bound invalid: {name}")
        if self.attempt_seconds >= self.lease_seconds:
            raise ValueError("attempt deadline must precede lease expiry")
        if self.material_seconds > self.proof_seconds:
            raise ValueError("material delivery cannot outlive proof")

    def require_realm(self, realm: str) -> None:
        if realm != self.realm:
            raise PolicyUnavailable("a policy cannot activate another realm")

    def full_session_seconds(self, role: str) -> int:
        """A full session's fixed length by the account's role when it is issued (D1)."""
        if role not in ROLES:
            raise ValueError("unknown account role")
        if role == "administrator":
            return self.administrator_session_seconds
        return self.member_session_seconds

    @property
    def limited_session_seconds(self) -> int:
        """A purpose-limited session's length (lifecycle status, consent-pending)."""
        return self.session_seconds

    @property
    def d1_shaped(self) -> bool:
        """Every complete policy has D1's lengths by role: it carries D1's cookies, D2's
        sign-in limits and the first-sign-in steps."""
        return True

    @property
    def entry_limits(self):
        """D2's three sign-in limits (security-design § 3.2)."""
        from backend.modules.accounts.entry_limits import SIGN_IN_LIMITS

        return SIGN_IN_LIMITS


# The composed realm: D1's shape with the synthetic lengths (every session 15 minutes)
# and every other value U2's.
U8_SYNTHETIC_POLICY = CompletePolicy(
    policy_id="u8-synthetic-v1", realm="service-operations", max_accounts=20,
    max_body_bytes=65536, max_password_bytes=1024, max_value_bytes=4096,
    max_page_size=50, max_scopes=32, max_outstanding=100,
    session_seconds=900, proof_seconds=300, material_seconds=60,
    cursor_seconds=300, lease_seconds=15, attempt_seconds=10,
    max_attempts=3, period_seconds=900, quota=3,
    member_session_seconds=900, administrator_session_seconds=900,
    account_mail_per_day=90,
)


# Production (D1): a member's session 12 hours, an administrator's 1 hour, a
# purpose-limited one 15 minutes, the second factor within 5 minutes and an account cap
# of 500; every other field as in U2's synthetic policy.
PRODUCTION_POLICY = CompletePolicy(
    policy_id="docsuri-production-v1", realm="production", max_accounts=500,
    max_body_bytes=65536, max_password_bytes=1024, max_value_bytes=4096,
    max_page_size=50, max_scopes=32, max_outstanding=100,
    session_seconds=900, proof_seconds=300, material_seconds=60,
    cursor_seconds=300, lease_seconds=15, attempt_seconds=10,
    max_attempts=3, period_seconds=900, quota=3,
    member_session_seconds=12 * 3600, administrator_session_seconds=3600,
    account_mail_per_day=5,
)

# Each complete realm's policy, as `control_policy.for_realm` and the host read them.
COMPLETE_POLICIES = {
    "service-operations": U8_SYNTHETIC_POLICY,
    "production": PRODUCTION_POLICY,
}
