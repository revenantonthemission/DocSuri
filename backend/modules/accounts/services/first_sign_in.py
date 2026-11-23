"""Sign-in under a D1-shaped policy, and a migrated account's first sign-in (U8 plan Step 19;
D1, D2, BR8.5, BR8.6, NFR2.1, C02 4.0.0 A3).

Only `u8-synthetic-v1` and `docsuri-production-v1` reach this module, through U8's
`CompleteControlEntryService`; every earlier realm's policy keeps `ControlEntryService`'s
built sign-in. Sign-in answers C02 4.0.0's
`AccessSignInResult`:

- **Limits (D2).** The three sign-in limits are checked and counted before any password
  is checked; a failed sign-in counts against its email in its own short transaction. A
  sign-in the admission refuses, or a reset-required one the forced reset's own account
  checks refuse, counts against its email as a wrong password does (Step 53(l), L1-85).
- **Admission (§ 3.5).** While admission is maintainer-only, every account that is not an
  administrator is refused with the same answer as a wrong password, and counted as one.
- **Reset-required.** An imported account without a usable password verifier gets no
  session. A reset proof is created and its mail goes through the account-mail adapter
  (the gate, then the allowance); the answer says whether the mail was accepted, held or
  over the allowance. One sign-in operation makes one proof and one message, so a retry
  sends nothing twice.
- **Consent-pending.** An account without a recorded decision for each of v2's consent
  purposes (a migrated account: imports carry no consent, and registration records
  them) gets a 15-minute `consent_pending` session. `guard_session` passes only full
  sessions, so every guard denies it; AccountAccess serves it here, for listing and
  giving consents only. When the last purpose is decided, a member without a second
  factor's session becomes a full session of the member's length; any other account's
  ends, and its next sign-in meets the second factor.
- **Setup-only (decision of 2026-10-22).** An administrator without a second factor (under
  these policies every administrator is a migrated one: the role is not mutable and
  registration makes members) gets a 15-minute session with purpose `mfa` that every
  guard denies for anything but enrolling the second factor through U2's flow. The
  sign-in answers it as an authenticated, primary-level session. Confirming the factor
  ends it; the next sign-in meets the second factor and issues the 1-hour administrator
  session.
- **Lengths (D1).** A full session takes its fixed length from the account's role when it
  is issued; nothing extends one. Every issue time comes from the injected clock.
"""

from __future__ import annotations

import datetime as dt
import hmac
import json
from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from backend.modules.accounts.control_repository import ControlRepository
from backend.modules.accounts.entry_limits import count_account_mail
from backend.modules.accounts.integrations.account_mail import AccountMessage
from backend.modules.accounts.models import DomainException, EmailAddress, normalize_email
from backend.modules.accounts.services.guarded_entry import SessionTransport
from backend.transactions import Authority
from psycopg.types.json import Jsonb

# v2's consent purposes, each needing a recorded decision (frontend-components.md,
# ConsentStep: `local-research` is required, `personalization` optional and off).
REQUIRED_CONSENTS = ("local-research", "personalization")
CONSENT_PURPOSE = "consent_pending"
SETUP_PURPOSE = "mfa"
COMPLETIONS = ("pending", "full_session", "sign_in_again")


@dataclass(frozen=True)
class ConsentOutcome:
    """A consent given under a consent-pending session: the C02 record, and what became of
    the session (`pending`, `full_session` with its new expiry, or `sign_in_again`)."""

    record: dict
    completion: str
    expires_at: dt.datetime | None = None


def _iso(moment: dt.datetime) -> str:
    return moment.isoformat()


