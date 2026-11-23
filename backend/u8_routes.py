"""The complete assembly's routes (U8 plan Step 39; FR3.1, BR3.1, BR3.8, BR5.1–BR5.6, BR5.9,
A1, A2, A5, A8, security-design § 3.6, performance-design § 10).

`u8_host.host_app` mounts, through `routers`, every owner's routes in one application:

- AccountAccess's `account_router` and U2's `control_router` with the lifecycle service;
- the C01 host routes, resolving from the registry: `host-resolve-navigation` over
  `u8_registry.NAVIGATION` and each capability's derived state, and the capability list,
  `GET /api/v2/capabilities`, which answers a signed-in caller the capability catalog and
  a caller with no session only `Readiness.public_projection()` (BR5.9);
- U3's corpus and reading routes, C13's byte route for a paper's asset bytes
  (`u8_asset_bytes`, Step 127), discovery with `CompleteSearch` and citations, library,
  settings with Personalization's controls, and usage;
- assistance, U4's research routes with A2's job list, U5's topics routes, U6's export
  routes and the C11 routes;
- `/privacy` and `/terms` as script-free documents from the build, and the static shell
  for `/sign-in/callback/{provider}` and every workspace destination.

Every route has a route class, and every route is either on the public list (the health
routes, `/privacy`, `/terms`, the sign-in entry routes and the static shell), a token
route (U5's cancellation link, guarded by its own single-use capability), or behind its
owner's guard: mounted through the shared browser boundary under an owner's prefix. The
assembly check (`check_routes`) refuses a route that has no class or is none of these, and
a route whose own request would be recorded under another class: a template registered
before a later route whose request it matches, when the two classes differ. The static
catch-all takes its class last, where `assemble` mounts it (`register_classes`), so the
class recorded is the class of the route that served the request (Step 129, record 102).

A route two contributions both mount (U5's contribution carries a settings router,
which the complete assembly mounts once with Personalization's controls) is mounted
once: the first one mounted is kept (`combined`).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.convertors import (
    FloatConvertor,
    IntegerConvertor,
    PathConvertor,
    StringConvertor,
    UUIDConvertor,
)
from starlette.routing import compile_path, replace_params

from .local_browser import (
    ENTRY_COOKIE,
    BrowserDenied,
    boundary_route,
    optional_authority,
    post_context,
    read_payload,
    request_identifier,
)
from .u8_registry import NAVIGATION

PUBLIC_ROUTES = frozenset({
    ("GET", "/health/live"), ("GET", "/health/ready"),
    ("GET", "/privacy"), ("GET", "/terms"),
    ("GET", "/sign-in/callback/{provider}"), ("GET", "/{path:path}"),
    # The sign-in entry routes: no session is needed to reach them.
    ("GET", "/api/v2/session"),
    ("GET", "/api/v2/identity/callback/{provider}"),
    *(("POST", "/api/v2/c02/" + name) for name in (
        "access-inspect-session", "access-register", "access-request-verification",
        "access-verify-email", "access-login", "access-request-password-reset",
        "access-complete-password-reset", "access-complete-email-change",
        "access-verify-mfa", "access-recover-mfa", "access-begin-identity-flow",
        "access-request-reactivation", "lifecycle-reactivate",
    )),
})
TOKEN_ROUTES = frozenset({
    ("GET", "/api/v2/topics/email-unsubscribe/{token}"),
    ("POST", "/api/v2/topics/email-unsubscribe/{token}"),
})
OWNER_PREFIXES = (
    "/api/v2/c01/", "/api/v2/c02/", "/api/v2/c03/", "/api/v2/c04/", "/api/v2/c05/",
    "/api/v2/c06/", "/api/v2/c07/", "/api/v2/c09/", "/api/v2/c11/", "/api/v2/topics",
    "/api/v2/jobs/", "/api/v2/capabilities", "/api/v2/identity/", "/api/v2/session",
    "/api/v2/papers/",
)
ACCEPT_WORDS = (
    "accept-", "request", "save-", "update", "create-", "replace-", "remove-", "delete-",
    "change-", "grant-", "revoke-", "begin-", "confirm-", "complete-", "reset", "unlink",
    "clear-", "retry-", "cancel-", "prepare-", "logout", "login", "register", "verify",
    "recover", "reactivate", "finish-", "discard-", "approve-", "configure-", "disconnect-",
    "execute-", "settle-",
)
ADMINISTRATION = ("/api/v2/c11/", "/api/v2/c03/usage-list-records",
                  "/api/v2/c03/usage-read-assignment", "/api/v2/c03/usage-grant-entitlement",
                  "/api/v2/c03/usage-revoke-entitlement")
PROVIDERS = ("google", "orcid")
NAVIGATION_LOG = logging.getLogger("docsuri.navigation")
RESOLVER = "u8_routes.navigation_items"
STATE_REASONS = {"unavailable": "nav.capabilityUnavailable", "stale": "nav.capabilityStale",
                 "unknown": "nav.capabilityUnknown"}
CATALOG_STATES = {"available": "available", "degraded": "degraded"}
# `sample_path`'s sample for each of Starlette's five built convertors.
SAMPLES = ((IntegerConvertor, 1), (FloatConvertor, 1.5), (UUIDConvertor, UUID(int=1)),
           (StringConvertor, "sample"), (PathConvertor, "sample"))


# --- route classes and access ---------------------------------------------------------


def route_class(method: str, path: str) -> str:
    """performance-design § 10's class of one route template."""
    if path.startswith("/health/"):
        return "health"
    if path in ("/privacy", "/terms", "/{path:path}", "/sign-in/callback/{provider}"):
        return "static"
    if path.endswith("/events"):
        return "stream"
    if path.startswith(ADMINISTRATION):
        return "administration"
    if path in ("/api/v2/capabilities",) or path.startswith("/api/v2/c01/"):
        return "navigation"
    if path == "/api/v2/c05/search":
        return "search"
    if path == "/api/v2/c04/read-asset" or path.startswith("/api/v2/papers/"):
        return "asset"
    name = path.rsplit("/", 1)[-1]
    if method in ("PUT", "PATCH", "DELETE"):
        return "accept"
    if method == "POST" and any(word in name for word in ACCEPT_WORDS):
        return "accept"
    if method == "POST" and path.startswith("/api/v2/topics"):
        return "accept"
    return "read"


