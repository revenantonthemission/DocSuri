"""AccountAccess's entry in the two complete realms (U8 plan Steps 19 and 21; D1–D3).

`CompleteControlEntryService` is U2's `ControlEntryService` with the complete realms'
parts (the person's decision of 2026-10-24, "Move, scope tools, test U2"):

- D2's three sign-in limits, checked and counted before any password is checked;
- admission (security-design § 3.5) for every path that issues or upgrades a session,
  and registration closed until public activation opens it;
- every account email through the realm's account mail (`account_mail`): the local
  mailbox in the composed realm, Resend in production once it is active, each request's
  proof recorded first and its message keyed by the request's operation, so a retry is
  the same message; the four signed-out requests store their message in the outbox in
  the proof's transaction and answer at once, and the host's sender sends it
  (`u8_mail_outbox.py`, Step 53(h), L1-69); every kind counts against the account's
  daily limit (Step 53(i), L1-71);
- the first sign-in's steps (`services/first_sign_in.py`) and the reset-required marker;
- the composition's one clock for every issue time (decision "One clock").

Before anything else it refuses a policy that is not a `CompletePolicy`, and
production's policy without an admission. U2's realm keeps the built entry unchanged.
"""

from __future__ import annotations

import datetime as dt
import json
import threading
from collections.abc import Callable
from uuid import NAMESPACE_URL, UUID, uuid5

from backend.modules.accounts.control_policy import PolicyUnavailable
from backend.modules.accounts.control_repository import ControlRepository
from backend.modules.accounts.entry_limits import (
    AccountMailLimitReached,
    AccountMailUnavailable,
    EntryLimits,
    count_account_mail,
    current_address,
)
from backend.modules.accounts.integrations.account_mail import (
    AccountMail,
    AccountMessage,
    LocalAccountMail,
)
from backend.modules.accounts.models import (
    DomainException,
    EmailAddress,
    InvalidPasswordException,
    normalize_email,
)
from backend.modules.accounts.password import PasswordPolicy
from backend.modules.accounts.services.control_entry import ControlEntryService
from backend.modules.accounts.services.guarded_entry import SessionTransport
from backend.modules.accounts.u8_control_policy import Admission, CompletePolicy
from backend.modules.accounts.u8_mail_outbox import queue as queue_mail
from backend.transactions import Authority, Busy, guard
from psycopg.types.json import Jsonb


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class PasswordPolicyRefused(ValueError):
    """A new password the password policy refuses (your answer of 2026-11-11, "Say the
    password is too weak"). Registration, reset completion and password change answer it
    as 422 `INVALID_ARGUMENT` with `messageKey` `password.policy` (`u8_control_http.py`,
    `u8_local_http.py`). It is a `ValueError`, so any route that does not map it still
    answers the boundary's built 409, never a 500."""

    status, code, message_key = 422, "INVALID_ARGUMENT", "password.policy"

    def __init__(self) -> None:
        super().__init__("password outside the password policy")


def _evaluate_password(password: str) -> None:
    """The password policy, its refusal translated: `PasswordPolicy.evaluate` raises the
    shared `DomainException`, which no boundary branch answers."""
    try:
        PasswordPolicy.evaluate(password)
    except InvalidPasswordException as refused:
        raise PasswordPolicyRefused() from refused


def _limit_email(value: str) -> str:
    """The email a sign-in limit keys on: the normalized address, or, when it is no valid
    address, the submitted text normalized the same way (trimmed, lower-case). The sign-in
    then takes the unknown address's path and counts its failure under the same key."""
    try:
        return EmailAddress(normalize_email(value)).value
    except (TypeError, ValueError, DomainException):
        return normalize_email(value) if isinstance(value, str) else ""


def request_email(value: str) -> str:
    """An address a request names, normalized; one the contract's schema accepts but the
    account model refuses (for example one with `!`) raises `ValueError`, which the
    boundary answers as the route's built invalid-input refusal, 409 `CONFLICT` with
    `request.conflict` (your answer of 2026-11-11 on the follow-up's review, "Extend it to
    all five"). The model's own `InvalidEmailException` is a `DomainException` that no
    boundary branch answers, so it used to answer a bare 500."""
    try:
        return EmailAddress(normalize_email(value)).value
    except DomainException:
        raise ValueError("invalid email address") from None


