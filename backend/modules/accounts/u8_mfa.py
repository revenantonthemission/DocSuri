"""AccountAccess's second factor in the two complete realms (U8 plan Step 19; D1).

`CompleteMfaService` is U2's `ControlMfaService` with D1's parts (the person's decision
of 2026-10-24, "Move, scope tools, test U2"):

- admission (security-design § 3.5) again before the second factor issues a full
  session, and that session's fixed length by role from the composition's clock;
- `setup=True` on the three enrolment calls runs them through `SetupEnrolment`: an
  administrator's 15-minute setup-only session (purpose `mfa`) may enrol the second
  factor, and only that, and confirming the factor ends the session.

Both refuse an entry without a first sign-in, so they never run in U2's realm.
"""

from __future__ import annotations

from uuid import UUID

from backend.modules.accounts.services.control_mfa import ControlMfaService
from backend.transactions import Authority

_HOOKS = ("_reauthenticate", "_authorize", "_confirmed", "_admit_continuation",
          "_full_session")


def _require_complete_entry(entry) -> None:
    if any(not callable(getattr(ControlMfaService, hook, None)) for hook in _HOOKS):
        raise TypeError("U2's ControlMfaService lacks one of its hooks")
    if getattr(entry, "first_sign_in", None) is None:
        raise PermissionError("the complete second factor needs the complete entry")


class SetupEnrolment(ControlMfaService):
    """Enrolment under an administrator's setup-only session: the setup session's check
    replaces the full-session guard, and the confirmed factor ends that session."""

    def __init__(self, entry):
        _require_complete_entry(entry)
        super().__init__(entry)

    def _reauthenticate(self, authority: Authority, password: str) -> None:
        self.entry.first_sign_in.reauthenticate_setup(authority, password)

    def _authorize(self, conn, authority: Authority):
        return self.entry.first_sign_in.check_setup(conn, authority)

    def _confirmed(self, conn, authority: Authority) -> None:
        # The setup-only session ends with the enrolment; the next sign-in meets the new
        # factor and issues the full administrator session.
        conn.execute(
            "UPDATE accounts.session SET revoked=true WHERE id=%s AND account_id=%s",
            (authority.session_id, authority.account_id),
        )


class CompleteMfaService(ControlMfaService):
    def __init__(self, entry):
        _require_complete_entry(entry)
        super().__init__(entry)
        self.setup = SetupEnrolment(entry)

    def begin(
        self, authority: Authority, password: str, operation: UUID, *, setup: bool = False
    ) -> dict:
        if setup:
            return self.setup.begin(authority, password, operation)
        return super().begin(authority, password, operation)

    def material(
        self, authority: Authority, identifier: UUID, delivery: str, *, setup: bool = False
    ) -> dict:
        if setup:
            return self.setup.material(authority, identifier, delivery)
        return super().material(authority, identifier, delivery)

    def confirm(
        self, authority: Authority, identifier: UUID, code: str, operation: UUID, *,
        setup: bool = False,
    ) -> dict:
        if setup:
            return self.setup.confirm(authority, identifier, code, operation)
        return super().confirm(authority, identifier, code, operation)

    def _admit_continuation(self, account: dict) -> None:
        # Admission again before the full session (security-design § 3.5).
        self.entry.require_admitted(account)

    def _full_session(self, conn, account: dict, challenge: UUID) -> dict:
        # D1: the full session's fixed length by role, from the composition's clock.
        return conn.execute(
            "UPDATE accounts.session SET purpose='full_session',mfa_at=clock_timestamp(),"
            "expires_at=%s::timestamptz+(%s*interval '1 second') WHERE id=%s RETURNING *",
            (
                self.entry.issue_time(),
                self.policy.full_session_seconds(account["role"]),
                challenge,
            ),
        ).fetchone()
