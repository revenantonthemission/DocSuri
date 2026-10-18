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


@dataclass(frozen=True)
class DigestMailResult:
    state: str
    receipt: str | None = None
    acknowledged_at: dt.datetime | None = None

    def __post_init__(self):
        if self.state not in ("accepted", "refused", "unknown"):
            raise ValueError("unsupported transport result")
        if self.state == "accepted" and (not self.receipt or not self.acknowledged_at):
            raise ValueError("acceptance requires a receipt and time")


class LocalDigestMail:
    path_kind = "local-sink"

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

    async def send(self, recipient, presentation, request_key, *, unsubscribe_url=None):
        if recipient != self._permitted_recipient:
            return DigestMailResult("refused")
        # The service issues this run-bound opaque capability. A configured
        # static URL alone is never sufficient to claim working cancellation.
        if not isinstance(unsubscribe_url, str) or not re.fullmatch(
            re.escape(self._unsubscribe_origin)
            + r"/api/v2/topics/email-unsubscribe/[A-Za-z0-9_-]{43}",
            unsubscribe_url,
        ):
            return DigestMailResult("refused")
        key = str(UUID(str(request_key)))
        url = unsubscribe_url
        payload = {
            "from": self._sender,
            "to": [recipient],
            "subject": presentation["subject"],
            "text": presentation["text"] + f"\n\nUnsubscribe: {url}",
            "html": presentation["html"]
            + f'<p><a href="{html_module.escape(url, quote=True)}">Unsubscribe / 구독 해지</a></p>',
            "headers": {
                "List-Unsubscribe": f"<{url}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            },
        }
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
            if response.status_code in (400, 401, 403, 404, 413, 422, 429):
                return DigestMailResult("refused")
            return DigestMailResult("unknown")
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return DigestMailResult("unknown")


def digest_mail_binding(*, synthetic, provider=None, configuration=None):
    if synthetic:
        if provider not in (None, "local-sink") or configuration:
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
    )