class FirstSignIn:
    def __init__(self, entry):
        # U2's built policy has no D1 shape at all: refused, never failed on.
        if not getattr(entry.control_policy, "d1_shaped", False):
            raise ValueError("first sign-in runs only under a D1-shaped policy")
        self.entry = entry
        self.transactions, self.policy = entry.transactions, entry.control_policy

    # --- shared reads --------------------------------------------------------------

    @staticmethod
    def pending(conn, account_id: UUID) -> list[str]:
        """The consent purposes still without a recorded decision."""
        decided = {
            row["purpose"]
            for row in conn.execute(
                "SELECT purpose FROM accounts.consent WHERE account_id=%s", (account_id,)
            ).fetchall()
        }
        return [purpose for purpose in REQUIRED_CONSENTS if purpose not in decided]

    @staticmethod
    def has_factor(conn, account_id: UUID) -> bool:
        return conn.execute(
            "SELECT 1 FROM accounts.mfa_enrollment WHERE account_id=%s AND state='active'",
            (account_id,),
        ).fetchone() is not None

    @staticmethod
    def pending_revision(account_id: UUID, purpose: str) -> str:
        """The revision a not-yet-decided purpose is listed under, so a decision on it
        compares like any other consent change."""
        return str(uuid5(NAMESPACE_URL, f"docsuri-consent-pending:{account_id}:{purpose}"))

    @staticmethod
    def _public_session(row: dict) -> dict:
        return {
            "sessionId": str(row["id"]),
            "accountId": str(row["account_id"]),
            "authorityRevision": str(row["authority_revision"]),
            "verified": True,
            "authenticationLevel": "mfa" if row.get("mfa_at") else "primary",
            "expiresAt": _iso(row["expires_at"]),
        }

    def public(self, conn, row: dict) -> dict:
        """The sign-in answer for one issued session (an `AccessSignInResult`)."""
        if row["purpose"] == CONSENT_PURPOSE:
            return {
                "state": "consent_pending",
                "session": self._public_session(row),
                "consentPurposeIds": self.pending(conn, row["account_id"]),
                "expiresAt": _iso(row["expires_at"]),
            }
        if row["purpose"] == SETUP_PURPOSE:
            return {"state": "authenticated", "session": self._public_session(row)}
        return self.entry.public_session(row)

    # --- sign-in -------------------------------------------------------------------

    def login(self, email: str, password: str, *, operation: UUID | None = None,
              flow_binding: str = "diagnostic") -> SessionTransport:
        entry = self.entry
        entry._admit(sign_in_email=email)
        try:
            email = EmailAddress(normalize_email(email)).value
        except DomainException:
            # Your answer of 2026-11-11 on the follow-up's review ("Extend it to all
            # five"): an address the contract's schema accepts but the account model
            # refuses (one with `!`) takes the unknown address's path below, the same
            # password-bound work, lookup, dummy comparison, counted failure and refusal,
            # so the answer never says whether an account exists.
            email = normalize_email(email)
        entry.verifier("password-bound", password)
        observed = self.transactions.run(
            "accounts",
            lambda conn: conn.execute(
                "SELECT * FROM accounts.account WHERE email=%s", (email,)
            ).fetchone(),
        )
        reset = bool(observed and observed["reset_required"])
        # The same password work for every outcome, so the answer's timing says nothing.
        matched = entry._matches_password(
            observed["password_hash"] if observed and not reset else entry._dummy, password
        )
        if not observed or not (matched or reset):
            entry.count_failed_sign_in(email)
            raise PermissionError("credentials unavailable")
        try:
            entry.require_admitted(observed)
        except PermissionError:
            # Your answer of 2026-11-09 (L1-85, U8 plan Step 53(l)): every account this
            # refuses, reset-required or not, counts against its email as a wrong password
            # does, so six tries tell nothing about the address.
            entry.count_failed_sign_in(email)
            raise
        operation = operation or uuid4()
        if reset:
            return self._reset_required(operation, email, flow_binding, observed)
        return self._issue(operation, email, password, flow_binding, observed)

    def _issue(self, operation, email, password, flow_binding, observed) -> SessionTransport:
        entry = self.entry
        intent = entry.verifier("login-intent", json.dumps([email, password, flow_binding]))
        token = entry.verifier("login-cookie", str(operation) + ":" + intent)
        csrf = entry.verifier("session-csrf", token)

        def write(conn):
            account = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR UPDATE", (observed["id"],)
            ).fetchone()
            if (
                not account["active"]
                or not account["verified"]
                or account["lifecycle_state"] != "active"
                or account["password_hash"] != observed["password_hash"]
            ):
                raise PermissionError("credentials unavailable")
            entry.require_admitted(account)
            previous = conn.execute(
                "SELECT * FROM accounts.entry_receipt WHERE operation_id=%s", (operation,)
            ).fetchone()
            if previous:
                if previous["kind"] != "login" or previous["intent_hash"] != intent:
                    raise ValueError("login operation conflict")
                return self._replay(conn, account, token)
            purpose, seconds = self._entry_session(conn, account)
            row = conn.execute(
                "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,"
                "authority_revision,expires_at,purpose,flow_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) "
                "RETURNING *",
                (
                    uuid4(), account["id"], entry.verifier("session", token),
                    entry.verifier("csrf", csrf), account["authority_revision"],
                    entry.clock() + dt.timedelta(seconds=seconds), purpose, uuid4(),
                ),
            ).fetchone()
            outcome = self.public(conn, row)
            conn.execute(
                "INSERT INTO accounts.entry_receipt VALUES(%s,'login',%s,%s)",
                (operation, intent, Jsonb(outcome)),
            )
            return outcome

        return SessionTransport(token, csrf, self.transactions.run("accounts", write))

    def _entry_session(self, conn, account) -> tuple[str, int]:
        """The session a successful password opens, and its length (D1, BR8.6)."""
        if self.pending(conn, account["id"]):
            return CONSENT_PURPOSE, self.policy.limited_session_seconds
        factor = self.has_factor(conn, account["id"])
        if account["role"] == "administrator" and not factor:
            return SETUP_PURPOSE, self.policy.limited_session_seconds
        if account["role"] == "administrator" or factor:
            return "primary_mfa_continuation", self.policy.proof_seconds
        return "full_session", self.policy.full_session_seconds(account["role"])

    def _replay(self, conn, account, token) -> dict:
        row = conn.execute(
            "SELECT *,expires_at>clock_timestamp() AS fresh FROM accounts.session "
            "WHERE token_hash=%s",
            (self.entry.verifier("session", token),),
        ).fetchone()
        if (
            not row
            or row["revoked"]
            or not row["fresh"]
            or row["authority_revision"] != account["authority_revision"]
        ):
            raise PermissionError("session unavailable")
        return self.public(conn, row)

    def _reset_required(self, operation, email, flow_binding, observed) -> SessionTransport:
        """No session: a reset proof, its mail and the answer saying what became of it."""
        entry = self.entry
        intent = entry.verifier("reset-required-login", json.dumps([email, flow_binding]))
        seed = entry.verifier("reset-required", str(operation))
        identifier = uuid5(NAMESPACE_URL, "docsuri-reset-required-proof:" + seed)
        proof = entry.verifier("reset-required-proof", seed)
        key = str(uuid5(NAMESPACE_URL, "docsuri-reset-required-message:" + seed))
        # Your answer of 2026-11-08 (L1-71, U8 plan Step 53(i)): the hold, then the
        # allowance's limit, read before the transaction opens, each looked up with a
        # default (false and None), so an adapter without it never answers early.
        held_for_all = getattr(entry.account_mail, "held_for_all", None)
        held = bool(callable(held_for_all) and held_for_all())
        limit_reached = getattr(entry.account_mail, "limit_reached", None)
        limited = (not held and callable(limit_reached)
                   and limit_reached(key) is not None)
        early = {"state": "reset_required", "messageKey": key}

        def prepare(conn):
            previous = conn.execute(
                "SELECT * FROM accounts.entry_receipt WHERE operation_id=%s", (operation,)
            ).fetchone()
            if previous:
                if previous["kind"] != "login" or previous["intent_hash"] != intent:
                    raise ValueError("login operation conflict")
                return previous["outcome"], False
            account = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR UPDATE", (observed["id"],)
            ).fetchone()
            if (
                not account["active"]
                or not account["verified"]
                or account["lifecycle_state"] != "active"
                or not account["reset_required"]
            ):
                raise PermissionError("credentials unavailable")
            entry.require_admitted(account)
            # After the account's own checks, because this answer already names the
            # account: no proof, receipt or place is written and nothing is delivered.
            if held:
                return {**early, "delivery": "held"}, True
            if limited:
                return {**early, "delivery": "over_allowance"}, True
            exists = conn.execute(
                "SELECT 1 FROM accounts.control_proof WHERE id=%s", (identifier,)
            ).fetchone()
            # The account's emails a UTC day (L1-71), counted only when the proof is new,
            # so a retry whose proof already exists counts nothing more.
            if not exists and not count_account_mail(
                conn, account_id=account["id"], now=entry.clock(),
                per_day=self.policy.account_mail_per_day,
            ):
                return {**early, "delivery": "over_allowance"}, True
            # The same proof for every retry of one operation, so its message is the same.
            conn.execute(
                "INSERT INTO accounts.control_proof(id,account_id,purpose,proof_hash,flow_hash,"
                "authority_revision,lifecycle_revision,expires_at) VALUES(%s,%s,'password-reset',"
                "%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING",
                (
                    identifier, account["id"], entry.verifier("reset-proof", proof),
                    entry.verifier("flow", flow_binding), account["authority_revision"],
                    account["lifecycle_revision"],
                    entry.clock() + dt.timedelta(seconds=self.policy.proof_seconds),
                ),
            )
            return None, False

        try:
            recorded, _early = self.transactions.run("accounts", prepare)
        except PermissionError:
            # Refused by the account checks or the admission (L1-85, Step 53(l)): counted
            # once the accounts run has ended and rolled back, in the count's own short
            # transaction, since the per-owner gate lets one run per owner at a time.
            entry.count_failed_sign_in(email)
            raise
        if recorded is not None:
            return SessionTransport("", "", recorded)
        delivery = entry.account_mail.deliver(
            AccountMessage(
                "password-reset", key, observed["id"],
                {
                    "challengeId": str(identifier), "proof": proof,
                    "flowBinding": flow_binding, "email": email, "purpose": "password-reset",
                },
            )
        )
        outcome = {"state": "reset_required", "delivery": delivery, "messageKey": key}

        def record(conn):
            conn.execute(
                "INSERT INTO accounts.entry_receipt VALUES(%s,'login',%s,%s) "
                "ON CONFLICT(operation_id) DO NOTHING",
                (operation, intent, Jsonb(outcome)),
            )
            return conn.execute(
                "SELECT outcome FROM accounts.entry_receipt WHERE operation_id=%s", (operation,)
            ).fetchone()["outcome"]

        return SessionTransport("", "", self.transactions.run("accounts", record))

    # --- limited sessions ----------------------------------------------------------

    def _limited_row(self, conn, token: str, csrf: str | None, purpose: str) -> dict:
        entry = self.entry
        found = conn.execute(
            "SELECT account_id FROM accounts.session WHERE token_hash=%s",
            (entry.verifier("session", token),),
        ).fetchone()
        if not found:
            raise PermissionError("session unavailable")
        account = conn.execute(
            "SELECT * FROM accounts.account WHERE id=%s FOR UPDATE", (found["account_id"],)
        ).fetchone()
        row = conn.execute(
            "SELECT *,expires_at>clock_timestamp() AS fresh FROM accounts.session "
            "WHERE token_hash=%s FOR UPDATE",
            (entry.verifier("session", token),),
        ).fetchone()
        if (
            row["purpose"] != purpose
            or row["revoked"]
            or not row["fresh"]
            or row["authority_revision"] != account["authority_revision"]
            or not account["active"]
            or not account["verified"]
            or account["lifecycle_state"] != "active"
            or (purpose == SETUP_PURPOSE and account["role"] != "administrator")
            or (csrf is not None and not hmac.compare_digest(
                row["csrf_hash"], entry.verifier("csrf", csrf)
            ))
        ):
            raise PermissionError("session unavailable")
        return dict(row, account=account)

    def limited_purpose(self, token: str) -> str | None:
        """`consent_pending` or `mfa` for a current limited session, else None."""
        if not token:
            return None

        def read(conn):
            row = conn.execute(
                "SELECT purpose FROM accounts.session WHERE token_hash=%s AND NOT revoked "
                "AND expires_at>clock_timestamp()",
                (self.entry.verifier("session", token),),
            ).fetchone()
            return row["purpose"] if row else None

        purpose = self.transactions.run("accounts", read)
        return purpose if purpose in (CONSENT_PURPOSE, SETUP_PURPOSE) else None

    def limited_session(self, token: str, csrf: str | None, purpose: str) -> dict:
        return self.transactions.run(
            "accounts", lambda conn: self._limited_row(conn, token, csrf, purpose)
        )

    # --- consents under a consent-pending session -----------------------------------

    def consents(self, token: str, csrf: str) -> tuple[UUID, list[dict]]:
        """Every v2 consent purpose: decided ones as recorded, the others listed revoked
        under their pending revision."""

        def read(conn):
            row = self._limited_row(conn, token, csrf, CONSENT_PURPOSE)
            account = row["account_id"]
            recorded = {
                item["purpose"]: item
                for item in conn.execute(
                    "SELECT purpose,granted,revision,effective_at FROM accounts.consent "
                    "WHERE account_id=%s",
                    (account,),
                ).fetchall()
            }
            items = []
            for purpose in REQUIRED_CONSENTS:
                item = recorded.get(purpose)
                items.append({
                    "purpose": purpose,
                    "granted": bool(item and item["granted"]),
                    "revision": str(item["revision"]) if item
                    else self.pending_revision(account, purpose),
                    "effective_at": _iso(item["effective_at"] if item
                                         else row["account"]["created_at"]),
                })
            return account, items

        return self.transactions.run("accounts", read)

    def give_consent(self, token: str, csrf: str, operation: UUID, expected: UUID,
                     purpose: str, granted: bool) -> ConsentOutcome:
        if purpose not in REQUIRED_CONSENTS or type(granted) is not bool:
            raise ValueError("registered consent purpose and decision required")
        intent = {"expectedRevision": str(expected), "purpose": purpose, "granted": granted}

        def write(conn):
            row = self._limited_row(conn, token, csrf, CONSENT_PURPOSE)
            account = row["account"]
            self.entry.require_admitted(account)
            digest, prior = ControlRepository.replay(conn, account["id"], "consent",
                                                     operation, intent)
            if prior is not None:
                return ConsentOutcome(prior, "pending")
            record, authority = self._decide(conn, row, account, expected, purpose, granted)
            conn.execute(
                "INSERT INTO accounts.consent_obligation(id,account_id,purpose,consent_revision,"
                "authority_revision,granted) VALUES(%s,%s,%s,%s,%s,%s)",
                (operation, account["id"], purpose, UUID(record["revision"]), authority, granted),
            )
            ControlRepository.record(conn, account["id"], "consent", operation, digest, record)
            return self._complete(conn, row, account, record)

        return self.transactions.run("accounts", write)

    def _decide(self, conn, row, account, expected, purpose, granted) -> tuple[dict, UUID]:
        current = conn.execute(
            "SELECT * FROM accounts.consent WHERE account_id=%s AND purpose=%s FOR UPDATE",
            (account["id"], purpose),
        ).fetchone()
        revision, authority = uuid4(), uuid4()
        if current is not None:
            if current["revision"] != expected:
                raise ValueError("stale consent revision")
            changed = conn.execute(
                "UPDATE accounts.consent SET granted=%s,revision=%s,"
                "effective_at=clock_timestamp() WHERE account_id=%s AND purpose=%s "
                "RETURNING effective_at",
                (granted, revision, account["id"], purpose),
            ).fetchone()
        else:
            if str(expected) != self.pending_revision(account["id"], purpose):
                raise ValueError("stale consent revision")
            changed = conn.execute(
                "INSERT INTO accounts.consent(account_id,purpose,granted,revision) "
                "VALUES(%s,%s,%s,%s) RETURNING effective_at",
                (account["id"], purpose, granted, revision),
            ).fetchone()
        # As every consent change: a new authority revision ends every other session.
        conn.execute(
            "UPDATE accounts.account SET authority_revision=%s WHERE id=%s",
            (authority, account["id"]),
        )
        conn.execute(
            "UPDATE accounts.session SET revoked=true WHERE account_id=%s AND id<>%s",
            (account["id"], row["id"]),
        )
        conn.execute(
            "UPDATE accounts.session SET authority_revision=%s WHERE id=%s", (authority, row["id"])
        )
        return {
            "consentId": purpose,
            "accountId": str(account["id"]),
            "purposeId": purpose,
            "decision": "granted" if granted else "revoked",
            "revision": str(revision),
            "effectiveAt": _iso(changed["effective_at"]),
            "policyRef": self.policy.reference,
        }, authority

    def _complete(self, conn, row, account, record) -> ConsentOutcome:
        """Once nothing is pending: a factor-less member's session becomes a full one of
        the member's length; any other account's ends (it meets the second factor)."""
        if self.pending(conn, account["id"]):
            return ConsentOutcome(record, "pending")
        if account["role"] == "member" and not self.has_factor(conn, account["id"]):
            expires = self.entry.clock() + dt.timedelta(
                seconds=self.policy.full_session_seconds("member")
            )
            conn.execute(
                "UPDATE accounts.session SET purpose='full_session',expires_at=%s WHERE id=%s",
                (expires, row["id"]),
            )
            return ConsentOutcome(record, "full_session", expires)
        conn.execute("UPDATE accounts.session SET revoked=true WHERE id=%s", (row["id"],))
        return ConsentOutcome(record, "sign_in_again")

    # --- the setup-only session ----------------------------------------------------

    def setup_authority(self, token: str, csrf: str) -> Authority:
        row = self.limited_session(token, csrf, SETUP_PURPOSE)
        return Authority(row["account_id"], row["id"])

    def check_setup(self, conn, authority: Authority) -> UUID:
        """Inside an enrolment write: the setup-only session is still current. Returns the
        account's authority revision, as `guard` does."""
        account = conn.execute(
            "SELECT * FROM accounts.account WHERE id=%s FOR SHARE", (authority.account_id,)
        ).fetchone()
        row = conn.execute(
            "SELECT *,expires_at>clock_timestamp() AS fresh FROM accounts.session "
            "WHERE id=%s AND account_id=%s FOR SHARE",
            (authority.session_id, authority.account_id),
        ).fetchone()
        if (
            not account
            or not row
            or row["purpose"] != SETUP_PURPOSE
            or row["revoked"]
            or not row["fresh"]
            or row["authority_revision"] != account["authority_revision"]
            or account["role"] != "administrator"
            or not account["active"]
            or not account["verified"]
            or account["lifecycle_state"] != "active"
        ):
            raise PermissionError("setup session unavailable")
        self.entry.require_admitted(account)
        return account["authority_revision"]

    def reauthenticate_setup(self, authority: Authority, password: str) -> None:
        """U2's reauthentication, for the setup-only session."""
        entry = self.entry
        entry.verifier("password-bound", password)
        observed = self.transactions.run(
            "accounts",
            lambda conn: conn.execute(
                "SELECT password_hash FROM accounts.account WHERE id=%s", (authority.account_id,)
            ).fetchone(),
        )
        if not observed or not entry._matches_password(observed["password_hash"], password):
            raise PermissionError("reauthentication required")

        def check(conn):
            self.check_setup(conn, authority)
            current = conn.execute(
                "SELECT password_hash FROM accounts.account WHERE id=%s", (authority.account_id,)
            ).fetchone()
            if current["password_hash"] != observed["password_hash"]:
                raise PermissionError("credential changed during reauthentication")

        self.transactions.run("accounts", check)
