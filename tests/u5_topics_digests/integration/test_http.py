"""Mounted topics boundary: literal REST over the real realm with real session
verification. Denials are plain refusals; a foreign identifier is
indistinguishable from a missing one."""

import datetime as dt
import secrets
from types import SimpleNamespace
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.modules.topics.http import topics_router
from backend.modules.topics.repository import TopicsRepository
from backend.modules.topics.service import TopicsService
from backend.transactions import Authority, OwnerTransactions

W1 = ("2026-01-01", "2026-01-07")


def unique(base):
    return f"{base}-{uuid4().hex[:10]}"


@pytest.fixture(scope="module")
def mounted(realm):
    transactions = OwnerTransactions(realm)
    entry = GuardedEntryService(transactions)
    service = TopicsService(transactions)
    repository = TopicsRepository(transactions)
    app = FastAPI()
    app.include_router(topics_router(transactions, entry=entry, service=service))
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


def test_follow_duplicate_notice_and_reactivation(mounted):
    key = unique("http-topic")
    first = post(
        mounted.client,
        "/api/v2/topics",
        {"topicKey": key, "displayName": "HTTP Topic"},
    )
    assert first.status_code == 200 and first.json()["reactivated"] is False
    duplicate = post(
        mounted.client,
        "/api/v2/topics",
        {"topicKey": key, "displayName": "HTTP Topic"},
    )
    assert duplicate.status_code == 409 and duplicate.json()["code"] == "CONFLICT"
    topic_id = first.json()["topicId"]
    removed = delete(mounted.client, f"/api/v2/topics/{topic_id}")
    assert removed.status_code == 200 and removed.json()["status"] == "unsubscribed"
    again = post(
        mounted.client,
        "/api/v2/topics",
        {"topicKey": key, "displayName": "HTTP Topic"},
    )
    assert again.status_code == 200 and again.json()["reactivated"] is True
    listed = mounted.client.get("/api/v2/topics")
    assert listed.status_code == 200
    assert topic_id in [row["topicId"] for row in listed.json()["topics"]]


def test_revision_conflict_response(mounted):
    topic_id = follow(mounted.client)["topicId"]
    revision = revision_of(mounted, topic_id)
    stale = mounted.client.put(
        f"/api/v2/topics/{topic_id}/settings",
        json={
            "revision": revision + 3,
            "cadence": "daily",
            "deliveryTimeLocal": "09:00",
            "contentWindowDays": 7,
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert stale.status_code == 409 and stale.json()["code"] == "STALE_REVISION"
    current = mounted.client.put(
        f"/api/v2/topics/{topic_id}/settings",
        json={
            "revision": revision,
            "cadence": "weekly",
            "deliveryTimeLocal": "09:30",
            "deliveryDay": "mon",
            "contentWindowDays": 30,
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert current.status_code == 200 and current.json()["unchanged"] is False
    view = mounted.client.get(f"/api/v2/topics/{topic_id}/settings")
    assert view.status_code == 200
    assert view.json()["settings"]["cadence"] == "weekly"
    invalid = mounted.client.put(
        f"/api/v2/topics/{topic_id}/settings",
        json={
            "revision": revision + 1,
            "cadence": "hourly",
            "deliveryTimeLocal": "09:30",
            "contentWindowDays": 30,
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert invalid.status_code == 422 and invalid.json()["code"] == "INVALID_ARGUMENT"


def test_owner_denial_indistinguishable_from_missing(mounted):
    topic_id = follow(mounted.client)["topicId"]
    revision = revision_of(mounted, topic_id)
    for response in (
        mounted.other.get(f"/api/v2/topics/{topic_id}/settings"),
        delete(mounted.other, f"/api/v2/topics/{topic_id}"),
        mounted.other.put(
            f"/api/v2/topics/{topic_id}/settings",
            json={
                "revision": revision,
                "cadence": "daily",
                "deliveryTimeLocal": "09:00",
                "contentWindowDays": 7,
            },
            headers={"Idempotency-Key": str(uuid4())},
        ),
        mounted.other.post(
            f"/api/v2/topics/{topic_id}/runs/{uuid4()}/resolve",
            json={"decision": "delivered", "assumption": "named"},
            headers={"Idempotency-Key": str(uuid4())},
        ),
    ):
        # The refusal shape is identical to a nonexistent identifier's.
        assert response.status_code == 404, response.text
        assert response.json()["code"] == "NOT_FOUND"


def test_anonymous_refusal(mounted):
    anonymous = TestClient(mounted.client.app, base_url=mounted.client.base_url)
    # Transport preconditions pass; the missing session identity is what refuses.
    anonymous.headers.update({"Origin": str(mounted.client.base_url), "X-CSRF-Token": "0" * 64})
    assert anonymous.get("/api/v2/topics").status_code == 401
    assert (
        post(anonymous, "/api/v2/topics", {"topicKey": "x", "displayName": "x"}).status_code
        == 401
    )
    assert (
        delete(anonymous, f"/api/v2/topics/{uuid4()}").status_code == 401
    )
    anonymous.close()


def test_resolve_guards_and_assumption(mounted):
    topic_id = follow(mounted.client)["topicId"]
    revision = revision_of(mounted, topic_id)
    repository = mounted.repository
    run, _ = repository.prepare_run(
        UUID(topic_id),
        dt.date(2026, 1, 1),
        dt.date(2026, 1, 7),
        revision,
        [{"versionId": "v-http", "paperId": "p-http", "title": "T", "publishedOn": "2026-01-03"}],
    )    # A prepared run is not awaiting reconciliation: the resolve control refuses.
    prepared = post(
        mounted.client,
        f"/api/v2/topics/{topic_id}/runs/{run['id']}/resolve",
        {"decision": "delivered", "assumption": "named"},
    )
    assert prepared.status_code == 409 and prepared.json()["code"] == "CONFLICT"
    assert repository.begin_send(run["id"], "local-sink") is not None
    repository.record_transport_facts(
        run["id"], acknowledged_at=dt.datetime.now(dt.UTC)
    )
    repository.finish_send(run["id"], "unknown")
    # The resolve body must name the assumption (BR3.2).
    unnamed = post(
        mounted.client,
        f"/api/v2/topics/{topic_id}/runs/{run['id']}/resolve",
        {"decision": "delivered"},
    )
    assert unnamed.status_code == 422 and unnamed.json()["code"] == "INVALID_ARGUMENT"
    resolved = post(
        mounted.client,
        f"/api/v2/topics/{topic_id}/runs/{run['id']}/resolve",
        {"decision": "delivered", "assumption": "the sink acknowledged before the cut"},
    )
    assert resolved.status_code == 200 and resolved.json()["state"] == "sent"
    # A resolved run is closed: the state machine refuses a second resolution.
    closed = post(
        mounted.client,
        f"/api/v2/topics/{topic_id}/runs/{run['id']}/resolve",
        {"decision": "not-delivered", "assumption": "second guess"},
    )
    assert closed.status_code == 409 and closed.json()["code"] == "CONFLICT"