def access_of(route, method: str) -> str | None:
    """`public`, `token`, `guarded`, or None for a route that is none of them."""
    if (method, route.path) in PUBLIC_ROUTES:
        return "public"
    if (method, route.path) in TOKEN_ROUTES:
        return "token"
    if type(route).__name__ == "BoundaryRoute" and route.path.startswith(OWNER_PREFIXES):
        return "guarded"
    return None


def flat_routes(routes) -> list:
    """The concrete routes behind `routes`: FastAPI keeps an included router as one entry
    (`original_router`), so each is opened in turn. Every owner router names its full
    paths, so an included router with a prefix is refused rather than guessed at."""
    found = []
    for route in routes:
        inner = getattr(route, "original_router", None)
        if inner is None:
            found.append(route)
            continue
        if getattr(route.include_context, "prefix", "") not in ("", None):
            raise ValueError("an included router with a prefix is not part of the inventory")
        found += flat_routes(inner.routes)
    return found


def sample_path(template: str) -> str:
    """A request path for `template`: each parameter takes a sample by its convertor,
    filled through Starlette's own `replace_params`. A convertor outside the five built
    ones has no sample and stops the assembly, as a route without a class does."""
    _, path_format, convertors = compile_path(template)
    params = {}
    for name, convertor in convertors.items():
        sample = next((value for kind, value in SAMPLES if type(convertor) is kind), None)
        if sample is None:
            raise ValueError(f"route parameter without a sample: {template}")
        params[name] = sample
    path, _ = replace_params(path_format, convertors, params)
    return path


