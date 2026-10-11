"""Same-origin host for the explicit synthetic composition, with truthful readiness."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .local_profile import LocalProfile


def assemble(profile: LocalProfile) -> FastAPI:
    app = FastAPI(
        title="DocSuri local research workspace", docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.profile = profile
    app.state.capabilities = {}
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
        required = {
            "accounts",
            "corpus",
            "discovery",
            "library",
            "personalization",
            "usage",
            "assistance",
            "operations",
        }
        missing = sorted(required - {k for k, v in app.state.capabilities.items() if v is True})
        return JSONResponse(
            {"ready": not missing, "missing": missing}, status_code=503 if missing else 200
        )

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
