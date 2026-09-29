"""Readonly R1C HTTP surface.

Every route here observes. Nothing in this module creates a run, a ledger row, a scan job or a
grant, and nothing refreshes a caller authorisation. Peer identity is taken *only* from the
ASGI scope key that the TLS transport injects after verifying a client certificate
(:mod:`docsuri_platform_integrity.api.server`); request headers are never consulted, so a
caller cannot assert its own identity.
"""

import asyncio
import re
from contextlib import asynccontextmanager

import anyio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# The daemon is loopback-only. A non-loopback peer is answered exactly like an unknown path so
# the service does not confirm its own existence to anything off-host.
LOOPBACK = frozenset({"127.0.0.1", "::1"})
HEALTH_PATHS = frozenset({"/healthz", "/readyz"})
MAX_REQUEST_BYTES = 256 * 1024
MAX_RESPONSE_BYTES = 1024**2
MAX_RESPONSE_ITEMS = 100
DEADLINE_SECONDS = 3
METADATA_ADMISSIONS = 8
HEALTH_ADMISSIONS = 2
FINGERPRINT = re.compile(r"\A[0-9a-f]{64}\Z")


def peer_identity(scope) -> str | None:
    """The verified peer identity, or None. Never falls back to a header or a query parameter."""
    value = scope.get("client_certificate_fingerprint")
    return value if isinstance(value, str) and FINGERPRINT.match(value) else None


def item_count(result) -> int:
    """Every item a response can carry, so the cap cannot be sidestepled by a different field."""
    return sum(
        len(getattr(result, name, ()) or ())
        for name in ("evidence_ids", "exception_ids", "diagnostics", "selections", "reasons")
    )


def create_app(service, *, peers: frozenset[str] = LOOPBACK) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        yield

    app = FastAPI(
        title="DocSuri platform evidence",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    metadata = anyio.CapacityLimiter(METADATA_ADMISSIONS)
    health = anyio.CapacityLimiter(HEALTH_ADMISSIONS)

    def reject(reason: str, status: int):
        return JSONResponse({"reason": reason}, status_code=status)

    @app.middleware("http")
    async def bounded_request(request: Request, call_next):
        host = request.client.host if request.client else None
        if host not in peers:
            return reject("not_found", 404)
        health_path = request.url.path in HEALTH_PATHS
        length = request.headers.get("content-length", "0")
        if not length.isdigit() or int(length) > MAX_REQUEST_BYTES:
            return reject("request_limit", 413)
        # This daemon is readonly; request bodies/chunked bodies are never accepted. Answered
        # before the auth gate because a fixed refusal reveals nothing about identity.
        if int(length) or request.headers.get("transfer-encoding"):
            return reject("body_not_supported", 400)
        fingerprint = peer_identity(request.scope)
        if not health_path and fingerprint is None:
            # Reject before spending an admission so unauthenticated callers cannot consume
            # the read budget of authenticated ones.
            return reject("unauthenticated", 401)
        limiter = health if health_path else metadata
        try:
            limiter.acquire_nowait()
        except anyio.WouldBlock:
            return reject("busy", 503)
        try:
            async with asyncio.timeout(DEADLINE_SECONDS):
                return await call_next(request)
        except TimeoutError:
            return reject("observation_timeout", 503)
        except Exception:
            return reject("observation_unavailable", 503)
        finally:
            limiter.release()

    @app.get("/healthz")
    async def healthz():
        # Liveness only: no dependency, no subject, no authorisation.
        return {"alive": True}

    @app.get("/readyz")
    async def readyz(request: Request):
        subject = request.query_params.get("subject")
        state = await anyio.to_thread.run_sync(
            lambda: service.readiness(peer_identity(request.scope), subject),
            abandon_on_cancel=True,
        )
        ready = bool(state["shallow"]) and bool(state["deep"])
        return JSONResponse(state, status_code=200 if ready else 503)

    # Subjects and releases are Refs, whose pattern admits "/" (e.g. "repo/one"), so the
    # parameter must span path segments. The value is only ever a policy key, never a file path.
    @app.get("/internal/v1/evidence/{subject:path}")
    async def evidence(subject: str, request: Request):
        if len(subject) > 200:
            return reject("not_found", 404)
        fingerprint = peer_identity(request.scope)
        try:
            result = await anyio.to_thread.run_sync(
                service.read, fingerprint, subject, abandon_on_cancel=True
            )
        except (PermissionError, KeyError):
            # A denied subject and an absent subject are indistinguishable on purpose.
            return reject("not_found", 404)
        except Exception:
            return reject("evidence_unavailable", 503)
        if item_count(result) > MAX_RESPONSE_ITEMS:
            return reject("response_limit", 503)
        response = JSONResponse(result.model_dump(mode="json"))
        if len(response.body) > MAX_RESPONSE_BYTES:
            return reject("response_limit", 503)
        return response

    @app.get("/internal/v1/compatibility/{release:path}")
    async def compatibility(release: str, request: Request):
        if len(release) > 200:
            return reject("not_found", 404)
        fingerprint = peer_identity(request.scope)
        try:
            result = await anyio.to_thread.run_sync(
                service.compatibility, fingerprint, release, abandon_on_cancel=True
            )
        except (PermissionError, KeyError):
            return reject("not_found", 404)
        except Exception:
            return reject("compatibility_unavailable", 503)
        if item_count(result) > MAX_RESPONSE_ITEMS:
            return reject("response_limit", 503)
        response = JSONResponse(result.model_dump(mode="json"))
        if len(response.body) > MAX_RESPONSE_BYTES:
            return reject("response_limit", 503)
        return response

    return app
