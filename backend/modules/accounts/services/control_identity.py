"""Distinct identity-provider ports with a labelled synthetic protocol adapter."""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode
from uuid import UUID, uuid4

from backend.modules.accounts.control_repository import ControlRepository
from backend.modules.accounts.services.guarded_entry import SessionTransport
from backend.transactions import Authority, guard
from psycopg.types.json import Jsonb


@dataclass(frozen=True)
class IdentityClaims:
    provider: str
    subject: str
    issuer: str
    audience: str
    nonce: str
    verified_email: str | None
    profile: dict


class IdentityProvider(Protocol):
    name: str
    issuer: str
    audience: str
    callback: str

    def exchange(self, code: str, *, verifier: str, nonce: str) -> IdentityClaims: ...


class FixtureIdentityProvider:
    """Explicitly injected local adapter; never selected for public activation."""

    def __init__(self, name: str):
        if name not in ("google", "orcid"):
            raise ValueError("unsupported provider")
        self.name, self.issuer, self.audience = (
            name,
            "https://fixture.invalid/" + name,
            "docsuri-u2-fixture",
        )
        self.callback = "https://127.0.0.1:18049/api/v2/identity/callback/" + name
        self._codes: dict[str, tuple[str, IdentityClaims]] = {}

    def issue(self, claims: IdentityClaims, verifier: str) -> str:
        if len(self._codes) >= 20:
            raise ValueError("finite fixture code capacity")
        code = secrets.token_urlsafe(32)
        self._codes[code] = (verifier, claims)
        return code

    def exchange(self, code: str, *, verifier: str, nonce: str) -> IdentityClaims:
        value = self._codes.pop(code, None)
        if value is None or not hmac.compare_digest(value[0], verifier):
            raise PermissionError("provider code unavailable")
        return value[1]


