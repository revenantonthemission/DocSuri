"""Fixed outcome categories for every Notion answer (security design §7; D11, NFR3.6).

Pure functions only. Each one takes an exception raised inside one Notion operation and
returns a frozen `Verdict`: a category plus bounded facts (a refusal class, Notion's
stated wait, its request id, the page a "saved but busy" answer names). Nothing here
reads exception message text; facts come only from the HTTP status, the documented body
`code`, `additional_data` and the `Retry-After` header. The caller drops the exception
as soon as the verdict exists, so no exception object outlives its `except` block.

Documented signals, checked against the 2026-03-11 API reference on 2026-10-20:

- 429 `rate_limited`, with `additional_data.rate_limit_reason` set to
  `public_api_request_blocked` when retrying will not help; the stated wait is the
  integer `Retry-After` header, repeated as the string `additional_data.retry_after`;
- 529 `service_overload` (unknown to the SDK, so the code comes from the parsed body);
- 403 `restricted_resource` with `additional_data.block_limit` = `block_creation`;
- 503 `service_unavailable` with `additional_data.committed_resource_id` naming the page
  a create saved before Notion ran out of time.
"""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass

from notion_client.errors import HTTPResponseError

from .errors import ProtectionUnavailable

# -- categories ------------------------------------------------------------------------

OK = "ok"
# Writes (rules BR4.2).
CREATED = "created"
REFUSED = "refused"
RATE_LIMITED = "rate-limited"
UNCERTAIN = "uncertain"
# Reads (security design §7, reads table).
TOKEN_INVALID = "token-invalid"
NOT_READABLE = "not-readable"
RETRYABLE = "retryable"
COULD_NOT_CHECK = "could-not-check"
# Before any request leaves: no envelope to open, or custody failed (BR1.6).
NOT_CONNECTED = "not-connected"
PROTECTION_UNAVAILABLE = "protection-unavailable"

# Refusal classes of a write (ProviderNotionRefusalClass, A6 extension).
REFUSAL_TOKEN_INVALID = "token-invalid"
REFUSAL_NO_ACCESS = "no-access"
REFUSAL_DESTINATION_MISSING = "destination-missing"
REFUSAL_CONTENT_REJECTED = "content-rejected"
REFUSAL_BLOCK_LIMIT = "workspace-block-limit"
REFUSAL_PROVIDER_BLOCKED = "provider-blocked"

# Fixed causes of a could-not-check or uncertain verdict, for evidence and tests.
CAUSE_BUDGET = "budget"
CAUSE_INTERACTIVE_CAP = "interactive-cap"
CAUSE_PACE = "pace-unavailable"
CAUSE_PROVIDER_BLOCKED = "provider-blocked"
CAUSE_RESPONSE = "response"
CAUSE_TRANSPORT = "transport"

BLOCKED_REASON = "public_api_request_blocked"
BLOCK_CREATION = "block_creation"
# A stated wait longer than a day is not a wait any budget could honour.
MAX_STATED_WAIT_SECONDS = 86_400
_REQUEST_ID = re.compile(r"[0-9A-Za-z][0-9A-Za-z._:-]{0,127}")
_HEX32 = re.compile(r"[0-9a-f]{32}")
_UUID_FORM = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


@dataclass(frozen=True)
class Verdict:
    """One reduced answer. Every field is a fixed token, a bounded number or a validated
    identifier; none is provider text."""

    category: str
    refusal: str | None = None
    retry_after: int | None = None
    request_id: str | None = None
    committed_page_id: str | None = None
    cause: str | None = None


class ReducedError(Exception):
    """Carries an already-reduced verdict out of an operation's work.

    Raised only after the `except` block that produced the verdict has ended, with
    `from None`, so its `__cause__` and `__context__` are both None.
    """

    def __init__(self, verdict: Verdict):
        super().__init__(verdict.category)
        self.verdict = verdict


class NotConnected(Exception):
    """The stored connection holds no envelope: not connected, disconnected or revoked."""


class BudgetSpent(Exception):
    """A pace slot or a stated wait would end past the operation's remaining budget."""


class PaceUnavailable(Exception):
    """The pace record is missing or the reservation was busy (could-not-check, §9.2)."""


def normalise_id(value) -> str | None:
    """A Notion identifier as 32 lowercase hex digits, or None (security design §6.3).

    The hyphens of the 8-4-4-4-12 form are removed; nothing else is accepted.
    """
    if not isinstance(value, str):
        return None
    if _UUID_FORM.fullmatch(value):
        value = value.replace("-", "")
    return value if _HEX32.fullmatch(value) else None


def _parsed_body(error: HTTPResponseError) -> Mapping:
    body = getattr(error, "body", None)
    if not isinstance(body, str) or not body:
        return {}
    try:
        parsed = json.loads(body)
    except ValueError:
        return {}
    return parsed if isinstance(parsed, Mapping) else {}


def _code(error: HTTPResponseError, body: Mapping) -> str | None:
    """The documented error code: the SDK's when it knows it, else the parsed body's."""
    code = getattr(error, "code", None)
    value = getattr(code, "value", code)
    if isinstance(value, str) and not value.startswith("notionhq_client_"):
        return value
    parsed = body.get("code")
    return parsed if isinstance(parsed, str) else None


def _additional(error: HTTPResponseError, body: Mapping) -> Mapping:
    data = getattr(error, "additional_data", None)
    if isinstance(data, Mapping):
        return data
    parsed = body.get("additional_data")
    return parsed if isinstance(parsed, Mapping) else {}


def _request_id(error: HTTPResponseError, body: Mapping) -> str | None:
    for value in (getattr(error, "request_id", None), body.get("request_id")):
        if isinstance(value, str) and _REQUEST_ID.fullmatch(value):
            return value
    return None


