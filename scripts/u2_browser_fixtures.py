"""Private, run-bound synthetic browser credentials and proof access.

This CLI is a local test harness, never an HTTP endpoint. Secrets are written to
owner-only files; stdout contains only their fixed paths and the run identity.
Existing accounts and their saved work are never reset by repeated setup.
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


def setup(entry, path: Path, run_id: str) -> dict:
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
    for alias in ALIASES[:-1]:
        item = record["accounts"][alias]
        if item["ready"]:
            continue
        flow = str(uuid5(NAMESPACE_URL, run_id + ":browser:" + alias))
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
    return record


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
            setup(entry, path, profile.run_id)
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
