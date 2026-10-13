"""Verified ordinary entry for the isolated, finite local composition.

Credential work stays outside owner transactions. Opaque tokens use a protected
keyed verifier; public responses never contain verification or session secrets.
The delivery store is a local test mailbox, not a public email provider.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import stat
import threading
from dataclasses import dataclass
from uuid import UUID, uuid4

from argon2.exceptions import InvalidHashError, VerificationError
from backend.artifacts import PrivateArtifacts
from backend.transactions import Authority, Busy, OwnerTransactions, guard
from psycopg.types.json import Jsonb

from ..models import EmailAddress, normalize_email
from ..password import PasswordPolicy, get_password_hasher


@dataclass(frozen=True, repr=False)
class SessionTransport:
    """Only a trusted HTTP adapter may turn these values into cookies/headers."""

    token: str
    csrf: str
    public: dict


class GuardedEntryService:
    policy = "synthetic-local-entry-1"
    _credential_work = threading.BoundedSemaphore(1)

    def __init__(self, transactions: OwnerTransactions):
        self.transactions = transactions
        self.mail = PrivateArtifacts(transactions.profile.root / "verification-mail")
        key_path = transactions.profile.root / "account-verifier.key"
        try:
            descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(secrets.token_bytes(32))
                stream.flush()
                os.fsync(stream.fileno())
        descriptor = os.open(key_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_nlink != 1
            ):
                raise ValueError("account verifier key custody invalid")
            self._key = stream.read(33)
        if len(self._key) != 32:
            raise ValueError("account verifier key incomplete")
        # Repeat on reuse too: a prior crash may follow file fsync but precede
        # persistence of the directory entry. Never acknowledge with a lost key.
        directory = os.open(key_path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        self.hasher = get_password_hasher()
        self._dummy = self._hash_password(secrets.token_urlsafe(32))

    def _hash_password(self, password: str) -> str:
        if not self._credential_work.acquire(timeout=2):
            raise Busy("local credential work allocation exhausted")
        try:
            return self.hasher.hash(password)
        finally:
            self._credential_work.release()

    def _matches_password(self, encoded: str, password: str) -> bool:
        if not self._credential_work.acquire(timeout=2):
            raise Busy("local credential work allocation exhausted")
        try:
            return self.hasher.verify(encoded, password)
        except (VerificationError, InvalidHashError):
            return False
        finally:
            self._credential_work.release()

    def verifier(self, purpose: str, value: str) -> str:
        if not isinstance(value, str) or len(value.encode()) > 2048:
            raise ValueError("credential input exceeds local policy")
        return hmac.new(self._key, (purpose + "\0" + value).encode(), hashlib.sha256).hexdigest()

    def _admit(self) -> None:
        def write(conn):
            minute = conn.execute(
                "SELECT floor(extract(epoch FROM clock_timestamp())/60)::bigint AS minute"
            ).fetchone()["minute"]
            conn.execute("DELETE FROM accounts.entry_budget WHERE minute<%s", (minute,))
            row = conn.execute(
                "INSERT INTO accounts.entry_budget VALUES(%s,1) ON CONFLICT(minute) DO UPDATE "
                "SET attempts=accounts.entry_budget.attempts+1 WHERE accounts.entry_budget."
                "attempts<20 RETURNING attempts",
                (minute,),
            ).fetchone()
            if not row:
                raise Busy("local authentication attempt allocation exhausted")

        self.transactions.run("accounts", write)

    @staticmethod
    def _ack(operation: UUID) -> dict:
        return {
            "requestId": str(operation),
            "acknowledgement": "accepted",
            "messageKey": "access.check-local-verification-mail",
        }

    def register(
        self, operation: UUID, email: str, password: str, display_name: str, flow_binding: str
    ) -> dict:
        self._admit()
        email = EmailAddress(normalize_email(email)).value
        if not display_name.strip() or len(display_name.encode()) > 256:
            raise ValueError("invalid display name")
        if len(password.encode()) > 1024:
            raise ValueError("password exceeds local policy")
        PasswordPolicy.evaluate(password)
        password_hash = self._hash_password(password)
        intent = self.verifier(
            "registration",
            json.dumps([email, password, display_name, flow_binding], ensure_ascii=False),
        )
        challenge, proof, account = uuid4(), secrets.token_urlsafe(32), uuid4()
        # Private publication precedes durable metadata. Lost commits leave a
        # bounded private orphan, never a public proof or false verification.
        artifact = self.mail.publish(
            json.dumps(
                {
                    "challengeId": str(challenge),
                    "proof": proof,
                    "flowBinding": flow_binding,
                    "email": email,
                }
            ).encode()
        )

        def write(conn):
            prior = conn.execute(
                "SELECT * FROM accounts.entry_receipt WHERE operation_id=%s", (operation,)
            ).fetchone()
            if prior:
                if prior["kind"] != "register" or prior["intent_hash"] != intent:
                    raise ValueError("registration operation conflict")
                return prior["outcome"]
            # Capacity is checked independently of address existence. Otherwise
            # the full synthetic realm would become an account-enumeration oracle.
            count = conn.execute(
                "SELECT count(*) AS count FROM accounts.account WHERE active"
            ).fetchone()["count"]
            if count >= 2:
                raise Busy("local account allocation exhausted")
            existing = conn.execute(
                "SELECT id FROM accounts.account WHERE email=%s", (email,)
            ).fetchone()
            if not existing:
                row = conn.execute(
                    "INSERT INTO accounts.account(id,email,password_hash,display_name) "
                    "VALUES(%s,%s,%s,%s) RETURNING authority_revision",
                    (account, email, password_hash, display_name),
                ).fetchone()
                conn.execute(
                    "INSERT INTO accounts.challenge(id,account_id,proof_hash,authority_revision,"
                    "expires_at,purpose,delivery,flow_hash) VALUES(%s,%s,%s,%s,"
                    "clock_timestamp()+interval '15 minutes','verify-email','acknowledged',%s)",
                    (
                        challenge,
                        account,
                        self.verifier("proof", proof),
                        row["authority_revision"],
                        self.verifier("flow", flow_binding),
                    ),
                )
                conn.execute(
                    "INSERT INTO accounts.delivery VALUES(%s,%s,%s,%s)",
                    (challenge, artifact.name, artifact.sha256, artifact.size),
                )
                conn.execute(
                    "INSERT INTO accounts.consent(account_id,purpose,granted) "
                    "VALUES(%s,'local-research',true),(%s,'personalization',false)",
                    (account, account),
                )
            outcome = self._ack(operation)
            conn.execute(
                "INSERT INTO accounts.entry_receipt VALUES(%s,'register',%s,%s)",
                (operation, intent, Jsonb(outcome)),
            )
            return outcome

        return self.transactions.run("accounts", write)

    def request_verification(self, operation: UUID, email: str, flow_binding: str) -> dict:
        self._admit()
        email = EmailAddress(normalize_email(email)).value
        intent = self.verifier("resend", json.dumps([email, flow_binding]))
        challenge, proof = uuid4(), secrets.token_urlsafe(32)
        artifact = self.mail.publish(
            json.dumps(
                {
                    "challengeId": str(challenge),
                    "proof": proof,
                    "flowBinding": flow_binding,
                    "email": email,
                }
            ).encode()
        )

        def write(conn):
            prior = conn.execute(
                "SELECT * FROM accounts.entry_receipt WHERE operation_id=%s", (operation,)
            ).fetchone()
            if prior:
                if prior["intent_hash"] != intent:
                    raise ValueError("verification request conflict")
                return prior["outcome"]
            row = conn.execute(
                "SELECT * FROM accounts.account WHERE email=%s FOR UPDATE", (email,)
            ).fetchone()
            if row and row["active"] and not row["verified"]:
                conn.execute(
                    "UPDATE accounts.challenge SET consumed=true WHERE account_id=%s", (row["id"],)
                )
                conn.execute(
                    "INSERT INTO accounts.challenge(id,account_id,proof_hash,"
                    "authority_revision,expires_at,purpose,delivery,flow_hash) VALUES(%s,%s,%s,%s,"
                    "clock_timestamp()+interval '15 minutes','verify-email','acknowledged',%s)",
                    (
                        challenge,
                        row["id"],
                        self.verifier("proof", proof),
                        row["authority_revision"],
                        self.verifier("flow", flow_binding),
                    ),
                )
                conn.execute(
                    "INSERT INTO accounts.delivery VALUES(%s,%s,%s,%s)",
                    (challenge, artifact.name, artifact.sha256, artifact.size),
                )
            outcome = self._ack(operation)
            conn.execute(
                "INSERT INTO accounts.entry_receipt VALUES(%s,'verification',%s,%s)",
                (operation, intent, Jsonb(outcome)),
            )
            return outcome

        return self.transactions.run("accounts", write)

    def verify_email(
        self, challenge: UUID, proof: str, flow_binding: str, *, operation: UUID
    ) -> dict:
        self._admit()
        proof_hash, flow_hash = self.verifier("proof", proof), self.verifier("flow", flow_binding)

        def write(conn):
            found = conn.execute(
                "SELECT account_id FROM accounts.challenge WHERE id=%s", (challenge,)
            ).fetchone()
            if not found:
                raise PermissionError("verification unavailable")
            account = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR UPDATE", (found["account_id"],)
            ).fetchone()
            row = conn.execute(
                "SELECT *,expires_at>clock_timestamp() AS fresh FROM "
                "accounts.challenge WHERE id=%s FOR UPDATE",
                (challenge,),
            ).fetchone()
            intent = self.verifier("consume", json.dumps([str(challenge), proof, flow_binding]))
            prior = conn.execute(
                "SELECT * FROM accounts.entry_receipt WHERE operation_id=%s", (operation,)
            ).fetchone()
            if prior:
                if (
                    prior["intent_hash"] == intent
                    and account["active"]
                    and account["verified"]
                    and row["authority_revision"] == account["authority_revision"]
                ):
                    return {
                        "resourceId": str(challenge),
                        "revision": self.verifier("verified-challenge-revision", str(challenge)),
                        "requestId": str(operation),
                    }
                raise PermissionError("verification unavailable")
            if (
                not account["active"]
                or account["verified"]
                or row["consumed"]
                or not row["fresh"]
                or row["authority_revision"] != account["authority_revision"]
                or not hmac.compare_digest(row["proof_hash"], proof_hash)
                or not row["flow_hash"]
                or not hmac.compare_digest(row["flow_hash"], flow_hash)
            ):
                raise PermissionError("verification unavailable")
            conn.execute("UPDATE accounts.challenge SET consumed=true WHERE id=%s", (challenge,))
            conn.execute("UPDATE accounts.account SET verified=true WHERE id=%s", (account["id"],))
            conn.execute(
                "INSERT INTO accounts.entry_receipt VALUES(%s,'verification',%s,%s)",
                (operation, intent, Jsonb({"verified": True})),
            )
            return {
                "resourceId": str(challenge),
                "revision": self.verifier("verified-challenge-revision", str(challenge)),
                "requestId": str(operation),
            }

        return self.transactions.run("accounts", write)

    def login(
        self,
        email: str,
        password: str,
        *,
        operation: UUID | None = None,
        flow_binding: str = "diagnostic",
    ) -> SessionTransport:
        self._admit()
        email = EmailAddress(normalize_email(email)).value
        self.verifier("password-bound", password)
        observed = self.transactions.run(
            "accounts",
            lambda conn: conn.execute(
                "SELECT * FROM accounts.account WHERE email=%s", (email,)
            ).fetchone(),
        )
        valid = self._matches_password(
            observed["password_hash"] if observed else self._dummy, password
        )
        if not valid or not observed:
            raise PermissionError("credentials unavailable")
        operation = operation or uuid4()
        intent = self.verifier("login-intent", json.dumps([email, password, flow_binding]))
        token = self.verifier("login-cookie", str(operation) + ":" + intent)
        session = uuid4()
        csrf = self.verifier("session-csrf", token)

        def write(conn):
            row = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR UPDATE", (observed["id"],)
            ).fetchone()
            if (
                not row
                or not row["active"]
                or not row["verified"]
                or row["password_hash"] != observed["password_hash"]
            ):
                raise PermissionError("credentials unavailable")
            prior = conn.execute(
                "SELECT * FROM accounts.entry_receipt WHERE operation_id=%s", (operation,)
            ).fetchone()
            if prior:
                if prior["kind"] != "login" or prior["intent_hash"] != intent:
                    raise ValueError("login operation conflict")
                recorded = prior["outcome"]["session"]
                if recorded["accountId"] != str(row["id"]):
                    raise PermissionError("credentials unavailable")
                guard(conn, Authority(row["id"], UUID(recorded["sessionId"])))
                active = conn.execute(
                    "SELECT token_hash,csrf_hash FROM accounts.session WHERE id=%s",
                    (UUID(recorded["sessionId"]),),
                ).fetchone()
                if active["token_hash"] != self.verifier("session", token) or active[
                    "csrf_hash"
                ] != self.verifier("csrf", csrf):
                    raise PermissionError("session unavailable")
                return prior["outcome"]
            conn.execute(
                "UPDATE accounts.session SET revoked=true WHERE account_id=%s", (row["id"],)
            )
            conn.execute(
                "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,"
                "authority_revision,expires_at) VALUES(%s,%s,%s,%s,%s,"
                "clock_timestamp()+interval '1 hour')",
                (
                    session,
                    row["id"],
                    self.verifier("session", token),
                    self.verifier("csrf", csrf),
                    row["authority_revision"],
                ),
            )
            outcome = {
                "state": "authenticated",
                "session": {
                    "sessionId": str(session),
                    "accountId": str(row["id"]),
                    "authorityRevision": str(row["authority_revision"]),
                    "verified": True,
                    "authenticationLevel": "primary",
                },
            }
            conn.execute(
                "INSERT INTO accounts.entry_receipt VALUES(%s,'login',%s,%s)",
                (operation, intent, Jsonb(outcome)),
            )
            return outcome

        return SessionTransport(token, csrf, self.transactions.run("accounts", write))

    def _current_session(self, token: str, *, csrf: str | None = None) -> dict:
        hashed = self.verifier("session", token)

        def read(conn):
            row = conn.execute(
                "SELECT * FROM accounts.session WHERE token_hash=%s", (hashed,)
            ).fetchone()
            if not row:
                raise PermissionError("session unavailable")
            authority = Authority(row["account_id"], row["id"])
            guard(conn, authority)
            if csrf is not None and not hmac.compare_digest(
                row["csrf_hash"], self.verifier("csrf", csrf)
            ):
                raise PermissionError("session unavailable")
            return row

        return self.transactions.run("accounts", read)

    def authenticate(self, token: str, *, csrf: str | None = None) -> Authority:
        row = self._current_session(token, csrf=csrf)
        return Authority(row["account_id"], row["id"])

    def inspect_session(self, token: str) -> SessionTransport:
        """Recover the current session's CSRF without rotating it across tabs.

        Only possession of the opaque cookie and the protected verifier key
        derives this token. The persisted verifier and current authority still
        gate every bootstrap; an old or revoked session cannot be resurrected.
        """
        csrf = self.verifier("session-csrf", token)
        row = self._current_session(token, csrf=csrf)
        return SessionTransport(
            token,
            csrf,
            {
                "state": "authenticated",
                "session": {
                    "sessionId": str(row["id"]),
                    "accountId": str(row["account_id"]),
                    "authorityRevision": str(row["authority_revision"]),
                    "verified": True,
                    "authenticationLevel": "primary",
                    "expiresAt": row["expires_at"].isoformat(),
                },
            },
        )

    def logout(self, authority: Authority, *, operation: UUID | None = None) -> dict:
        operation = operation or uuid4()

        def write(conn):
            guard(conn, authority)
            conn.execute(
                "UPDATE accounts.session SET revoked=true WHERE id=%s AND account_id=%s",
                (authority.session_id, authority.account_id),
            )
            return {
                "resourceId": str(authority.session_id),
                "revision": self.verifier("revoked-session-revision", str(authority.session_id)),
                "requestId": str(operation),
            }

        return self.transactions.run("accounts", write)
