"""AccountAccess's `importAccount` and `importIdentityLink` operations (U8 plan Step 31; A4,
BR8.2, BR8.5, BR8.13, BR8.14).

Under trusted composition authority only, never a browser route. The migration tool
hands one v1 account or identity link as A4's envelope (`AccountImport`,
`IdentityLinkImport`) with its derived target identity, and AccountAccess decides by its
own rules before its repository writes (Step 7, `repository/imports.py`):

- **State** (BR8.13): a deactivated or pending-deletion account is `closed-in-v1` and
  never active; a pending one is `unverified-in-v1`; a locked one is `locked-in-v1`,
  unless your decision maps it to an import that must reset its password
  (`import-reset-required`).
- **Email** (BR8.14): none is `no-email`; it is stored lower-case, and one an existing
  account already holds (`email-taken`) is `email-case-conflict`.
- **Role**: v1's `user` is a member and `admin` an administrator.
- **Credentials** (BR8.5): v1's Argon2id verifier is carried unchanged, since v1 and v2
  verify with the same Argon2id hasher; a provider-only account (v1's `!`) carries none
  and stores the fixed placeholder no verifier accepts; anything else is marked
  reset-required. No plaintext, pepper or re-hash is ever introduced.
- **Display name**: v1 has none and v2 requires one (`required-field-without-source`):
  only the name your mapping rule derives is stored.
- **Links**: an unconfirmed v1 link is `unconfirmed-link`; a second link of one provider
  is `duplicate-provider-link`; a link whose account was not imported is
  `dependency-not-migrated`.

Each answers A4's `ImportOutcome`, with its source key and target identity.
"""

from __future__ import annotations

import datetime as dt
from uuid import UUID

from backend.import_parity import outcome, stored_digest

from ..repository.imports import AccountImports

STATES = ("active", "pending", "locked", "deactivated", "pending_deletion")
STATE_REASONS = {
    "pending": "unverified-in-v1", "locked": "locked-in-v1",
    "deactivated": "closed-in-v1", "pending_deletion": "closed-in-v1",
}
ROLES = {"user": "member", "admin": "administrator"}
PROVIDER_ONLY = "!"
RESET_RULE = "import-reset-required"
# The owner's refusal keys and the misfit reasons they are (the brief's mapping).
REFUSAL_REASONS = {"email-taken": "email-case-conflict"}


def carried_verifier(password_hash: str | None) -> tuple[str | None, bool]:
    """The verifier carried unchanged and whether a reset is required (BR8.5)."""
    from backend.modules.accounts.password import get_password_hasher

    if password_hash in (None, PROVIDER_ONLY):
        return None, False
    if not isinstance(password_hash, str) or not password_hash.startswith("$argon2id$"):
        return None, True
    try:
        get_password_hasher().check_needs_rehash(password_hash)
    except Exception:  # noqa: BLE001 - a hash the verifier cannot read is not carried
        return None, True
    return password_hash, False


def _refused(target: UUID, reason: str) -> dict:
    return outcome("refused", stored_digest({"account": str(target), "refused": reason}),
                   reason=reason)


class V1AccountImport:
    def __init__(self, transactions):
        self.repository = AccountImports(transactions)

    def import_account(self, target_id: UUID, *, source_key: str, email: str | None,
                       email_verified: bool, password_verifier: str | None, state: str,
                       role: str, created_at: dt.datetime, display_name: str | None,
                       mapping: frozenset[str] = frozenset()) -> dict:
        """A4's `importAccount`; `mapping` holds the rules your decisions approved."""
        if state not in STATES or role not in ROLES:
            raise ValueError("account import outside A4's envelope")
        result = self._decide(target_id, email=email, email_verified=email_verified,
                              password_verifier=password_verifier, state=state, role=role,
                              created_at=created_at, display_name=display_name,
                              mapping=mapping)
        return {"sourceKey": source_key, "targetId": str(target_id), **result}

    def _decide(self, target_id, *, email, email_verified, password_verifier, state, role,
                created_at, display_name, mapping) -> dict:
        if state in STATE_REASONS and not (state == "locked" and RESET_RULE in mapping):
            return _refused(target_id, STATE_REASONS[state])
        if not email:
            return _refused(target_id, "no-email")
        if not display_name:
            return _refused(target_id, "required-field-without-source")
        verifier, reset = carried_verifier(password_verifier)
        if state == "locked":
            verifier, reset = None, True
        stored = self.repository.import_account(
            target_id, email=email.lower(), email_verified=bool(email_verified),
            role=ROLES[role], display_name=display_name, password_verifier=verifier,
            reset_required=reset, created_at=created_at,
        )
        reason = stored.get("reasonKey")
        if reason is not None:
            return {**stored, "reasonKey": REFUSAL_REASONS.get(reason, reason)}
        return stored

    def import_identity_link(self, target_id: UUID, *, source_key: str, account_id: UUID,
                             provider: str, subject: str, confirmed: bool,
                             linked_at: dt.datetime) -> dict:
        """A4's `importIdentityLink`."""
        if not confirmed:
            result = outcome("refused", stored_digest({"link": str(target_id),
                                                       "refused": "unconfirmed-link"}),
                             reason="unconfirmed-link")
        else:
            result = self.repository.import_identity_link(
                target_id, account_id=account_id, provider=provider, subject=subject,
                linked_at=linked_at)
        return {"sourceKey": source_key, "targetId": str(target_id), **result}

    def parity(self, kind: str, *, now: dt.datetime) -> dict:
        return self.repository.parity(kind, now=now)
