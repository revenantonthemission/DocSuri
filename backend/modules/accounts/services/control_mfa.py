"""Protected local MFA material and replay-fenced TOTP continuation."""

from __future__ import annotations

import base64
import hmac
import secrets
import struct
from urllib.parse import quote
from uuid import UUID, uuid4

from backend.modules.accounts.control_policy import PolicyUnavailable
from backend.modules.accounts.control_repository import ControlRepository
from backend.modules.accounts.services.guarded_entry import SessionTransport
from backend.transactions import Authority, guard


def totp(seed: str, step: int) -> str:
    """RFC 6238 SHA-1, six digits, 30-second steps; no external service."""
    value = hmac.digest(base64.b32decode(seed), struct.pack(">Q", step), "sha1")
    offset = value[-1] & 15
    return f"{(struct.unpack('>I', value[offset : offset + 4])[0] & 0x7FFFFFFF) % 1000000:06d}"


class ControlMfaService:
    def __init__(self, entry):
        self.entry = entry
        self.transactions, self.policy = entry.transactions, entry.control_policy

    def begin(self, authority: Authority, password: str, operation: UUID) -> dict:
        self.entry.reauthenticate(authority, password)
        identifier, delivery = uuid4(), uuid4()
        seed = base64.b32encode(secrets.token_bytes(20)).decode()
        codes = [secrets.token_hex(12) for _ in range(8)]
        encrypted = self.entry.protect("mfa:" + str(identifier), {"seed": seed, "codes": codes})

        def write(conn):
            guard(conn, authority, purpose="account-control")
            conn.execute(
                "SELECT id FROM accounts.account WHERE id=%s FOR UPDATE", (authority.account_id,)
            )
            digest, prior = ControlRepository.replay(
                conn, authority.account_id, "mfa-begin", operation, {"purpose": "enroll"}
            )
            if prior is not None:
                return prior
            conn.execute(
                "UPDATE accounts.mfa_enrollment SET state='invalidated' WHERE account_id=%s AND state='inactive'",
                (authority.account_id,),
            )
            if conn.execute(
                "SELECT 1 FROM accounts.mfa_enrollment WHERE account_id=%s AND state='active'",
                (authority.account_id,),
            ).fetchone():
                raise ValueError("active enrollment requires controlled replacement")
            row = conn.execute(
                "INSERT INTO accounts.mfa_enrollment(id,account_id,key_version,ciphertext,delivery_hash,delivery_expires_at,state) "
                "VALUES(%s,%s,'u2-v1',%s,%s,clock_timestamp()+(%s*interval '1 second'),'inactive') RETURNING delivery_expires_at",
                (
                    identifier,
                    authority.account_id,
                    encrypted,
                    self.entry.verifier("mfa-delivery", str(delivery)),
                    self.policy.material_seconds,
                ),
            ).fetchone()
            for code in codes:
                conn.execute(
                    "INSERT INTO accounts.mfa_recovery(enrollment_id,code_hash) VALUES(%s,%s)",
                    (identifier, self.entry.verifier("mfa-recovery", code)),
                )
            return ControlRepository.record(
                conn,
                authority.account_id,
                "mfa-begin",
                operation,
                digest,
                {
                    "enrollmentId": str(identifier),
                    "deliveryReference": str(delivery),
                    "expiresAt": row["delivery_expires_at"].isoformat(),
                    "nextAction": "confirm_factor",
                },
            )

        return self.transactions.run("accounts", write)

    def material(self, authority: Authority, identifier: UUID, delivery: str) -> dict:
        def write(conn):
            guard(conn, authority, purpose="account-control")
            row = conn.execute(
                "SELECT *,delivery_expires_at>clock_timestamp() AS fresh FROM accounts.mfa_enrollment "
                "WHERE id=%s AND account_id=%s FOR UPDATE",
                (identifier, authority.account_id),
            ).fetchone()
            if (
                not row
                or row["state"] != "inactive"
                or row["delivered_at"]
                or not row["fresh"]
                or not hmac.compare_digest(
                    row["delivery_hash"], self.entry.verifier("mfa-delivery", delivery)
                )
            ):
                raise PermissionError("enrollment material unavailable; start a new enrollment")
            material = self.entry.reveal("mfa:" + str(identifier), row["ciphertext"])
            conn.execute(
                "UPDATE accounts.mfa_enrollment SET delivered_at=clock_timestamp() WHERE id=%s",
                (identifier,),
            )
            return {
                "enrollmentId": str(identifier),
                "seed": material["seed"],
                "provisioningUri": "otpauth://totp/DocSuri:"
                + quote(str(authority.account_id))
                + "?secret="
                + material["seed"]
                + "&issuer=DocSuri",
                "recoveryCodes": material["codes"],
                "expiresAt": row["delivery_expires_at"].isoformat(),
            }

        return self.transactions.run("accounts", write)

    def _factor(self, conn, row: dict, code: str) -> int:
        if not isinstance(code, str) or len(code) != 6 or not code.isascii() or not code.isdigit():
            raise PermissionError("factor unavailable")
        seed = self.entry.reveal("mfa:" + str(row["id"]), row["ciphertext"])["seed"]
        step = int(
            conn.execute(
                "SELECT floor(extract(epoch FROM clock_timestamp())/30)::bigint AS step"
            ).fetchone()["step"]
        )
        for candidate in (step, step - 1):
            if (row["last_step"] is None or candidate > row["last_step"]) and hmac.compare_digest(
                totp(seed, candidate), code
            ):
                return candidate
        raise PermissionError("factor unavailable")

    def confirm(self, authority: Authority, identifier: UUID, code: str, operation: UUID) -> dict:
        def write(conn):
            guard(conn, authority, purpose="account-control")
            digest, prior = ControlRepository.replay(
                conn,
                authority.account_id,
                "mfa-confirm",
                operation,
                {"enrollment": str(identifier), "proof": self.entry.verifier("factor", code)},
            )
            if prior is not None:
                return prior
            row = conn.execute(
                "SELECT *,delivery_expires_at>clock_timestamp() AS fresh FROM accounts.mfa_enrollment "
                "WHERE id=%s AND account_id=%s FOR UPDATE",
                (identifier, authority.account_id),
            ).fetchone()
            if not row or row["state"] != "inactive" or not row["delivered_at"] or not row["fresh"]:
                raise PermissionError("enrollment unavailable")
            step = self._factor(conn, row, code)
            revision = uuid4()
            conn.execute(
                "UPDATE accounts.mfa_enrollment SET state='active',last_step=%s,revision=%s WHERE id=%s",
                (step, revision, identifier),
            )
            return ControlRepository.record(
                conn,
                authority.account_id,
                "mfa-confirm",
                operation,
                digest,
                {
                    "resourceId": str(identifier),
                    "revision": str(revision),
                    "requestId": str(operation),
                },
            )

        return self.transactions.run("accounts", write)

    def verify(
        self, token: str, csrf: str, challenge: UUID, flow: UUID, code: str
    ) -> SessionTransport:
        observed = self.entry._current_session(token, csrf=csrf, limited=True)
        if (
            observed["purpose"] != "primary_mfa_continuation"
            or observed["id"] != challenge
            or observed["flow_id"] != flow
        ):
            raise PermissionError("primary continuation required")

        def write(conn):
            account = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR UPDATE", (observed["account_id"],)
            ).fetchone()
            session = conn.execute(
                "SELECT *,expires_at>clock_timestamp() AS fresh FROM accounts.session WHERE id=%s FOR UPDATE",
                (challenge,),
            ).fetchone()
            if (
                not account["active"]
                or not account["verified"]
                or account["lifecycle_state"] != "active"
                or session["revoked"]
                or not session["fresh"]
                or session["authority_revision"] != account["authority_revision"]
                or session["purpose"] != "primary_mfa_continuation"
            ):
                raise PermissionError("primary continuation unavailable")
            row = conn.execute(
                "SELECT * FROM accounts.mfa_enrollment WHERE account_id=%s AND state='active' FOR UPDATE",
                (account["id"],),
            ).fetchone()
            if not row:
                raise PermissionError("factor unavailable")
            step = self._factor(conn, row, code)
            conn.execute(
                "UPDATE accounts.mfa_enrollment SET last_step=%s WHERE id=%s", (step, row["id"])
            )
            session = conn.execute(
                "UPDATE accounts.session SET purpose='full_session',mfa_at=clock_timestamp(),"
                "expires_at=clock_timestamp()+(%s*interval '1 second') WHERE id=%s RETURNING *",
                (self.policy.session_seconds, challenge),
            ).fetchone()
            return self.entry.public_session(session)

        return SessionTransport(token, csrf, self.transactions.run("accounts", write))

    def recover(self, *args, **kwargs):
        raise PolicyUnavailable("controlled MFA recovery remains gated; no administrator bypass")
