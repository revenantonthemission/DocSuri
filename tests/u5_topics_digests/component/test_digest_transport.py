"""Fake HTTP contract checks; these are not external delivery evidence."""

import asyncio
import datetime as dt
from uuid import uuid4

import httpx
import pytest

from backend.modules.accounts.integrations.digest_email import (
    DigestMailResult,
    LocalDigestMail,
    ResendDigestMail,
    digest_mail_binding,
)

ORIGIN = "https://example.invalid"
URL = ORIGIN + "/api/v2/topics/email-unsubscribe/" + "x" * 43
PRESENTATION = {"subject": "Digest", "text": "Papers", "html": "<p>Papers</p>"}


class FakeClient:
    def __init__(self, response):
        self.response, self.calls = response, []

    def __call__(self, **kwargs):
        assert kwargs == {"timeout": 3.0}
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def adapter(fake):
    return ResendDigestMail(
        api_key="secret-test",
        sender="sender@example.invalid",
        unsubscribe_url=ORIGIN,
        permitted_recipient="owner@example.invalid",
        client_factory=fake,
    )


def send(mail, *, url=URL, recipient="owner@example.invalid", key=None):
    return asyncio.run(mail.send(recipient, PRESENTATION, key or uuid4(), unsubscribe_url=url))


def test_acceptance_retains_actual_receipt_and_one_click_headers():
    receipt, key = str(uuid4()), uuid4()
    fake = FakeClient(httpx.Response(200, json={"id": receipt}))
    result = send(adapter(fake), key=key)
    assert result.state == "accepted" and result.receipt == receipt
    assert result.acknowledged_at.tzinfo == dt.UTC
    assert len(fake.calls) == 1
    request = fake.calls[0][1]
    assert request["headers"]["Idempotency-Key"] == str(key)
    assert request["json"]["headers"] == {
        "List-Unsubscribe": f"<{URL}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
    assert URL in request["json"]["text"] and URL in request["json"]["html"]


@pytest.mark.parametrize(
    "status,state",
    [(422, "refused"), (429, "refused"), (408, "unknown"), (409, "unknown"), (500, "unknown")],
)
def test_refusal_and_ambiguous_status_never_retry(status, state):
    fake = FakeClient(httpx.Response(status, json={"message": "secret-test owner@example.invalid"}))
    result = send(adapter(fake))
    assert result.state == state and len(fake.calls) == 1
    if state == "unknown":
        # Ambiguous statuses carry no refusal detail at all.
        assert result == DigestMailResult("unknown")
    assert "secret-test" not in repr(result) and "owner@" not in repr(result)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={}),
        httpx.Response(201, json={"id": "bad"}),
        httpx.Response(200, content=b"not-json"),
        httpx.ReadTimeout("secret-test"),
    ],
)
def test_malformed_success_or_lost_response_is_unknown(response):
    fake = FakeClient(response)
    assert send(adapter(fake)) == DigestMailResult("unknown")
    assert len(fake.calls) == 1


@pytest.mark.parametrize(
    "url",
    [
        None,
        ORIGIN,
        "https://foreign.invalid/api/v2/topics/email-unsubscribe/" + "x" * 43,
        URL + "?extra=1",
    ],
)
def test_missing_or_wrong_capability_refused_before_network(url):
    fake = FakeClient(httpx.Response(200, json={"id": str(uuid4())}))
    assert send(adapter(fake), url=url).state == "refused"
    assert fake.calls == []


def test_recipient_is_bounded_and_local_binding_ignores_ambient_secrets(monkeypatch):
    fake = FakeClient(httpx.Response(200, json={"id": str(uuid4())}))
    assert send(adapter(fake), recipient="other@example.invalid").state == "refused"
    assert fake.calls == []
    monkeypatch.setenv("RESEND_API_KEY", "fake-ambient-secret")
    local = digest_mail_binding(synthetic=True)
    assert isinstance(local, LocalDigestMail) and local.path_kind == "local-sink"
    assert send(local).receipt.startswith("local:")
    with pytest.raises(ValueError):
        digest_mail_binding(synthetic=True, provider="resend")
    with pytest.raises(ValueError):
        digest_mail_binding(synthetic=False, provider="ses")


def test_configuration_and_result_require_evidence():
    with pytest.raises(ValueError):
        DigestMailResult("accepted")
    with pytest.raises(ValueError):
        digest_mail_binding(
            synthetic=False, provider="resend", configuration={"freePlanVerified": True}
        )
    with pytest.raises(ValueError):
        ResendDigestMail(
            api_key="k",
            sender="s",
            permitted_recipient="r",
            unsubscribe_url="http://example.invalid",
        )
