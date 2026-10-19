"""Single-purpose email cancellation capabilities; no browser authority is forged.

Raw URLs are secrets: host/proxy access logging MUST omit this route, and must
not capture request bodies. The response never echoes the token or owner data.
Expiry is supplied by the approved realm/activation policy, never a new default.
"""

import datetime as dt
import hashlib
import re
import secrets
from email import policy
from email.parser import BytesParser
from urllib.parse import parse_qsl, urlsplit

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool
from starlette.responses import HTMLResponse, PlainTextResponse

from .repository import TopicsRepository

PREFIX = "/api/v2/topics/email-unsubscribe/"
TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
CANCELLATION_PATH = re.compile(re.escape(PREFIX) + r"[A-Za-z0-9_-]{43}\Z")


def approved_origin(origin, *, synthetic=False):
    """An exact HTTPS origin (loopback HTTP only for synthetic realms), or ValueError."""
    parsed = urlsplit(origin) if isinstance(origin, str) else None
    local = (
        synthetic
        and parsed is not None
        and parsed.scheme == "http"
        and parsed.hostname in ("localhost", "127.0.0.1")
    )
    if (
        parsed is None
        or not (parsed.scheme == "https" or local)
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("approved unsubscribe origin required")
    return origin.rstrip("/")


# Response headers of the cancellation page and its POST answer.
#
# `same-origin`, not `no-referrer`: under the Fetch standard's "append a request
# `Origin` header" step, a non-GET, non-CORS request (the page's own form POST)
# serializes its `Origin` as `null` when the document's policy is `no-referrer`,
# but as the document's real origin under `same-origin` when the target is
# same-origin. The form posts back to its own URL, so the browser then sends the
# approved public origin. The token-bearing URL still never leaves this origin as
# a referrer: `same-origin` sends no referrer cross-origin, and the CSP below
# loads no subresource and allows form submission only to this origin.
HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": "default-src 'none'; form-action 'self'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
}
_PAGE_HEADERS = tuple(
    (name.lower().encode("latin-1"), value.encode("latin-1")) for name, value in HEADERS.items()
)
_PAGE_HEADER_NAMES = frozenset(name for name, _ in _PAGE_HEADERS)


def _with_page_headers(headers):
    """A new header list: the cancellation page's own values replace any others."""
    kept = [(name, value) for name, value in headers if name.lower() not in _PAGE_HEADER_NAMES]
    return kept + list(_PAGE_HEADERS)


class PublicCancellationOrigin:
    """ASGI middleware for the real composition's cancellation path only.

    Installed outermost by `assemble_u5_real`. On a well-formed cancellation
    path, for GET and POST only, it:

    - drops an `Origin` header that equals the approved public origin exactly, so
      the browser confirmation from that origin passes the host boundary; any
      other origin, including `null`, still reaches (and is refused by) it;
    - restores the cancellation page's own `HEADERS` on the response. The host
      boundary writes host-wide `Referrer-Policy: no-referrer` and its CSP on
      every response; left in place, the browser's form POST would carry
      `Origin: null` and be refused (review finding R-15).

    Every other path and method passes through untouched. The single-use
    capability itself, not the origin, authorizes the effect.
    """

    def __init__(self, app, *, origin):
        self.app = app
        self.origin = approved_origin(origin).encode("ascii")

    async def __call__(self, scope, receive, send):
        if not (
            scope["type"] == "http"
            and scope.get("method") in ("GET", "POST")
            and CANCELLATION_PATH.fullmatch(scope.get("path", ""))
        ):
            await self.app(scope, receive, send)
            return
        headers = [
            (name, value)
            for name, value in scope["headers"]
            if not (name == b"origin" and value == self.origin)
        ]
        if len(headers) != len(scope["headers"]):
            scope = dict(scope, headers=headers)

        async def send_with_page_headers(message):
            if message["type"] == "http.response.start":
                message = dict(message, headers=_with_page_headers(message.get("headers", [])))
            await send(message)

        await self.app(scope, receive, send_with_page_headers)


