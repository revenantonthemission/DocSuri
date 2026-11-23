"""Operator-only real composition, its activation and adapter (`backend/u5_real_delivery.py`):
configuration refusals, provider configuration, activation-file custody and the
message preview.

Fake transport and fake credentials only; no check here contacts a provider, and none
is evidence of external delivery. Moved unchanged from `test_real_composition.py`
(plan Step 35, decision L3-1); the shared builders are in `real_composition_kit.py`.
"""

import asyncio
import datetime as dt
import json
import os
from uuid import uuid4

import httpx
import pytest
from backend.u5_real_delivery import (
    ACTIVATION_FILE,
    REDACTED_TOKEN,
    RealDeliveryRefused,
    load_activation,
    message_preview,
    parse_activation,
    provider_configuration,
    real_mail,
)

from tests.u5_topics_digests.real_composition_kit import (
    ENVIRON,
    FAKE_KEY,
    NOW,
    PUBLIC,
    FakeClient,
    activation,
    activation_value,
    profile,
)


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