def check_routes(routes, classes) -> dict[tuple[str, str], tuple[str, str]]:
    """The assembly check: every route has a class and an access, and a request to the
    route is recorded under that class; returns the inventory
    `(method, path) -> (class, access)`. The agreement check refuses a template
    registered before a later route whose own request it matches, only when the two
    routes' classes differ: two overlapping routes of one class pass, since the request
    is then recorded under the right class anyway (Step 129, record 102)."""
    inventory = {}
    for route in flat_routes(routes):
        for method in sorted(getattr(route, "methods", None) or ()):
            if method == "HEAD":
                continue
            found = classes.template_class(method, route.path)
            if found is None:
                raise ValueError(f"route without a route class: {method} {route.path}")
            recorded = classes.classify(method, sample_path(route.path))
            if recorded != found:
                raise ValueError(f"route recorded under another class: {method} {route.path}")
            access = access_of(route, method)
            if access is None:
                raise ValueError(f"route neither public nor guarded: {method} {route.path}")
            inventory[(method, route.path)] = (found, access)
    return inventory


def register_classes(classes, routes) -> None:
    for route in flat_routes(routes):
        methods = tuple(sorted(m for m in (getattr(route, "methods", None) or ()) if m != "HEAD"))
        for method in methods:
            if classes.template_class(method, route.path) is None:
                classes.register(route.path, route_class(method, route.path), methods=(method,))


def combined(routers) -> APIRouter:
    """One router holding each route once: the first router that mounts a method and
    path keeps it."""
    result, seen = APIRouter(), set()
    for router in routers:
        for route in flat_routes(router.routes):
            keys = {(method, route.path) for method in (getattr(route, "methods", None) or ())}
            if keys & seen:
                continue
            seen |= keys
            result.routes.append(route)
    return result


# --- C01: navigation and the capability list ---------------------------------------------


def navigation_items(states: dict, *, signed_in: bool, administrator: bool) -> list[dict]:
    """BR5.2 from the registry: each entry's availability and reason key, in placement
    order; the footer's legal entries are always available (A1)."""
    items = []
    for entry in sorted(NAVIGATION, key=lambda value: value.order):
        reason = None
        if entry.placement == "footer":
            available = True
        elif entry.access == "administrator" and not administrator:
            available, reason = False, "nav.administratorOnly"
        else:
            state = states.get(entry.capability_id)
            value = state.state if state is not None else "unknown"
            if value in ("available", "degraded"):
                if entry.access != "anonymous" and not signed_in:
                    available, reason = False, "nav.authenticationRequired"
                else:
                    available = True
                    reason = "nav.capabilityDegraded" if value == "degraded" else None
            else:
                available, reason = False, STATE_REASONS.get(value, "nav.capabilityUnknown")
        item = {"routeId": entry.route_id, "titleKey": entry.title_key, "path": entry.path,
                "capabilityId": entry.capability_id, "available": available,
                "placement": entry.placement}
        if reason is not None:
            item["reasonKey"] = reason
        items.append(item)
    return items


def resolve_items(states: dict, *, signed_in: bool, administrator: bool) -> list[dict]:
    """The route's resolution: `navigation_items`, then one log line keyed by the current
    request's identifier, naming where the decision was made and what it held back, so a
    failing request is followed through the logs to the resolver (the repair exercise,
    BR10.3)."""
    items = navigation_items(states, signed_in=signed_in, administrator=administrator)
    NAVIGATION_LOG.info("navigation.resolved", extra={
        "requestId": request_identifier(), "event": "navigation.resolved",
        "location": RESOLVER,
        "unavailable": sorted(item["routeId"] for item in items if not item["available"])})
    return items