class EmailUnsubscribe:
    def __init__(self, transactions, *, origin, expires_at, synthetic=False):
        origin = approved_origin(origin, synthetic=synthetic)
        if not isinstance(expires_at, dt.datetime) or expires_at.tzinfo is None:
            raise ValueError("explicit capability policy expiry required")
        self.transactions, self.origin, self.expires_at = transactions, origin, expires_at

    def issue(self, run_id):
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()

        def write(conn):
            row = conn.execute(
                "SELECT topic_id FROM topics.digest_run WHERE id=%s", (run_id,)
            ).fetchone()
            if not row:
                raise ValueError("unsubscribe binding unavailable")
            topic = conn.execute(
                "SELECT * FROM topics.followed_topic WHERE id=%s FOR UPDATE", (row["topic_id"],)
            ).fetchone()
            if not topic or topic["status"] != "active":
                raise ValueError("unsubscribe binding unavailable")
            result = conn.execute(
                "INSERT INTO topics.email_unsubscribe"
                "(token_hash,account_id,topic_id,run_id,expires_at) "
                "SELECT %s,%s,%s,id,%s FROM topics.digest_run WHERE id=%s AND state='sending' "
                "AND %s > clock_timestamp() RETURNING run_id",
                (
                    digest,
                    topic["account_id"],
                    topic["id"],
                    self.expires_at,
                    run_id,
                    self.expires_at,
                ),
            ).fetchone()
            if not result:
                raise ValueError("unsubscribe binding unavailable")

        self.transactions.run("topics", write)
        return self.origin + PREFIX + token

    def cancel(self, token):
        if not TOKEN.fullmatch(token):
            return
        digest = hashlib.sha256(token.encode()).hexdigest()

        def write(conn):
            binding = conn.execute(
                "SELECT topic_id FROM topics.email_unsubscribe WHERE token_hash=%s", (digest,)
            ).fetchone()
            if not binding:
                return
            topic = conn.execute(
                "SELECT * FROM topics.followed_topic WHERE id=%s FOR UPDATE", (binding["topic_id"],)
            ).fetchone()
            capability = conn.execute(
                "SELECT * FROM topics.email_unsubscribe WHERE token_hash=%s "
                "AND consumed_at IS NULL AND revoked_at IS NULL "
                "AND expires_at > clock_timestamp() FOR UPDATE",
                (digest,),
            ).fetchone()
            if not capability or not topic or topic["account_id"] != capability["account_id"]:
                return
            TopicsRepository.unsubscribe_locked(conn, topic)
            conn.execute(
                "UPDATE topics.email_unsubscribe SET consumed_at=clock_timestamp() "
                "WHERE token_hash=%s",
                (digest,),
            )

        self.transactions.run("topics", write)


def valid_form(content_type, body):
    if len(body) > 4096 or "\r" in content_type or "\n" in content_type:
        return False
    try:
        media = content_type.split(";", 1)[0].strip().lower()
        if media == "application/x-www-form-urlencoded":
            fields = parse_qsl(
                body.decode("ascii"), keep_blank_values=True, strict_parsing=True, max_num_fields=2
            )
            return fields == [("List-Unsubscribe", "One-Click")]
        if media != "multipart/form-data":
            return False
        message = BytesParser(policy=policy.default).parsebytes(
            b"Content-Type: "
            + content_type.encode("ascii")
            + b"\r\nMIME-Version: 1.0\r\n\r\n"
            + body
        )
        if not message.is_multipart() or message.defects:
            return False
        parts = list(message.iter_parts())
        if len(parts) != 1:
            return False
        part = parts[0]
        return (
            not part.defects
            and not part.is_multipart()
            and part.get_content_disposition() == "form-data"
            and part.get_param("name", header="content-disposition") == "List-Unsubscribe"
            and part.get_filename() is None
            and part.get_payload(decode=True) == b"One-Click"
        )
    except (ValueError, UnicodeError, TypeError):
        return False


def unsubscribe_router(service):
    router = APIRouter()

    @router.get(PREFIX + "{token}")
    async def confirmation(token: str):
        # Link scanners only see a generic confirmation; even valid tokens are
        # not looked up on GET. No token is echoed into HTML or redirects.
        return HTMLResponse(
            '<!doctype html><html lang="ko"><meta charset="utf-8"><title>구독 해지</title>'
            "<h1>이메일 구독 해지</h1><p>이 메일의 주제 구독을 해지하려면 확인해 주세요.</p>"
            '<form method="post"><input type="hidden" name="List-Unsubscribe" value="One-Click">'
            '<button type="submit">구독 해지 확인</button></form></html>',
            headers=HEADERS,
        )

    @router.post(PREFIX + "{token}")
    async def cancel(request: Request, token: str):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4096:
                return PlainTextResponse("잘못된 요청입니다.", status_code=400, headers=HEADERS)
        if not valid_form(request.headers.get("content-type", ""), bytes(body)):
            return PlainTextResponse("잘못된 요청입니다.", status_code=400, headers=HEADERS)
        try:
            await run_in_threadpool(service.cancel, token)
        except Exception:
            # Never propagate an exception containing SQL bindings or the URL.
            return PlainTextResponse(
                "잠시 후 다시 시도해 주세요.", status_code=503, headers=HEADERS
            )
        return PlainTextResponse("구독 해지 요청을 처리했습니다.", headers=HEADERS)

    return router
