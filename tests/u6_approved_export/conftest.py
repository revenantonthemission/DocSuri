"""Fail-closed fixtures for an explicitly owned, unexpired U6 PostgreSQL realm."""

import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import psycopg
import pytest
from backend.local_profile import LocalProfile, private_bytes
from backend.transactions import Authority, OwnerTransactions
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

# The environment persists across phases; synthetic owners are bounded per realm.
MAX_SYNTHETIC_ACCOUNTS = 20


class NetworkRefused(RuntimeError):
    """Raised by the test-wide stand-in for the network transport."""


def refuse_network_transport():
    raise NetworkRefused("tests never build the network transport")


@pytest.fixture(scope="session", autouse=True)
def no_network_transport():
    """NFR6.3: for the whole run, building the Notion network transport fails, so no
    test can reach the network. Code reaches it only as
    `notion_session.network_transport()`, so this is the single point to replace."""
    from backend.modules.export import notion_session

    patch = pytest.MonkeyPatch()
    patch.setattr(notion_session, "network_transport", refuse_network_transport)
    yield refuse_network_transport
    patch.undo()


@pytest.fixture(scope="session")
def realm():
    profile = LocalProfile.load(Path(os.environ["DOCSURI_U6_ENVIRONMENT_FILE"]))
    assert profile.realm == "approved-export" and profile.database_name == "docsuri_u6"
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
def operator(realm):
    """The operator path: the administrative login acting as `docsuri_export_owner`.

    The key commands reach envelopes this way (cicd-pipeline §4.5); tests use it only for
    the operator-only re-seal functions, never to seed or bypass runtime grants.
    """
    secret = json.loads(private_bytes(realm.root / "migration-credentials.json"))
    conn = psycopg.connect(
        host="127.0.0.1",
        port=realm.database_port,
        dbname=realm.database_name,
        user="postgres",
        password=secret["databaseAdminPassword"],
        connect_timeout=3,
        row_factory=dict_row,
    )
    try:
        assert (
            conn.execute("SELECT run_id FROM public.docsuri_local_identity").fetchone()["run_id"]
            == realm.run_id
        )
        conn.execute("SET ROLE docsuri_export_owner")
        conn.commit()
        yield conn
    finally:
        conn.close()


def _make_authority(connect, realm, *, suffix):
    owner, session, revision = [
        uuid5(NAMESPACE_URL, realm.run_id + suffix)
        for suffix in (f"u6-owner-{suffix}", f"u6-session-{suffix}", f"u6-authority-{suffix}")
    ]
    with connect("accounts") as conn:
        conn.execute("LOCK TABLE accounts.account IN SHARE ROW EXCLUSIVE MODE")
        exists = conn.execute("SELECT id FROM accounts.account WHERE id=%s", (owner,)).fetchone()
        if (
            not exists
            and conn.execute("SELECT count(*) AS n FROM accounts.account").fetchone()["n"]
            >= MAX_SYNTHETIC_ACCOUNTS
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
    with connect("personalization") as conn:
        conn.execute(
            "INSERT INTO personalization.settings(account_id,revision,defaults) VALUES(%s,%s,%s) ON CONFLICT(account_id) DO UPDATE SET revision=excluded.revision,defaults=personalization.settings.defaults || excluded.defaults",
            (owner, uuid4(), Jsonb({"timeZone": "UTC"})),
        )
    return Authority(owner, session)


@pytest.fixture
def authority(connect, realm):
    return _make_authority(connect, realm, suffix="a")


@pytest.fixture
def authority_b(connect, realm):
    return _make_authority(connect, realm, suffix="b")
