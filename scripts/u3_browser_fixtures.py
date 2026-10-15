"""Reconcile explicit U3 browser fixtures or run one bounded maintenance action.

Browser accounts are synthetic members of the owned realm; the maintenance
admin carries explicit corpus-maintenance authority. Secret material never
leaves the private run root and is never printed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ops/src"))

RUN = Path("/tmp/docsuri-u3-run").resolve()

PASSWORD_A = "Browser!U3-A-2026"
PASSWORD_B = "Browser!U3-B-2026"
PASSWORD_ADMIN = "Browser!U3-Admin-2026"
EMAIL_A = "browser-a@u3.fixture.example.com"
EMAIL_B = "browser-b@u3.fixture.example.com"
EMAIL_ADMIN = "browser-admin@u3.fixture.example.com"
ACTIONS = ("setup", "publish", "reset-corpus", "withdraw", "restore-eligible", "expire", "reset-jobs")


def _profile(path: Path):
    from backend.local_profile import LocalProfile

    profile = LocalProfile.load(path)
    if profile.realm != "corpus-maintenance" or profile.root != RUN:
        raise SystemExit("refused: U3 owned realm required")
    return profile


def _private_json(path: Path, value: object) -> None:
    if path.parent != RUN or path.is_symlink():
        raise SystemExit("refused: private output outside owned run")
    temporary = path.with_name(path.name + ".pending")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        0o600,
    )
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _admin_connection(profile):
    import psycopg
    from psycopg.rows import dict_row

    from backend.local_profile import private_bytes

    credentials = json.loads(private_bytes(RUN / "migration-credentials.json"))
    return psycopg.connect(
        host="127.0.0.1",
        port=profile.database_port,
        dbname=profile.database_name,
        user="postgres",
        password=credentials["databaseAdminPassword"],
        connect_timeout=3,
        row_factory=dict_row,
    )


def setup(profile) -> dict:
    from uuid import NAMESPACE_URL, uuid5

    from backend.modules.accounts.services.guarded_entry import GuardedEntryService
    from backend.transactions import OwnerTransactions

    transactions = OwnerTransactions(profile)
    try:
        entry = GuardedEntryService(transactions)
        fixtures = {"runId": profile.run_id, "accounts": {}}
        with _admin_connection(profile) as conn:
            conn.execute("SET session_replication_role = replica")
            conn.execute("DELETE FROM accounts.entry_budget")
            conn.execute("SET session_replication_role = origin")
            conn.commit()
            for key, email, password in (
                ("memberA", EMAIL_A, PASSWORD_A),
                ("memberB", EMAIL_B, PASSWORD_B),
                ("admin", EMAIL_ADMIN, PASSWORD_ADMIN),
            ):
                account = uuid5(NAMESPACE_URL, profile.run_id + ":browser:" + key)
                revision = uuid5(NAMESPACE_URL, profile.run_id + ":browser:revision:" + key)
                conn.execute(
                    "INSERT INTO accounts.account(id,email,password_hash,verified,active,"
                    "authority_revision,display_name) VALUES(%s,%s,%s,true,true,%s,%s) "
                    "ON CONFLICT(id) DO UPDATE SET email=excluded.email,verified=true,"
                    "active=true,authority_revision=excluded.authority_revision",
                    (account, email, entry._hash_password(password), revision, key),
                )
                conn.execute(
                    "INSERT INTO accounts.consent(account_id,purpose,granted) "
                    "VALUES(%s,'local-research',true) "
                    "ON CONFLICT(account_id,purpose) DO UPDATE SET granted=true",
                    (account,),
                )
                fixtures["accounts"][key] = {
                    "email": email,
                    "password": password,
                    "accountId": str(account),
                }
            conn.execute(
                "INSERT INTO corpus.maintenance_actor(account_id) VALUES(%s) "
                "ON CONFLICT(account_id) DO NOTHING",
                (uuid5(NAMESPACE_URL, profile.run_id + ":browser:admin"),),
            )
            conn.commit()
        _private_json(RUN / "browser-fixtures.json", fixtures)
        return {"state": "fixtures-ready", "accounts": sorted(fixtures["accounts"])}
    finally:
        transactions.close()


def _maintenance(profile):
    from backend.artifacts import PrivateArtifacts
    from backend.modules.corpus.maintenance import CorpusMaintenance
    from backend.transactions import OwnerTransactions

    transactions = OwnerTransactions(profile)
    from backend.u3_host import FixtureSourceProvider

    files = PrivateArtifacts(profile.root / "corpus-files", maximum_bytes=2097152)
    return transactions, CorpusMaintenance(
        transactions, files, FixtureSourceProvider(profile.root)
    )


def _admin_authority(profile):
    from uuid import NAMESPACE_URL, uuid5

    from backend.transactions import Authority

    account = uuid5(NAMESPACE_URL, profile.run_id + ":browser:admin")
    session = uuid5(NAMESPACE_URL, profile.run_id + ":browser:session:admin")
    with _admin_connection(profile) as conn:
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,"
            "authority_revision,expires_at,purpose) "
            "SELECT %s,%s,'u3-browser-admin','u3-browser-admin',authority_revision,"
            "clock_timestamp()+interval '60 minutes','full_session' FROM accounts.account "
            "WHERE id=%s ON CONFLICT(id) DO UPDATE SET revoked=false,"
            "expires_at=excluded.expires_at",
            (session, account, account),
        )
        conn.commit()
    return Authority(account, session)


def withdraw(profile, paper: str, reason: str) -> dict:
    transactions, maintenance = _maintenance(profile)
    try:
        authority = _admin_authority(profile)
        result = maintenance.record_change(
            authority,
            {
                "paperId": paper,
                "changeKind": "withdrawal",
                "disposition": "withdrawn",
                "reasonKey": reason,
                "policy": {"policyId": "u3-source-eligibility", "revision": "1"},
            },
        )
        return {"state": "withdrawn", "factId": result["factId"]}
    finally:
        transactions.close()


def expire(profile, paper: str) -> dict:
    transactions, _ = _maintenance(profile)
    try:
        transactions.run("assistance", lambda conn: _expire(conn, paper))
        return {"state": "expired", "paperId": paper}
    finally:
        transactions.close()


def _expire(conn, paper):
    conn.execute(
        "UPDATE assistance.result SET availability='expired' WHERE version_id LIKE %s",
        (paper + "%",),
    )
    return True


def reset_corpus(profile) -> dict:
    """Admin-side reset of the synthetic corpus between browser files.

    Only synthetic corpus rows are removed; account, session and maintenance
    authority rows stay. A restart/interruption journey is never combined with
    this reset.
    """
    with _admin_connection(profile) as conn:
        conn.execute("SET session_replication_role = replica")
        for table in (
            "corpus.run_effect",
            "corpus.run",
            "corpus.change_fact",
            "corpus.projection_batch",
            "corpus.generation",
            "corpus.quarantine",
            "corpus.asset",
        ):
            conn.execute(f"DELETE FROM {table}")
        conn.execute("UPDATE corpus.change_sequence SET fact_position=0")
        conn.execute("DELETE FROM corpus.projection")
        conn.execute("DELETE FROM corpus.version")
        conn.execute("DELETE FROM corpus.paper")
        conn.execute("SET session_replication_role = origin")
        conn.commit()
    return {"state": "corpus-reset"}


def publish(profile, papers: list[str]) -> dict:
    """Idempotently publish the named fixture sources through the owner service."""
    from uuid import uuid4

    transactions, maintenance = _maintenance(profile)
    try:
        authority = _admin_authority(profile)
        published = []
        for paper in papers:
            scope = [f"fixture-{paper.split('-', 1)[1]}"]
            body = {
                "operation": "ingest",
                "sourceScopeIds": scope,
                "authoritativeInputRevision": "u3-browser-1",
                "inputManifestHash": hashlib.sha256(
                    ("|".join(scope) + "browser").encode()
                ).hexdigest(),
                "sourcePolicy": {"policyId": "u3-corpus-maintenance", "revision": "1"},
                "compatibilityRevision": "u3-projection-1",
            }
            accepted = maintenance.accept(authority, uuid4(), body)
            outcome = maintenance.execute(accepted["runId"])
            published.append({"paper": paper, "state": outcome["state"]})
        return {"state": "published", "runs": published}
    finally:
        transactions.close()


def restore_eligible(profile, paper: str) -> dict:
    """Explicit eligibility grant for a restricted version (never for withdrawn)."""
    transactions, maintenance = _maintenance(profile)
    try:
        authority = _admin_authority(profile)
        result = maintenance.record_change(
            authority,
            {
                "paperId": paper,
                "versionId": f"{paper}:v1",
                "changeKind": "version-change",
                "disposition": "eligible",
                "reasonKey": "browser-restore",
                "policy": {"policyId": "u3-source-eligibility", "revision": "1"},
            },
        )
        return {"state": "eligible", "factId": result["factId"]}
    finally:
        transactions.close()


def reset_jobs(profile) -> dict:
    transactions, _ = _maintenance(profile)
    try:
        with _admin_connection(profile) as conn:
            conn.execute("SET session_replication_role = replica")
            conn.execute("DELETE FROM assistance.event")
            conn.execute("DELETE FROM assistance.result")
            conn.execute("DELETE FROM assistance.job")
            conn.execute("DELETE FROM assistance.admission")
            conn.execute("DELETE FROM usage.reservation")
            conn.execute("DELETE FROM usage.entitlement")
            conn.execute("SET session_replication_role = origin")
            conn.commit()
        return {"state": "jobs-reset"}
    finally:
        transactions.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment-file", type=Path, required=True)
    parser.add_argument("--action", choices=ACTIONS, required=True)
    parser.add_argument("--paper")
    parser.add_argument("--reason", default="browser-withdrawal")
    args = parser.parse_args()
    if args.environment_file.is_symlink() or args.environment_file.resolve() != RUN / "environment.json":
        raise SystemExit("refused: only the U3 owned manifest is accepted")
    profile = _profile(args.environment_file.resolve())
    if args.action == "setup":
        result = setup(profile)
    elif args.action == "publish":
        result = publish(
            profile, [name for name in (args.paper or "paper-alpha,paper-gamma").split(",")]
        )
    elif args.action == "reset-corpus":
        result = reset_corpus(profile)
    elif args.action == "withdraw":
        if not args.paper:
            parser.error("--paper is required for withdraw")
        result = withdraw(profile, args.paper, args.reason)
    elif args.action == "expire":
        if not args.paper:
            parser.error("--paper is required for expire")
        result = expire(profile, args.paper)
    elif args.action == "restore-eligible":
        if not args.paper:
            parser.error("--paper is required for restore-eligible")
        result = restore_eligible(profile, args.paper)
    else:
        result = reset_jobs(profile)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
