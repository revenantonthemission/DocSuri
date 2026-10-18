"""Cookie-free cancellation route plus real owner-store capability behavior."""

import datetime as dt
import hashlib
from uuid import uuid4

import pytest
from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.topics.control_lifecycle import TopicsDigestsLifecycleParticipant
from backend.modules.topics.repository import TopicsRepository
from backend.modules.topics.unsubscribe import PREFIX, EmailUnsubscribe, unsubscribe_router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb


class RecordingService:
    def __init__(self):
        self.calls = []

    def cancel(self, token):
        self.calls.append(token)


def mounted(service):
    app = FastAPI()
    app.include_router(unsubscribe_router(service))
    return TestClient(app, base_url="https://example.invalid")


def test_get_is_generic_read_only_confirmation():
    service = RecordingService()
    with mounted(service) as client:
        token = "x" * 43
        result = client.get(PREFIX + token)
        assert result.status_code == 200 and token not in result.text
        assert "구독 해지 확인" in result.text and service.calls == []
        assert result.headers["referrer-policy"] == "no-referrer"


def test_both_one_click_encodings_without_cookies_or_auth():
    service = RecordingService()
    with mounted(service) as client:
        path = PREFIX + "x" * 43
        assert client.post(path, data={"List-Unsubscribe": "One-Click"}).status_code == 200
        assert client.post(path, files={"List-Unsubscribe": (None, "One-Click")}).status_code == 200
        assert service.calls == ["x" * 43] * 2


