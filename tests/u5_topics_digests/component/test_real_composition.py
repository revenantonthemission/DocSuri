"""Operator-only real composition: configuration refusals and truthful labels.

Fake transport and fake credentials only; no check here contacts a provider,
and none is evidence of external delivery.
"""

import asyncio
import datetime as dt
import json
import os
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from backend.local_host import assemble
from backend.modules.accounts.integrations.digest_email import digest_mail_binding
from backend.modules.topics.unsubscribe import (
    HEADERS,
    PREFIX,
    PublicCancellationOrigin,
    unsubscribe_router,
)
from backend.u5_host import digest_capability, topics_contribution
from backend.u5_policy import REAL_DEMONSTRATION_TOPICS, SYNTHETIC_TOPICS, TopicsPolicy
from backend.u5_real_delivery import (
    ACTIVATION_FILE,
    REDACTED_TOKEN,
    RealDeliveryRefused,
    load_activation,
    message_preview,
    parse_activation,
    provider_configuration,
    real_mail,
    real_topics_factory,
)
from fastapi.testclient import TestClient

from tests.u5_topics_digests.fetch_origin import NULL_ORIGIN, form_post_origin

PUBLIC = "https://unsubscribe.fixture.invalid"
FAKE_KEY = "re_fakeCredentialNeverReal_0123456789"
ENVIRON = {"EMAIL_PROVIDER": "resend", "RESEND_API_KEY": FAKE_KEY}
NOW = dt.datetime(2026, 10, 19, 3, 0, tzinfo=dt.UTC)


def profile(tmp_path=None):
    return SimpleNamespace(
        run_id="docsuri-u5-0123456789abcdef",
        realm="topics-digests",
        origin="https://127.0.0.1:18089",
        expires_at=(NOW + dt.timedelta(hours=20)).timestamp(),
        root=tmp_path,
    )


def activation_value(**changes):
    value = {
        "runId": "docsuri-u5-0123456789abcdef",
        "sender": "no-reply@docsuri.fixture.invalid",
        "permittedRecipient": "owner@fixture.invalid",
        "unsubscribeOrigin": PUBLIC,
        "capabilityExpiresAt": (NOW + dt.timedelta(hours=12)).isoformat(),
        "freePlanVerified": True,
        "unsubscribeEndpointVerified": True,
    }
    value.update(changes)
    return value


def activation(**changes):
    return parse_activation(activation_value(**changes), profile(), now=NOW)


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
        self.calls.append((args, kwargs))
        return self.response


def fake_transactions():
    return SimpleNamespace(profile=profile())


def test_valid_activation_and_environment_build_the_real_adapter():
    chosen = activation()
    assert chosen.capability_expires_at.tzinfo is not None
    fake = FakeClient(httpx.Response(200, json={"id": str(uuid4())}))
    mail = real_mail(chosen, ENVIRON, client_factory=fake)
    assert mail.path_kind == "real"
    assert mail.permitted_recipient == "owner@fixture.invalid"
    assert mail.permits("owner@fixture.invalid") and not mail.permits("other@fixture.invalid")
    url = PUBLIC + "/api/v2/topics/email-unsubscribe/" + "y" * 43
    presentation = {"subject": "S", "text": "T", "html": "<p>H</p>"}
    result = asyncio.run(
        mail.send("owner@fixture.invalid", presentation, uuid4(), unsubscribe_url=url)
    )
    assert result.state == "accepted" and len(fake.calls) == 1


