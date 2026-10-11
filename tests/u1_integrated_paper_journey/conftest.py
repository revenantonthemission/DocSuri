"""Exactly owned PostgreSQL fixtures; runtime checks never run as provisioner."""

from __future__ import annotations

import json
import os
import fcntl
import stat
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

import psycopg
import pytest

from backend.local_profile import LocalProfile


class ProtectedCredentials(dict):
    def __repr__(self):
        return "<protected disposable credentials>"


@pytest.fixture(scope="session", autouse=True)
def exclusive_fixture_environment():
    """All phase and cumulative runs share one nonblocking mutation lock."""
    profile = LocalProfile.load(Path(os.environ["DOCSURI_U1_ENVIRONMENT_FILE"]))
    descriptor = os.open(
        profile.root / "fixture-run.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
    )
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            pytest.fail("U1 fixture lock is not an owned regular file")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pytest.fail("U1 fixture environment is already in use; run phases serially")
        yield profile.root / "fixture-run.lock"
    finally:
        os.close(descriptor)


@pytest.fixture(scope="module")
def realm():
    profile = LocalProfile.load(Path(os.environ["DOCSURI_U1_ENVIRONMENT_FILE"]))
    credentials = ProtectedCredentials(
        json.loads((profile.root / "owner-credentials.json").read_text())
    )
    assert credentials["runId"] == profile.run_id
    return profile, credentials


@pytest.fixture
def connect(realm):
    profile, credentials = realm
    opened = []

    def connection(owner, *, isolation="SERIALIZABLE"):
        conn = psycopg.connect(
            host="127.0.0.1",
            port=profile.database_port,
            dbname="docsuri_u1",
            user=f"docsuri_{owner}",
            password=credentials["roles"][owner],
            connect_timeout=3,
        )
        conn.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation}")
        identity = conn.execute("SELECT run_id FROM public.docsuri_local_identity").fetchone()[0]
        assert identity == profile.run_id
        conn.commit()
        conn.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
        opened.append(conn)
        return conn

    yield connection
    for conn in opened:
        conn.close()


@pytest.fixture
def identities(connect, realm):
    run_id = realm[0].run_id
    a, b, s, rev = [
        uuid5(NAMESPACE_URL, run_id + name) for name in ("a", "b", "session", "authority")
    ]
    with connect("accounts") as conn:
        for account, name in ((a, "a"), (b, "b")):
            conn.execute(
                "INSERT INTO accounts.account(id,email,password_hash,verified,active,authority_revision,display_name) VALUES(%s,%s,%s,true,true,%s,%s) ON CONFLICT(id) DO UPDATE SET verified=true,active=true,authority_revision=excluded.authority_revision",
                (account, name + "@fixture.invalid", "db-fixture-not-a-login-hash", rev, name),
            )
            for purpose in ("local-research", "personalization"):
                conn.execute(
                    "INSERT INTO accounts.consent(account_id,purpose,granted) VALUES(%s,%s,true) ON CONFLICT(account_id,purpose) DO UPDATE SET granted=true",
                    (account, purpose),
                )
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,expires_at) VALUES(%s,%s,'db-fixture-session','db-fixture-csrf',%s,clock_timestamp()+interval '1 hour') ON CONFLICT(id) DO UPDATE SET revoked=false,expires_at=excluded.expires_at,authority_revision=excluded.authority_revision",
            (s, a, rev),
        )
    with connect("corpus") as conn:
        conn.execute(
            "INSERT INTO corpus.paper(id,title,authors,metadata) VALUES('fixture-paper','Private database fixture','[]','{}') ON CONFLICT(id) DO UPDATE SET withdrawn=false"
        )
        conn.execute(
            "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,private_path,eligible,purpose,provenance,content) VALUES('fixture-v1','fixture-paper','https://fixture.invalid/paper',%s,'v1','fixture-only',true,'local-research','{}','{}') ON CONFLICT(id) DO UPDATE SET eligible=true",
            ("a" * 64,),
        )
    with connect("library") as conn:
        conn.execute(
            "INSERT INTO library.history_boundary(account_id) VALUES(%s) ON CONFLICT DO NOTHING",
            (a,),
        )
        conn.execute("DELETE FROM library.saved_paper WHERE account_id=%s", (a,))
    return {
        "a": a,
        "b": b,
        "session": s,
        "revision": rev,
        "paper": "fixture-paper",
        "version": "fixture-v1",
    }