@pytest.mark.parametrize(
    "body",
    [
        "List-Unsubscribe=One-Click&accountId=other",
        "List-Unsubscribe=One-Click&List-Unsubscribe=One-Click",
        "List-Unsubscribe=no",
        "x" * 4097,
    ],
)
def test_malformed_or_override_forms_cannot_cancel(body):
    service = RecordingService()
    with mounted(service) as client:
        result = client.post(
            PREFIX + "x" * 43,
            content=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert result.status_code == 400 and service.calls == []
        assert client.delete(PREFIX + "x" * 43).status_code == 405


def test_multipart_file_or_extra_field_refused():
    service = RecordingService()
    with mounted(service) as client:
        for fields in (
            {"List-Unsubscribe": ("file", "One-Click")},
            {"List-Unsubscribe": (None, "One-Click"), "topic": (None, "other")},
        ):
            assert client.post(PREFIX + "x" * 43, files=fields).status_code == 400
        assert service.calls == []


def test_cancellation_error_does_not_disclose_secret():
    class Broken:
        def cancel(self, token):
            raise RuntimeError(token)

    with mounted(Broken()) as client:
        response = client.post(PREFIX + "x" * 43, data={"List-Unsubscribe": "One-Click"})
        assert response.status_code == 503 and "x" * 43 not in response.text


def prepared(transactions, authority):
    repository = TopicsRepository(transactions)
    key = "email-unsubscribe-" + uuid4().hex
    result = repository.follow(authority, key, "Unsubscribe fixture")
    topic = result["topic"]
    run, _ = repository.prepare_run(
        topic["id"],
        dt.date(2026, 1, 1),
        dt.date(2026, 1, 7),
        1,
        [
            {
                "versionId": "fixture-v",
                "paperId": "fixture-p",
                "title": "Paper",
                "publishedOn": "2026-01-02",
            }
        ],
    )
    assert repository.begin_send(run["id"], "local-sink")
    return repository, topic, run, key


def test_hash_only_binding_repeat_and_refollow_revocation(transactions, authority, realm):
    repository, topic, run, key = prepared(transactions, authority)
    service = EmailUnsubscribe(
        transactions,
        origin="https://example.invalid",
        expires_at=dt.datetime.fromtimestamp(realm.expires_at, dt.UTC),
    )
    url = service.issue(run["id"])
    token = url.rsplit("/", 1)[1]
    row = repository.system(
        lambda conn: conn.execute(
            "SELECT * FROM topics.email_unsubscribe WHERE run_id=%s", (run["id"],)
        ).fetchone()
    )
    assert row["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert token not in repr(row)
    service.cancel(token)
    service.cancel(token)
    assert (
        repository.system(
            lambda conn: conn.execute(
                "SELECT status FROM topics.followed_topic WHERE id=%s", (topic["id"],)
            ).fetchone()
        )["status"]
        == "unsubscribed"
    )
    repository.follow(authority, key, "Unsubscribe fixture")
    service.cancel(token)
    assert (
        repository.system(
            lambda conn: conn.execute(
                "SELECT status FROM topics.followed_topic WHERE id=%s", (topic["id"],)
            ).fetchone()
        )["status"]
        == "active"
    )


def test_assembled_cookie_free_cancellation_and_hash_erasure(transactions, authority, realm):
    from backend.u5_host import assemble_u5

    repository, topic, run, _ = prepared(transactions, authority)
    issuer = EmailUnsubscribe(
        transactions,
        origin=realm.origin,
        expires_at=dt.datetime.fromtimestamp(realm.expires_at, dt.UTC),
        synthetic=True,
    )
    path = PREFIX + issuer.issue(run["id"]).rsplit("/", 1)[1]
    app = assemble_u5(realm)
    # Enter the real lifecycle so readiness and the bounded worker participate.
    # Keep token-bearing requests outside assertions: failure diagnostics must
    # contain only the status code, never the cancellation capability URL.
    with TestClient(app, base_url=realm.origin) as client:
        # Initial admission is closed until a genuine capacity observation.
        # Perform the same bounded database probe as the worker, without
        # changing the admission decision or waiting on scheduler timing.
        app.state.control_capacity.refresh()
        assert not client.cookies
        confirmation_status = client.get(path).status_code
        assert confirmation_status == 200
        cancellation_status = client.post(path, data={"List-Unsubscribe": "One-Click"}).status_code
        assert cancellation_status == 200
        row = repository.system(
            lambda conn: conn.execute(
                "SELECT status FROM topics.followed_topic WHERE id=%s", (topic["id"],)
            ).fetchone()
        )
        assert row["status"] == "unsubscribed"
        assert (
            repository.system(
                lambda conn: conn.execute(
                    "SELECT state FROM topics.digest_run WHERE id=%s", (run["id"],)
                ).fetchone()
            )["state"]
            == "sending"
        )
        request_id, revision = uuid4(), uuid4()

        def authorize_erasure(conn):
            conn.execute(
                "UPDATE accounts.account SET lifecycle_revision=%s WHERE id=%s",
                (revision, authority.account_id),
            )
            conn.execute(
                "INSERT INTO accounts.lifecycle_request(id,account_id,revision,action,policy_ref,manifest_revision,manifest,disposition,reason_key) VALUES(%s,%s,%s,'erase',%s,'unsubscribe-test',%s,'pending','pending')",
                (
                    request_id,
                    authority.account_id,
                    revision,
                    Jsonb(SYNTHETIC_POLICY.reference),
                    Jsonb([["TopicsDigests", "live_records"]]),
                ),
            )
            conn.execute(
                "INSERT INTO accounts.lifecycle_scope(request_id,participant,scope,generation,lease_until,attempts) VALUES(%s,'TopicsDigests','live_records',1,clock_timestamp()+interval '15 seconds',1)",
                (request_id,),
            )

        transactions.run("accounts", authorize_erasure)
        result = TopicsDigestsLifecycleParticipant(transactions).apply(
            dict(
                request_id=request_id,
                account_id=authority.account_id,
                lifecycle_revision=revision,
                participant="TopicsDigests",
                scope="live_records",
                generation=1,
                action="erase",
                policy_ref=SYNTHETIC_POLICY.reference,
                manifest_revision="unsubscribe-test",
            )
        )
        assert result["disposition"] == "complete"
        assert (
            repository.system(
                lambda conn: conn.execute(
                    "SELECT count(*) AS n FROM topics.email_unsubscribe WHERE run_id=%s",
                    (run["id"],),
                ).fetchone()
            )["n"]
            == 0
        )


def test_unissued_and_expired_capabilities_do_not_mutate(transactions, authority, realm):
    repository, topic, run, _ = prepared(transactions, authority)
    service = EmailUnsubscribe(
        transactions,
        origin="https://example.invalid",
        expires_at=dt.datetime.fromtimestamp(realm.expires_at, dt.UTC),
    )
    token = service.issue(run["id"]).rsplit("/", 1)[1]
    # Preserve created<expires constraint while representing a past policy bound.
    repository.system(
        lambda conn: conn.execute(
            "UPDATE topics.email_unsubscribe SET created_at=clock_timestamp()-interval '2 hours',expires_at=clock_timestamp()-interval '1 hour' WHERE run_id=%s",
            (run["id"],),
        )
    )
    service.cancel(token)
    service.cancel("z" * 43)
    assert (
        repository.system(
            lambda conn: conn.execute(
                "SELECT status FROM topics.followed_topic WHERE id=%s", (topic["id"],)
            ).fetchone()
        )["status"]
        == "active"
    )
