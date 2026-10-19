"""Assembled real composition against the owned store, with a fake transport only.

These checks prove the composition, allocation and cancellation wiring. They are
simulated contract evidence: no provider is contacted and nothing is delivered.
"""

import dataclasses
import datetime as dt
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.modules.topics.repository import TopicsRepository
from backend.modules.topics.unsubscribe import HEADERS, PREFIX, EmailUnsubscribe
from backend.u5_policy import REAL_DEMONSTRATION_TOPICS
from backend.u5_real_delivery import (
    REDACTED_TOKEN,
    RealDeliveryRefused,
    assemble_u5_real,
    parse_activation,
    real_mail,
    real_topics_factory,
)
from tests.u5_topics_digests.conftest import _make_authority
from tests.u5_topics_digests.fetch_origin import NULL_ORIGIN, form_post_origin

PUBLIC = "https://unsubscribe.fixture.invalid"
FAKE_KEY = "re_fakeCredentialNeverReal_abcdef0123"
ENVIRON = {"EMAIL_PROVIDER": "resend", "RESEND_API_KEY": FAKE_KEY}


class FakeClient:
    def __init__(self, response):
        self.response, self.calls = response, []

    def __call__(self, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):
        self.calls.append(kwargs["json"]["to"])
        return self.response


def activation_value(realm, recipient):
    return {
        "runId": realm.run_id,
        "sender": "no-reply@docsuri.fixture.invalid",
        "permittedRecipient": recipient,
        "unsubscribeOrigin": PUBLIC,
        "capabilityExpiresAt": (dt.datetime.now(dt.UTC) + dt.timedelta(minutes=30)).isoformat(),
        "freePlanVerified": True,
        "unsubscribeEndpointVerified": True,
    }


def activation(realm, recipient):
    return parse_activation(activation_value(realm, recipient), realm)


def spent(repository):
    return repository.system(
        lambda conn: conn.execute(
            "SELECT count(*) AS n FROM topics.send_log_entry WHERE path_kind='real'"
        ).fetchone()["n"]
    )


def prepared_run(repository, authority, start):
    topic = repository.follow(authority, str(uuid4()), "Real budget")["topic"]["id"]
    run, _ = repository.prepare_run(
        topic,
        start,
        start + dt.timedelta(days=6),
        1,
        [{"title": "Original title", "publishedOn": start.isoformat()}],
    )
    return topic, run


def state_of(repository, run_id):
    return repository.system(
        lambda conn: conn.execute(
            "SELECT state FROM topics.digest_run WHERE id=%s", (run_id,)
        ).fetchone()["state"]
    )


def email_of(connect, authority):
    with connect("accounts") as conn:
        return conn.execute(
            "SELECT email FROM accounts.account WHERE id=%s", (authority.account_id,)
        ).fetchone()["email"]


def test_real_allocation_spends_once_and_failure_never_replenishes(
    transactions, connect, realm, authority_b
):
    owner = _make_authority(connect, realm, suffix="real-budget")
    chosen = activation(realm, email_of(connect, owner))
    fake = FakeClient(httpx.Response(422, json={"message": "refused"}))
    mail = real_mail(chosen, ENVIRON, client_factory=fake)
    repository = TopicsRepository(transactions)
    before = spent(repository)
    policy = dataclasses.replace(REAL_DEMONSTRATION_TOPICS, real_send_limit=before + 1)
    contribution = real_topics_factory(chosen, mail, policy=policy)(
        transactions, SimpleNamespace(), None, None
    )
    other_topic, other = prepared_run(repository, authority_b, dt.date(2026, 3, 1))
    first_topic, first = prepared_run(repository, owner, dt.date(2026, 3, 1))
    second_topic, second = prepared_run(repository, owner, dt.date(2026, 3, 1))
    try:
        contribution["scheduler"].run_once()
        contribution["scheduler"].run_once()
        # Exactly one real attempt, to the permitted recipient only.
        assert fake.calls == [[chosen.permitted_recipient]]
        assert spent(repository) == before + 1
        assert state_of(repository, first["id"]) == "failed"
        assert state_of(repository, second["id"]) == "prepared"
        assert state_of(repository, other["id"]) == "prepared"
        log = repository.system(
            lambda conn: conn.execute(
                "SELECT * FROM topics.send_log_entry WHERE run_id=%s", (first["id"],)
            ).fetchone()
        )
        assert log["path_kind"] == "real" and log["transport_receipt"] is None
        assert log["evidence_retain_until"] - log["attempted_at"] == dt.timedelta(days=30)
        # The provider's refusal keeps its status; the free-text body is not a name.
        outcome = repository.system(
            lambda conn: conn.execute(
                "SELECT failure_reason,provider_status,provider_error "
                "FROM topics.delivery_outcome WHERE run_id=%s",
                (first["id"],),
            ).fetchone()
        )
        assert outcome == {
            "failure_reason": "delivery-path-refused",
            "provider_status": 422,
            "provider_error": "name-unavailable",
        }
    finally:
        for topic in (other_topic, first_topic, second_topic):
            repository.discard_prepared_runs(topic)


