"""Same-origin host for the explicit synthetic composition, with truthful readiness.

C01 requests the installed route manifest and validates the caller's access rule;
navigation never submits work and returns only permitted destinations. Readiness
derives from recorded owner store observations: a missing or stale observation
never passes.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import local_observation
from .local_browser import (
    ENTRY_COOKIE,
    JOURNEY_ORIGIN,
    BrowserDenied,
    boundary_route,
    post_context,
    read_payload,
)
from .local_profile import LocalProfile, private_bytes
from .transactions import OWNERS

SEARCH_POLICY = {"policyId": "synthetic-paper-search", "revision": "1"}
READING_POLICY = {"policyId": "local-research", "revision": "1"}
LIBRARY_POLICY = {"policyId": "synthetic-local-library", "revision": "1"}
SETTINGS_POLICY = {"policyId": "synthetic-personal-settings", "revision": "1"}
USAGE_POLICY = {"policyId": "synthetic-four-no-reset", "revision": "1"}
ENTRY_POLICY = {"policyId": "synthetic-local-entry", "revision": "1"}

# Finite installed route manifest. One entry per mounted browser surface; the
# page routes are served by the same static workspace build.
NAVIGATION = (
    {
        "routeId": "search",
        "titleKey": "nav.search",
        "path": "/search",
        "capabilityId": "discovery.search",
        "ownerBound": False,
    },
    {
        "routeId": "paper",
        "titleKey": "nav.paper",
        "path": "/paper",
        "capabilityId": "corpus.reading",
        "ownerBound": False,
    },
    {
        "routeId": "library",
        "titleKey": "nav.library",
        "path": "/library",
        "capabilityId": "library.saved-work",
        "ownerBound": True,
    },
    {
        "routeId": "settings",
        "titleKey": "nav.settings",
        "path": "/settings",
        "capabilityId": "personalization.settings",
        "ownerBound": True,
    },
    {
        "routeId": "usage",
        "titleKey": "nav.usage",
        "path": "/usage",
        "capabilityId": "usage.wallet",
        "ownerBound": True,
    },
    {
        "routeId": "jobs",
        "titleKey": "nav.jobs",
        "path": "/jobs",
        "capabilityId": "assistance.summary",
        "ownerBound": True,
    },
    {
        "routeId": "account",
        "titleKey": "nav.account",
        "path": "/account",
        "capabilityId": "account.entry",
        "ownerBound": False,
    },
)


def catalog_revision(catalog) -> str:
    return hashlib.sha256(
        json.dumps(catalog, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def navigation_items(catalog, *, authenticated: bool) -> list[dict]:
    """Only permitted destinations: pending capabilities and owner-bound routes
    stay visible but unavailable to an anonymous caller."""
    states = {item["id"]: item["state"] for item in catalog}
    items = []
    for entry in NAVIGATION:
        available = states.get(entry["capabilityId"]) == "available"
        reason = None
        if not available:
            reason = "nav.capabilityPending"
        elif entry["ownerBound"] and not authenticated:
            available = False
            reason = "nav.authenticationRequired"
        items.append(
            {
                "routeId": entry["routeId"],
                "titleKey": entry["titleKey"],
                "path": entry["path"],
                "capabilityId": entry["capabilityId"],
                "available": available,
                "reasonKey": reason,
            }
        )
    return items


def host_router(transactions, *, entry, anonymous, catalog) -> APIRouter:
    """C01: return the permitted navigation manifest for the current principal."""
    from docsuri_shared.workspace import wire

    origin = transactions.profile.origin
    router = APIRouter(route_class=boundary_route(origin))

    @router.post("/api/v2/c01/host-resolve-navigation")
    async def resolve_navigation(request: Request):
        operation, session, authority = await post_context(
            request, origin=origin, entry=entry, anonymous=anonymous
        )
        value = await read_payload(request, wire.HostNavigationInputHttp)
        requested = value["routeId"]
        if requested not in {item["routeId"] for item in NAVIGATION}:
            raise BrowserDenied(404, "NOT_FOUND")
        if session is not None:
            revision = session.public["session"]["authorityRevision"]
        else:
            # The anonymous bootstrap flow is the caller's current authority
            # revision; a new flow mints a new revision and prior state clears.
            revision = hashlib.sha256(
                anonymous.read(request.cookies.get(ENTRY_COOKIE, "")).flow.encode()
            ).hexdigest()
        return wire.HostNavigationResult.model_validate(
            {
                "manifestRevision": catalog_revision(catalog),
                "authorityRevision": revision,
                "items": navigation_items(catalog, authenticated=session is not None),
                "resolvedRouteId": requested,
                "returnContext": value.get("returnContext"),
                # A caller with no current session cannot reuse a prior
                # authenticated owner's private rendering state.
                "clearPriorOwnerState": authority is None,
            }
        ).model_dump(mode="json", exclude_none=True)

    return router


def assistance_readiness(profile: LocalProfile) -> bool:
    """True only when an owned marker records reviewed real model evidence."""
    try:
        value = json.loads(private_bytes(profile.root / "assistance-readiness.json"))
    except (OSError, ValueError):
        return False
    return (
        isinstance(value, dict)
        and value.get("runId") == profile.run_id
        and value.get("state") == "ready"
        and isinstance(value.get("evidenceSha256"), str)
        and len(value["evidenceSha256"]) == 64
    )


def journey_capabilities(quality_ready: bool) -> list[dict]:
    """Public safe retained-choice vocabulary; no private operational evidence."""
    return [
        {
            "id": "discovery.search",
            "state": "available",
            "modeIds": ["lexical"],
            "languageIds": ["en", "ko"],
            "levelIds": ["list"],
            "formatIds": ["json"],
            "policy": SEARCH_POLICY,
        },
        {
            "id": "corpus.reading",
            "state": "available",
            "modeIds": ["section"],
            "languageIds": ["en"],
            "levelIds": ["full"],
            "formatIds": ["json"],
            "policy": READING_POLICY,
        },
        {
            "id": "library.saved-work",
            "state": "available",
            "modeIds": ["paper", "query"],
            "languageIds": ["en"],
            "levelIds": ["reference"],
            "formatIds": ["json"],
            "policy": LIBRARY_POLICY,
        },
        {
            "id": "personalization.settings",
            "state": "available",
            "modeIds": ["defaults", "appearance"],
            "languageIds": ["en"],
            "levelIds": ["owner"],
            "formatIds": ["json"],
            "policy": SETTINGS_POLICY,
        },
        {
            "id": "usage.wallet",
            "state": "available",
            "modeIds": ["synthetic-four-no-reset"],
            "languageIds": ["en"],
            "levelIds": ["owner"],
            "formatIds": ["json"],
            "policy": USAGE_POLICY,
        },
        {
            "id": "assistance.summary",
            "state": "available" if quality_ready else "policy_pending",
            "modeIds": ["key-sections"] if quality_ready else [],
            "languageIds": ["en"],
            "levelIds": ["selected-source"],
            "formatIds": ["json"],
            "policy": {"policyId": "local-research", "revision": "1"},
        },
        {
            "id": "assistance.translation",
            "state": "available" if quality_ready else "policy_pending",
            "modeIds": ["key-sections"] if quality_ready else [],
            "languageIds": ["en", "ko"],
            "levelIds": ["selected-source"],
            "formatIds": ["json"],
            "policy": {"policyId": "local-research", "revision": "1"},
        },
        {
            "id": "account.entry",
            "state": "available",
            "modeIds": ["email-verification"],
            "languageIds": ["ko"],
            "levelIds": ["primary"],
            "formatIds": ["cookie"],
            "policy": ENTRY_POLICY,
        },
    ]


def assemble(profile: LocalProfile, *, routers=(), lifespan=None) -> FastAPI:
    app = FastAPI(
        title="DocSuri local research workspace",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.profile = profile
    app.state.capabilities = {}
    app.state.capability_catalog = []
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1"])

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        if request.headers.get("origin") not in (None, profile.origin):
            return JSONResponse(
                {
                    "code": "FORBIDDEN",
                    "messageKey": "request.origin",
                    "requestId": "boundary",
                    "retryable": False,
                },
                status_code=403,
            )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'"
        )
        return response

    @app.get("/health/live")
    async def live():
        return {"process": "alive", "profile": "synthetic-local"}

    @app.get("/health/ready")
    async def ready():
        required = getattr(app.state, "required_capabilities", None)
        transactions = getattr(app.state, "transactions", None)
        if required is None or transactions is None:
            return JSONResponse({"ready": False, "missing": ["assembly"]}, status_code=503)
        report = await run_in_threadpool(local_observation.readiness, transactions, required)
        return JSONResponse(report, status_code=200 if report["ready"] else 503)

    @app.get("/api/v2/capabilities")
    async def capability_catalog():
        from docsuri_shared.workspace import wire

        catalog = app.state.capability_catalog
        return wire.CapabilityCatalog.model_validate(
            {"revision": catalog_revision(catalog), "capabilities": catalog}
        ).model_dump(mode="json", exclude_none=True)

    for router in routers:
        app.include_router(router)

    build = Path(__file__).resolve().parents[1] / "frontend/dist"

    @app.get("/{path:path}")
    async def static_workspace(path: str):
        if path.startswith(("api/", "health/")):
            return JSONResponse(
                {
                    "code": "NOT_READY",
                    "messageKey": "capability.notReady",
                    "requestId": "assembly",
                    "retryable": False,
                },
                status_code=503,
            )
        target = (build / path).resolve()
        if not target.is_relative_to(build.resolve()):
            return JSONResponse(
                {
                    "code": "NOT_FOUND",
                    "messageKey": "resource.notFound",
                    "requestId": "assembly",
                    "retryable": False,
                },
                status_code=404,
            )
        if target.is_file():
            return FileResponse(target)
        index = build / "index.html"
        if not index.is_file():
            return JSONResponse(
                {
                    "code": "NOT_READY",
                    "messageKey": "build.missing",
                    "requestId": "assembly",
                    "retryable": False,
                },
                status_code=503,
            )
        return FileResponse(index)

    return app


def from_environment() -> FastAPI:
    from .app import create_app

    manifest = os.environ.get("DOCSURI_U1_ENVIRONMENT_FILE")
    if not manifest:
        raise ValueError("DOCSURI_U1_ENVIRONMENT_FILE is required; no production fallback")
    return create_app(local_environment=Path(manifest))


def assemble_journey(profile: LocalProfile) -> FastAPI:
    """Explicit owned composition; no ambient settings or startup migrations."""
    from .artifacts import PrivateArtifacts
    from .modules.accounts.local_http import account_router
    from .modules.accounts.preauthentication import Preauthentication
    from .modules.accounts.services.guarded_entry import GuardedEntryService
    from .modules.corpus.local_http import corpus_router
    from .modules.corpus.repository import CorpusRepository
    from .modules.discovery.local_http import discovery_router
    from .modules.library.local_http import library_router
    from .modules.personalization.local_http import settings_router
    from .modules.plans.local_http import usage_router
    from .modules.summarization.local_http import assistance_router
    from .transactions import OwnerTransactions

    controls = profile.realm == "account-controls" and profile.origin == "https://127.0.0.1:18049"
    if not controls and (profile.realm != "journey" or profile.origin != JOURNEY_ORIGIN):
        raise ValueError("journey assembly requires the owned HTTPS realm")
    transactions = OwnerTransactions(profile)
    try:
        if controls:
            from .modules.accounts.control_policy import SYNTHETIC_POLICY
            from .modules.accounts.services.control_entry import ControlEntryService

            entry = ControlEntryService(transactions, SYNTHETIC_POLICY)
        else:
            entry = GuardedEntryService(transactions)
        anonymous = Preauthentication(entry)
        corpus_repository = CorpusRepository(
            transactions,
            PrivateArtifacts(profile.root / "corpus-files", maximum_bytes=2097152),
        )
        assistance_files = PrivateArtifacts(profile.root / "assistance-files")
        quality_ready = assistance_readiness(profile)
        catalog = journey_capabilities(quality_ready)
        if controls:
            for capability in catalog:
                if capability['id'] == 'usage.wallet':
                    capability['policy'] = SYNTHETIC_POLICY.reference
                    capability['modeIds'] = ['finite-synthetic-period']
            for name, modes in (
                ('account.controls',['profile','consent','credentials','mfa','lifecycle']),
                ('account.identity-fixtures',['google','orcid']),
                ('personalization.reset',['delete_behavior','reset_profile']),
                ('usage.administration',['synthetic-free']),
            ):
                catalog.append({'id':name,'state':'available','modeIds':modes,'languageIds':['ko'],
                    'levelIds':['synthetic-only'],'formatIds':['json'],'policy':SYNTHETIC_POLICY.reference})
            catalog.append({'id':'account.public-activation','state':'policy_pending','modeIds':[],
                'languageIds':['ko'],'levelIds':['G1-G8-evidence-required'],'formatIds':['json'],
                'policy':SYNTHETIC_POLICY.reference})
        personalization = None
        library_activity = corpus_activity = None
        if controls:
            from .modules.accounts.control_cursor import ControlCursor
            from .modules.personalization.control_service import PersonalizationControlService, ProducerBinding
            from .modules.personalization.activity import ActivityRelay
            library_producer, corpus_producer = ProducerBinding("Library"), ProducerBinding("CorpusContent")
            personalization = PersonalizationControlService(transactions, SYNTHETIC_POLICY,
                ControlCursor(bytes.fromhex(entry.verifier("cursor", "u2-controls-v1"))),
                producers=(library_producer, corpus_producer))
            library_activity = ActivityRelay(personalization, library_producer)
            corpus_activity = ActivityRelay(personalization, corpus_producer)
        routers = (
            account_router(entry),
            host_router(transactions, entry=entry, anonymous=anonymous, catalog=catalog),
            corpus_router(transactions, entry=entry, activity=corpus_activity),
            discovery_router(transactions, entry=entry, anonymous=anonymous),
            library_router(transactions, entry=entry, activity=library_activity),
            settings_router(transactions, entry=entry, controls=personalization),
            usage_router(transactions, entry=entry),
            assistance_router(
                transactions,
                entry=entry,
                files=assistance_files,
                quality_ready=quality_ready,
                corpus_repository=corpus_repository,
            ),
        )
        lifecycle = None
        if controls:
            from .modules.accounts.control_http import control_router
            from .modules.accounts.services.control_lifecycle import ControlLifecycleService

            manifest = (
                ("AccountAccess", "live_records"),
                ("AccountAccess", "derived_artifacts"),
                ("Library", "live_records"),
                ("Personalization", "live_records"),
                ("Personalization", "derived_artifacts"),
                ("Personalization", "pending_work"),
                ("UsageEntitlements", "live_records"),
                ("PaperAssistance", "live_records"),
                ("PaperAssistance", "derived_artifacts"),
                ("PaperAssistance", "pending_work"),
                ("DiscoveryCitations", "live_records"),
                ("ServiceOperations", "backups"),
                ("ServiceOperations", "restore_enforcement"),
            )
            lifecycle = ControlLifecycleService(entry, manifest, revision="u2-owners-v1")
            routers += (control_router(entry, lifecycle),)

        @asynccontextmanager
        async def lifetime(app):
            try:
                yield
            finally:
                transactions.close()

        app = assemble(profile, routers=routers, lifespan=lifetime)
        app.state.personalization = personalization
        app.state.entry = entry
        app.state.lifecycle = lifecycle
        if controls:
            from .control_worker import ControlWorker
            app.state.control_worker = ControlWorker(entry,lifecycle,personalization,assistance_files)
        app.state.transactions = transactions
        app.state.capability_catalog = catalog
        app.state.required_capabilities = set(OWNERS)
        # One bounded observation per installed owner, recorded through the
        # operations owner; readiness derives from these, never from a mount
        # boolean or a process liveness check.
        observations = local_observation.observe_all(transactions)
        local_observation.record(transactions, observations)
        app.state.capabilities = {
            owner: row["disposition"] in ("available", "degraded")
            for owner, row in observations.items()
        }
        return app
    except BaseException:
        transactions.close()
        raise
