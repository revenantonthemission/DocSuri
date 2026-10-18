"""Canonical Personalization settings bindings for the local journey assembly."""

from __future__ import annotations

from uuid import UUID

from docsuri_shared.workspace import wire
from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from backend.local_browser import (
    BrowserDenied,
    boundary_route,
    optional_authority,
    post_context,
    read_payload,
    require_policy,
)
from backend.modules.personalization.guarded_service import (
    INTEREST_VOCABULARY,
    POLICY,
    GuardedSettingsService,
)


def settings_router(transactions, *, entry, controls=None) -> APIRouter:
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
        require_policy(value, POLICY)
        changes = {
            key: value[key]
            for key in ("searchDefaults", "assistanceDefaults", "appearance", "timeZone")
            if value.get(key) is not None
        }
        try:
            return await run_in_threadpool(
                service.update, authority, operation, value["expectedRevision"], changes
            )
        except ValueError as error:
            if str(error).startswith("unsupported "):
                raise BrowserDenied(422, "INVALID_ARGUMENT") from None
            raise

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

    if transactions.profile.realm == "account-controls":
        from backend.modules.accounts.control_confirmation import ResetConfirmationService
        from backend.modules.accounts.control_cursor import ControlCursor
        from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
        from backend.modules.personalization.control_service import (
            PersonalizationControlService,
            ProducerBinding,
        )
        from backend.modules.personalization.reset_repository import ResetRepository

        policy = SYNTHETIC_POLICY
        cursor = ControlCursor(bytes.fromhex(entry.verifier("cursor", "u2-controls-v1")))
        controls = controls or PersonalizationControlService(
            transactions, policy, cursor, producers=(ProducerBinding("Library"),)
        )
        resets = ResetRepository(transactions, policy, cursor)
        confirmations = ResetConfirmationService(transactions, policy, entry)

        async def read_authority(request):
            authority = await optional_authority(request, entry=entry)
            if authority is None:
                raise BrowserDenied(401, "UNAUTHENTICATED")
            return authority

        @router.post("/api/v2/c03/settings-list-suggestions")
        async def suggestions(request: Request):
            _, authority = await authenticated(request)
            value = await read_payload(request, wire.SettingsSuggestionInputHttp)
            return await run_in_threadpool(
                controls.suggestions,
                authority,
                limit=value["page"].get("limit", 20),
                cursor=value["page"].get("cursor"),
                identity_link_id=value.get("identityLinkId"),
            )

        @router.post("/api/v2/c03/settings-list-recent-papers")
        async def recent(request: Request):
            _, authority = await authenticated(request)
            value = await read_payload(request, wire.SettingsRecentInputHttp)
            return await run_in_threadpool(
                controls.recent,
                authority,
                limit=value["page"].get("limit", 20),
                cursor=value["page"].get("cursor"),
            )

        @router.post("/api/v2/c03/settings-prepare-reset")
        async def prepare_reset(request: Request):
            operation, authority = await authenticated(request)
            value = await read_payload(request, wire.SettingsResetPrepareInputHttp)
            require_policy(value, policy.reference)
            # Bind the caller's observed token. Acceptance checks its current
            # value atomically with consuming this confirmation and the effect.
            return await run_in_threadpool(
                confirmations.prepare,
                authority,
                operation,
                action=value["action"],
                expected=UUID(value["expectedRevision"]),
                proof=value["currentProof"],
            )

        @router.post("/api/v2/c03/settings-reset")
        async def reset(request: Request):
            operation, authority = await authenticated(request)
            value = await read_payload(request, wire.SettingsResetInputHttp)
            require_policy(value, policy.reference)
            return await run_in_threadpool(
                resets.accept,
                authority,
                operation,
                UUID(value["expectedRevision"]),
                value["action"],
                manifest=(("Personalization", "behavior"), ("ServiceOperations", "restore")),
                manifest_revision="u2-reset-manifest-1",
                confirmation=UUID(value["confirmationRef"]),
            )

        @router.get("/api/v2/c03/settings-resets")
        async def list_resets(request: Request):
            authority = await read_authority(request)
            params = request.query_params
            if set(params) - {"view", "limit", "cursor"} or any(
                len(params.getlist(key)) != 1 for key in params
            ):
                raise BrowserDenied(422, "INVALID_ARGUMENT")
            try:
                limit = int(params["limit"])
                view = params["view"]
            except (ValueError, KeyError):
                raise BrowserDenied(422, "INVALID_ARGUMENT") from None
            return await run_in_threadpool(
                resets.list, authority, view=view, limit=limit, cursor=params.get("cursor")
            )

        @router.get("/api/v2/c03/settings-resets/{resetId}")
        async def inspect_reset(resetId: str, request: Request):
            authority = await read_authority(request)
            if request.query_params:
                raise BrowserDenied(422, "INVALID_ARGUMENT")
            try:
                identifier = UUID(resetId)
            except ValueError:
                raise BrowserDenied(422, "INVALID_ARGUMENT") from None
            return await run_in_threadpool(resets.inspect, authority, identifier)

    return router
