"""AccountAccess's account browser routes under D1 (U8 plan Step 19; decisions of
2026-10-22 and the person's decision of 2026-10-24, "Move, scope tools, test U2").

`d1_account_router(entry)` is U2's `account_router` with these routes, matched before
the built ones:

- sign-in answers C02 4.0.0's `AccessSignInResult`, and its session cookie's `Max-Age`
  is the issued session's remaining length (a reset-required answer carries none);
- the bootstrap keeps a limited session's cookie (consent-pending or setup-only) and
  hands it its CSRF token;
- registration answers a password the password policy refuses with 422
  `INVALID_ARGUMENT` and `messageKey` `password.policy` (your answer of 2026-11-11).

It refuses an entry without a first sign-in, so it never serves U2's realm.
"""

from __future__ import annotations

import psycopg
from backend.local_browser import (
    ENTRY_COOKIE,
    SESSION_COOKIE,
    BrowserDenied,
    boundary_route,
    fresh_expiry,
    post_context,
    private_cookie,
    read_payload,
)
from docsuri_shared.workspace import wire
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .local_http import ENTRY_POLICY, account_router
from .preauthentication import Preauthentication
from .u8_control_http import _flat, answer_weak_password
from .u8_control_policy import remaining_seconds

# The production profile's infinite expiry as an entry context's ceiling: far past any
# context's 900 s, and an integer `int()` accepts.
ENTRY_CONTEXT_CEILING = 2 ** 53
REGISTER = "/api/v2/c02/access-register"


class D1AccountRoutes:
    def __init__(self, entry):
        self.entry, self.first = entry, entry.first_sign_in
        self.origin = entry.transactions.profile.origin
        self.anonymous = Preauthentication(entry)
        # The built registration handler, filled once U2's router is assembled.
        self.built: dict[str, object] = {}
        if self.anonymous.expires_at == float("inf"):
            # The production profile never expires, and U2's `issue` takes the earlier of
            # a context's 900 s and the profile's expiry through `int()`, which refuses
            # infinity: there a context is bounded by its own lifetime (Step 88(a)).
            self.anonymous.expires_at = ENTRY_CONTEXT_CEILING
        self.router = APIRouter(route_class=boundary_route(self.origin, missing=(403, "FORBIDDEN")))
        self._mount()

    def limited_bootstrap(self, token: str):
        """A consent-pending or setup-only session: its CSRF token and its cookie kept.
        A setup-only session is signed in at the primary level, as its sign-in answered;
        a consent-pending one is not signed in until its consents are recorded."""
        purpose = self.first.limited_purpose(token)
        if purpose is None:
            return None
        row = self.first.limited_session(token, None, purpose)
        signed_in = purpose == "mfa"
        return {
            "signedIn": signed_in,
            "accountId": str(row["account_id"]) if signed_in else None,
            "authorityRevision": str(row["authority_revision"]) if signed_in else None,
            "csrfToken": self.entry.verifier("session-csrf", token),
        }

    def signed_in(self, result) -> JSONResponse:
        """C02 4.0.0's `AccessSignInResult`; the cookie lasts exactly as long as the
        session it carries, and a reset-required answer carries none."""
        public = result.public
        response = JSONResponse(
            wire.AccessSignInResult.model_validate(public).model_dump(
                mode="json", exclude_none=True
            )
        )
        if public["state"] != "reset_required":
            expires = public.get("expiresAt") or public["session"]["expiresAt"]
            private_cookie(
                response, SESSION_COOKIE, result.token,
                remaining_seconds(expires, self.entry.clock()),
            )
        return response

    def _mount(self) -> None:
        router, entry, anonymous = self.router, self.entry, self.anonymous

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
            limited = None
            if token and not session:
                try:
                    limited = await run_in_threadpool(self.limited_bootstrap, token)
                except (PermissionError, psycopg.errors.InsufficientPrivilege):
                    limited = None
            public = session.public.get("session") if session else None
            response = JSONResponse(
                wire.SessionBootstrap.model_validate(
                    limited
                    or {
                        "signedIn": bool(public),
                        "accountId": public["accountId"] if public else None,
                        "authorityRevision": public["authorityRevision"] if public else None,
                        "csrfToken": session.csrf if session else context_value.csrf,
                    }
                ).model_dump(mode="json")
            )
            private_cookie(
                response, ENTRY_COOKIE, context_value.cookie,
                fresh_expiry(context_value.expires_at),
            )
            if token and not session and limited is None:
                private_cookie(response, SESSION_COOKIE, "", 0)
            return response

        @router.post("/api/v2/c02/access-login")
        async def login(request: Request):
            operation, _, _ = await post_context(
                request, origin=self.origin, entry=entry, anonymous=anonymous
            )
            value = await read_payload(request, wire.AccessLoginInputHttp)
            if value.get("policyRef") != ENTRY_POLICY:
                raise BrowserDenied(503, "POLICY_UNRESOLVED")
            result = await run_in_threadpool(
                entry.login,
                value["email"],
                value["password"],
                operation=operation,
                flow_binding=anonymous.read(request.cookies.get(ENTRY_COOKIE, "")).flow,
            )
            return self.signed_in(result)

        @router.post(REGISTER)
        async def register(request: Request):
            # The built registration; a password the policy refuses answers 422
            # `password.policy` (your answer of 2026-11-11).
            return await answer_weak_password(self.built[REGISTER], request)


def d1_account_router(entry) -> APIRouter:
    """U2's account router with D1's sign-in, bootstrap and registration refusal, for the
    two complete realms."""
    if getattr(entry, "first_sign_in", None) is None:
        raise PermissionError("the D1 routes need the complete entry")
    routes = D1AccountRoutes(entry)
    router = account_router(entry, routes=routes.router)
    own = {route.endpoint for route in routes.router.routes}
    for route in _flat(router.routes):
        if getattr(route, "path", None) == REGISTER and route.endpoint not in own:
            routes.built[REGISTER] = route.endpoint
    if REGISTER not in routes.built:
        raise RuntimeError("U2's account router lacks its registration route")
    return router