class CompleteControlEntryService(ControlEntryService):
    def __init__(
        self,
        transactions,
        policy: CompletePolicy,
        *,
        clock: Callable[[], dt.datetime] | None = None,
        admission: Admission | None = None,
        account_mail: AccountMail | None = None,
    ):
        if not isinstance(policy, CompletePolicy):
            raise PolicyUnavailable("the complete entry runs only a complete realm's policy")
        if policy.realm == "production" and admission is None:
            raise PolicyUnavailable("production's entry requires its admission")
        if not callable(getattr(ControlEntryService, "_password_reset_applied", None)):
            raise TypeError("U2's ControlEntryService lacks its reset hook")
        super().__init__(transactions, policy)
        # The composition's one clock (decision "One clock").
        self.clock = clock or _utc_now
        self.admission = admission
        # The account-mail adapter: the built local mailbox until the composition wires
        # the gate, the allowance or the real Resend adapter in.
        self.account_mail = account_mail or LocalAccountMail(self.mail)
        # Set once a signed-out mail request's transaction commits, to wake the host's
        # account-mail sender (U8 plan Step 53(h), L1-69).
        self.mail_waiting = threading.Event()
        from backend.modules.accounts.services.first_sign_in import FirstSignIn

        self.first_sign_in = FirstSignIn(self)

    # --- D2 and admission ----------------------------------------------------------------

    def _admit(self, sign_in_email: str | None = None) -> None:
        """D2: the three limits, checked and counted in one transaction before any
        password is checked; the email limit for sign-in only."""
        store = EntryLimits(self.transactions, self.control_policy.entry_limits)
        address = self.verifier("entry-address", current_address())
        email = None if sign_in_email is None else self.verifier(
            "entry-email", _limit_email(sign_in_email)
        )
        now = self.clock()
        self.transactions.run(
            "accounts",
            lambda conn: store.check_and_count(
                conn, address_digest=address, email_digest=email, now=now
            ),
        )

    def count_failed_sign_in(self, email: str) -> None:
        """A failed sign-in, against its email, in its own short transaction (D2)."""
        EntryLimits(self.transactions, self.control_policy.entry_limits).record_failure(
            email_digest=self.verifier("entry-email", _limit_email(email)), now=self.clock()
        )

    def require_admitted(self, account: dict) -> None:
        """Admission (security-design § 3.5) for every path that issues or upgrades a
        session: password sign-in, provider sign-in, the second factor and the setup-only
        session. While admission is maintainer-only, every account that is not an
        administrator is refused with the answer a wrong password gets. Without an
        admission (the composed realm) nothing changes."""
        if self.admission is not None and not self.admission.admits(account["role"]):
            raise PermissionError("credentials unavailable")

    def account_of(self, email: str) -> UUID | None:
        """The v2 account an address belongs to, or None: v2's emails are unique and
        lower-case, so the rehearsal bound compares accounts (BR7.5), never addresses."""
        try:
            value = EmailAddress(normalize_email(email)).value
        except (TypeError, ValueError, DomainException):
            return None
        row = self.transactions.run(
            "accounts",
            lambda conn: conn.execute(
                "SELECT id FROM accounts.account WHERE email=%s", (value,)
            ).fetchone(),
        )
        return row["id"] if row else None

    def issue_time(self) -> dt.datetime:
        """The issue time every session counts from: the composition's clock."""
        return self.clock()

    def login(
        self,
        email: str,
        password: str,
        *,
        operation: UUID | None = None,
        flow_binding: str = "diagnostic",
    ) -> SessionTransport:
        return self.first_sign_in.login(
            email, password, operation=operation, flow_binding=flow_binding
        )

    def _password_reset_applied(self, conn, account: dict) -> None:
        # A completed reset clears the reset-required marker (A3, BR8.6).
        conn.execute(
            "UPDATE accounts.account SET reset_required=false WHERE id=%s", (account["id"],)
        )

    # --- New passwords the policy refuses (your answer of 2026-11-11) -------------------

    def complete_password_reset(
        self, operation: UUID, challenge: UUID, proof: str, flow_binding: str, new_password: str
    ) -> dict:
        """U2's reset completion, its policy refusal answered as `PasswordPolicyRefused`;
        admission still runs first."""
        try:
            return super().complete_password_reset(
                operation, challenge, proof, flow_binding, new_password
            )
        except InvalidPasswordException as refused:
            raise PasswordPolicyRefused() from refused

    def change_password(
        self, authority: Authority, operation: UUID, current_password: str, new_password: str
    ) -> dict:
        """U2's password change, its policy refusal answered as `PasswordPolicyRefused`;
        the current password is still checked first."""
        try:
            return super().change_password(
                authority, operation, current_password, new_password
            )
        except InvalidPasswordException as refused:
            raise PasswordPolicyRefused() from refused

    # --- Registration ----------------------------------------------------------------------

    def register(
        self, operation: UUID, email: str, password: str, display_name: str, flow_binding: str
    ) -> dict:
        """Registration stays closed under an admission until the public-activation
        evidence and the maintainer's decision open it (security-design § 3.5)."""
        if self.admission is not None and not self.admission.registration_open:
            raise PolicyUnavailable("registration stays closed until public activation")
        self._admit()
        # The route's built invalid-input refusal, as an invalid display name gets.
        email = request_email(email)
        if not display_name.strip() or len(display_name.encode()) > 256:
            raise ValueError("invalid display name")
        if len(password.encode()) > 1024:
            raise ValueError("password exceeds local policy")
        _evaluate_password(password)
        password_hash = self._hash_password(password)
        intent = self.verifier(
            "registration",
            json.dumps([email, password, display_name, flow_binding], ensure_ascii=False),
        )
        challenge, proof, key = self._mail_identity("registration", operation)
        account = uuid5(NAMESPACE_URL, "docsuri-registration-account:" + key)
        refusal = self._mail_refusal(key)

        def prepare(conn):
            prior = conn.execute(
                "SELECT * FROM accounts.entry_receipt WHERE operation_id=%s", (operation,)
            ).fetchone()
            if prior:
                if prior["kind"] != "register" or prior["intent_hash"] != intent:
                    raise ValueError("registration operation conflict")
                return prior["outcome"], None
            if refusal is not None:
                raise refusal()  # L1-53, then L1-10: before any account read
            # Capacity is checked independently of address existence (as built), so a
            # taken address at the cap gets the same busy answer as a free one.
            count = conn.execute(
                "SELECT count(*) AS count FROM accounts.account WHERE active"
            ).fetchone()["count"]
            if count >= self.account_limit:
                raise Busy("local account allocation exhausted")
            existing = conn.execute(
                "SELECT id FROM accounts.account WHERE email=%s", (email,)
            ).fetchone()
            if existing:
                # The address is taken: the same answer, and no message (never says so).
                return self._record_entry(conn, operation, "register", intent), False
            row = conn.execute(
                "INSERT INTO accounts.account(id,email,password_hash,display_name) "
                "VALUES(%s,%s,%s,%s) RETURNING authority_revision",
                (account, email, password_hash, display_name),
            ).fetchone()
            conn.execute(
                "INSERT INTO accounts.challenge(id,account_id,proof_hash,authority_revision,"
                "expires_at,purpose,delivery,flow_hash) VALUES(%s,%s,%s,%s,"
                "clock_timestamp()+(%s*interval '1 second'),'verify-email','acknowledged',%s)",
                (challenge, account, self.verifier("proof", proof), row["authority_revision"],
                 self.verification_seconds, self.verifier("flow", flow_binding)),
            )
            conn.execute(
                "INSERT INTO accounts.consent(account_id,purpose,granted) "
                "VALUES(%s,'local-research',true),(%s,'personalization',false)",
                (account, account),
            )
            # The new account's verification link waits in the outbox (L1-69), counted
            # against the account's day (L1-71).
            if self._count_mail(conn, account):
                self._queue(conn, key, "verification", {
                    "challengeId": str(challenge), "proof": proof,
                    "flowBinding": flow_binding,
                }, challenge_id=challenge)
            return self._record_entry(conn, operation, "register", intent), True

        recorded, _ = self.transactions.run("accounts", prepare)
        self.mail_waiting.set()
        return recorded

    # --- Account mail (U8 plan Step 21; the person's decision of 2026-10-23) --------------
    #
    # Each request records its proof first, then sends one message, its proof and message
    # key derived from the request's operation so a retry is the same message under the
    # same reservation. Answers are unchanged: they never say whether an account exists
    # or what became of its message.

    def _mail_identity(self, kind: str, operation: UUID) -> tuple[UUID, str, str]:
        """The proof's identity, the proof and the message key for one request."""
        seed = self.verifier(kind + "-request-seed", str(operation))
        identifier = uuid5(NAMESPACE_URL, f"docsuri-{kind}-proof:" + seed)
        proof = self.verifier(kind + "-request-proof", seed)
        key = str(uuid5(NAMESPACE_URL, f"docsuri-{kind}-message:" + seed))
        return identifier, proof, key

    def _mail_refusal(self, key: str):
        """The up-front refusal of one mail request, or None (U8 plan Step 53(d) and (g);
        L1-10, L1-53). Read after `_admit()` and before the accounts transaction opens,
        so no connection waits on the ledger's lock; `prepare` raises what this returns
        only after its replay check, so a replayed operation keeps its first answer.

        The hold is read first: while no account mail can be sent, a limit's wait would
        name a time at which mail still cannot go out. Each method is looked up with a
        default that answers false or None, so an adapter without it never refuses."""
        held_for_all = getattr(self.account_mail, "held_for_all", None)
        if callable(held_for_all) and held_for_all():
            return AccountMailUnavailable
        limit_reached = getattr(self.account_mail, "limit_reached", None)
        limit = limit_reached(key) if callable(limit_reached) else None
        if limit is None:
            return None
        now = self.clock()
        return lambda: AccountMailLimitReached(limit, now=now)

    def _late_refusal(self, delivery: str, key: str) -> Busy | None:
        """The signed-in email change's refusal at delivery (Step 53(d), (g)): `held`
        fails plainly; `over_allowance` names the limit a second read finds, or no wait
        when a place freed or the UTC day or month turned since `deliver()` read the
        counts."""
        if delivery == "held":
            return AccountMailUnavailable()
        if delivery != "over_allowance":
            return None
        limit_reached = getattr(self.account_mail, "limit_reached", None)
        limit = limit_reached(key) if callable(limit_reached) else None
        return AccountMailLimitReached(limit, now=self.clock())

    def _count_mail(self, conn, account: UUID) -> bool:
        """Count one account email against the account's UTC day on the entry's clock
        (Step 53(i), L1-71): False at the policy's daily limit, and nothing changes."""
        return count_account_mail(
            conn, account_id=account, now=self.clock(),
            per_day=self.control_policy.account_mail_per_day,
        )

    def _queue(self, conn, key: str, purpose: str, payload: dict, *,
               challenge_id: UUID | None = None, control_proof_id: UUID | None = None):
        """Store a signed-out request's message in the outbox, in its proof's transaction
        (Step 53(h), L1-69); the payload holds no address."""
        queue_mail(conn, entry=self, message_key=key, purpose=purpose, payload=payload,
                   now=self.clock(), challenge_id=challenge_id,
                   control_proof_id=control_proof_id)

    def _new_proof(self, conn, identifier: UUID, account: UUID) -> bool:
        """True when this request writes its proof now and the account's day still has a
        place (L1-71). A proof that already exists counts nothing more; at the limit the
        request writes no proof or row and answers as for an unknown address."""
        if conn.execute("SELECT 1 FROM accounts.control_proof WHERE id=%s",
                        (identifier,)).fetchone():
            return True
        return self._count_mail(conn, account)

    def _send_mail(self, purpose: str, key: str, account: UUID, payload: dict):
        """One account message through the realm's account mail. Returns `deliver()`'s
        answer beside the local mailbox's artifact for it, so the proof can name its file
        for the realm's mailbox readers; a real provider's message has none."""
        delivery = self.account_mail.deliver(AccountMessage(purpose, key, account, payload))
        artifact_of = getattr(self.account_mail, "artifact_of", None)
        return delivery, (artifact_of(key) if callable(artifact_of) else None)

    def _name_delivery(self, conn, identifier: UUID, artifact, extra: dict | None = None):
        if artifact is None:
            return
        protected = self.protect("proof:" + str(identifier),
                                 {**(extra or {}), "delivery": artifact.name})
        conn.execute(
            "UPDATE accounts.control_proof SET protected_payload=%s,key_version=%s WHERE id=%s",
            (protected, self.protection_version(protected), identifier),
        )

    def _record_entry(self, conn, operation: UUID, kind: str, intent: str) -> dict:
        conn.execute(
            "INSERT INTO accounts.entry_receipt VALUES(%s,%s,%s,%s) "
            "ON CONFLICT(operation_id) DO NOTHING",
            (operation, kind, intent, Jsonb(self._ack(operation))),
        )
        return conn.execute(
            "SELECT outcome FROM accounts.entry_receipt WHERE operation_id=%s", (operation,)
        ).fetchone()["outcome"]

    def request_password_reset(self, operation: UUID, email: str, flow_binding: str) -> dict:
        self._admit()
        email = request_email(email)
        intent = self.verifier("password-reset-request", json.dumps([email, flow_binding]))
        identifier, proof, key = self._mail_identity("password-reset", operation)
        refusal = self._mail_refusal(key)

        def prepare(conn):
            prior = conn.execute(
                "SELECT * FROM accounts.entry_receipt WHERE operation_id=%s", (operation,)
            ).fetchone()
            if prior:
                if prior["kind"] != "password-reset" or prior["intent_hash"] != intent:
                    raise ValueError("reset request conflict")
                return prior["outcome"], None
            if refusal is not None:
                raise refusal()  # L1-53, then L1-10: before any account read
            row = conn.execute(
                "SELECT * FROM accounts.account WHERE email=%s FOR UPDATE", (email,)
            ).fetchone()
            if (row and row["active"] and row["verified"]
                    and row["lifecycle_state"] == "active"
                    and self._new_proof(conn, identifier, row["id"])):
                protected = self.protect("proof:" + str(identifier), {"messageKey": key})
                conn.execute(
                    "INSERT INTO accounts.control_proof(id,account_id,purpose,proof_hash,flow_hash,"
                    "authority_revision,lifecycle_revision,"
                    "protected_payload,key_version,expires_at) "
                    "VALUES(%s,%s,'password-reset',%s,%s,%s,%s,%s,%s,"
                    "clock_timestamp()+(%s*interval '1 second')) "
                    "ON CONFLICT(id) DO NOTHING",
                    (
                        identifier,
                        row["id"],
                        self.verifier("reset-proof", proof),
                        self.verifier("flow", flow_binding),
                        row["authority_revision"],
                        row["lifecycle_revision"],
                        protected,
                        self.protection_version(protected),
                        self.control_policy.proof_seconds,
                    ),
                )
                self._queue(conn, key, "password-reset", {
                    "challengeId": str(identifier), "proof": proof,
                    "flowBinding": flow_binding, "purpose": "password-reset",
                }, control_proof_id=identifier)
            return self._record_entry(conn, operation, "password-reset", intent), True

        recorded, _ = self.transactions.run("accounts", prepare)
        self.mail_waiting.set()
        return recorded

    def request_verification(self, operation: UUID, email: str, flow_binding: str) -> dict:
        """The verification link for an unverified account, through the realm's account
        mail (`verification`); the built mailbox row (`accounts.delivery`) is kept for a
        local mailbox's message, which the realm's mailbox readers follow."""
        self._admit()
        email = request_email(email)
        intent = self.verifier("resend", json.dumps([email, flow_binding]))
        challenge, proof, key = self._mail_identity("verification", operation)
        refusal = self._mail_refusal(key)

        def prepare(conn):
            prior = conn.execute(
                "SELECT * FROM accounts.entry_receipt WHERE operation_id=%s", (operation,)
            ).fetchone()
            if prior:
                if prior["intent_hash"] != intent:
                    raise ValueError("verification request conflict")
                return prior["outcome"], None
            if refusal is not None:
                raise refusal()  # L1-53, then L1-10: before any account read
            row = conn.execute(
                "SELECT * FROM accounts.account WHERE email=%s FOR UPDATE", (email,)
            ).fetchone()
            if not (row and row["active"] and not row["verified"]):
                return self._record_entry(conn, operation, "verification", intent), True
            exists = conn.execute("SELECT 1 FROM accounts.challenge WHERE id=%s",
                                  (challenge,)).fetchone()
            if not exists:
                # The day's count first (L1-71), before the earlier challenges are marked
                # used, so a request at the limit changes nothing and the owner's last
                # link still works.
                if not self._count_mail(conn, row["id"]):
                    return self._record_entry(conn, operation, "verification", intent), True
                conn.execute(
                    "UPDATE accounts.challenge SET consumed=true WHERE account_id=%s",
                    (row["id"],),
                )
                conn.execute(
                    "INSERT INTO accounts.challenge(id,account_id,proof_hash,"
                    "authority_revision,expires_at,purpose,delivery,flow_hash) VALUES(%s,%s,%s,%s,"
                    "clock_timestamp()+(%s*interval '1 second'),'verify-email','acknowledged',%s)",
                    (
                        challenge,
                        row["id"],
                        self.verifier("proof", proof),
                        row["authority_revision"],
                        self.verification_seconds,
                        self.verifier("flow", flow_binding),
                    ),
                )
            self._queue(conn, key, "verification", {
                "challengeId": str(challenge), "proof": proof, "flowBinding": flow_binding,
            }, challenge_id=challenge)
            return self._record_entry(conn, operation, "verification", intent), True

        recorded, _ = self.transactions.run("accounts", prepare)
        self.mail_waiting.set()
        return recorded

    def request_email_change(
        self,
        authority: Authority,
        operation: UUID,
        password: str,
        new_email: str,
        flow_binding: str,
    ) -> dict:
        self.reauthenticate(authority, password)
        new_email = request_email(new_email)
        identifier, proof, key = self._mail_identity("email-change", operation)
        intent = self.verifier("email-change", json.dumps([new_email, flow_binding]))
        refusal = self._mail_refusal(key)

        def prior_of(conn):
            prior = conn.execute(
                "SELECT * FROM accounts.control_receipt "
                "WHERE account_id=%s AND kind='email-request' AND key=%s",
                (authority.account_id, operation),
            ).fetchone()
            if prior and prior["intent_hash"] != intent:
                raise ValueError("email request conflict")
            return prior

        def prepare(conn):
            guard(conn, authority, purpose="account-control")
            account = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR UPDATE", (authority.account_id,)
            ).fetchone()
            prior = prior_of(conn)
            if prior:
                return prior["outcome"]
            if refusal is not None:
                # L1-53, then L1-10: after only the session guard and the caller's own
                # row; nothing is read by the new address.
                raise refusal()
            # The caller's account's day (L1-71), counted only when the proof is new:
            # a retry after a late refusal counts nothing more. At the limit, nothing is
            # written and the wait runs to the next 00:00 UTC.
            if not self._new_proof(conn, identifier, authority.account_id):
                raise AccountMailLimitReached("daily", now=self.clock())
            protected = self.protect("proof:" + str(identifier),
                                     {"email": new_email, "messageKey": key})
            conn.execute(
                "INSERT INTO accounts.control_proof(id,account_id,purpose,proof_hash,flow_hash,"
                "authority_revision,lifecycle_revision,"
                "protected_payload,key_version,expires_at) "
                "VALUES(%s,%s,'email-change',%s,%s,%s,%s,%s,%s,"
                "clock_timestamp()+(%s*interval '1 second')) "
                "ON CONFLICT(id) DO NOTHING",
                (
                    identifier,
                    authority.account_id,
                    self.verifier("email-proof", proof),
                    self.verifier("flow", flow_binding),
                    account["authority_revision"],
                    account["lifecycle_revision"],
                    protected,
                    self.protection_version(protected),
                    self.control_policy.proof_seconds,
                ),
            )
            return None

        recorded = self.transactions.run("accounts", prepare)
        if recorded is not None:
            return recorded
        # The link goes to the new address, for the account that asked.
        delivery, artifact = self._send_mail("email-change", key, authority.account_id, {
            "challengeId": str(identifier), "proof": proof, "flowBinding": flow_binding,
            "email": new_email, "purpose": "email-change",
        })
        late = self._late_refusal(delivery, key)
        if late is not None:
            # No receipt is recorded; the proof written before delivery stays for the
            # same operation's retry (Step 53(d), (g)).
            raise late

        def record(conn):
            guard(conn, authority, purpose="account-control")
            prior = prior_of(conn)
            if prior:
                return prior["outcome"]
            self._name_delivery(conn, identifier, artifact, {"email": new_email})
            return ControlRepository.record(
                conn, authority.account_id, "email-request", operation, intent, self._ack(operation)
            )

        return self.transactions.run("accounts", record)

    def request_reactivation(self, operation: UUID, email: str, flow_binding: str) -> dict:
        """A withdrawn account's reactivation link, sent through the realm's account mail
        as its `reactivation` message (your decision of 2026-10-23). The proof is recorded
        before the message leaves, the same for every retry of one operation, and the
        answer is the same acknowledgement whether or not an account exists, whatever
        became of the message; nothing is sent for an unknown, active or erased account."""
        self._admit()
        email = request_email(email)
        intent = self.verifier("reactivation-request", json.dumps([email, flow_binding]))
        identifier, proof, key = self._mail_identity("reactivation", operation)
        refusal = self._mail_refusal(key)

        def prepare(conn):
            prior = conn.execute(
                "SELECT * FROM accounts.entry_receipt WHERE operation_id=%s", (operation,)
            ).fetchone()
            if prior:
                if prior["kind"] != "reactivation" or prior["intent_hash"] != intent:
                    raise ValueError("reactivation request conflict")
                return prior["outcome"], None
            if refusal is not None:
                raise refusal()  # L1-53, then L1-10: before any account read
            row = conn.execute(
                "SELECT * FROM accounts.account WHERE email=%s FOR UPDATE", (email,)
            ).fetchone()
            if (row and row["verified"] and row["lifecycle_state"] == "withdrawn"
                    and self._new_proof(conn, identifier, row["id"])):
                protected = self.protect("proof:" + str(identifier), {"messageKey": key})
                conn.execute(
                    "INSERT INTO accounts.control_proof(id,account_id,purpose,proof_hash,flow_hash,"
                    "authority_revision,lifecycle_revision,"
                    "protected_payload,key_version,expires_at) "
                    "VALUES(%s,%s,'reactivate',%s,%s,%s,%s,%s,%s,"
                    "clock_timestamp()+(%s*interval '1 second')) "
                    "ON CONFLICT(id) DO NOTHING",
                    (
                        identifier,
                        row["id"],
                        self.verifier("reactivation-proof", proof),
                        self.verifier("flow", flow_binding),
                        row["authority_revision"],
                        row["lifecycle_revision"],
                        protected,
                        self.protection_version(protected),
                        self.control_policy.proof_seconds,
                    ),
                )
                self._queue(conn, key, "reactivation", {
                    "challengeId": str(identifier), "proof": proof,
                    "flowBinding": flow_binding, "purpose": "reactivate",
                }, control_proof_id=identifier)
            return self._record_entry(conn, operation, "reactivation", intent), True

        recorded, _ = self.transactions.run("accounts", prepare)
        self.mail_waiting.set()
        return recorded
