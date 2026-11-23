"""AccountAccess's A4 writes and parity reads (U8 plan Step 7; BR8.2, BR8.3, BR8.5, BR8.10).

The repository writes values the import operation (Step 31) has already validated and
mapped: the target identity derived from (v1, kind, source id), the lower-case email,
the v2 role, the carried password verifier or none, and the reset-required marker. It
writes as AccountAccess's own login, compares the stored normalized fields with the
incoming ones, and answers `imported`, `unchanged`, `updated` or `refused` with the
digest of what is stored. An imported account gets no consent: its first sign-in opens
the consent-pending session (A3). A changed account gets a new authority revision, so
every session made under the old values ends.

The parity digest covers every account or identity link (a final run starts from an
empty database), or an explicit set of target identities. Its fields never include a
verifier or an identity subject in the clear, only their digests.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from uuid import UUID

from backend.import_parity import decide, outcome, parity, secret_digest, stored_digest
from psycopg.types.json import Jsonb

OWNER = "accounts"
# The stored stand-in for "no password verifier": no verifier accepts it, so the
# account signs in only through a provider or after a reset (BR8.5).
NO_PASSWORD = "imported-without-password-verifier"
ROLES = ("member", "administrator")
PROVIDERS = ("google", "orcid")
MAX_PARITY_RECORDS = 100_000


def _time(moment: dt.datetime) -> str:
    if moment.tzinfo is None:
        raise ValueError("import times must be aware")
    return moment.astimezone(dt.UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def account_fields(
    *, email: str, email_verified: bool, role: str, display_name: str,
    password_verifier: str | None, reset_required: bool, created_at: dt.datetime,
) -> dict:
    """The compared normalized fields of one account."""
    if not isinstance(email, str) or email != email.lower() or not 3 <= len(email) <= 320:
        raise ValueError("an imported email must be lower-case and bounded")
    if role not in ROLES or type(email_verified) is not bool or type(reset_required) is not bool:
        raise ValueError("account import fields outside their vocabulary")
    if not isinstance(display_name, str) or len(display_name.encode()) > 256:
        raise ValueError("display name outside its bound")
    return {
        "email": email,
        "emailVerified": email_verified,
        "role": role,
        "displayName": display_name,
        "passwordDigest": secret_digest(password_verifier),
        "resetRequired": reset_required,
        "createdAt": _time(created_at),
    }


def _stored_account(row: dict) -> dict:
    verifier = None if row["password_hash"] == NO_PASSWORD else row["password_hash"]
    return account_fields(
        email=row["email"], email_verified=row["verified"], role=row["role"],
        display_name=row["display_name"], password_verifier=verifier,
        reset_required=row["reset_required"], created_at=row["created_at"],
    )


def link_fields(*, account_id: UUID, provider: str, subject: str) -> dict:
    if provider not in PROVIDERS or not isinstance(subject, str) or not 1 <= len(subject) <= 512:
        raise ValueError("identity link fields outside their vocabulary")
    return {
        "account": str(account_id), "provider": provider,
        "subjectDigest": secret_digest(subject),
    }


class AccountImports:
    def __init__(self, transactions):
        self.transactions = transactions

    def import_account(
        self, target_id: UUID, *, email: str, email_verified: bool, role: str,
        display_name: str, password_verifier: str | None, reset_required: bool,
        created_at: dt.datetime,
    ) -> dict:
        fields = account_fields(
            email=email, email_verified=email_verified, role=role, display_name=display_name,
            password_verifier=password_verifier, reset_required=reset_required,
            created_at=created_at,
        )
        incoming = stored_digest(fields)
        stored_verifier = NO_PASSWORD if password_verifier is None else password_verifier

        def write(conn):
            row = conn.execute(
                "SELECT * FROM accounts.account WHERE id=%s FOR UPDATE", (target_id,)
            ).fetchone()
            other = conn.execute(
                "SELECT 1 FROM accounts.account WHERE email=%s AND id<>%s", (email, target_id)
            ).fetchone()
            if other:
                current = stored_digest(_stored_account(row)) if row else incoming
                return outcome("refused", current, reason="email-taken")
            disposition = decide(stored_digest(_stored_account(row)) if row else None, incoming)
            if disposition == "imported":
                conn.execute(
                    "INSERT INTO accounts.account(id,email,password_hash,verified,active,"
                    "display_name,created_at,role,reset_required) "
                    "VALUES(%s,%s,%s,%s,true,%s,%s,%s,%s)",
                    (target_id, email, stored_verifier, email_verified, display_name,
                     created_at, role, reset_required),
                )
            elif disposition == "updated":
                conn.execute(
                    "UPDATE accounts.account SET email=%s,password_hash=%s,verified=%s,"
                    "display_name=%s,created_at=%s,role=%s,reset_required=%s,"
                    "authority_revision=gen_random_uuid() WHERE id=%s",
                    (email, stored_verifier, email_verified, display_name, created_at, role,
                     reset_required, target_id),
                )
            return outcome(disposition, incoming)

        return self.transactions.run(OWNER, write)

    def import_identity_link(
        self, target_id: UUID, *, account_id: UUID, provider: str, subject: str,
        linked_at: dt.datetime,
    ) -> dict:
        fields = link_fields(account_id=account_id, provider=provider, subject=subject)
        incoming = stored_digest(fields)

        def write(conn):
            if not conn.execute(
                "SELECT 1 FROM accounts.account WHERE id=%s", (account_id,)
            ).fetchone():
                return outcome("refused", incoming, reason="dependency-not-migrated")
            row = conn.execute(
                "SELECT * FROM accounts.identity_link WHERE id=%s FOR UPDATE", (target_id,)
            ).fetchone()
            clash = conn.execute(
                "SELECT id FROM accounts.identity_link WHERE id<>%s AND ((provider=%s AND "
                "subject=%s) OR (account_id=%s AND provider=%s))",
                (target_id, provider, subject, account_id, provider),
            ).fetchone()
            if clash:
                return outcome("refused", incoming, reason="duplicate-provider-link")
            existing = (
                stored_digest(link_fields(
                    account_id=row["account_id"], provider=row["provider"], subject=row["subject"]
                )) if row else None
            )
            disposition = decide(existing, incoming)
            provenance = Jsonb({"source": "v1-import", "linkedAt": _time(linked_at)})
            if disposition == "imported":
                conn.execute(
                    "INSERT INTO accounts.identity_link(id,account_id,provider,subject,provenance) "
                    "VALUES(%s,%s,%s,%s,%s)",
                    (target_id, account_id, provider, subject, provenance),
                )
            elif disposition == "updated":
                conn.execute(
                    "UPDATE accounts.identity_link SET account_id=%s,provider=%s,subject=%s,"
                    "provenance=%s,revision=gen_random_uuid() WHERE id=%s",
                    (account_id, provider, subject, provenance, target_id),
                )
            return outcome(disposition, incoming)

        return self.transactions.run(OWNER, write)

    def parity(
        self, kind: str, *, now: dt.datetime, target_ids: Iterable[UUID] | None = None
    ) -> dict:
        """The order-independent digest of every stored account or identity link (or of
        the named ones); reading it writes nothing."""
        if kind not in ("account", "identity-link"):
            raise ValueError("AccountAccess holds no such import kind")
        ids = None if target_ids is None else sorted({UUID(str(value)) for value in target_ids})
        table = "accounts.account" if kind == "account" else "accounts.identity_link"

        def read(conn):
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE %s::uuid[] IS NULL OR id=ANY(%s::uuid[]) "
                "ORDER BY id LIMIT %s",
                (ids, ids, MAX_PARITY_RECORDS + 1),
            ).fetchall()
            if len(rows) > MAX_PARITY_RECORDS:
                raise ValueError("parity read exceeds its bound")
            return rows

        rows = self.transactions.run(OWNER, read)
        if kind == "account":
            digests = [stored_digest(_stored_account(row)) for row in rows]
        else:
            digests = [
                stored_digest(link_fields(
                    account_id=row["account_id"], provider=row["provider"], subject=row["subject"]
                ))
                for row in rows
            ]
        return parity(kind, digests, _time(now))