def test_assembled_real_host_is_labelled_and_accepts_public_cancellation(
    transactions, authority, realm, monkeypatch
):
    from backend.u5_host import assemble_u5

    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", FAKE_KEY)
    synthetic = assemble_u5(realm)
    try:
        record = next(
            row for row in synthetic.state.capability_catalog if row["id"] == "topics.digest"
        )
        assert record["modeIds"] == ["synthetic-only"]
    finally:
        synthetic.state.transactions.close()

    chosen = activation(realm, "nobody-real@fixture.invalid")
    fake = FakeClient(httpx.Response(500))
    app = assemble_u5_real(realm, chosen, environ=ENVIRON, client_factory=fake)
    record = next(row for row in app.state.capability_catalog if row["id"] == "topics.digest")
    assert record["modeIds"] == ["real-bounded"]
    assert record["policy"]["policyId"] == "u5-real-demonstration"

    repository = TopicsRepository(transactions)
    topic, run = prepared_run(repository, authority, dt.date(2026, 4, 1))
    assert repository.begin_send(run["id"], "local-sink") is not None
    issuer = EmailUnsubscribe(
        transactions,
        origin=PUBLIC,
        expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(minutes=10),
    )
    token = issuer.issue(run["id"]).rsplit("/", 1)[1]
    path = PREFIX + token
    # A second capability for the mail-app one-click (header-less) POST.
    one_click_topic, one_click_run = prepared_run(repository, authority, dt.date(2026, 4, 8))
    assert repository.begin_send(one_click_run["id"], "local-sink") is not None
    one_click_path = PREFIX + issuer.issue(one_click_run["id"]).rsplit("/", 1)[1]
    form = {"List-Unsubscribe": "One-Click"}
    with TestClient(app, base_url=realm.origin) as client:
        app.state.control_capacity.refresh()
        # Token-bearing URLs stay out of assertion messages: compare statuses only.
        page = client.get(path)
        page_status = page.status_code
        assert page_status == 200
        assert page.headers.get_list("referrer-policy") == ["same-origin"]
        assert page.headers.get_list("content-security-policy") == [
            HEADERS["Content-Security-Policy"]
        ]
        foreign_status = client.post(
            path, data=form, headers={"Origin": "https://other.invalid"}
        ).status_code
        assert foreign_status == 403
        null_status = client.post(path, data=form, headers={"Origin": NULL_ORIGIN}).status_code
        assert null_status == 403
        other_path_status = client.post(
            "/api/v2/topics", json={}, headers={"Origin": PUBLIC}
        ).status_code
        assert other_path_status == 403
        # R-15: the Origin a browser sends for the page's own form POST, derived
        # from the Referrer-Policy the real composition actually served.
        public_url = PUBLIC + path
        browser_origin = form_post_origin(page.headers["referrer-policy"], public_url, public_url)
        assert browser_origin == PUBLIC
        confirmed_status = client.post(
            path, data=form, headers={"Origin": browser_origin}
        ).status_code
        assert confirmed_status == 200
        one_click_status = client.post(one_click_path, data=form).status_code
        assert one_click_status == 200

    def status_of(topic_id):
        return repository.system(
            lambda conn: conn.execute(
                "SELECT status FROM topics.followed_topic WHERE id=%s", (topic_id,)
            ).fetchone()["status"]
        )

    assert status_of(topic) == "unsubscribed"
    assert status_of(one_click_topic) == "unsubscribed"
    assert fake.calls == []
    repository.finish_send(run["id"], "failed", failure_reason="test-closed")
    repository.finish_send(one_click_run["id"], "failed", failure_reason="test-closed")


