"""Owned U2 PostgreSQL fixtures. Recovery tests never reseed the environment."""
from __future__ import annotations

import fcntl
import json
import os
import signal
import stat
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import psycopg
import pytest
from psycopg.rows import dict_row

from backend.local_profile import LocalProfile
from backend.transactions import Authority, OwnerTransactions


@pytest.fixture(scope="session")
def realm():
    profile = LocalProfile.load(Path(os.environ["DOCSURI_U2_ENVIRONMENT_FILE"]))
    assert profile.database_name == "docsuri_u2" and profile.realm == "account-controls"
    credentials = json.loads((profile.root / "owner-credentials.json").read_text())
    assert credentials["runId"] == profile.run_id
    return profile, credentials


@pytest.fixture(scope="session", autouse=True)
def exclusive_environment(realm):
    descriptor = os.open(realm[0].root / "fixture-run.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        metadata = os.fstat(descriptor)
        assert stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.getuid()
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


@pytest.fixture
def connect(realm):
    profile, credentials = realm
    opened = []

    def connection(owner, *, autocommit=False):
        conn = psycopg.connect(host="127.0.0.1", port=profile.database_port,
            dbname=profile.database_name, user=f"docsuri_{owner}", password=credentials["roles"][owner],
            connect_timeout=3, row_factory=dict_row, autocommit=autocommit)
        assert conn.execute("SELECT run_id FROM public.docsuri_local_identity").fetchone()["run_id"] == profile.run_id
        if not autocommit:
            conn.commit()
        opened.append(conn)
        return conn

    yield connection
    for conn in opened:
        conn.close()


@pytest.fixture
def identities(connect, realm):
    run = realm[0].run_id
    a, b, session, revision = [uuid5(NAMESPACE_URL, run + item) for item in ("owner-a", "owner-b", "session-a", "authority-a")]
    with connect("accounts") as conn:
        for account, label in ((a, "a"), (b, "b")):
            conn.execute("INSERT INTO accounts.account(id,email,password_hash,verified,active,authority_revision,display_name) "
                "VALUES(%s,%s,'database-fixture-not-a-login-hash',true,true,%s,%s) ON CONFLICT(id) DO UPDATE "
                "SET verified=true,active=true,lifecycle_state='active',role='member',authority_revision=excluded.authority_revision",
                (account, f"u2-{label}@fixture.invalid", revision, label))
            for purpose in ("local-research", "personalization"):
                conn.execute("INSERT INTO accounts.consent(account_id,purpose,granted) VALUES(%s,%s,true) "
                    "ON CONFLICT(account_id,purpose) DO UPDATE SET granted=true", (account, purpose))
        conn.execute("INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,expires_at) "
            "VALUES(%s,%s,'u2-db-session','u2-db-csrf',%s,clock_timestamp()+interval '15 minutes') "
            "ON CONFLICT(id) DO UPDATE SET revoked=false,purpose='full_session',mfa_at=NULL,"
            "expires_at=excluded.expires_at,authority_revision=excluded.authority_revision", (session, a, revision))
    return {"a": a, "b": b, "session": session, "revision": revision}


@pytest.fixture
def authority(identities):
    return Authority(identities["a"], identities["session"])


@pytest.fixture
def transactions(realm):
    transactions = OwnerTransactions(realm[0])
    yield transactions
    transactions.close()


DISCARDED_OWNER_TABLES = (
    "accounts",
    "assistance",
    "corpus",
    "discovery",
    "library",
    "operations",
    "personalization",
    "usage",
)


@pytest.fixture
def fixture_discard(realm):
    """Admin-side discard of exactly this case's run-scoped fixture owners.

    Behavior verification always runs through the runtime owner roles; this
    teardown only removes the synthetic owner rows a case created so repeated
    runs cannot exceed the finite experiment footprint or leave an inconsistent
    erased owner behind for other layers.
    """
    accounts: list = []

    def register(*identifiers) -> None:
        accounts.extend(identifiers)

    yield register
    if not accounts:
        return
    identifiers = [str(account) for account in accounts]
    profile = realm[0]
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
        # Indirect rows (whose link column is not account_id) precede the direct
        # sweep because their parent rows disappear in that sweep.
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
            conn.execute(statement, (identifiers,))
        for row in conn.execute(
            "SELECT table_schema,table_name FROM information_schema.columns "
            "WHERE column_name='account_id' AND table_schema = ANY(%s)",
            (list(DISCARDED_OWNER_TABLES),),
        ).fetchall():
            conn.execute(
                f'DELETE FROM "{row["table_schema"]}"."{row["table_name"]}" '
                "WHERE account_id = ANY(%s)",
                (identifiers,),
            )
        conn.execute("DELETE FROM accounts.account WHERE id = ANY(%s)", (identifiers,))
        conn.execute("SET session_replication_role = origin")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def clear_resets(realm):
    """Admin-side removal of reset responsibilities a case created.

    Reset acceptance and discovery are the behavior under test; the finite
    outstanding cap must never be consumed by fixtures that never complete,
    so a case's own responsibilities are removed after it.
    """
    accounts: list = []

    def register(*identifiers) -> None:
        accounts.extend(identifiers)

    yield register
    if not accounts:
        return
    identifiers = [str(account) for account in accounts]
    profile = realm[0]
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
            "DELETE FROM personalization.reset_scope WHERE reset_id IN "
            "(SELECT id FROM personalization.reset_responsibility WHERE account_id = ANY(%s))",
            "DELETE FROM personalization.reset_responsibility WHERE account_id = ANY(%s)",
        ):
            conn.execute(statement, (identifiers,))
        conn.execute("SET session_replication_role = origin")
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def bounded_case():
    """Hard per-case deadline includes fixture setup and teardown, not diagnostics."""
    def expired(signum, frame):
        raise TimeoutError("U2 case exceeded the finite 30 second execution limit")

    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 30)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
