"""Canonical Personalization settings bindings for the local journey assembly."""

from __future__ import annotations

from docsuri_shared.workspace import wire
from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from backend.local_browser import (
    BrowserDenied,
    boundary_route,
    post_context,
    read_payload,
    require_policy,
)
from backend.modules.personalization.guarded_service import (
    INTEREST_VOCABULARY,
    POLICY,
    GuardedSettingsService,
)


def settings_router(transactions, *, entry) -> APIRouter:
    origin = transactions.profile.origin
    service = GuardedSettingsService(transactions)
    router = APIRouter(route_class=boundary_route(origin))

    async def authenticated(request: Request):
        operation, _, authority = await post_context(
            request, origin=origin, entry=entry, anonymous=None
        )
        if authority is None:
            raise BrowserDenied(401, "UNAUTHENTICATED")
        return operation, authority

    @router.post("/api/v2/c03/settings-read")
    async def read_settings(request: Request):
        _, authority = await authenticated(request)
        await read_payload(request, wire.SettingsReadInputHttp)
        return await run_in_threadpool(service.read, authority)

    @router.post("/api/v2/c03/settings-update")
    async def update_settings(request: Request):
        operation, authority = await authenticated(request)
        value = await read_payload(request, wire.SettingsUpdateInputHttp)
        changes = {
            key: value[key]
            for key in ("searchDefaults", "assistanceDefaults", "appearance")
            if value.get(key) is not None
        }
        return await run_in_threadpool(
            service.update, authority, operation, value["expectedRevision"], changes
        )

    @router.post("/api/v2/c03/settings-update-onboarding")
    async def update_onboarding(request: Request):
        operation, authority = await authenticated(request)
        value = await read_payload(request, wire.SettingsOnboardingInputHttp)
        require_policy(value, POLICY)
        interests = value["interestIds"]
        if len(interests) != len(set(interests)) or any(
            interest not in INTEREST_VOCABULARY for interest in interests
        ):
            raise BrowserDenied(422, "INVALID_ARGUMENT")
        return await run_in_threadpool(
            service.update_onboarding,
            authority,
            operation,
            value["expectedRevision"],
            value["action"],
            interests,
        )

    return router
