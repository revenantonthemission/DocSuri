"""Fail-closed fixtures for an explicitly owned, unexpired U4 PostgreSQL realm."""

import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import psycopg
import pytest
from psycopg.rows import dict_row

from backend.local_profile import LocalProfile, private_bytes
from backend.transactions import Authority, OwnerTransactions


@pytest.fixture(scope="session")
def realm():
    profile = LocalProfile.load(Path(os.environ["DOCSURI_U4_ENVIRONMENT_FILE"]))
    assert profile.realm == "research-workspace" and profile.database_name == "docsuri_u4"
    return profile


@pytest.fixture
def transactions(realm):
    value = OwnerTransactions(realm)
    yield value
    value.close()


@pytest.fixture
def connect(realm):
    credentials = json.loads(private_bytes(realm.root / "owner-credentials.json"))
    assert credentials["runId"] == realm.run_id
    opened = []

    def open_connection(owner):
        conn = psycopg.connect(
            host="127.0.0.1",
            port=realm.database_port,
            dbname=realm.database_name,
            user=f"docsuri_{owner}",
            password=credentials["roles"][owner],
            row_factory=dict_row,
        )
        assert (
            conn.execute("SELECT run_id FROM public.docsuri_local_identity").fetchone()["run_id"]
            == realm.run_id
        )
        conn.commit()
        opened.append(conn)
        return conn

    yield open_connection
    for conn in opened:
        conn.close()


@pytest.fixture
def authority(connect, realm):
    owner, session, revision = [
        uuid5(NAMESPACE_URL, realm.run_id + suffix)
        for suffix in ("u4-owner-a", "u4-session-a", "u4-authority-a")
    ]
    with connect("accounts") as conn:
        conn.execute("LOCK TABLE accounts.account IN SHARE ROW EXCLUSIVE MODE")
        exists = conn.execute("SELECT id FROM accounts.account WHERE id=%s", (owner,)).fetchone()
        if (
            not exists
            and conn.execute("SELECT count(*) AS n FROM accounts.account").fetchone()["n"] >= 20
        ):
            pytest.fail("Synthetic account allocation exhausted; a fresh owned realm is required")
        conn.execute(
            "INSERT INTO accounts.account(id,email,password_hash,verified,active,authority_revision,display_name) VALUES(%s,%s,'not-login-material',true,true,%s,'synthetic') ON CONFLICT(id) DO UPDATE SET active=true,verified=true,authority_revision=excluded.authority_revision",
            (owner, f"{owner}@fixture.invalid", revision),
        )
        conn.execute(
            "INSERT INTO accounts.consent(account_id,purpose,granted) VALUES(%s,'local-research',true) ON CONFLICT(account_id,purpose) DO UPDATE SET granted=true",
            (owner,),
        )
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,expires_at) VALUES(%s,%s,%s,%s,%s,clock_timestamp()+interval '30 minutes') ON CONFLICT(id) DO UPDATE SET revoked=false,authority_revision=excluded.authority_revision,expires_at=excluded.expires_at",
            (session, owner, str(uuid4()), str(uuid4()), revision),
        )
    return Authority(owner, session)
