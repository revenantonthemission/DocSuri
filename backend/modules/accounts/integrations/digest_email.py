"""Digest-specific transport facts; existing account mail interfaces stay intact.

Only an explicitly configured free Resend binding can use the network. A local
profile never consults ambient provider credentials. Acknowledgement is not
proof of inbox delivery, and uncertain responses never authorize another POST.
"""

import datetime as dt
import html as html_module
import re
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID

import httpx

# The provider answered with a definite rejection (statuses below).
PROVIDER_REFUSAL = "delivery-path-refused"
# Refusals decided on this host before any network call: the provider never saw them.
RECIPIENT_NOT_PERMITTED = "recipient-not-permitted"
UNSUBSCRIBE_URL_INVALID = "unsubscribe-url-invalid"
LOCAL_REFUSALS = (RECIPIENT_NOT_PERMITTED, UNSUBSCRIBE_URL_INVALID)
# Explicit rejection only. 408/409/5xx can follow an accepted send and stay unknown.
REFUSED_STATUSES = (400, 401, 403, 404, 413, 422, 429)
# Resend's machine-readable error `name` (e.g. `validation_error`). Anything else,
# including an unreadable body, is replaced by the fixed placeholder: free text
# from the provider (its `message`) is never kept because it can echo the request.
PROVIDER_ERROR_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}")
PROVIDER_ERROR_UNAVAILABLE = "name-unavailable"


def _is_error_name(value) -> bool:
    return isinstance(value, str) and PROVIDER_ERROR_NAME.fullmatch(value) is not None


def valid_provider_refusal(status, name) -> bool:
    """A refusing HTTP status with a validated error name or the fixed placeholder."""
    return (
        type(status) is int
        and status in REFUSED_STATUSES
        and (name == PROVIDER_ERROR_UNAVAILABLE or _is_error_name(name))
    )


@dataclass(frozen=True)
class DigestMailResult:
    """One transport outcome. Refusal detail is bounded, non-secret and refused-only.

    `refusal_reason` names who refused (a local reason, or the provider);
    `provider_status`/`provider_error` are the provider's HTTP status and
    validated error name, present only when the provider itself refused.
    """

    state: str
    receipt: str | None = None
    acknowledged_at: dt.datetime | None = None
    refusal_reason: str | None = None
    provider_status: int | None = None
    provider_error: str | None = None

    def __post_init__(self):
        if self.state not in ("accepted", "refused", "unknown"):
            raise ValueError("unsupported transport result")
        if self.state == "accepted" and (not self.receipt or not self.acknowledged_at):
            raise ValueError("acceptance requires a receipt and time")
        detail = (self.refusal_reason, self.provider_status, self.provider_error)
        if self.state != "refused":
            if detail != (None, None, None):
                raise ValueError("refusal detail belongs only to a refusal")
            return
        if self.refusal_reason not in (None, PROVIDER_REFUSAL, *LOCAL_REFUSALS):
            raise ValueError("unsupported refusal reason")
        if self.provider_status is None:
            if self.provider_error is not None:
                raise ValueError("a provider error name requires its status")
            return
        if self.refusal_reason != PROVIDER_REFUSAL or not valid_provider_refusal(
            self.provider_status, self.provider_error
        ):
            raise ValueError("provider refusal detail is invalid")

    @property
    def failure_reason(self) -> str:
        """The recorded failure reason; a detail-free refusal is the provider path's."""
        return self.refusal_reason or PROVIDER_REFUSAL


def provider_error_name(response) -> str:
    """Resend's error `name` when it is a short identifier, else the placeholder.

    Reads nothing else from the body; never raises, so a malformed refusal body
    cannot turn a definite rejection into an unknown outcome.
    """
    try:
        value = response.json()
    except ValueError:
        return PROVIDER_ERROR_UNAVAILABLE
    name = value.get("name") if isinstance(value, dict) else None
    return name if _is_error_name(name) else PROVIDER_ERROR_UNAVAILABLE


UNSUBSCRIBE_PATH = "/api/v2/topics/email-unsubscribe/"