def test_operator_tool_prepares_and_previews_without_sending(transactions, realm):
    from scripts.u5_real_delivery import (
        allocation,
        check,
        prepare,
        preview,
        provision,
        stable_id,
    )

    chosen = activation(realm, "u5-real-tool@fixture.invalid")
    choices = {
        "language": "ko",
        "time_zone": "UTC",
        "topic_name": "실제 전송 확인",
        "delivery_time": "09:00",
    }
    provisioned = provision(realm, transactions, chosen, **choices)
    assert provisioned["recipient"] == {"provisioned": True, "granted": True}
    assert provisioned["effectivePreferences"]["languageId"] == "ko"
    assert provision(realm, transactions, chosen, **choices)["state"] == "provisioned"
    for invalid in ({"language": "fr"}, {"time_zone": "Mars/Base"}, {"delivery_time": "9h"}):
        with pytest.raises(RealDeliveryRefused):
            provision(realm, transactions, chosen, **dict(choices, **invalid))
    with pytest.raises(RealDeliveryRefused):
        provision(realm, transactions, activation(realm, "else@fixture.invalid"), **choices)

    repository = TopicsRepository(transactions)
    before = allocation(transactions)
    try:
        result = prepare(realm, transactions, chosen)
        # Browser fixtures seed eligible papers dated today in every test realm.
        assert result["state"] == "prepared" and result["items"] >= 1
        shown = preview(realm, transactions, chosen)
        assert shown["runId"] == result["runId"]
        assert shown["message"]["to"] == [chosen.permitted_recipient]
        assert REDACTED_TOKEN in shown["message"]["headers"]["List-Unsubscribe"]
        assert "최신 논문" in shown["message"]["text"]
        assert shown["allocation"] == before
        assert state_of(repository, result["runId"]) == "prepared"
        issued = repository.system(
            lambda conn: conn.execute(
                "SELECT count(*) AS n FROM topics.email_unsubscribe WHERE run_id=%s",
                (result["runId"],),
            ).fetchone()["n"]
        )
        assert issued == 0
        report = check(realm, transactions, ENVIRON)
        assert report["resendApiKeyPresent"] and report["ready"] is False
        assert FAKE_KEY not in json.dumps(report, default=str)
    finally:
        repository.discard_prepared_runs(stable_id(realm.run_id, "topic"))
    with pytest.raises(RealDeliveryRefused):
        preview(realm, transactions, chosen)


def test_operator_actions_read_the_private_activation_record(transactions, realm, tmp_path):
    import argparse
    import os

    from scripts.u5_real_delivery import run_action, stable_id

    # The record lives in a private copy of the realm's custody shape; the
    # realm directory itself is never given a test activation record.
    path = tmp_path / "real-delivery.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(activation_value(realm, "u5-real-tool@fixture.invalid"), stream)
    profile = SimpleNamespace(
        run_id=realm.run_id, root=tmp_path, expires_at=realm.expires_at, origin=realm.origin
    )

    def act(action, **extra):
        return run_action(
            argparse.Namespace(action=action, **extra), profile, transactions, ENVIRON
        )

    report = act("check")
    assert report["activation"] == "ok" and report["provider"] == "ok"
    assert report["allocation"]["limit"] == 1
    assert report["ready"] == (report["allocation"]["remaining"] > 0)
    assert FAKE_KEY not in json.dumps(report, default=str)
    unconfigured = run_action(argparse.Namespace(action="check"), profile, transactions, {})
    assert unconfigured["ready"] is False and "EMAIL_PROVIDER" in unconfigured["provider"]
    # Same choices as the tool test above: provisioning never rewrites settings.
    choices = {
        "language": "ko",
        "time_zone": "UTC",
        "topic_name": "실제 전송 확인",
        "delivery_time": "09:00",
    }
    assert act("provision", **choices)["state"] == "provisioned"
    repository = TopicsRepository(transactions)
    try:
        prepared = act("prepare")
        shown = act("preview")
        assert shown["runId"] == prepared["runId"]
        assert shown["message"]["from"] == "no-reply@docsuri.fixture.invalid"
        recorded = act("outcome")
        assert recorded["runId"] == prepared["runId"] and recorded["state"] == "prepared"
        assert recorded["sendLog"] is None
    finally:
        repository.discard_prepared_runs(stable_id(realm.run_id, "topic"))


