"""Bounded refusal detail: fake HTTP only, zero network, no external delivery evidence.

A definite provider refusal keeps its HTTP status and validated error name; a
refusal decided on this host before any network call keeps a distinct reason;
nothing secret, no recipient and no provider free text is retained.
"""

import datetime as dt
import hashlib
from uuid import uuid4

import httpx
import pytest

from backend.modules.accounts.integrations.digest_email import (
    LOCAL_REFUSALS,
    PROVIDER_ERROR_UNAVAILABLE,
    PROVIDER_REFUSAL,
    RECIPIENT_NOT_PERMITTED,
    REFUSED_STATUSES,
    UNSUBSCRIBE_URL_INVALID,
    DigestMailResult,
    provider_error_name,
    valid_provider_refusal,
)
from scripts.u5_real_delivery import outcome_view, refusal_view
from tests.u5_topics_digests.component.test_digest_transport import (
    ORIGIN,
    FakeClient,
    adapter,
    send,
)

SECRET_BODY = {
    "statusCode": 403,
    "name": "validation_error",
    "message": "secret-test owner@example.invalid domain is not verified",
}


@pytest.mark.parametrize("status", REFUSED_STATUSES)
def test_each_refused_status_records_status_and_error_name(status):
    fake = FakeClient(httpx.Response(status, json=dict(SECRET_BODY, statusCode=status)))
    result = send(adapter(fake))
    assert result.state == "refused" and len(fake.calls) == 1
    assert result.refusal_reason == PROVIDER_REFUSAL == result.failure_reason
    assert result.provider_status == status
    assert result.provider_error == "validation_error"
    # Neither the key, the recipient nor the provider's free text survives.
    shown = repr(result)
    for forbidden in ("secret-test", "owner@", "not verified", "Bearer"):
        assert forbidden not in shown


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(403, json={"name": "Validation Error"}),
        httpx.Response(403, json={"name": "x" * 65}),
        httpx.Response(403, json={"name": "owner@example.invalid"}),
        httpx.Response(403, json={"name": "validation_error\n"}),
        httpx.Response(403, json={"name": 403}),
        httpx.Response(403, json={"message": "no name here"}),
        httpx.Response(403, json=["validation_error"]),
        httpx.Response(403, content=b"<html>forbidden</html>"),
        httpx.Response(403),
    ],
)
def test_invalid_or_missing_error_name_becomes_the_placeholder(response):
    fake = FakeClient(response)
    result = send(adapter(fake))
    assert result.state == "refused" and result.provider_status == 403
    assert result.provider_error == PROVIDER_ERROR_UNAVAILABLE
    assert provider_error_name(response) == PROVIDER_ERROR_UNAVAILABLE


def test_local_refusals_are_distinct_and_never_reach_the_network():
    fake = FakeClient(httpx.Response(200, json={"id": str(uuid4())}))
    recipient = send(adapter(fake), recipient="other@example.invalid")
    capability = send(adapter(fake), url=ORIGIN)
    assert fake.calls == []
    assert recipient.failure_reason == RECIPIENT_NOT_PERMITTED
    assert capability.failure_reason == UNSUBSCRIBE_URL_INVALID
    for result in (recipient, capability):
        assert result.state == "refused"
        assert (result.provider_status, result.provider_error) == (None, None)
    assert set(LOCAL_REFUSALS) == {RECIPIENT_NOT_PERMITTED, UNSUBSCRIBE_URL_INVALID}


@pytest.mark.parametrize(
    "fields",
    [
        {"state": "unknown", "provider_status": 403, "provider_error": "validation_error"},
        {"state": "unknown", "refusal_reason": PROVIDER_REFUSAL},
        {"state": "refused", "refusal_reason": "provider said no"},
        {"state": "refused", "provider_error": "validation_error"},
        {
            "state": "refused",
            "refusal_reason": PROVIDER_REFUSAL,
            "provider_status": 500,
            "provider_error": "validation_error",
        },
        {
            "state": "refused",
            "refusal_reason": PROVIDER_REFUSAL,
            "provider_status": True,
            "provider_error": "validation_error",
        },
        {
            "state": "refused",
            "refusal_reason": PROVIDER_REFUSAL,
            "provider_status": 403,
            "provider_error": "Not Verified",
        },
        {
            "state": "refused",
            "refusal_reason": RECIPIENT_NOT_PERMITTED,
            "provider_status": 403,
            "provider_error": "validation_error",
        },
    ],
)
def test_result_rejects_inconsistent_refusal_detail(fields):
    with pytest.raises(ValueError):
        DigestMailResult(**fields)


def test_detail_free_refusal_keeps_the_provider_path_reason():
    # An adapter that reports a bare refusal is still recorded on the provider path.
    assert DigestMailResult("refused").failure_reason == PROVIDER_REFUSAL
    assert valid_provider_refusal(422, PROVIDER_ERROR_UNAVAILABLE)
    assert not valid_provider_refusal(408, "validation_error")
    assert not valid_provider_refusal("403", "validation_error")


def outcome_row(**changes):
    row = {
        "id": uuid4(),
        "state": "failed",
        "window_start": dt.date(2026, 10, 13),
        "window_end": dt.date(2026, 10, 19),
        "observed_state": "failed",
        "reconciled_state": None,
        "failure_reason": PROVIDER_REFUSAL,
        "provider_status": 403,
        "provider_error": "validation_error",
        "path_kind": "real",
        "attempted_at": dt.datetime(2026, 10, 19, 4, 49, 59, tzinfo=dt.UTC),
        "acknowledged_at": None,
        "transport_receipt": None,
        "evidence_retain_until": dt.datetime(2026, 11, 18, 4, 49, 59, tzinfo=dt.UTC),
        "evidence_expired_at": None,
    }
    row.update(changes)
    return row


def test_outcome_prints_the_provider_refusal_detail():
    view = outcome_view(outcome_row())
    assert view["failureReason"] == PROVIDER_REFUSAL
    assert view["refusal"] == {
        "decidedBy": "provider",
        "reason": PROVIDER_REFUSAL,
        "reachedProvider": True,
        "httpStatus": 403,
        "errorName": "validation_error",
        "detailRecorded": True,
    }
    assert view["sendLog"]["providerReceipt"] is None


def test_outcome_distinguishes_local_legacy_and_non_failed_runs():
    for reason in ("recipient-unavailable", *LOCAL_REFUSALS):
        local = refusal_view(
            outcome_row(failure_reason=reason, provider_status=None, provider_error=None)
        )
        assert local == {"decidedBy": "local", "reason": reason, "reachedProvider": False}
    # The first attempt predates refusal detail: it says so rather than guessing.
    legacy = refusal_view(outcome_row(provider_status=None, provider_error=None))
    assert legacy["decidedBy"] == "provider" and legacy["detailRecorded"] is False
    assert legacy["reachedProvider"] is None and legacy["httpStatus"] is None
    other = refusal_view(
        outcome_row(failure_reason="test-closed", provider_status=None, provider_error=None)
    )
    assert other["decidedBy"] == "unclassified" and other["reachedProvider"] is None
    sent_receipt = str(uuid4())
    sent = outcome_view(
        outcome_row(
            state="sent",
            observed_state="sent",
            failure_reason=None,
            provider_status=None,
            provider_error=None,
            transport_receipt=sent_receipt,
        )
    )
    assert sent["refusal"] is None
    assert (
        sent["sendLog"]["providerReceiptSha256"]
        == hashlib.sha256(sent_receipt.encode()).hexdigest()
    )