def digest_message(*, sender, recipient, presentation, unsubscribe_url):
    """The exact provider payload: content plus the run-bound cancellation additions.

    Pure and network-free, so an operator preview shows byte-for-byte what a
    send would submit (with the bearer token replaced before display).
    """
    link = (
        f'<p><a href="{html_module.escape(unsubscribe_url, quote=True)}">'
        "Unsubscribe / 구독 해지</a></p>"
    )
    body, closing, rest = presentation["html"].rpartition("</body>")
    # Keep the cancellation link inside the document body when one is present.
    html = body + link + closing + rest if closing else presentation["html"] + link
    return {
        "from": sender,
        "to": [recipient],
        "subject": presentation["subject"],
        "text": presentation["text"] + f"\n\nUnsubscribe: {unsubscribe_url}",
        "html": html,
        "headers": {
            "List-Unsubscribe": f"<{unsubscribe_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    }


class LocalDigestMail:
    path_kind = "local-sink"
    permitted_recipient = None  # No address restriction: nothing leaves the host.

    def permits(self, recipient):
        return True

    async def send(self, recipient, presentation, request_key, *, unsubscribe_url=None):
        return DigestMailResult("accepted", "local:" + str(request_key), dt.datetime.now(dt.UTC))


class ResendDigestMail:
    path_kind = "real"
    endpoint = "https://api.resend.com/emails"

    def __init__(
        self,
        *,
        api_key,
        sender,
        unsubscribe_url,
        permitted_recipient,
        client_factory=httpx.AsyncClient,
    ):
        parsed = urlsplit(unsubscribe_url)
        if (
            not api_key
            or not sender
            or not permitted_recipient
            or parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("explicit digest delivery configuration required")
        self._api_key = api_key
        self._sender = sender
        self._unsubscribe_origin = unsubscribe_url.rstrip("/")
        self._permitted_recipient = permitted_recipient
        self._client_factory = client_factory

    @property
    def permitted_recipient(self):
        return self._permitted_recipient

    def permits(self, recipient):
        """Only the one operator-authorized address may receive a real digest."""
        return recipient == self._permitted_recipient

    async def send(self, recipient, presentation, request_key, *, unsubscribe_url=None):
        if not self.permits(recipient):
            return DigestMailResult("refused", refusal_reason=RECIPIENT_NOT_PERMITTED)
        # The service issues this run-bound opaque capability. A configured
        # static URL alone is never sufficient to claim working cancellation.
        if not isinstance(unsubscribe_url, str) or not re.fullmatch(
            re.escape(self._unsubscribe_origin)
            + re.escape(UNSUBSCRIBE_PATH)
            + r"[A-Za-z0-9_-]{43}",
            unsubscribe_url,
        ):
            return DigestMailResult("refused", refusal_reason=UNSUBSCRIBE_URL_INVALID)
        key = str(UUID(str(request_key)))
        payload = digest_message(
            sender=self._sender,
            recipient=recipient,
            presentation=presentation,
            unsubscribe_url=unsubscribe_url,
        )
        try:
            async with self._client_factory(timeout=3.0) as client:
                response = await client.post(
                    self.endpoint,
                    headers={"Authorization": f"Bearer {self._api_key}", "Idempotency-Key": key},
                    json=payload,
                )
            if response.status_code in (200, 201):
                value = response.json()
                receipt = str(UUID(value["id"]))
                return DigestMailResult("accepted", receipt, dt.datetime.now(dt.UTC))
            # Explicit rejection only. 408/409/5xx can follow an accepted send.
            if response.status_code in REFUSED_STATUSES:
                return DigestMailResult(
                    "refused",
                    refusal_reason=PROVIDER_REFUSAL,
                    provider_status=response.status_code,
                    provider_error=provider_error_name(response),
                )
            return DigestMailResult("unknown")
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return DigestMailResult("unknown")


def digest_mail_binding(*, synthetic, provider=None, configuration=None, client_factory=None):
    """Bind the digest transport; `client_factory` replaces HTTP only in contract tests."""
    if synthetic:
        if provider not in (None, "local-sink") or configuration or client_factory is not None:
            raise ValueError("synthetic delivery must remain network-disabled")
        return LocalDigestMail()
    if provider != "resend" or not configuration:
        raise ValueError("an explicit free digest adapter is required")
    if (
        configuration.get("freePlanVerified") is not True
        or configuration.get("unsubscribeEndpointVerified") is not True
    ):
        raise ValueError("verified free plan and bounded allocation required")
    return ResendDigestMail(
        api_key=configuration.get("apiKey"),
        sender=configuration.get("sender"),
        unsubscribe_url=configuration.get("unsubscribeUrl", ""),
        permitted_recipient=configuration.get("permittedRecipient"),
        **({"client_factory": client_factory} if client_factory is not None else {}),
    )
