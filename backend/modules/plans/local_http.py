"""Canonical UsageEntitlements browser binding for the local journey assembly."""

from __future__ import annotations

from datetime import UTC, datetime

from docsuri_shared.workspace import wire
from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from backend.local_browser import (
    BrowserDenied,
    boundary_route,
    post_context,
    read_payload,
)
from backend.modules.plans.guarded_repository import GuardedUsageRepository

POLICY = {"policyId": "synthetic-four-no-reset", "revision": "1"}


def usage_router(transactions, *, entry) -> APIRouter:
    origin = transactions.profile.origin
    repository = GuardedUsageRepository(transactions)
    router = APIRouter(route_class=boundary_route(origin))

    async def authenticated(request: Request):
        operation, _, authority = await post_context(
            request, origin=origin, entry=entry, anonymous=None
        )
        if authority is None:
            raise BrowserDenied(401, "UNAUTHENTICATED")
        return operation, authority

    @router.post("/api/v2/c03/usage-inspect")
    async def inspect(request: Request):
        _, authority = await authenticated(request)
        await read_payload(request, wire.UsageInspectInputHttp)
        await run_in_threadpool(repository.ensure_entitlement, authority)
        policy = await run_in_threadpool(repository.current, authority)
        counts = policy["counts"]
        used = counts.get("committed", 0)
        reserved = counts.get("reserved", 0)
        # The finite synthetic wallet has no reset; its period is the exact
        # owned environment retention window, never an invented billing cycle.
        period_end = datetime.fromtimestamp(transactions.profile.expires_at, UTC)
        measure = {
            "state": "known",
            "metricId": "paper-assistance",
            "allocated": int(policy["allocation"]),
            "used": int(used),
            "reserved": int(reserved),
            "remaining": max(0, int(policy["allocation"]) - used - reserved),
            "periodId": "synthetic-environment-retention",
            "periodStart": policy["created_at"].isoformat(),
            "periodEnd": period_end.isoformat(),
            "policyRef": POLICY,
        }
        return wire.UsageMeasurePage.model_validate(
            {
                "items": [measure],
                "page": {"nextCursor": None, "snapshotRevision": str(policy["revision"])},
                "appliedLimit": 1,
                "policyRef": POLICY,
            }
        ).model_dump(mode="json", exclude_none=True)

    return router
