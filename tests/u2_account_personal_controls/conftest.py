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
