"""Every row of security design §7's write and read tables, from documented signals only."""

import json

import httpx
import pytest
from backend.modules.export import classification as c
from backend.modules.export.errors import ProtectionUnavailable
from notion_client.errors import build_request_error

PAGE = "0b7d2a51c4e94f36a8e1d2c3b4a59687"


def answer(status: int, code: str | None, *, additional=None, retry_after=None, message="m"):
    """The SDK's error for one documented answer, exactly as the SDK builds it."""
    body = {"object": "error", "status": status, "message": message, "request_id": "req-1"}
    if code is not None:
        body["code"] = code
    if additional is not None:
        body["additional_data"] = additional
    headers = {"retry-after": str(retry_after)} if retry_after is not None else {}
    response = httpx.Response(status, headers=headers, text=json.dumps(body))
    return build_request_error(response, response.text)


WRITE_REFUSALS = [
    (answer(401, "unauthorized"), c.REFUSAL_TOKEN_INVALID),
    (answer(404, "object_not_found"), c.REFUSAL_DESTINATION_MISSING),
    (answer(403, "restricted_resource"), c.REFUSAL_NO_ACCESS),
    (
        answer(403, "restricted_resource", additional={"block_limit": "block_creation"}),
        c.REFUSAL_BLOCK_LIMIT,
    ),
    (answer(400, "validation_error"), c.REFUSAL_CONTENT_REJECTED),
    (
        answer(
            429,
            "rate_limited",
            additional={"rate_limit_reason": "public_api_request_blocked"},
            retry_after=5,
        ),
        c.REFUSAL_PROVIDER_BLOCKED,
    ),
]


@pytest.mark.parametrize(("error", "refusal"), WRITE_REFUSALS)
def test_definite_write_refusals_carry_their_class(error, refusal):
    verdict = c.classify_write(error)
    assert verdict == c.Verdict(c.REFUSED, refusal=refusal, request_id="req-1")


def test_a_529_counts_as_rate_limited_with_its_stated_wait():
    error = answer(529, "service_overload", additional={"retry_after": "9"})
    assert c.classify_write(error).category == c.RATE_LIMITED
    assert c.classify_write(error).retry_after == 9
    assert c.classify_read(error).category == c.RETRYABLE


def test_an_unblocked_429_is_rate_limited_and_the_header_states_the_wait():
    error = answer(
        429,
        "rate_limited",
        additional={"rate_limit_reason": "public_api_request_rate_limit", "retry_after": "3"},
        retry_after=7,
    )
    assert c.classify_write(error) == c.Verdict(c.RATE_LIMITED, retry_after=7, request_id="req-1")
    assert c.classify_read(error).category == c.RETRYABLE


def test_a_blocked_429_is_provider_blocked_and_never_retryable():
    error = WRITE_REFUSALS[-1][0]
    assert c.classify_read(error) == c.Verdict(c.COULD_NOT_CHECK, cause=c.CAUSE_PROVIDER_BLOCKED)


def test_a_403_with_another_block_limit_value_is_no_access():
    error = answer(403, "restricted_resource", additional={"block_limit": "other"})
    assert c.classify_write(error).refusal == c.REFUSAL_NO_ACCESS


def test_a_saved_but_busy_answer_names_its_committed_page():
    error = answer(
        503,
        "service_unavailable",
        additional={"committed_resource_id": "0b7d2a51-c4e9-4f36-a8e1-d2c3b4a59687"},
    )
    verdict = c.classify_write(error)
    assert verdict.category == c.UNCERTAIN and verdict.committed_page_id == PAGE


@pytest.mark.parametrize(
    "error",
    [
        answer(409, "conflict_error"),
        answer(500, "internal_server_error"),
        answer(502, "bad_gateway"),
        answer(503, "service_unavailable"),
        answer(504, "gateway_timeout"),
        answer(401, None),
        answer(429, None),
        TimeoutError(),
        httpx.ConnectError("x"),
        json.JSONDecodeError("x", "y", 0),
        ValueError("anything unexpected"),
    ],
)
def test_everything_else_is_uncertain_for_a_write(error):
    verdict = c.classify_write(error)
    assert verdict.category == c.UNCERTAIN and verdict.refusal is None


@pytest.mark.parametrize(
    ("error", "category"),
    [
        (answer(401, "unauthorized"), c.TOKEN_INVALID),
        (answer(403, "restricted_resource"), c.NOT_READABLE),
        (answer(404, "object_not_found"), c.NOT_READABLE),
        (answer(500, "internal_server_error"), c.COULD_NOT_CHECK),
        (answer(400, "validation_error"), c.COULD_NOT_CHECK),
        (TimeoutError(), c.COULD_NOT_CHECK),
        (c.BudgetSpent(), c.COULD_NOT_CHECK),
        (c.PaceUnavailable(), c.COULD_NOT_CHECK),
        (httpx.ReadError("x"), c.COULD_NOT_CHECK),
    ],
)
def test_the_read_table(error, category):
    assert c.classify_read(error).category == category


def test_custody_and_absence_are_classified_before_any_request():
    for classify in (c.classify_read, c.classify_write):
        assert classify(ProtectionUnavailable("key-missing")).category == c.PROTECTION_UNAVAILABLE
        assert classify(c.NotConnected()).category == c.NOT_CONNECTED
        reduced = c.ReducedError(c.Verdict(c.NOT_READABLE))
        assert classify(reduced).category == c.NOT_READABLE


def test_message_text_never_decides_a_class():
    plain = answer(403, "restricted_resource", message="block_creation public_api_request_blocked")
    assert c.classify_write(plain).refusal == c.REFUSAL_NO_ACCESS
    misleading = answer(500, "internal_server_error", message="unauthorized 401 rate_limited")
    assert c.classify_write(misleading).category == c.UNCERTAIN


def test_identifiers_are_normalised_to_32_lowercase_hex():
    assert c.normalise_id("0b7d2a51-c4e9-4f36-a8e1-d2c3b4a59687") == PAGE
    assert c.normalise_id(PAGE) == PAGE
    for bad in (PAGE.upper(), PAGE[:-1], "../" + PAGE, "0b7d2a51c4e9-4f36-a8e1-d2c3b4a59687", 7):
        assert c.normalise_id(bad) is None