def test_operator_tool_refuses_unsafe_recipient_states(transactions, connect, realm, authority):
    from scripts.u5_real_delivery import prepare, provision

    choices = {"language": "ko", "time_zone": "UTC", "delivery_time": "09:00"}
    chosen = activation(realm, "u5-real-tool@fixture.invalid")
    with pytest.raises(RealDeliveryRefused, match="topic name"):
        provision(realm, transactions, chosen, topic_name="", **choices)
    # Preparing for an address that is not the provisioned recipient never proceeds.
    with pytest.raises(RealDeliveryRefused, match="not provisioned"):
        prepare(realm, transactions, activation(realm, "unprovisioned@fixture.invalid"))
    # Another account already owns the address: the tool never adopts it.
    taken = email_of(connect, authority)
    other_realm = SimpleNamespace(
        run_id="docsuri-u5-" + uuid4().hex[:16], root=realm.root, expires_at=realm.expires_at
    )
    owned = parse_activation(
        dict(activation_value(realm, taken), runId=other_realm.run_id), other_realm
    )
    with pytest.raises(RealDeliveryRefused, match="another account"):
        provision(other_realm, transactions, owned, topic_name="Taken", **choices)


def test_operator_outcome_prints_the_recorded_provider_refusal(transactions, realm):
    """Provision, prepare, a refused fake send, then the read-only outcome action."""
    from scripts.u5_real_delivery import outcome, prepare, provision

    # A separate demonstration identity keeps this topic apart from the tool tests.
    other = SimpleNamespace(
        run_id="docsuri-u5-" + uuid4().hex[:16],
        root=realm.root,
        expires_at=realm.expires_at,
        origin=realm.origin,
    )
    recipient = f"u5-refusal-{uuid4().hex[:8]}@fixture.invalid"
    chosen = parse_activation(
        dict(
            activation_value(realm, recipient),
            runId=other.run_id,
            sender="no-reply@mail.fixture.invalid",
        ),
        other,
    )
    provision(
        other,
        transactions,
        chosen,
        language="en",
        time_zone="UTC",
        topic_name="Refusal detail",
        delivery_time="09:00",
    )
    prepared = prepare(other, transactions, chosen)
    assert prepared["state"] == "prepared"
    body = {
        "statusCode": 403,
        "name": "validation_error",
        "message": "The mail.fixture.invalid domain is not verified for " + recipient,
    }
    fake = FakeClient(httpx.Response(403, json=body))
    mail = real_mail(chosen, ENVIRON, client_factory=fake)
    repository = TopicsRepository(transactions)
    policy = dataclasses.replace(REAL_DEMONSTRATION_TOPICS, real_send_limit=spent(repository) + 1)
    contribution = real_topics_factory(chosen, mail, policy=policy)(
        transactions, SimpleNamespace(), None, None
    )
    contribution["scheduler"].run_once()
    assert fake.calls == [[recipient]]
    recorded = outcome(other, transactions)
    assert recorded["runId"] == prepared["runId"] and recorded["state"] == "failed"
    assert recorded["failureReason"] == "delivery-path-refused"
    assert recorded["refusal"] == {
        "decidedBy": "provider",
        "reason": "delivery-path-refused",
        "reachedProvider": True,
        "httpStatus": 403,
        "errorName": "validation_error",
        "detailRecorded": True,
    }
    printed = json.dumps(recorded, default=str)
    for forbidden in (FAKE_KEY, recipient, "not verified", "Bearer"):
        assert forbidden not in printed