def test_sender_domain_may_differ_from_the_unsubscribe_origin_host():
    """The verified sending domain and the public cancellation host are independent."""
    chosen = activation(
        sender="no-reply@mail.rvnnt.dev", unsubscribeOrigin="https://docsuri.rvnnt.dev"
    )
    assert chosen.sender == "no-reply@mail.rvnnt.dev"
    assert chosen.unsubscribe_origin == "https://docsuri.rvnnt.dev"
    fake = FakeClient(httpx.Response(200, json={"id": str(uuid4())}))
    mail = real_mail(chosen, ENVIRON, client_factory=fake)
    url = "https://docsuri.rvnnt.dev/api/v2/topics/email-unsubscribe/" + "k" * 43
    presentation = {"subject": "S", "text": "T", "html": "<p>H</p>"}
    result = asyncio.run(
        mail.send("owner@fixture.invalid", presentation, uuid4(), unsubscribe_url=url)
    )
    assert result.state == "accepted" and len(fake.calls) == 1
    submitted = fake.calls[0][1]["json"]
    assert submitted["from"] == "no-reply@mail.rvnnt.dev"
    assert submitted["headers"]["List-Unsubscribe"] == f"<{url}>"
    preview = message_preview(
        {
            "id": uuid4(),
            "request_key": uuid4(),
            "state": "prepared",
            "window_start": dt.date(2026, 10, 13),
            "window_end": dt.date(2026, 10, 19),
            "presentation": presentation,
        },
        chosen,
    )
    assert preview["message"]["from"] == "no-reply@mail.rvnnt.dev"
    assert preview["message"]["headers"]["List-Unsubscribe"].startswith(
        "<https://docsuri.rvnnt.dev/api/v2/topics/email-unsubscribe/"
    )
    # The cancellation link still binds to the configured origin, not the sender.
    foreign = "https://mail.rvnnt.dev/api/v2/topics/email-unsubscribe/" + "k" * 43
    refused = asyncio.run(
        mail.send("owner@fixture.invalid", presentation, uuid4(), unsubscribe_url=foreign)
    )
    assert refused.failure_reason == "unsubscribe-url-invalid" and len(fake.calls) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"runId": "docsuri-u5-ffffffffffffffff"},
        {"sender": "Name <no-reply@docsuri.fixture.invalid>"},
        {"sender": "no-reply@docsuri.fixture.invalid\nBcc: x@y.invalid"},
        {"permittedRecipient": ""},
        {"permittedRecipient": ["owner@fixture.invalid"]},
        {"unsubscribeOrigin": "http://unsubscribe.fixture.invalid"},
        {"unsubscribeOrigin": "https://127.0.0.1"},
        {"unsubscribeOrigin": "https://localhost"},
        {"unsubscribeOrigin": PUBLIC + "/path"},
        {"unsubscribeOrigin": PUBLIC + ":8443"},
        {"capabilityExpiresAt": "2026-10-19T15:00:00"},
        {"capabilityExpiresAt": (NOW - dt.timedelta(minutes=1)).isoformat()},
        {"capabilityExpiresAt": (NOW + dt.timedelta(days=2)).isoformat()},
        {"capabilityExpiresAt": "tomorrow"},
        {"freePlanVerified": False},
        {"freePlanVerified": "true"},
        {"unsubscribeEndpointVerified": None},
    ],
)
def test_every_invalid_activation_field_refuses(changes):
    with pytest.raises(RealDeliveryRefused):
        activation(**changes)


@pytest.mark.parametrize("field", ["freePlanVerified", "unsubscribeEndpointVerified", "sender"])
def test_missing_or_extra_activation_fields_refuse(field):
    value = activation_value()
    del value[field]
    with pytest.raises(RealDeliveryRefused):
        parse_activation(value, profile(), now=NOW)
    with pytest.raises(RealDeliveryRefused):
        parse_activation(dict(activation_value(), apiKey=FAKE_KEY), profile(), now=NOW)


@pytest.mark.parametrize(
    "environ",
    [
        {},
        {"RESEND_API_KEY": FAKE_KEY},
        {"EMAIL_PROVIDER": "ses", "RESEND_API_KEY": FAKE_KEY},
        {"EMAIL_PROVIDER": "resend"},
        {"EMAIL_PROVIDER": "resend", "RESEND_API_KEY": ""},
        {"EMAIL_PROVIDER": "resend", "RESEND_API_KEY": " " + FAKE_KEY},
        {"EMAIL_PROVIDER": "resend", "RESEND_API_KEY": '"' + FAKE_KEY + '"'},
        {"EMAIL_PROVIDER": "resend", "RESEND_API_KEY": "sk_" + FAKE_KEY[3:]},
    ],
)
def test_provider_environment_refuses_without_echoing_the_credential(environ):
    with pytest.raises(RealDeliveryRefused) as refused:
        real_mail(activation(), environ, client_factory=FakeClient(None))
    assert FAKE_KEY not in str(refused.value) and FAKE_KEY not in repr(refused.value)