def _whole_seconds(value) -> int | None:
    if isinstance(value, str) and value.isascii() and value.isdigit():
        seconds = int(value)
        return seconds if seconds <= MAX_STATED_WAIT_SECONDS else None
    return None


def stated_wait(error: HTTPResponseError, additional: Mapping) -> int | None:
    """Notion's stated wait in whole seconds: the `Retry-After` header, else the body's
    `additional_data.retry_after` string. An HTTP-date or anything else gives None."""
    headers = getattr(error, "headers", None)
    header = headers.get("retry-after") if headers is not None else None
    seconds = _whole_seconds(header.strip() if isinstance(header, str) else None)
    if seconds is not None:
        return seconds
    return _whole_seconds(additional.get("retry_after"))


@dataclass(frozen=True)
class _Answer:
    status: int
    code: str | None
    additional: Mapping
    request_id: str | None
    retry_after: int | None


def _answer(error: HTTPResponseError) -> _Answer:
    body = _parsed_body(error)
    additional = _additional(error, body)
    status = getattr(error, "status", None)
    return _Answer(
        status=status if type(status) is int else 0,
        code=_code(error, body),
        additional=additional,
        request_id=_request_id(error, body),
        retry_after=stated_wait(error, additional),
    )


def _is_retry_signal(answer: _Answer) -> bool:
    """The two answers Notion documents as retryable for any method (BR4.2)."""
    if answer.status == 429 and answer.code == "rate_limited":
        return answer.additional.get("rate_limit_reason") != BLOCKED_REASON
    return answer.status == 529 and answer.code == "service_overload"


def _is_blocked(answer: _Answer) -> bool:
    return (
        answer.status == 429
        and answer.code == "rate_limited"
        and answer.additional.get("rate_limit_reason") == BLOCKED_REASON
    )


def _preflight(error: BaseException) -> Verdict | None:
    """Verdicts shared by reads and writes; None when the error needs the table."""
    if isinstance(error, ReducedError):
        return error.verdict
    if isinstance(error, NotConnected):
        return Verdict(NOT_CONNECTED)
    if isinstance(error, ProtectionUnavailable):
        return Verdict(PROTECTION_UNAVAILABLE)
    return None


def _write_refusal(answer: _Answer) -> str | None:
    refusals = {
        (401, "unauthorized"): REFUSAL_TOKEN_INVALID,
        (404, "object_not_found"): REFUSAL_DESTINATION_MISSING,
        (400, "validation_error"): REFUSAL_CONTENT_REJECTED,
    }
    refusal = refusals.get((answer.status, answer.code))
    if refusal is not None:
        return refusal
    if answer.status == 403 and answer.code == "restricted_resource":
        if answer.additional.get("block_limit") == BLOCK_CREATION:
            return REFUSAL_BLOCK_LIMIT
        return REFUSAL_NO_ACCESS
    if _is_blocked(answer):
        return REFUSAL_PROVIDER_BLOCKED
    return None


def classify_write(error: BaseException) -> Verdict:
    """The write table of security design §7. Any doubt is uncertain, never a retry."""
    verdict = _preflight(error)
    if verdict is not None:
        return verdict
    if isinstance(error, PaceUnavailable):
        return Verdict(UNCERTAIN, cause=CAUSE_PACE)
    if isinstance(error, TimeoutError):
        return Verdict(UNCERTAIN, cause=CAUSE_BUDGET)
    if not isinstance(error, HTTPResponseError):
        return Verdict(UNCERTAIN, cause=CAUSE_TRANSPORT)
    answer = _answer(error)
    refusal = _write_refusal(answer)
    if refusal is not None:
        return Verdict(REFUSED, refusal=refusal, request_id=answer.request_id)
    if _is_retry_signal(answer):
        return Verdict(RATE_LIMITED, retry_after=answer.retry_after, request_id=answer.request_id)
    committed = None
    if answer.status == 503 and answer.code == "service_unavailable":
        committed = normalise_id(answer.additional.get("committed_resource_id"))
    return Verdict(
        UNCERTAIN,
        request_id=answer.request_id,
        committed_page_id=committed,
        cause=CAUSE_RESPONSE,
    )


def classify_read(error: BaseException) -> Verdict:
    """The read table of security design §7: ok is not an error, so every verdict here
    is token-invalid, not-readable, retryable or could-not-check."""
    verdict = _preflight(error)
    if verdict is not None:
        return verdict
    if isinstance(error, (TimeoutError, BudgetSpent)):
        return Verdict(COULD_NOT_CHECK, cause=CAUSE_BUDGET)
    if isinstance(error, PaceUnavailable):
        return Verdict(COULD_NOT_CHECK, cause=CAUSE_PACE)
    if not isinstance(error, HTTPResponseError):
        return Verdict(COULD_NOT_CHECK, cause=CAUSE_TRANSPORT)
    answer = _answer(error)
    if answer.status == 401 and answer.code == "unauthorized":
        return Verdict(TOKEN_INVALID, request_id=answer.request_id)
    if (answer.status, answer.code) in ((403, "restricted_resource"), (404, "object_not_found")):
        return Verdict(NOT_READABLE, request_id=answer.request_id)
    if _is_retry_signal(answer):
        return Verdict(RETRYABLE, retry_after=answer.retry_after, request_id=answer.request_id)
    if _is_blocked(answer):
        return Verdict(COULD_NOT_CHECK, cause=CAUSE_PROVIDER_BLOCKED)
    return Verdict(COULD_NOT_CHECK, request_id=answer.request_id, cause=CAUSE_RESPONSE)