def is_administrator(transactions, authority) -> bool:
    """An administrator whose second factor is current (the administration guard)."""
    from .modules.operations.http import administrator_check

    try:
        administrator_check(transactions, authority)
    except BrowserDenied:
        return False
    return True


def navigation_router(transactions, *, entry, anonymous, states, revision: str) -> APIRouter:
    from docsuri_shared.workspace import wire

    origin = transactions.profile.origin
    router = APIRouter(route_class=boundary_route(origin))

    @router.post("/api/v2/c01/host-resolve-navigation")
    async def resolve_navigation(request: Request):
        _, session, authority = await post_context(request, origin=origin, entry=entry,
                                                   anonymous=anonymous)
        value = await read_payload(request, wire.HostNavigationInputHttp)
        current = await run_in_threadpool(states)
        administrator = authority is not None and await run_in_threadpool(
            is_administrator, transactions, authority)
        items = resolve_items(current, signed_in=session is not None,
                              administrator=administrator)
        if value["routeId"] not in {item["routeId"] for item in items}:
            raise BrowserDenied(404, "NOT_FOUND")
        if session is not None:
            authority_revision = session.public["session"]["authorityRevision"]
        else:
            authority_revision = hashlib.sha256(
                anonymous.read(request.cookies.get(ENTRY_COOKIE, "")).flow.encode()
            ).hexdigest()
        return wire.HostNavigationResult.model_validate({
            "manifestRevision": revision,
            "authorityRevision": authority_revision,
            "items": items,
            "resolvedRouteId": value["routeId"],
            "returnContext": value.get("returnContext"),
            "clearPriorOwnerState": authority is None,
        }).model_dump(mode="json", exclude_none=True)

    return router


def catalog_rows(rows: list[dict], states: dict) -> list[dict]:
    """The contributions' capability rows, each with its derived state where the registry
    observes it: available or degraded as derived, anything else unavailable; a row
    pending a policy stays pending."""
    result = []
    for row in rows:
        state = states.get(row["id"])
        if state is not None and row["state"] != "policy_pending":
            row = {**row, "state": CATALOG_STATES.get(state.state, "unavailable")}
        result.append(row)
    return result


MAINTAINER_ONLY = "admission-maintainer-only"


def with_admission(page: dict, admission) -> dict:
    """While admission is maintainer-only (security-design § 3.5), `account.entry` reads
    degraded with that reason, so the workspace shows the maintenance notice with its
    administrator sign-in link (BR6.4). Nothing else of the page changes."""
    if getattr(admission, "state", None) != "maintainer-only":
        return page
    items = [
        {**item, "state": "degraded", "reasonKey": MAINTAINER_ONLY}
        if item["capabilityId"] == "account.entry" else item
        for item in page["items"]
    ]
    return {**page, "items": items}


