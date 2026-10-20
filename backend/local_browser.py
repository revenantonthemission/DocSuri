"""Shared browser boundary for the explicit local HTTPS journey assembly.

Every canonical browser route uses the same Host/scheme/origin/cookie bounds,
bounded JSON bodies, server-derived principal and canonical safe error mapping.
Owner routers supply their own services; this module never resolves a caller-
supplied identity and never reads ambient settings.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import time
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import psycopg
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .modules.accounts.control_policy import PolicyUnavailable
from .transactions import Authority, Busy, UnknownCommit

SESSION_COOKIE = "session_id"
ENTRY_COOKIE = "docsuri_entry"
JOURNEY_ORIGIN = "https://127.0.0.1:18039"
JOURNEY_AUTHORITY = "127.0.0.1:18039"
CONTROLS_ORIGIN = "https://127.0.0.1:18049"
CORPUS_ORIGIN = "https://127.0.0.1:18059"
RESEARCH_ORIGIN = "https://127.0.0.1:18079"
TOPICS_ORIGIN = "https://127.0.0.1:18089"
EXPORT_ORIGIN = "https://127.0.0.1:18099"


class BrowserDenied(Exception):
    """A bounded browser precondition failed before any owner effect."""

    def __init__(self, status: int, code: str, *, retry_after: int | None = None):
        self.status, self.code, self.retry_after = status, code, retry_after


def error_response(status: int, code: str, *, retry_after: int | None = None) -> JSONResponse:
    from docsuri_shared.workspace import wire

    value = {
        "code": code,
        "requestId": str(uuid4()),
        "retryable": code in {"RATE_LIMITED", "DEPENDENCY_UNAVAILABLE"},
        "messageKey": "request." + code.lower(),
    }
    if retry_after is not None:
        value["retryAfterSeconds"] = retry_after
    response = JSONResponse(
        wire.Error.model_validate(value).model_dump(mode="json", exclude_none=True),
        status_code=status,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def private_cookie(response, name, value, lifetime) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max(0, int(lifetime)),
        path="/",
        secure=True,
        httponly=True,
        samesite="strict",
    )


def boundary_route(
    origin: str,
    *,
    authority: str | None = None,
    missing: tuple[int, str] = (404, "FORBIDDEN"),
):
    """One route class for every canonical browser adapter; identical dispositions."""
    if origin not in (
        JOURNEY_ORIGIN, CONTROLS_ORIGIN, CORPUS_ORIGIN, RESEARCH_ORIGIN, TOPICS_ORIGIN,
        EXPORT_ORIGIN,
    ):
        raise ValueError("unowned browser origin")
    expected_authority = urlsplit(origin).netloc
    if authority is not None and authority != expected_authority:
        raise ValueError("browser authority does not match owned origin")
    authority = expected_authority

    class BoundaryRoute(APIRoute):
        def get_route_handler(self):
            handler = super().get_route_handler()

            async def bounded(request: Request):
                try:
                    if (
                        request.url.scheme != "https"
                        or request.headers.get("host") != authority
                        or len(request.headers.get("cookie", "")) > 4096
                        or len(request.headers.getlist("origin")) > 1
                        or request.headers.get("origin") not in (None, origin)
                    ):
                        raise BrowserDenied(403, "FORBIDDEN")
                    result = await handler(request)
                    result.headers["Cache-Control"] = "no-store"
                    result.headers["X-Content-Type-Options"] = "nosniff"
                    return result
                except BrowserDenied as exc:
                    return error_response(exc.status, exc.code, retry_after=exc.retry_after)
                except PolicyUnavailable:
                    return error_response(503, "POLICY_UNRESOLVED")
                except (PermissionError, LookupError, psycopg.errors.InsufficientPrivilege):
                    # Foreign and nonexistent private identifiers share this disposition.
                    return error_response(*missing)
                except (
                    psycopg.errors.SerializationFailure,
                    psycopg.errors.DeadlockDetected,
                    psycopg.errors.UniqueViolation,
                    psycopg.errors.RaiseException,
                ):
                    # Owner-declared conflicts (40001 revision, 23505 changed
                    # intent, P0001 guard decision) are definite refusals.
                    return error_response(409, "CONFLICT")
                except psycopg.errors.CheckViolation:
                    return error_response(422, "INVALID_ARGUMENT")
                except (ValidationError, json.JSONDecodeError, UnicodeError):
                    return error_response(422, "INVALID_ARGUMENT")
                except UnknownCommit:
                    return error_response(409, "UNKNOWN_OUTCOME")
                except Busy:
                    return error_response(429, "RATE_LIMITED")
                except TimeoutError:
                    return error_response(504, "DEADLINE_EXCEEDED")
                except ValueError:
                    return error_response(409, "CONFLICT")
                except (psycopg.OperationalError, psycopg.InterfaceError):
                    return error_response(503, "DEPENDENCY_UNAVAILABLE")

            return bounded

    return BoundaryRoute


async def read_payload(request: Request, schema):
    """Finite JSON body; the declared contract shape is authoritative."""
    if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
        raise BrowserDenied(422, "INVALID_ARGUMENT")
    raw = bytearray()
    maximum = (
        65536
        if request.headers.get("host") in (
            "127.0.0.1:18049", "127.0.0.1:18059", "127.0.0.1:18079", "127.0.0.1:18089",
            "127.0.0.1:18099",
        )
        else 8192
    )
    async with asyncio.timeout(5):
        async for chunk in request.stream():
            if len(raw) + len(chunk) > maximum:
                raise BrowserDenied(422, "INVALID_ARGUMENT")
            raw.extend(chunk)

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise BrowserDenied(422, "INVALID_ARGUMENT")
            result[key] = value
        return result

    value = json.loads(bytes(raw), object_pairs_hook=unique_object)
    return schema.model_validate(value).model_dump(mode="json", exclude_none=True)


def require_post_headers(request: Request, origin: str) -> UUID:
    """Origin + exactly bounded CSRF transport + operation identity."""
    if request.headers.get("origin") != origin:
        raise BrowserDenied(403, "FORBIDDEN")
    csrf = request.headers.get("x-csrf-token", "")
    if len(csrf) != 64 or any(character not in "0123456789abcdef" for character in csrf):
        raise BrowserDenied(403, "FORBIDDEN")
    try:
        operation = UUID(request.headers.get("idempotency-key", ""))
    except (ValueError, AttributeError):
        raise BrowserDenied(400, "INVALID_ARGUMENT") from None
    return operation


async def post_context(request: Request, *, origin: str, entry, anonymous):
    """Server-derived principal: existing session or bound anonymous entry flow.

    ``anonymous=None`` marks a protected route: an anonymous caller is refused
    before any owner transaction rather than receiving a guest context.
    """
    operation = require_post_headers(request, origin)
    csrf = request.headers["x-csrf-token"]
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        session = await run_in_threadpool(entry.inspect_session, token)
        if not hmac.compare_digest(session.csrf, csrf):
            raise BrowserDenied(403, "FORBIDDEN")
        if "session" not in session.public:
            raise BrowserDenied(401, "UNAUTHENTICATED")
        authority = Authority(
            UUID(session.public["session"]["accountId"]),
            UUID(session.public["session"]["sessionId"]),
        )
        return operation, session, authority
    if anonymous is None:
        raise BrowserDenied(401, "UNAUTHENTICATED")
    anonymous.read(request.cookies.get(ENTRY_COOKIE, ""), csrf=csrf)
    return operation, None, None


async def optional_authority(request: Request, *, entry):
    """Guest-permitted reads: an authenticated cookie yields authority; otherwise none."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        session = await run_in_threadpool(entry.inspect_session, token)
    except (PermissionError, psycopg.errors.InsufficientPrivilege):
        return None
    if "session" not in session.public:
        return None
    return Authority(
        UUID(session.public["session"]["accountId"]),
        UUID(session.public["session"]["sessionId"]),
    )


async def require_authority(request: Request, *, entry) -> Authority:
    """Protected reads: an authenticated cookie is required; an anonymous caller
    is refused before any owner transaction (no guest context, no CSRF demand)."""
    authority = await optional_authority(request, entry=entry)
    if authority is None:
        raise BrowserDenied(401, "UNAUTHENTICATED")
    return authority


def entry_flow(request: Request, anonymous) -> str:
    return anonymous.read(request.cookies.get(ENTRY_COOKIE, "")).flow


def require_policy(value: dict, expected: dict) -> None:
    if value.get("policyRef") != expected:
        raise BrowserDenied(503, "POLICY_UNRESOLVED")


def fresh_expiry(expires_at: float) -> float:
    return min(3600, max(0.0, expires_at - time.time()))
