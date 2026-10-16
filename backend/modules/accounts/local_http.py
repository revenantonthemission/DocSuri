"""Canonical account browser bindings for the explicit local HTTPS assembly."""

from __future__ import annotations

import hmac
from uuid import UUID

import psycopg
from backend.local_browser import (
    CONTROLS_ORIGIN,
    CORPUS_ORIGIN,
    ENTRY_COOKIE,
    JOURNEY_ORIGIN,
    RESEARCH_ORIGIN,
    SESSION_COOKIE,
    BrowserDenied,
    boundary_route,
    error_response,
    fresh_expiry,
    post_context,
    private_cookie,
    read_payload,
    require_post_headers,
)
from docsuri_shared.workspace import wire
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .preauthentication import Preauthentication
from .services.guarded_entry import GuardedEntryService

ENTRY_POLICY = {"policyId": "synthetic-local-entry", "revision": "1"}

__all__ = [
    "BrowserDenied",
    "ENTRY_COOKIE",
    "ENTRY_POLICY",
    "SESSION_COOKIE",
    "account_router",
    "error_response",
    "private_cookie",
]


def account_router(entry: GuardedEntryService) -> APIRouter:
    origin = entry.transactions.profile.origin
    if origin not in (JOURNEY_ORIGIN, CONTROLS_ORIGIN, CORPUS_ORIGIN, RESEARCH_ORIGIN):
        raise ValueError("account browser transport requires the owned HTTPS origin")
    anonymous = Preauthentication(entry)
    # Account errors keep their established 403 disposition for denied identities.
    router = APIRouter(route_class=boundary_route(origin, missing=(403, "FORBIDDEN")))

    async def payload(request, schema):
        return await read_payload(request, schema)

    async def context(request):
        return await post_context(request, origin=origin, entry=entry, anonymous=anonymous)

    def entry_flow(request):
        return anonymous.read(request.cookies.get(ENTRY_COOKIE, "")).flow

    def policy(value):
        if value.get("policyRef") != ENTRY_POLICY:
            raise BrowserDenied(503, "POLICY_UNRESOLVED")

    @router.get("/api/v2/session")
    async def bootstrap(request: Request):
        try:
            context_value = anonymous.read(request.cookies.get(ENTRY_COOKIE, ""))
        except PermissionError:
            context_value = anonymous.issue()
        token = request.cookies.get(SESSION_COOKIE)
        session = None
        if token:
            try:
                session = await run_in_threadpool(entry.inspect_session, token)
            except (PermissionError, psycopg.errors.InsufficientPrivilege):
                pass
        public = session.public.get("session") if session else None
        response = JSONResponse(
            wire.SessionBootstrap.model_validate(
                {
                    "signedIn": bool(public),
                    "accountId": public["accountId"] if public else None,
                    "authorityRevision": public["authorityRevision"] if public else None,
                    "csrfToken": session.csrf if session else context_value.csrf,
                }
            ).model_dump(mode="json")
        )
        private_cookie(
            response, ENTRY_COOKIE, context_value.cookie, fresh_expiry(context_value.expires_at)
        )
        if token and not session:
            private_cookie(response, SESSION_COOKIE, "", 0)
        return response

    @router.post("/api/v2/c02/access-inspect-session")
    async def inspect(request: Request):
        operation = require_post_headers(request, origin)
        token = request.cookies.get(SESSION_COOKIE)
        session = await run_in_threadpool(entry.inspect_session, token) if token else None
        if session:
            if not hmac.compare_digest(session.csrf, request.headers['x-csrf-token']):
                raise BrowserDenied(403, 'FORBIDDEN')
        else:
            anonymous.read(request.cookies.get(ENTRY_COOKIE, ''), csrf=request.headers['x-csrf-token'])
        await payload(request, wire.AccessSessionInputHttp)
        return wire.AccessSessionStatus.model_validate(
            session.public if session else {"state": "anonymous", "requestId": str(operation)}
        ).model_dump(mode="json", exclude_none=True)

    @router.post("/api/v2/c02/access-register")
    async def register(request: Request):
        operation, _, _ = await context(request)
        value = await payload(request, wire.AccessRegisterInputHttp)
        policy(value)
        result = await run_in_threadpool(
            entry.register,
            operation,
            value["email"],
            value["password"],
            value.get("displayName", "연구자"),
            entry_flow(request),
        )
        return wire.AccessChallengeDelivery.model_validate(result).model_dump(mode="json")

    @router.post("/api/v2/c02/access-request-verification")
    async def resend(request: Request):
        operation, _, _ = await context(request)
        value = await payload(request, wire.AccessEmailRequestInputHttp)
        policy(value)
        result = await run_in_threadpool(
            entry.request_verification, operation, value["email"], entry_flow(request)
        )
        return wire.AccessChallengeDelivery.model_validate(result).model_dump(mode="json")

    @router.post("/api/v2/c02/access-verify-email")
    async def verify(request: Request):
        operation, _, _ = await context(request)
        value = (await payload(request, wire.AccessVerifyEmailInputHttp))["verification"]
        if value["flowBinding"] != entry_flow(request):
            raise BrowserDenied(403, "FORBIDDEN")
        result = await run_in_threadpool(
            entry.verify_email,
            UUID(value["challengeId"]),
            value["proof"],
            value["flowBinding"],
            operation=operation,
        )
        return wire.Ack.model_validate(result).model_dump(mode="json")

    @router.post("/api/v2/c02/access-login")
    async def login(request: Request):
        operation, _, _ = await context(request)
        value = await payload(request, wire.AccessLoginInputHttp)
        policy(value)
        result = await run_in_threadpool(
            entry.login,
            value["email"],
            value["password"],
            operation=operation,
            flow_binding=entry_flow(request),
        )
        response = JSONResponse(
            wire.AccessLoginResult.model_validate(result.public).model_dump(
                mode="json", exclude_none=True
            )
        )
        # Keep the still-valid pre-auth flow cookie for a lost response whose
        # Set-Cookie reached the browser but whose body did not. Bootstrap gets
        # the new session CSRF; exact retry then retains the original flow.
        private_cookie(
            response,
            SESSION_COOKIE,
            result.token,
            min(3600, fresh_expiry(anonymous.expires_at)),
        )
        return response

    @router.post("/api/v2/c02/access-logout")
    async def logout(request: Request):
        operation, _, authority = await context(request)
        await payload(request, wire.AccessLogoutInputHttp)
        if authority is None:
            raise BrowserDenied(401, "UNAUTHENTICATED")
        result = await run_in_threadpool(entry.logout, authority, operation=operation)
        response = JSONResponse(wire.Ack.model_validate(result).model_dump(mode="json"))
        private_cookie(response, SESSION_COOKIE, "", 0)
        private_cookie(response, ENTRY_COOKIE, "", 0)
        return response

    return router