def capability_router(transactions, *, entry, readiness, rows: list[dict]) -> APIRouter:
    from docsuri_shared.workspace import wire

    origin = transactions.profile.origin
    router = APIRouter(route_class=boundary_route(origin))

    @router.get("/api/v2/capabilities")
    async def capabilities(request: Request):
        authority = await optional_authority(request, entry=entry)
        states = await run_in_threadpool(readiness().states)
        if authority is None:
            page = with_admission(readiness().public_projection(states),
                                  getattr(entry, "admission", None))
            return wire.HostPublicCapabilityPage.model_validate(page).model_dump(mode="json")
        current = catalog_rows(rows, states)
        revision = hashlib.sha256(json.dumps(current, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
        return wire.CapabilityCatalog.model_validate(
            {"revision": revision, "capabilities": current}
        ).model_dump(mode="json", exclude_none=True)

    return router


def public_capability_router(transactions, *, readiness) -> APIRouter:
    """The capabilities' public projection only, with no session read: production
    without account-controls (your decision of 2026-10-24, BR6.4) mounts no entry, so
    every caller is answered as a signed-out one."""
    from docsuri_shared.workspace import wire

    origin = transactions.profile.origin
    router = APIRouter(route_class=boundary_route(origin))

    @router.get("/api/v2/capabilities")
    async def capabilities(request: Request):
        states = await run_in_threadpool(readiness().states)
        page = readiness().public_projection(states)
        return wire.HostPublicCapabilityPage.model_validate(page).model_dump(mode="json")

    return router


# --- static documents ---------------------------------------------------------------------


def static_router(build: Path) -> APIRouter:
    """`/privacy` and `/terms` from the release's build, `no-store`, and the static shell
    for the identity arrival page (A8, BR5.6, D3)."""
    router = APIRouter()

    def missing() -> JSONResponse:
        return JSONResponse({"code": "NOT_READY", "messageKey": "build.missing",
                             "requestId": request_identifier("assembly"), "retryable": False},
                            status_code=503)

    def document(name: str):
        path = build / name
        if not path.is_file() or path.is_symlink():
            return missing()
        return FileResponse(path, media_type="text/html; charset=utf-8",
                            headers={"Cache-Control": "no-store"})

    @router.get("/privacy")
    async def privacy():
        return document("privacy.html")

    @router.get("/terms")
    async def terms():
        return document("terms.html")

    @router.get("/sign-in/callback/{provider}")
    async def identity_arrival(provider: str):
        if provider not in PROVIDERS:
            return JSONResponse({"code": "NOT_FOUND", "messageKey": "resource.notFound",
                                 "requestId": request_identifier("assembly"),
                                 "retryable": False}, status_code=404)
        return document("index.html")

    return router


# --- C13's job registry -------------------------------------------------------------------

JOB_POLL_SECONDS, JOB_STREAM_SECONDS = 1.0, 30.0


def _route(routes, method: str, path: str):
    for route in flat_routes(routes):
        if route.path == path and method in (getattr(route, "methods", None) or ()):
            return route
    return None


def job_registry_router(transactions, *, entry, research, assistance) -> APIRouter:
    """`GET /api/v2/jobs/{jobId}` and its events, resolved by the registry (C13: "registry
    resolves the actual operation owner"): a research or novelty job is answered from
    ResearchWorkspace's own snapshot, owner-scoped; any other identifier goes to
    PaperAssistance's own route, unchanged. Reading never starts, repeats or cancels
    work; another owner's job answers exactly as a missing one."""
    import asyncio
    import time
    from uuid import UUID

    from docsuri_shared.workspace import wire
    from fastapi.responses import StreamingResponse
    from psycopg.errors import InsufficientPrivilege

    from .modules.summarization.local_http import TERMINAL, _frame

    origin = transactions.profile.origin
    router = APIRouter(route_class=boundary_route(origin, missing=(404, "NOT_FOUND")))
    snapshot_route = _route(assistance.routes, "GET", "/api/v2/jobs/{job_id}")
    events_route = _route(assistance.routes, "GET", "/api/v2/jobs/{job_id}/events")

    async def caller(request: Request, job_id: str):
        authority = await optional_authority(request, entry=entry)
        if authority is None:
            raise BrowserDenied(401, "UNAUTHENTICATED")
        try:
            return authority, UUID(job_id)
        except ValueError:
            raise BrowserDenied(422, "INVALID_ARGUMENT") from None

    def research_snapshot(authority, identifier) -> dict | None:
        # The owner's current authority is checked on every read: a session revoked or a
        # research consent withdrawn since the job began is refused, never a 500.
        try:
            row = research.repository.run(authority, lambda conn: conn.execute(
                "SELECT * FROM research.job WHERE id=%s AND owner_id=%s",
                (identifier, authority.account_id)).fetchone())
        except (InsufficientPrivilege, PermissionError):
            raise BrowserDenied(403, "FORBIDDEN") from None
        if row is None:
            return None
        return wire.JobSnapshot.model_validate(research.snapshot(authority, row)).model_dump(
            mode="json")

    @router.get("/api/v2/jobs/{job_id}")
    async def job_snapshot(request: Request, job_id: str):
        authority, identifier = await caller(request, job_id)
        value = await run_in_threadpool(research_snapshot, authority, identifier)
        if value is None:
            return await snapshot_route.endpoint(request, job_id)
        return value

    @router.get("/api/v2/jobs/{job_id}/events")
    async def job_events(request: Request, job_id: str):
        authority, identifier = await caller(request, job_id)
        first = await run_in_threadpool(research_snapshot, authority, identifier)
        if first is None:
            return await events_route.endpoint(request, job_id)
        header = request.headers.get("last-event-id", "")
        cursor = int(header) if header.isdigit() else -1

        async def frames():
            last, value = cursor, first
            deadline = time.monotonic() + JOB_STREAM_SECONDS
            while time.monotonic() < deadline:
                if value is None:
                    yield _frame(None, "error", {"code": "NOT_FOUND", "retryable": False,
                                                 "requestId": str(identifier),
                                                 "messageKey": "job.notFound"})
                    return
                if value["seq"] > last:
                    last = value["seq"]
                    yield _frame(last, "snapshot", value)
                if value["state"] in TERMINAL or await request.is_disconnected():
                    return
                await asyncio.sleep(JOB_POLL_SECONDS)
                try:
                    value = await run_in_threadpool(research_snapshot, authority, identifier)
                except BrowserDenied:
                    # The authority ended while the stream was open: one closing frame.
                    yield _frame(None, "error", {"code": "FORBIDDEN", "retryable": False,
                                                 "requestId": str(identifier),
                                                 "messageKey": "job.authorityEnded"})
                    return

        return StreamingResponse(frames(), media_type="text/event-stream")

    return router


def job_list_key(cursor_key: bytes) -> bytes:
    """The job list's own cursor key, derived from the profile's cursor key."""
    return hmac.digest(cursor_key, b"docsuri-u8-job-list-v1", "sha256")


# --- shutdown (R7) ------------------------------------------------------------------------

RETRY_MILLISECONDS = 2000


class StreamDrain:
    """Event streams close with a retry hint when the host begins to drain (R7): an open
    stream gets a final `retry:` frame and ends, so the browser reconnects after the
    restart from its last event id; a new stream asked for while draining is answered
    503 with `Retry-After`. Every other request passes through unchanged."""

    def __init__(self, app, *, draining):
        self.app, self.draining = app, draining

    async def __call__(self, scope, receive, send):
        import asyncio
        import contextlib

        if scope["type"] != "http" or not scope["path"].endswith("/events"):
            return await self.app(scope, receive, send)
        if self.draining.is_set():
            return await self._refuse(send)
        state = {"started": False, "finished": False}

        async def tracked(message):
            if state["finished"]:
                return
            if message["type"] == "http.response.start":
                state["started"] = True
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body"):
                state["finished"] = True

        inner = asyncio.create_task(self.app(scope, receive, tracked))
        waiting = asyncio.create_task(self.draining.wait())
        done, _ = await asyncio.wait({inner, waiting}, return_when=asyncio.FIRST_COMPLETED)
        if inner in done:
            waiting.cancel()
            return inner.result()
        inner.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await inner
        if not state["started"]:
            return await self._refuse(send)
        if not state["finished"]:
            await send({"type": "http.response.body",
                        "body": f"retry: {RETRY_MILLISECONDS}\n\n".encode(), "more_body": False})
        return None

    @staticmethod
    async def _refuse(send) -> None:
        body = json.dumps({"code": "NOT_READY", "messageKey": "capability.notReady",
                           "requestId": request_identifier("drain"), "retryable": True}).encode()
        await send({"type": "http.response.start", "status": 503, "headers": [
            (b"content-type", b"application/json"), (b"cache-control", b"no-store"),
            (b"retry-after", b"2"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