class ControlIdentityService:
    def __init__(self, entry, providers: dict[str, IdentityProvider]):
        if set(providers) != {"google", "orcid"} or any(
            name != provider.name for name, provider in providers.items()
        ):
            raise ValueError("distinct Google and ORCID adapters required")
        self.entry, self.providers, self.transactions = entry, providers, entry.transactions

    def begin(
        self, authority: Authority | None, provider: str, intent: str, binding: str, route: str
    ) -> dict:
        if (
            provider not in self.providers
            or intent not in ("sign_in", "link")
            or route not in ("search", "library", "settings")
        ):
            raise ValueError("identity flow input unavailable")
        if intent == "link" and authority is None:
            raise PermissionError("link owner required")
        adapter = self.providers[provider]
        identifier, state, nonce, verifier = (
            uuid4(),
            secrets.token_urlsafe(32),
            secrets.token_urlsafe(24),
            secrets.token_urlsafe(32),
        )

        def write(conn):
            revision = guard(conn, authority, purpose="account-control") if authority else None
            count = conn.execute(
                "SELECT count(*) AS n FROM accounts.identity_flow WHERE expires_at>clock_timestamp() AND disposition IN ('pending','exchanging')"
            ).fetchone()["n"]
            if count >= 20:
                raise ValueError("finite identity flow capacity")
            row = conn.execute(
                "INSERT INTO accounts.identity_flow(id,account_id,provider,intent,state_hash,binding_hash,authority_revision,"
                "callback_id,return_route,secret_ciphertext,key_version,expires_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'u2-v1',"
                "clock_timestamp()+interval '5 minutes') RETURNING expires_at",
                (
                    identifier,
                    authority.account_id if authority else None,
                    provider,
                    intent,
                    self.entry.verifier("identity-state", state),
                    self.entry.verifier("flow", binding),
                    revision,
                    adapter.callback,
                    route,
                    self.entry.protect(
                        "identity:" + str(identifier), {"nonce": nonce, "verifier": verifier}
                    ),
                ),
            ).fetchone()
            return {
                "flowId": str(identifier),
                "state": state,
                "expiresAt": row["expires_at"].isoformat(),
                "provider": provider,
                "callback": adapter.callback,
                "fixtureOnly": True,
            }

        return self.transactions.run("accounts", write)

    def fixture_authorization(self, accepted: dict) -> str:
        """Only the installed synthetic adapter can issue a local protocol fixture."""
        provider = self.providers[accepted["provider"]]
        if not isinstance(provider, FixtureIdentityProvider):
            raise PermissionError("fixture provider required")
        identifier = UUID(accepted["flowId"])

        def read(conn):
            row = conn.execute(
                "SELECT secret_ciphertext,disposition FROM accounts.identity_flow WHERE id=%s",
                (identifier,),
            ).fetchone()
            if not row or row["disposition"] != "pending":
                raise PermissionError("fixture flow unavailable")
            return self.entry.reveal("identity:" + str(identifier), row["secret_ciphertext"])

        secret = self.transactions.run("accounts", read)
        claims = IdentityClaims(
            provider.name,
            "synthetic-researcher-" + provider.name,
            provider.issuer,
            provider.audience,
            secret["nonce"],
            None,
            {"displayName": "합성 연구자", "works": []},
        )
        code = provider.issue(claims, secret["verifier"])
        return (
            provider.callback
            + "?"
            + urlencode({"flow": str(identifier), "state": accepted["state"], "code": code})
        )

    def complete(
        self,
        identifier: UUID,
        state: str,
        binding: str,
        code: str,
        callback: str,
        authority: Authority | None,
    ) -> dict:
        def claim(conn):
            found = conn.execute(
                "SELECT account_id FROM accounts.identity_flow WHERE id=%s", (identifier,)
            ).fetchone()
            if not found:
                raise PermissionError("identity flow unavailable")
            if found["account_id"]:
                if not authority or authority.account_id != found["account_id"]:
                    raise PermissionError("identity owner unavailable")
                revision = guard(conn, authority, purpose="account-control")
            else:
                revision = None
            row = conn.execute(
                "SELECT *,expires_at>clock_timestamp() AS fresh FROM accounts.identity_flow WHERE id=%s FOR UPDATE",
                (identifier,),
            ).fetchone()
            if (
                row["callback_id"] != callback
                or not hmac.compare_digest(
                    row["state_hash"], self.entry.verifier("identity-state", state)
                )
                or not hmac.compare_digest(
                    row["binding_hash"], self.entry.verifier("flow", binding)
                )
                or row["authority_revision"] != revision
            ):
                raise PermissionError("identity flow unavailable")
            if row["disposition"] == "complete":
                return row, None
            if not row["fresh"] or row["disposition"] != "pending":
                raise PermissionError("identity exchange not replayable")
            conn.execute(
                "UPDATE accounts.identity_flow SET disposition='exchanging' WHERE id=%s",
                (identifier,),
            )
            return row, self.entry.reveal("identity:" + str(identifier), row["secret_ciphertext"])

        row, protected = self.transactions.run("accounts", claim)
        token = self.entry.verifier("identity-cookie", str(identifier))
        csrf = self.entry.verifier("session-csrf", token)
        if protected is None:
            if row["intent"] == "sign_in":
                return self.entry.inspect_session(token)
            return row["outcome"]
        adapter = self.providers[row["provider"]]
        try:
            claims = adapter.exchange(
                code, verifier=protected["verifier"], nonce=protected["nonce"]
            )
            if (
                claims.provider != adapter.name
                or claims.issuer != adapter.issuer
                or claims.audience != adapter.audience
                or not hmac.compare_digest(claims.nonce, protected["nonce"])
                or not claims.subject
                or len(claims.subject.encode()) > 512
            ):
                raise PermissionError("provider claims unavailable")
        except Exception:
            self.transactions.run(
                "accounts",
                lambda conn: conn.execute(
                    "UPDATE accounts.identity_flow SET disposition='unknown' WHERE id=%s AND disposition='exchanging'",
                    (identifier,),
                ),
            )
            raise

        def finish(conn):
            if authority:
                revision = guard(conn, authority, purpose="account-control")
                if revision != row["authority_revision"]:
                    raise PermissionError("identity owner changed")
            account = None
            if row["intent"] == "sign_in":
                candidate = conn.execute(
                    "SELECT account_id FROM accounts.identity_link WHERE provider=%s AND subject=%s",
                    (claims.provider, claims.subject),
                ).fetchone()
                if not candidate:
                    raise PermissionError("verified identity link required")
                account = conn.execute(
                    "SELECT * FROM accounts.account WHERE id=%s FOR UPDATE",
                    (candidate["account_id"],),
                ).fetchone()
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,23))",
                (claims.provider + ":" + claims.subject,),
            )
            flow = conn.execute(
                "SELECT * FROM accounts.identity_flow WHERE id=%s FOR UPDATE", (identifier,)
            ).fetchone()
            if flow["disposition"] != "exchanging":
                raise ValueError("identity flow changed")
            linked = conn.execute(
                "SELECT * FROM accounts.identity_link WHERE provider=%s AND subject=%s",
                (claims.provider, claims.subject),
            ).fetchone()
            if row["intent"] == "link":
                if linked and linked["account_id"] != authority.account_id:
                    raise PermissionError("provider identity already bound")
                if not linked:
                    linked = conn.execute(
                        "INSERT INTO accounts.identity_link(id,account_id,provider,subject,provenance) VALUES(%s,%s,%s,%s,%s) RETURNING *",
                        (
                            uuid4(),
                            authority.account_id,
                            claims.provider,
                            claims.subject,
                            Jsonb(
                                {
                                    "source": claims.provider,
                                    "fixtureOnly": True,
                                    "profile": claims.profile,
                                }
                            ),
                        ),
                    ).fetchone()
                outcome = {
                    "linkId": str(linked["id"]),
                    "provider": claims.provider,
                    "revision": str(linked["revision"]),
                }
            else:
                if not linked or linked["account_id"] != account["id"]:
                    raise PermissionError(
                        "identity registration requires verified local account linking"
                    )
                if (
                    not account["active"]
                    or not account["verified"]
                    or account["lifecycle_state"] != "active"
                ):
                    raise PermissionError("linked account unavailable")
                factor = conn.execute(
                    "SELECT id FROM accounts.mfa_enrollment WHERE account_id=%s AND state='active'",
                    (account["id"],),
                ).fetchone()
                if account["role"] == "administrator" and not factor:
                    raise PermissionError("administrator factor unavailable")
                requires_mfa = account["role"] == "administrator" or factor is not None
                session = conn.execute(
                    "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,expires_at,purpose,flow_id) "
                    "VALUES(%s,%s,%s,%s,%s,clock_timestamp()+(%s*interval '1 second'),%s,%s) RETURNING *",
                    (
                        uuid4(),
                        account["id"],
                        self.entry.verifier("session", token),
                        self.entry.verifier("csrf", csrf),
                        account["authority_revision"],
                        self.entry.control_policy.proof_seconds
                        if requires_mfa
                        else self.entry.control_policy.session_seconds,
                        "primary_mfa_continuation" if requires_mfa else "full_session",
                        identifier,
                    ),
                ).fetchone()
                outcome = self.entry.public_session(session)
            conn.execute(
                "UPDATE accounts.identity_flow SET disposition='complete',outcome=%s WHERE id=%s",
                (Jsonb(outcome), identifier),
            )
            return outcome

        outcome = self.transactions.run("accounts", finish)
        return SessionTransport(token, csrf, outcome) if row["intent"] == "sign_in" else outcome

    def list_links(self, authority: Authority) -> list[dict]:
        def read(conn):
            guard(conn, authority, purpose="account-control")
            return [
                {
                    "linkId": str(row["id"]),
                    "provider": row["provider"],
                    "revision": str(row["revision"]),
                    "providerSubject": row["subject"],
                    "profileAvailable": bool(row["provenance"].get("profile")),
                }
                for row in conn.execute(
                    "SELECT id,provider,revision,subject,provenance FROM accounts.identity_link WHERE account_id=%s ORDER BY provider LIMIT 2",
                    (authority.account_id,),
                ).fetchall()
            ]

        return self.transactions.run("accounts", read)

    def unlink(
        self, authority: Authority, identifier: UUID, expected: UUID, operation: UUID | None = None
    ) -> dict:
        operation = operation or uuid4()

        def write(conn):
            guard(conn, authority, purpose="account-control")
            account = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR UPDATE", (authority.account_id,)
            ).fetchone()
            digest, prior = ControlRepository.replay(
                conn,
                authority.account_id,
                "unlink",
                operation,
                {"identityLinkId": str(identifier), "expectedRevision": str(expected)},
            )
            if prior is not None:
                return prior
            row = conn.execute(
                "SELECT * FROM accounts.identity_link WHERE id=%s AND account_id=%s FOR UPDATE",
                (identifier, authority.account_id),
            ).fetchone()
            if not row or row["revision"] != expected:
                raise ValueError("link revision unavailable")
            if not account["verified"] or not account["password_hash"].startswith("$argon2"):
                raise PermissionError("verified surviving credential required")
            conn.execute("DELETE FROM accounts.identity_link WHERE id=%s", (identifier,))
            return ControlRepository.record(
                conn,
                authority.account_id,
                "unlink",
                operation,
                digest,
                {
                    "resourceId": str(identifier),
                    "revision": str(uuid4()),
                    "requestId": str(operation),
                },
            )

        return self.transactions.run("accounts", write)

    def orcid_profile(self, authority: Authority) -> dict:
        def read(conn):
            guard(conn, authority, purpose="account-control")
            row = conn.execute(
                "SELECT * FROM accounts.identity_link WHERE account_id=%s AND provider='orcid'",
                (authority.account_id,),
            ).fetchone()
            if not row:
                return {"coverage": "unavailable", "reasonKey": "orcid-not-linked", "profile": {}}
            return {
                "coverage": "partial",
                "source": "orcid",
                "revision": str(row["revision"]),
                "fixtureOnly": True,
                "profile": row["provenance"].get("profile", {}),
            }

        return self.transactions.run("accounts", read)
