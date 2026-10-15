"""U2 credential controls with purpose-bound proof and limited MFA sessions."""

from __future__ import annotations

import hmac
import json
import secrets
from uuid import UUID, uuid4

from backend.modules.accounts.control_keys import ControlKeyring
from backend.modules.accounts.control_policy import ControlPolicy, PolicyUnavailable
from backend.modules.accounts.control_repository import ControlRepository
from backend.modules.accounts.models import EmailAddress, normalize_email
from backend.modules.accounts.password import PasswordPolicy
from backend.modules.accounts.services.guarded_entry import GuardedEntryService, SessionTransport
from backend.transactions import Authority, guard
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from psycopg.types.json import Jsonb


class ControlEntryService(GuardedEntryService):
    policy = "u2-synthetic-v1"

    def __init__(self, transactions, policy: ControlPolicy):
        policy.require_realm(transactions.profile.realm)
        self.control_policy = policy
        self.account_limit = policy.max_accounts
        self.verification_seconds = policy.proof_seconds
        if not (transactions.profile.root / "account-verifier.key").exists():
            occupied = transactions.run(
                "accounts",
                lambda conn: conn.execute(
                    "SELECT EXISTS(SELECT 1 FROM accounts.account) AS occupied"
                ).fetchone()["occupied"],
            )
            if occupied:
                raise PolicyUnavailable("existing accounts require retained verifier custody")
        super().__init__(transactions)
        self.keyring = ControlKeyring(
            transactions.profile.root,
            transactions.profile.run_id,
            bytes.fromhex(self.verifier("encryption", "u2-controls-v1")),
        )
        versions = self.transactions.run(
            "accounts",
            lambda conn: conn.execute(
                "SELECT key_version FROM accounts.control_proof WHERE key_version IS NOT NULL UNION "
                "SELECT key_version FROM accounts.mfa_enrollment UNION "
                "SELECT key_version FROM accounts.identity_flow LIMIT 4"
            ).fetchall(),
        )
        for row in versions:
            self.keyring.key(row["key_version"])

    def protect(self, purpose: str, value: dict) -> bytes:
        version = self.keyring.active_version.encode("ascii")
        nonce = secrets.token_bytes(12)
        return (
            b"DSC2"
            + bytes([len(version)])
            + version
            + nonce
            + AESGCM(self.keyring.key(version.decode("ascii"))).encrypt(
                nonce, json.dumps(value).encode(), purpose.encode() + b":" + version
            )
        )

    def reveal(self, purpose: str, value: bytes) -> dict:
        value = bytes(value)
        if value.startswith(b"DSC2"):
            if len(value) < 5 or not 1 <= value[4] <= 40:
                raise ValueError("invalid protected material envelope")
            version = value[5 : 5 + value[4]]
            body = value[5 + value[4] :]
            return json.loads(
                AESGCM(self.keyring.key(version.decode("ascii"))).decrypt(
                    body[:12], body[12:], purpose.encode() + b":" + version
                )
            )
        return json.loads(
            AESGCM(self.keyring.key("u2-v1")).decrypt(value[:12], value[12:], purpose.encode())
        )

    @staticmethod
    def protection_version(value: bytes) -> str:
        return value[5 : 5 + value[4]].decode("ascii") if value.startswith(b"DSC2") else "u2-v1"

    def _current_session(
        self, token: str, *, csrf: str | None = None, limited: bool = False
    ) -> dict:
        digest = self.verifier("session", token)

        def read(conn):
            observed = conn.execute(
                "SELECT account_id FROM accounts.session WHERE token_hash=%s", (digest,)
            ).fetchone()
            if not observed:
                raise PermissionError("session unavailable")
            account = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR SHARE", (observed["account_id"],)
            ).fetchone()
            row = conn.execute(
                "SELECT *,expires_at>clock_timestamp() AS fresh FROM accounts.session WHERE token_hash=%s FOR SHARE",
                (digest,),
            ).fetchone()
            if (
                not account["active"]
                or account["lifecycle_state"] != "active"
                or not account["verified"]
                or not row["fresh"]
                or row["revoked"]
                or row["authority_revision"] != account["authority_revision"]
            ):
                raise PermissionError("session unavailable")
            if row["purpose"] != "full_session" and not (
                limited and row["purpose"] == "primary_mfa_continuation"
            ):
                raise PermissionError("full session required")
            if csrf is not None and not hmac.compare_digest(
                row["csrf_hash"], self.verifier("csrf", csrf)
            ):
                raise PermissionError("session unavailable")
            return row

        return self.transactions.run("accounts", read)

    @staticmethod
    def public_session(row: dict) -> dict:
        if row["purpose"] == "primary_mfa_continuation":
            return {
                "state": "mfa_required",
                "challengeId": str(row["id"]),
                "flowBinding": str(row["flow_id"]),
                "expiresAt": row["expires_at"].isoformat(),
            }
        return {
            "state": "authenticated",
            "session": {
                "sessionId": str(row["id"]),
                "accountId": str(row["account_id"]),
                "authorityRevision": str(row["authority_revision"]),
                "verified": True,
                "authenticationLevel": "mfa" if row["mfa_at"] else "primary",
                "expiresAt": row["expires_at"].isoformat(),
            },
        }

    def inspect_session(self, token: str) -> SessionTransport:
        csrf = self.verifier("session-csrf", token)
        row = self._current_session(token, csrf=csrf, limited=True)
        return SessionTransport(token, csrf, self.public_session(row))

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
        if (
            not self._matches_password(
                observed["password_hash"] if observed else self._dummy, password
            )
            or not observed
        ):
            raise PermissionError("credentials unavailable")
        operation = operation or uuid4()
        intent = self.verifier("login-intent", json.dumps([email, password, flow_binding]))
        token = self.verifier("login-cookie", str(operation) + ":" + intent)
        csrf = self.verifier("session-csrf", token)

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
            previous = conn.execute(
                "SELECT * FROM accounts.entry_receipt WHERE operation_id=%s", (operation,)
            ).fetchone()
            if previous:
                if previous["kind"] != "login" or previous["intent_hash"] != intent:
                    raise ValueError("login operation conflict")
                row = conn.execute(
                    "SELECT *,expires_at>clock_timestamp() AS fresh FROM accounts.session WHERE token_hash=%s",
                    (self.verifier("session", token),),
                ).fetchone()
                if (
                    not row
                    or row["revoked"]
                    or not row["fresh"]
                    or row["authority_revision"] != account["authority_revision"]
                ):
                    raise PermissionError("session unavailable")
                return self.public_session(row)
            factor = conn.execute(
                "SELECT id FROM accounts.mfa_enrollment WHERE account_id=%s AND state='active'",
                (account["id"],),
            ).fetchone()
            requires_mfa = account["role"] == "administrator" or factor is not None
            if account["role"] == "administrator" and factor is None:
                raise PermissionError("administrator factor enrollment required")
            row = conn.execute(
                "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,expires_at,purpose,flow_id) "
                "VALUES(%s,%s,%s,%s,%s,clock_timestamp()+(%s*interval '1 second'),%s,%s) RETURNING *",
                (
                    uuid4(),
                    account["id"],
                    self.verifier("session", token),
                    self.verifier("csrf", csrf),
                    account["authority_revision"],
                    self.control_policy.proof_seconds
                    if requires_mfa
                    else self.control_policy.session_seconds,
                    "primary_mfa_continuation" if requires_mfa else "full_session",
                    uuid4(),
                ),
            ).fetchone()
            outcome = self.public_session(row)
            conn.execute(
                "INSERT INTO accounts.entry_receipt VALUES(%s,'login',%s,%s)",
                (operation, intent, Jsonb(outcome)),
            )
            return outcome

        return SessionTransport(token, csrf, self.transactions.run("accounts", write))

    def reauthenticate(self, authority: Authority, password: str) -> None:
        self.verifier("password-bound", password)
        observed = self.transactions.run(
            "accounts",
            lambda conn: conn.execute(
                "SELECT password_hash FROM accounts.account WHERE id=%s", (authority.account_id,)
            ).fetchone(),
        )
        if not observed or not self._matches_password(observed["password_hash"], password):
            raise PermissionError("reauthentication required")

        def check(conn):
            guard(conn, authority, purpose="account-control")
            current = conn.execute(
                "SELECT password_hash FROM accounts.account WHERE id=%s", (authority.account_id,)
            ).fetchone()
            if current["password_hash"] != observed["password_hash"]:
                raise PermissionError("credential changed during reauthentication")

        self.transactions.run("accounts", check)

    def request_password_reset(self, operation: UUID, email: str, flow_binding: str) -> dict:
        self._admit()
        email = EmailAddress(normalize_email(email)).value
        intent = self.verifier("password-reset-request", json.dumps([email, flow_binding]))
        identifier, proof = uuid4(), secrets.token_urlsafe(32)
        artifact = self.mail.publish(
            json.dumps(
                {
                    "challengeId": str(identifier),
                    "proof": proof,
                    "flowBinding": flow_binding,
                    "email": email,
                    "purpose": "password-reset",
                }
            ).encode()
        )

        def write(conn):
            prior = conn.execute(
                "SELECT * FROM accounts.entry_receipt WHERE operation_id=%s", (operation,)
            ).fetchone()
            if prior:
                if prior["kind"] != "password-reset" or prior["intent_hash"] != intent:
                    raise ValueError("reset request conflict")
                return prior["outcome"]
            row = conn.execute(
                "SELECT * FROM accounts.account WHERE email=%s FOR UPDATE", (email,)
            ).fetchone()
            if row and row["active"] and row["verified"] and row["lifecycle_state"] == "active":
                conn.execute(
                    "INSERT INTO accounts.control_proof(id,account_id,purpose,proof_hash,flow_hash,authority_revision,lifecycle_revision,"
                    "protected_payload,key_version,expires_at) VALUES(%s,%s,'password-reset',%s,%s,%s,%s,%s,%s,clock_timestamp()+(%s*interval '1 second'))",
                    (
                        identifier,
                        row["id"],
                        self.verifier("reset-proof", proof),
                        self.verifier("flow", flow_binding),
                        row["authority_revision"],
                        row["lifecycle_revision"],
                        (
                            protected := self.protect(
                                "proof:" + str(identifier), {"delivery": artifact.name}
                            )
                        ),
                        self.protection_version(protected),
                        self.control_policy.proof_seconds,
                    ),
                )
            outcome = self._ack(operation)
            conn.execute(
                "INSERT INTO accounts.entry_receipt VALUES(%s,'password-reset',%s,%s)",
                (operation, intent, Jsonb(outcome)),
            )
            return outcome

        return self.transactions.run("accounts", write)

    def complete_password_reset(
        self, operation: UUID, challenge: UUID, proof: str, flow_binding: str, new_password: str
    ) -> dict:
        self._admit()
        PasswordPolicy.evaluate(new_password)
        if len(new_password.encode()) > self.control_policy.max_password_bytes:
            raise ValueError("password outside policy")
        encoded = self._hash_password(new_password)
        intent = self.verifier(
            "reset-completion", json.dumps([str(challenge), proof, flow_binding, new_password])
        )

        def write(conn):
            found = conn.execute(
                "SELECT account_id FROM accounts.control_proof WHERE id=%s", (challenge,)
            ).fetchone()
            if not found:
                raise PermissionError("proof unavailable")
            account = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR UPDATE", (found["account_id"],)
            ).fetchone()
            row = conn.execute(
                "SELECT *,expires_at>clock_timestamp() AS fresh FROM accounts.control_proof WHERE id=%s FOR UPDATE",
                (challenge,),
            ).fetchone()
            if (
                row["purpose"] != "password-reset"
                or not hmac.compare_digest(row["proof_hash"], self.verifier("reset-proof", proof))
                or not hmac.compare_digest(row["flow_hash"], self.verifier("flow", flow_binding))
                or not account["active"]
                or account["lifecycle_state"] != "active"
            ):
                raise PermissionError("proof unavailable")
            prior = conn.execute(
                "SELECT * FROM accounts.control_receipt WHERE account_id=%s AND kind='password-reset' AND key=%s",
                (account["id"], operation),
            ).fetchone()
            if prior:
                if (
                    prior["intent_hash"] != intent
                    or row["operation_id"] != operation
                    or row["outcome"]["revision"] != str(account["authority_revision"])
                ):
                    raise PermissionError("proof unavailable")
                return prior["outcome"]
            if (
                not row["fresh"]
                or row["consumed_at"]
                or row["authority_revision"] != account["authority_revision"]
                or row["lifecycle_revision"] != account["lifecycle_revision"]
            ):
                raise PermissionError("proof unavailable")
            revision = uuid4()
            outcome = {
                "resourceId": str(account["id"]),
                "revision": str(revision),
                "requestId": str(operation),
            }
            conn.execute(
                "UPDATE accounts.account SET password_hash=%s,authority_revision=%s WHERE id=%s",
                (encoded, revision, account["id"]),
            )
            conn.execute(
                "UPDATE accounts.session SET revoked=true WHERE account_id=%s", (account["id"],)
            )
            conn.execute(
                "UPDATE accounts.control_proof SET consumed_at=clock_timestamp(),operation_id=%s,outcome=%s WHERE id=%s",
                (operation, Jsonb(outcome), challenge),
            )
            return ControlRepository.record(
                conn, account["id"], "password-reset", operation, intent, outcome
            )

        return self.transactions.run("accounts", write)

    def change_password(
        self, authority: Authority, operation: UUID, current_password: str, new_password: str
    ) -> dict:
        self.reauthenticate(authority, current_password)
        PasswordPolicy.evaluate(new_password)
        if len(new_password.encode()) > self.control_policy.max_password_bytes:
            raise ValueError("password outside policy")
        encoded = self._hash_password(new_password)
        intent = self.verifier("password-change", json.dumps([current_password, new_password]))

        def write(conn):
            guard(conn, authority, purpose="account-control")
            conn.execute(
                "SELECT id FROM accounts.account WHERE id=%s FOR UPDATE", (authority.account_id,)
            )
            prior = conn.execute(
                "SELECT * FROM accounts.control_receipt WHERE account_id=%s AND kind='password-change' AND key=%s",
                (authority.account_id, operation),
            ).fetchone()
            if prior:
                if prior["intent_hash"] != intent:
                    raise ValueError("credential operation conflict")
                return prior["outcome"]
            revision = uuid4()
            conn.execute(
                "UPDATE accounts.account SET password_hash=%s,authority_revision=%s WHERE id=%s",
                (encoded, revision, authority.account_id),
            )
            conn.execute(
                "UPDATE accounts.session SET revoked=true WHERE account_id=%s",
                (authority.account_id,),
            )
            return ControlRepository.record(
                conn,
                authority.account_id,
                "password-change",
                operation,
                intent,
                {
                    "resourceId": str(authority.account_id),
                    "revision": str(revision),
                    "requestId": str(operation),
                },
            )

        return self.transactions.run("accounts", write)

    def reconcile_credential_change(
        self, token: str, csrf: str, operation: UUID, kind: str, values: list[str]
    ) -> dict:
        """Read only an exact acknowledged effect through its still-fresh former session.

        Credential mutation revokes the submitting cookie atomically. Its lost response
        must remain discoverable without turning that revoked cookie into authority.
        A later authority change, expiry, different body or missing receipt denies this
        narrow recovery path; it never performs or repeats a credential mutation.
        """
        purposes = {"password-change": "password-change", "email-complete": "email-completion"}
        if kind not in purposes:
            raise PermissionError("credential receipt unavailable")
        intent = self.verifier(purposes[kind], json.dumps(values))

        def read(conn):
            observed = conn.execute(
                "SELECT account_id FROM accounts.session WHERE token_hash=%s",
                (self.verifier("session", token),),
            ).fetchone()
            if not observed:
                raise PermissionError("credential receipt unavailable")
            account = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR SHARE",
                (observed["account_id"],),
            ).fetchone()
            session = conn.execute(
                "SELECT *,expires_at>clock_timestamp() AS fresh FROM accounts.session "
                "WHERE token_hash=%s FOR SHARE",
                (self.verifier("session", token),),
            ).fetchone()
            receipt = conn.execute(
                "SELECT * FROM accounts.control_receipt WHERE account_id=%s AND kind=%s AND key=%s",
                (account["id"], kind, operation),
            ).fetchone()
            if (
                not session["fresh"]
                or session["purpose"] != "full_session"
                or not hmac.compare_digest(session["csrf_hash"], self.verifier("csrf", csrf))
                or not account["active"]
                or not account["verified"]
                or account["lifecycle_state"] != "active"
                or not receipt
                or not hmac.compare_digest(receipt["intent_hash"], intent)
                or receipt["outcome"]["revision"] != str(account["authority_revision"])
            ):
                raise PermissionError("credential receipt unavailable")
            return receipt["outcome"]

        return self.transactions.run("accounts", read)

    def request_email_change(
        self,
        authority: Authority,
        operation: UUID,
        password: str,
        new_email: str,
        flow_binding: str,
    ) -> dict:
        self.reauthenticate(authority, password)
        new_email = EmailAddress(normalize_email(new_email)).value
        identifier, proof = uuid4(), secrets.token_urlsafe(32)
        intent = self.verifier("email-change", json.dumps([new_email, flow_binding]))
        artifact = self.mail.publish(
            json.dumps(
                {
                    "challengeId": str(identifier),
                    "proof": proof,
                    "flowBinding": flow_binding,
                    "email": new_email,
                    "purpose": "email-change",
                }
            ).encode()
        )

        def write(conn):
            guard(conn, authority, purpose="account-control")
            account = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR UPDATE", (authority.account_id,)
            ).fetchone()
            prior = conn.execute(
                "SELECT * FROM accounts.control_receipt WHERE account_id=%s AND kind='email-request' AND key=%s",
                (authority.account_id, operation),
            ).fetchone()
            if prior:
                if prior["intent_hash"] != intent:
                    raise ValueError("email request conflict")
                return prior["outcome"]
            conn.execute(
                "INSERT INTO accounts.control_proof(id,account_id,purpose,proof_hash,flow_hash,authority_revision,lifecycle_revision,"
                "protected_payload,key_version,expires_at) VALUES(%s,%s,'email-change',%s,%s,%s,%s,%s,%s,clock_timestamp()+(%s*interval '1 second'))",
                (
                    identifier,
                    authority.account_id,
                    self.verifier("email-proof", proof),
                    self.verifier("flow", flow_binding),
                    account["authority_revision"],
                    account["lifecycle_revision"],
                    (
                        protected := self.protect(
                            "proof:" + str(identifier),
                            {"email": new_email, "delivery": artifact.name},
                        )
                    ),
                    self.protection_version(protected),
                    self.control_policy.proof_seconds,
                ),
            )
            return ControlRepository.record(
                conn, authority.account_id, "email-request", operation, intent, self._ack(operation)
            )

        return self.transactions.run("accounts", write)

    def complete_email_change(
        self, authority: Authority, operation: UUID, challenge: UUID, proof: str, flow_binding: str
    ) -> dict:
        intent = self.verifier(
            "email-completion", json.dumps([str(challenge), proof, flow_binding])
        )

        def write(conn):
            guard(conn, authority, purpose="account-control")
            account = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR UPDATE", (authority.account_id,)
            ).fetchone()
            row = conn.execute(
                "SELECT *,expires_at>clock_timestamp() AS fresh FROM accounts.control_proof WHERE id=%s AND account_id=%s FOR UPDATE",
                (challenge, authority.account_id),
            ).fetchone()
            if (
                not row
                or row["purpose"] != "email-change"
                or not row["fresh"]
                or row["consumed_at"]
                or row["authority_revision"] != account["authority_revision"]
                or row["lifecycle_revision"] != account["lifecycle_revision"]
                or not hmac.compare_digest(row["proof_hash"], self.verifier("email-proof", proof))
                or not hmac.compare_digest(row["flow_hash"], self.verifier("flow", flow_binding))
            ):
                raise PermissionError("email proof unavailable")
            email = self.reveal("proof:" + str(challenge), row["protected_payload"])["email"]
            if conn.execute(
                "SELECT 1 FROM accounts.account WHERE email=%s AND id<>%s",
                (email, authority.account_id),
            ).fetchone():
                raise PermissionError("email replacement unavailable")
            revision = uuid4()
            outcome = {
                "resourceId": str(authority.account_id),
                "revision": str(revision),
                "requestId": str(operation),
            }
            conn.execute(
                "UPDATE accounts.account SET email=%s,authority_revision=%s WHERE id=%s",
                (email, revision, authority.account_id),
            )
            conn.execute(
                "UPDATE accounts.session SET revoked=true WHERE account_id=%s",
                (authority.account_id,),
            )
            conn.execute(
                "UPDATE accounts.control_proof SET consumed_at=clock_timestamp(),operation_id=%s,outcome=%s WHERE id=%s",
                (operation, Jsonb(outcome), challenge),
            )
            return ControlRepository.record(
                conn, authority.account_id, "email-complete", operation, intent, outcome
            )

        return self.transactions.run("accounts", write)

    def logout(self, authority: Authority, *, operation: UUID | None = None) -> dict:
        operation = operation or uuid4()

        def write(conn):
            guard(conn, authority, purpose="account-control")
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

    def request_reactivation(self, operation: UUID, email: str, flow_binding: str) -> dict:
        self._admit()
        email = EmailAddress(normalize_email(email)).value
        intent = self.verifier("reactivation-request", json.dumps([email, flow_binding]))
        identifier, proof = uuid4(), secrets.token_urlsafe(32)
        artifact = self.mail.publish(
            json.dumps(
                {
                    "challengeId": str(identifier),
                    "proof": proof,
                    "flowBinding": flow_binding,
                    "email": email,
                    "purpose": "reactivate",
                }
            ).encode()
        )

        def write(conn):
            prior = conn.execute(
                "SELECT * FROM accounts.entry_receipt WHERE operation_id=%s", (operation,)
            ).fetchone()
            if prior:
                if prior["kind"] != "reactivation" or prior["intent_hash"] != intent:
                    raise ValueError("reactivation request conflict")
                return prior["outcome"]
            row = conn.execute(
                "SELECT * FROM accounts.account WHERE email=%s FOR UPDATE", (email,)
            ).fetchone()
            if row and row["verified"] and row["lifecycle_state"] == "withdrawn":
                conn.execute(
                    "INSERT INTO accounts.control_proof(id,account_id,purpose,proof_hash,flow_hash,authority_revision,lifecycle_revision,"
                    "protected_payload,key_version,expires_at) VALUES(%s,%s,'reactivate',%s,%s,%s,%s,%s,%s,clock_timestamp()+(%s*interval '1 second'))",
                    (
                        identifier,
                        row["id"],
                        self.verifier("reactivation-proof", proof),
                        self.verifier("flow", flow_binding),
                        row["authority_revision"],
                        row["lifecycle_revision"],
                        (
                            protected := self.protect(
                                "proof:" + str(identifier), {"delivery": artifact.name}
                            )
                        ),
                        self.protection_version(protected),
                        self.control_policy.proof_seconds,
                    ),
                )
            return_value = self._ack(operation)
            conn.execute(
                "INSERT INTO accounts.entry_receipt VALUES(%s,'reactivation',%s,%s)",
                (operation, intent, Jsonb(return_value)),
            )
            return return_value

        return self.transactions.run("accounts", write)