def test_provider_configuration_carries_the_operator_gates():
    configuration = provider_configuration(activation(), ENVIRON)
    assert configuration["freePlanVerified"] is True
    assert configuration["unsubscribeEndpointVerified"] is True
    assert configuration["unsubscribeUrl"] == PUBLIC


def test_activation_file_custody_and_absence(tmp_path):
    with pytest.raises(RealDeliveryRefused, match="absent"):
        load_activation(profile(tmp_path), now=NOW)
    path = tmp_path / ACTIVATION_FILE
    path.write_text(json.dumps(activation_value()))
    os.chmod(path, 0o644)
    with pytest.raises(RealDeliveryRefused, match="custody"):
        load_activation(profile(tmp_path), now=NOW)
    os.chmod(path, 0o600)
    assert load_activation(profile(tmp_path), now=NOW).sender.startswith("no-reply@")
    path.write_text("{not json")
    with pytest.raises(RealDeliveryRefused, match="JSON"):
        load_activation(profile(tmp_path), now=NOW)


def test_local_and_test_profiles_ignore_ambient_real_configuration(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("RESEND_API_KEY", FAKE_KEY)
    contribution = topics_contribution(fake_transactions(), SimpleNamespace(), None, None)
    assert contribution["delivery"].path_kind() == "local-sink"
    assert contribution["delivery"].recipient_scope() is None
    assert contribution["capabilities"][0]["modeIds"] == ["synthetic-only"]
    with pytest.raises(ValueError):
        digest_mail_binding(synthetic=True, client_factory=FakeClient(None))
    with pytest.raises(ValueError):
        digest_mail_binding(synthetic=True, provider="resend", configuration={"apiKey": "x"})
    real = real_mail(activation(), ENVIRON, client_factory=FakeClient(None))
    with pytest.raises(ValueError):
        topics_contribution(fake_transactions(), SimpleNamespace(), None, None, mail=real)


def test_capability_labels_follow_the_bound_adapter():
    synthetic = topics_contribution(fake_transactions(), SimpleNamespace(), None, None)
    assert synthetic["capabilities"][0] | {"policy": None} == {
        "id": "topics.digest",
        "state": "degraded",
        "modeIds": ["synthetic-only"],
        "languageIds": ["en", "ko"],
        "levelIds": ["standard"],
        "formatIds": ["email"],
        "policy": None,
    }
    mail = real_mail(activation(), ENVIRON, client_factory=FakeClient(None))
    real = real_topics_factory(activation(), mail)(
        fake_transactions(), SimpleNamespace(), None, None
    )
    record = real["capabilities"][0]
    assert record["modeIds"] == ["real-bounded"] and record["state"] == "degraded"
    assert record["policy"] == {"policyId": "u5-real-demonstration", "revision": "1"}
    assert real["delivery"].recipient_scope() == "owner@fixture.invalid"
    with pytest.raises(ValueError):
        digest_capability(SYNTHETIC_TOPICS, real["delivery"])
    with pytest.raises(ValueError):
        digest_capability(REAL_DEMONSTRATION_TOPICS, synthetic["delivery"])


def test_real_policy_is_one_send_and_thirty_day_retention():
    assert REAL_DEMONSTRATION_TOPICS.real_send_limit == 1
    assert REAL_DEMONSTRATION_TOPICS.real_evidence_retention_days == 30
    assert not REAL_DEMONSTRATION_TOPICS.synthetic_only
    for invalid in (
        {"synthetic_only": False, "real_send_limit": 1},
        {"synthetic_only": False, "real_send_limit": 1, "real_evidence_retention_days": 31},
        {"real_evidence_retention_days": 30},
        {"synthetic_only": False, "real_send_limit": 1, "real_evidence_retention_days": "30"},
    ):
        with pytest.raises(ValueError):
            TopicsPolicy(**invalid)
    with pytest.raises(RealDeliveryRefused):
        real_topics_factory(activation(), None, policy=SYNTHETIC_TOPICS)


def test_preview_redacts_the_token_and_never_shows_the_credential():
    run = {
        "id": uuid4(),
        "request_key": uuid4(),
        "state": "prepared",
        "window_start": dt.date(2026, 10, 13),
        "window_end": dt.date(2026, 10, 19),
        "preference_snapshot": {"languageId": "ko"},
        "presentation": {
            "subject": "[DocSuri] S",
            "text": "T",
            "html": "<html><body><p>H</p></body></html>",
        },
    }
    preview = message_preview(run, activation())
    message = preview["message"]
    url = PUBLIC + "/api/v2/topics/email-unsubscribe/" + REDACTED_TOKEN
    assert message["to"] == ["owner@fixture.invalid"]
    assert message["from"] == "no-reply@docsuri.fixture.invalid"
    assert message["text"] == "T\n\nUnsubscribe: " + url
    # The cancellation link stays inside the document body.
    assert message["html"] == (
        f'<html><body><p>H</p><p><a href="{url}">Unsubscribe / 구독 해지</a></p></body></html>'
    )
    assert message["headers"] == {
        "List-Unsubscribe": f"<{url}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
    assert preview["providerRequest"]["headers"]["Idempotency-Key"] == str(run["request_key"])
    assert FAKE_KEY not in json.dumps(preview, default=str)
    with pytest.raises(RealDeliveryRefused):
        message_preview(dict(run, state="sent"), activation())


def test_public_cancellation_origin_is_admitted_only_on_cancellation_paths():
    seen = []

    async def inner(scope, receive, send):
        seen.append(dict(scope["headers"]).get(b"origin"))

    middleware = PublicCancellationOrigin(inner, origin=PUBLIC)
    token_path = "/api/v2/topics/email-unsubscribe/" + "z" * 43

    def call(path, origin, method="POST"):
        scope = {"type": "http", "method": method, "path": path, "headers": [(b"origin", origin)]}
        asyncio.run(middleware(scope, None, None))

    call(token_path, PUBLIC.encode())
    call(token_path, b"https://elsewhere.fixture.invalid")
    call("/api/v2/topics", PUBLIC.encode())
    call(token_path + "x", PUBLIC.encode())
    call(token_path, PUBLIC.encode(), method="DELETE")
    assert seen == [
        None,
        b"https://elsewhere.fixture.invalid",
        PUBLIC.encode(),
        PUBLIC.encode(),
        PUBLIC.encode(),
    ]
    with pytest.raises(ValueError):
        PublicCancellationOrigin(inner, origin="http://unsubscribe.fixture.invalid")


class RecordingCancellation:
    def __init__(self):
        self.calls = []

    def cancel(self, token):
        self.calls.append(token)


def boundary_client(service):
    """The real host boundary, the cancellation router and the middleware.

    Same order as `assemble_u5_real`: `local_host.assemble` installs the
    boundary, then the middleware is added outermost. No database is needed
    because the recording service stands in for the capability store.
    """
    app = assemble(
        SimpleNamespace(origin="https://127.0.0.1:18089"), routers=[unsubscribe_router(service)]
    )
    app.add_middleware(PublicCancellationOrigin, origin=PUBLIC)
    return TestClient(app, base_url="https://127.0.0.1")


FORM = {"List-Unsubscribe": "One-Click"}


def test_fetch_origin_rule_follows_the_standard():
    page = PUBLIC + PREFIX + "a" * 43
    assert form_post_origin("no-referrer", page, page) == NULL_ORIGIN
    assert form_post_origin("same-origin", page, page) == PUBLIC
    assert form_post_origin("same-origin", page, "https://other.invalid/x") == NULL_ORIGIN
    assert form_post_origin("strict-origin", page, "http://other.invalid/x") == NULL_ORIGIN
    assert form_post_origin("strict-origin-when-cross-origin", page, page) == PUBLIC
    assert form_post_origin("origin", "https://h.invalid:8443/p", page) == "https://h.invalid:8443"


def test_cancellation_page_is_served_with_its_own_referrer_policy_and_csp():
    with boundary_client(RecordingCancellation()) as client:
        page = client.get(PREFIX + "b" * 43)
        other = client.get("/health/live")
    assert page.status_code == 200
    for name, value in HEADERS.items():
        # Exactly one value: the boundary's host-wide header must not survive.
        assert page.headers.get_list(name) == [value]
    assert page.headers["referrer-policy"] == "same-origin"
    assert "form-action 'self'" in page.headers["content-security-policy"]
    # Paths other than the cancellation path keep the boundary's headers.
    assert other.headers["referrer-policy"] == "no-referrer"
    assert "form-action" not in other.headers["content-security-policy"]


def test_browser_confirm_under_the_served_policy_passes_the_boundary():
    """R-15: the page's own form POST, with the Origin a browser derives from its policy."""
    service = RecordingCancellation()
    token = "c" * 43
    with boundary_client(service) as client:
        page = client.get(PREFIX + token)
        public_url = PUBLIC + PREFIX + token
        origin = form_post_origin(page.headers["referrer-policy"], public_url, public_url)
        assert origin == PUBLIC
        confirmed = client.post(PREFIX + token, data=FORM, headers={"Origin": origin})
    assert confirmed.status_code == 200
    assert confirmed.headers["referrer-policy"] == "same-origin"
    assert service.calls == [token]


def test_the_previous_no_referrer_page_produced_a_refused_null_origin():
    """Reproduces the live failure: `no-referrer` makes the browser send `Origin: null`."""
    service = RecordingCancellation()
    public_url = PUBLIC + PREFIX + "d" * 43
    origin = form_post_origin("no-referrer", public_url, public_url)
    with boundary_client(service) as client:
        refused = client.post(PREFIX + "d" * 43, data=FORM, headers={"Origin": origin})
    assert origin == NULL_ORIGIN
    assert refused.status_code == 403
    assert refused.json()["messageKey"] == "request.origin"
    assert service.calls == []


def test_only_the_exact_origin_on_the_exact_path_and_methods_is_admitted():
    service = RecordingCancellation()
    path = PREFIX + "e" * 43
    with boundary_client(service) as client:
        # Header-less RFC 8058 one-click POST (mail provider or mail app).
        assert client.post(path, data=FORM).status_code == 200
        for origin in (
            NULL_ORIGIN,
            "https://other.invalid",
            PUBLIC + ":8443",
            "http://unsubscribe.fixture.invalid",
        ):
            assert client.post(path, data=FORM, headers={"Origin": origin}).status_code == 403
        assert client.post(path + "x", data=FORM, headers={"Origin": PUBLIC}).status_code == 403
        assert client.post("/api/v2/topics", json={}, headers={"Origin": PUBLIC}).status_code == 403
        assert client.delete(path, headers={"Origin": PUBLIC}).status_code == 403
    assert service.calls == ["e" * 43]


def test_outcome_view_reports_receipt_and_its_digest():
    import hashlib

    from scripts.u5_real_delivery import outcome_view

    receipt = str(uuid4())
    base = {
        "id": uuid4(),
        "state": "sent",
        "window_start": dt.date(2026, 10, 13),
        "window_end": dt.date(2026, 10, 19),
        "observed_state": "sent",
        "reconciled_state": None,
        "failure_reason": None,
        "path_kind": "real",
        "attempted_at": NOW,
        "acknowledged_at": NOW,
        "transport_receipt": receipt,
        "evidence_retain_until": NOW + dt.timedelta(days=30),
        "evidence_expired_at": None,
    }
    view = outcome_view(base)
    assert view["sendLog"]["providerReceipt"] == receipt
    assert view["sendLog"]["providerReceiptSha256"] == hashlib.sha256(receipt.encode()).hexdigest()
    assert view["sendLog"]["evidenceExpired"] is False
    expired = outcome_view(dict(base, transport_receipt=None, evidence_expired_at=NOW))
    assert expired["sendLog"]["providerReceiptSha256"] is None
    assert expired["sendLog"]["evidenceExpired"] is True
    assert outcome_view(dict(base, path_kind=None, state="prepared"))["sendLog"] is None
