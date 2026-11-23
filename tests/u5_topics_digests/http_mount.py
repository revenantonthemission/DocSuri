"""The mounted topics and settings app over the real realm, with real session
verification, shared by `integration/test_http_owner_topics.py` and
`integration/test_http_settings_routes.py` (plan Step 35, decision L3-1). The two
names keep the collection order `test_http.py` had: the topics routes first.

`mount` is the module fixture both files used to share in `test_http.py`, moved
unchanged: each file declares its own module-scoped `mounted` fixture that yields
from it. Denials are plain refusals; a foreign identifier is indistinguishable from
a missing one."""

import secrets
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid4, uuid5

from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.modules.personalization.guarded_service import POLICY
from backend.modules.personalization.local_http import settings_router
from backend.modules.topics.http import topics_router
from backend.modules.topics.repository import TopicsRepository
from backend.modules.topics.service import TopicsService
from backend.transactions import Authority, OwnerTransactions
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb


def unique(base):
    return f"{base}-{uuid4().hex[:10]}"


def mount(realm):
    transactions = OwnerTransactions(realm)
    entry = GuardedEntryService(transactions)
    service = TopicsService(transactions)
    repository = TopicsRepository(transactions)
    app = FastAPI()
    app.include_router(topics_router(transactions, entry=entry, service=service))
    app.include_router(settings_router(transactions, entry=entry))
    clients, authorities = [], []
    # Reuse the conftest's two stable synthetic accounts: the realm's finite
    # account allocation is never spent on repeated module loads.
    for suffix in ("a", "b"):
        owner = uuid5(NAMESPACE_URL, realm.run_id + f"u5-owner-{suffix}")
        session = uuid4()
        revision = uuid5(NAMESPACE_URL, realm.run_id + f"u5-authority-{suffix}")
        token = secrets.token_hex(32)
        csrf = entry.verifier("session-csrf", token)

        def seed(conn):
            conn.execute("LOCK TABLE accounts.account IN SHARE ROW EXCLUSIVE MODE")
            conn.execute(
                "INSERT INTO accounts.account(id,email,password_hash,verified,active,"
                "authority_revision,display_name) VALUES(%s,%s,'fixture',true,true,%s,'HTTP fixture') "
                "ON CONFLICT(id) DO UPDATE SET active=true,verified=true,"
                "authority_revision=excluded.authority_revision",
                (owner, f"{owner}@fixture.invalid", revision),
            )
            conn.execute(
                "INSERT INTO accounts.consent(account_id,purpose,granted) "
                "VALUES(%s,'local-research',true) ON CONFLICT(account_id,purpose) "
                "DO UPDATE SET granted=true",
                (owner,),
            )
            conn.execute(
                "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,"
                "authority_revision,expires_at) VALUES(%s,%s,%s,%s,%s,"
                "clock_timestamp()+interval '30 minutes') ON CONFLICT(id) DO UPDATE SET "
                "revoked=false,authority_revision=excluded.authority_revision,"
                "expires_at=excluded.expires_at",
                (
                    session,
                    owner,
                    entry.verifier("session", token),
                    entry.verifier("csrf", csrf),
                    revision,
                ),
            )

        transactions.run("accounts", seed)
        transactions.run(
            "personalization",
            lambda conn: conn.execute(
                "INSERT INTO personalization.settings(account_id,revision,defaults) VALUES(%s,%s,%s) ON CONFLICT(account_id) DO UPDATE SET revision=excluded.revision,defaults=personalization.settings.defaults || excluded.defaults",
                (owner, uuid4(), Jsonb({"timeZone": "UTC"})),
            ),
        )
        client = TestClient(app, base_url=realm.origin)
        client.cookies.set("session_id", token)
        client.headers.update({"Origin": realm.origin, "X-CSRF-Token": csrf})
        clients.append(client)
        authorities.append(Authority(owner, session))
    yield SimpleNamespace(
        client=clients[0],
        other=clients[1],
        authority=authorities[0],
        other_authority=authorities[1],
        service=service,
        repository=repository,
        transactions=transactions,
    )
    for client in clients:
        client.close()
    transactions.close()


def post(client, path, body, key=None):
    return client.post(path, json=body, headers={"Idempotency-Key": str(key or uuid4())})


def delete(client, path, key=None):
    return client.delete(path, headers={"Idempotency-Key": str(key or uuid4())})


def follow(client, key=None):
    response = post(
        client,
        "/api/v2/topics",
        {"topicKey": unique("http-topic"), "displayName": "HTTP Topic"},
        key=key,
    )
    assert response.status_code == 200, response.text
    return response.json()


def revision_of(mounted, topic_id):
    return mounted.repository.system(
        lambda conn: conn.execute(
            "SELECT revision FROM topics.digest_settings WHERE topic_id=%s", (topic_id,)
        ).fetchone()
    )["revision"]


def settings_read(client):
    response = post(client, "/api/v2/c03/settings-read", {})
    assert response.status_code == 200, response.text
    return response.json()


def settings_update(client, revision, key=None, **changes):
    return post(
        client,
        "/api/v2/c03/settings-update",
        {"expectedRevision": revision, "policyRef": POLICY, **changes},
        key,
    )
