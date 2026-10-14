"""Private, run-bound synthetic browser credentials and proof access.

This CLI is a local test harness, never an HTTP endpoint. Secrets are written to
owner-only files; stdout contains only their fixed paths and the run identity.
Existing accounts and their saved work are never reset by repeated setup; only
this journey's explicitly disposable registration/lifecycle identities rotate
(with admin-side discard) when they cannot be reused.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import secrets
import stat
import sys
import time
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import psycopg
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.artifacts import Artifact
from backend.local_profile import LocalProfile
from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.accounts.services.control_entry import ControlEntryService
from backend.modules.accounts.services.control_mfa import ControlMfaService, totp
from backend.transactions import Authority, OwnerTransactions

ALIASES = ("memberA", "memberB", "admin", "lifecycle", "registration")


def private_json(path: Path, value=None):
    if value is None:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd) as stream:
            metadata = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_uid != os.getuid()
                or stat.S_IMODE(metadata.st_mode) != 0o600
                or metadata.st_size > 65536
            ):
                raise ValueError("private fixture custody mismatch")
            return json.load(stream)
    staging = path.with_name("." + path.name + ".part")
    fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(staging, path)
    finally:
        staging.unlink(missing_ok=True)


def proof_for(entry, email: str, purpose: str) -> dict:
    def read(conn):
        if purpose == "verify":
            row = conn.execute(
                "SELECT d.* FROM accounts.delivery d JOIN accounts.challenge c ON c.id=d.challenge_id "
                "JOIN accounts.account a ON a.id=c.account_id WHERE a.email=%s AND NOT c.consumed "
                "AND c.expires_at>clock_timestamp() ORDER BY c.expires_at DESC,c.id DESC LIMIT 1",
                (email,),
            ).fetchone()
            if not row:
                raise ValueError("fresh owned verification unavailable")
            return json.loads(
                entry.mail.read(
                    Artifact(
                        row["private_path"], row["content_hash"], row["byte_length"]
                    )
                )
            )
        row = conn.execute(
            "SELECT p.* FROM accounts.control_proof p JOIN accounts.account a ON a.id=p.account_id "
            "WHERE a.email=%s AND p.purpose=%s AND p.consumed_at IS NULL "
            "AND p.expires_at>clock_timestamp() ORDER BY p.expires_at DESC,p.id DESC LIMIT 1",
            (email, purpose),
        ).fetchone()
        if not row:
            raise ValueError("fresh owned proof unavailable")
        name = entry.reveal("proof:" + str(row["id"]), row["protected_payload"])[
            "delivery"
        ]
        # Exact encrypted owner reference, no directory-wide proof search.
        path = entry.mail.root / name
        value = private_json(path)
        if value["challengeId"] != str(row["id"]) or value["purpose"] != purpose:
            raise ValueError("proof binding mismatch")
        return value

    return entry.transactions.run("accounts", read)


DISCARD_TABLES = (
    "accounts",
    "assistance",
    "corpus",
    "discovery",
    "library",
    "operations",
    "personalization",
    "usage",
)


def discard_owner(profile, account_id: str) -> None:
    """Admin-side removal of exactly one rotated disposable browser fixture."""
    from psycopg.rows import dict_row

    credentials = json.loads((profile.root / "migration-credentials.json").read_text())
    conn = psycopg.connect(
        host="127.0.0.1",
        port=profile.database_port,
        dbname=profile.database_name,
        user="postgres",
        password=credentials["databaseAdminPassword"],
        connect_timeout=3,
        row_factory=dict_row,
    )
    try:
        conn.execute("SET session_replication_role = replica")
        for statement in (
            "DELETE FROM accounts.lifecycle_scope WHERE request_id IN "
            "(SELECT id FROM accounts.lifecycle_request WHERE account_id = ANY(%s))",
            "DELETE FROM accounts.lifecycle_evidence WHERE request_id IN "
            "(SELECT id FROM accounts.lifecycle_request WHERE account_id = ANY(%s))",
            "DELETE FROM accounts.delivery WHERE challenge_id IN "
            "(SELECT id FROM accounts.challenge WHERE account_id = ANY(%s))",
            "DELETE FROM personalization.reset_scope WHERE reset_id IN "
            "(SELECT id FROM personalization.reset_responsibility WHERE account_id = ANY(%s))",
            "DELETE FROM assistance.event WHERE job_id IN "
            "(SELECT id FROM assistance.job WHERE account_id = ANY(%s))",
            "DELETE FROM accounts.mfa_recovery WHERE enrollment_id IN "
            "(SELECT id FROM accounts.mfa_enrollment WHERE account_id = ANY(%s))",
            *(
                f"DELETE FROM {schema}.lifecycle_evidence WHERE request_id IN "
                "(SELECT id FROM accounts.lifecycle_request WHERE account_id = ANY(%s))"
                for schema in ("library", "personalization", "discovery", "usage", "assistance")
            ),
        ):
            conn.execute(statement, ([account_id],))
        for row in conn.execute(
            "SELECT table_schema,table_name FROM information_schema.columns "
            "WHERE column_name='account_id' AND table_schema = ANY(%s)",
            (list(DISCARD_TABLES),),
        ).fetchall():
            conn.execute(
                f'DELETE FROM "{row["table_schema"]}"."{row["table_name"]}" '
                "WHERE account_id = ANY(%s)",
                ([account_id],),
            )
        conn.execute("DELETE FROM accounts.account WHERE id = ANY(%s)", ([account_id],))
        conn.execute("SET session_replication_role = origin")
        conn.commit()
    finally:
        conn.close()


def rotate(record: dict, alias: str, run_id: str) -> None:
    item = record["accounts"][alias]
    item["email"] = f"{alias}-{run_id[-8:]}-{secrets.token_hex(4)}@browser.example.com"
    item["password"] = "Synthetic!" + secrets.token_hex(16)
    item["ready"] = False
    item.pop("accountId", None)
    item.pop("seed", None)


def setup(entry, path: Path, run_id: str, profile) -> dict:
    if path.exists():
        record = private_json(path)
        if record["runId"] != run_id or set(record["accounts"]) != set(ALIASES):
            raise ValueError("fixture run mismatch")
    else:
        record = {
            "runId": run_id,
            "accounts": {
                alias: {
                    "email": f"{alias.lower()}-{run_id[-8:]}@browser.example.com",
                    "password": "Synthetic!" + secrets.token_hex(16),
                    "ready": False,
                }
                for alias in ALIASES
            },
        }
        private_json(path, record)
    # The lifecycle journey withdraws its account and reactivation stays pending
    # by design, so that disposable identity rotates instead of poisoning login.
    lifecycle = record["accounts"]["lifecycle"]
    existing = entry.transactions.run(
        "accounts",
        lambda conn, lifecycle=lifecycle: conn.execute(
            "SELECT id,lifecycle_state FROM accounts.account WHERE email=%s",
            (lifecycle["email"],),
        ).fetchone(),
    )
    if existing and existing["lifecycle_state"] != "active":
        discard_owner(profile, str(existing["id"]))
        rotate(record, "lifecycle", run_id)
        private_json(path, record)
    for alias in ALIASES[:-1]:
        item = record["accounts"][alias]
        if item["ready"]:
            continue
        flow = str(uuid5(NAMESPACE_URL, run_id + ":browser:" + alias + ":" + item["email"]))
        operation = uuid5(NAMESPACE_URL, flow + ":register")
        existing = entry.transactions.run(
            "accounts",
            lambda conn, item=item: conn.execute(
                "SELECT id,verified,role FROM accounts.account WHERE email=%s",
                (item["email"],),
            ).fetchone(),
        )
        if not existing:
            entry.register(
                operation,
                item["email"],
                item["password"],
                "브라우저 검증 " + alias,
                flow,
            )
        if not existing or not existing["verified"]:
            proof = proof_for(entry, item["email"], "verify")
            entry.verify_email(
                UUID(proof["challengeId"]),
                proof["proof"],
                flow,
                operation=uuid5(NAMESPACE_URL, flow + ":verify"),
            )
        if existing and existing["role"] == "administrator":
            if alias != "admin" or "seed" not in item:
                raise ValueError(
                    "fixture administrator recovery requires its protected seed"
                )
            item.update(accountId=str(existing["id"]), ready=True)
            private_json(path, record)
            continue
        session = entry.login(item["email"], item["password"])
        state = session.public["session"]
        item["accountId"] = state["accountId"]
        if alias == "admin":
            authority = Authority(UUID(state["accountId"]), UUID(state["sessionId"]))
            mfa = ControlMfaService(entry)
            enrollment = mfa.begin(authority, item["password"], uuid4())
            material = mfa.material(
                authority,
                UUID(enrollment["enrollmentId"]),
                enrollment["deliveryReference"],
            )
            item["seed"] = material["seed"]
            private_json(path, record)
            mfa.confirm(
                authority,
                UUID(enrollment["enrollmentId"]),
                totp(item["seed"], int(time.time()) // 30 - 1),
                uuid4(),
            )
            entry.transactions.run(
                "accounts",
                lambda conn, authority=authority, item=item: conn.execute(
                    "UPDATE accounts.account SET role='administrator' WHERE id=%s AND email=%s",
                    (authority.account_id, item["email"]),
                ),
            )
        entry.logout(Authority(UUID(state["accountId"]), UUID(state["sessionId"])))
        item["ready"] = True
        private_json(path, record)
    # The registration journey must start from an unverified address. Existing
    # registered accounts are never reset; when no fresh verification can be
    # delivered, only this journey's disposable identity rotates.
    registration = record["accounts"]["registration"]
    existing = entry.transactions.run(
        "accounts",
        lambda conn, registration=registration: conn.execute(
            "SELECT id,verified FROM accounts.account WHERE email=%s",
            (registration["email"],),
        ).fetchone(),
    )
    reusable = existing is None
    if existing and not existing["verified"]:
        try:
            proof_for(entry, registration["email"], "verify")
            reusable = True
        except ValueError:
            reusable = False
    if not reusable:
        if existing:
            discard_owner(profile, str(existing["id"]))
        rotate(record, "registration", run_id)
        private_json(path, record)
    return record


def seed_corpus(transactions) -> None:
    """One deterministic readable/searchable fixture; idempotent by identity."""
    document = {
        "document": {
            "sections": [
                {
                    "id": "abstract",
                    "title": "Abstract",
                    "blocks": [
                        {
                            "id": "abstract-1",
                            "type": "paragraph",
                            "text": "Attention mechanisms transform sequence modeling. "
                            "Synthetic fixture content for browser verification.",
                        }
                    ],
                },
                {
                    "id": "method",
                    "title": "Method",
                    "blocks": [
                        {
                            "id": "method-1",
                            "type": "paragraph",
                            "text": "The fixture method keeps deterministic searchable text.",
                        }
                    ],
                },
            ]
        }
    }
    chunks = (
        ("abstract-1", "Abstract"),
        ("method-1", "Method"),
    )
    revision = uuid5(NAMESPACE_URL, transactions.profile.run_id + ":browser:corpus:revision")

    def write(conn):
        conn.execute(
            "INSERT INTO corpus.paper(id,title,authors,published_on,metadata) "
            "VALUES('u2-browser-paper','Attention Is All You Need (synthetic fixture)',%s,'2017-06-12',%s) "
            "ON CONFLICT(id) DO NOTHING",
            (Jsonb(["Synthetic Author"]), Jsonb({"localResearchOnly": True})),
        )
        conn.execute(
            "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
            "private_path,eligible,purpose,eligibility_revision,provenance,content) "
            "VALUES('u2-browser-version','u2-browser-paper','https://fixture.invalid/browser',%s,"
            "'u2-browser','fixture',true,'local-research',%s,%s,%s) ON CONFLICT(id) DO UPDATE "
            "SET eligible=true,purpose='local-research',eligibility_revision=excluded.eligibility_revision",
            ("a" * 64, revision, Jsonb({"fixtureOnly": True}), Jsonb(document)),
        )
        conn.execute("DELETE FROM corpus.projection WHERE version_id='u2-browser-version'")
        for ordinal, (anchor, section) in enumerate(chunks):
            text = next(
                block["text"]
                for candidate in document["document"]["sections"]
                for block in candidate["blocks"]
                if block["id"] == anchor
            )
            conn.execute(
                "INSERT INTO corpus.projection(version_id,ordinal,content_hash,anchor,section,text_content) "
                "VALUES('u2-browser-version',%s,%s,%s,%s,%s)",
                (ordinal, "a" * 64, anchor, section, text),
            )

    transactions.run("corpus", write)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment-file", type=Path, required=True)
    parser.add_argument("--action", choices=("setup", "proof", "totp"), required=True)
    parser.add_argument("--alias", choices=ALIASES)
    parser.add_argument(
        "--purpose", choices=("verify", "password-reset", "email-change", "reactivate")
    )
    args = parser.parse_args()
    profile = LocalProfile.load(args.environment_file)
    if profile.realm != "account-controls" or profile.database_name != "docsuri_u2":
        raise ValueError("owned U2 profile required")
    descriptor = os.open(
        profile.root
        / ("fixture-run.lock" if args.action == "setup" else "browser-proof.lock"),
        os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
        0o600,
    )
    transactions = OwnerTransactions(profile)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = profile.root / "browser-fixtures.json"
        entry = ControlEntryService(transactions, SYNTHETIC_POLICY)
        if args.action == "setup":
            setup(entry, path, profile.run_id, profile)
            seed_corpus(transactions)
            output = path
        else:
            record = private_json(path)
            if record["runId"] != profile.run_id or args.alias is None:
                raise ValueError("owned alias required")
            item = record["accounts"][args.alias]
            if args.action == "proof":
                if args.purpose is None:
                    raise ValueError("proof purpose required")
                value = proof_for(entry, item["email"], args.purpose)
            else:
                if args.alias != "admin" or "seed" not in item:
                    raise ValueError("seeded administrator required")
                value = {"proof": totp(item["seed"], int(time.time()) // 30)}
            output = profile.root / "browser-proof.json"
            private_json(output, value)
        print(json.dumps({"runId": profile.run_id, "privateFile": str(output)}))
    finally:
        transactions.close()
        os.close(descriptor)


if __name__ == "__main__":
    main()
