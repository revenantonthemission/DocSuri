"""Canonical UsageEntitlements browser binding for the local journey assembly."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

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
from backend.modules.plans.guarded_repository import GuardedUsageRepository

POLICY = {"policyId": "synthetic-four-no-reset", "revision": "1"}


def usage_router(transactions, *, entry) -> APIRouter:
    origin = transactions.profile.origin
    repository = GuardedUsageRepository(transactions)
    controls = transactions.profile.realm == "account-controls"
    if controls:
        from backend.modules.accounts.control_cursor import ControlCursor
        from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
        from backend.modules.plans.control_service import ControlUsageService

        control = ControlUsageService(transactions, SYNTHETIC_POLICY)
        cursor = ControlCursor(bytes.fromhex(entry.verifier("cursor", "usage-records")))
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
        value = await read_payload(request, wire.UsageInspectInputHttp)
        if controls:
            value["page"].setdefault("limit", 20)
            if (
                value["page"].get("cursor")
                or not 1 <= value["page"]["limit"] <= SYNTHETIC_POLICY.max_page_size
            ):
                raise BrowserDenied(422, "INVALID_ARGUMENT")
            current = await run_in_threadpool(repository.inspect_assignment, authority)
            tick = int(current["periodId"].split(":")[1])
            start = tick * SYNTHETIC_POLICY.period_seconds
            counts = current["counts"]
            allocated = current["allocation"] if current["disposition"] == "assigned" else 0
            used, reserved = counts.get("committed", 0), counts.get("reserved", 0)
            return wire.UsageMeasurePage.model_validate(
                {
                    "items": [
                        {
                            "state": "known",
                            "metricId": "paper-assistance",
                            "allocated": allocated,
                            "used": used,
                            "reserved": reserved,
                            "remaining": max(0, allocated - used - reserved),
                            "periodId": current["periodId"],
                            "periodStart": datetime.fromtimestamp(start, UTC).isoformat(),
                            "periodEnd": datetime.fromtimestamp(
                                start + SYNTHETIC_POLICY.period_seconds, UTC
                            ).isoformat(),
                            "policyRef": SYNTHETIC_POLICY.reference,
                        }
                    ],
                    "page": {"nextCursor": None, "snapshotRevision": current["revision"]},
                    "appliedLimit": value["page"]["limit"],
                    "policyRef": SYNTHETIC_POLICY.reference,
                }
            ).model_dump(mode="json", exclude_none=True)
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

    if controls:

        @router.post("/api/v2/c03/usage-list-records")
        async def records(request: Request):
            _, authority = await authenticated(request)
            value = await read_payload(request, wire.UsageRecordsInputHttp)
            return await run_in_threadpool(control.records, authority, value["page"], cursor)

        def entitlement(snapshot):
            value = snapshot["entitlement"]
            if value is None:
                return None
            return {
                "entitlementId": snapshot["accountId"],
                "accountId": snapshot["accountId"],
                "tierId": "synthetic-free",
                "revision": snapshot["revision"],
                "assignmentSource": "administrative_assignment",
                "policyRef": SYNTHETIC_POLICY.reference,
                "effectiveAt": value["effectiveAt"],
                "disposition": "revoked" if value["revoked"] else "active",
            }

        @router.post("/api/v2/c03/usage-read-assignment")
        async def assignment(request: Request):
            _, authority = await authenticated(request)
            value = await read_payload(request, wire.UsageAssignmentReadHttp)
            result = await run_in_threadpool(
                control.assignment, authority, UUID(value["accountId"])
            )
            return wire.UsageAssignmentSnapshot.model_validate(
                dict(result, entitlement=entitlement(result))
            ).model_dump(mode="json")

        @router.post("/api/v2/c03/usage-grant-entitlement")
        async def grant(request: Request):
            operation, authority = await authenticated(request)
            value = await read_payload(request, wire.UsageGrantInputHttp)
            require_policy(value, SYNTHETIC_POLICY.reference)
            if value["tierId"] != "synthetic-free":
                raise BrowserDenied(503, "POLICY_UNRESOLVED")
            result = await run_in_threadpool(
                control.assign,
                authority,
                UUID(value["accountId"]),
                operation,
                UUID(value["expectedRevision"]),
                allocation=SYNTHETIC_POLICY.quota,
                revoked=False,
                reason=value["reasonKey"],
            )
            return wire.UsageEntitlement.model_validate(result).model_dump(mode="json")

        @router.post("/api/v2/c03/usage-revoke-entitlement")
        async def revoke(request: Request):
            operation, authority = await authenticated(request)
            value = await read_payload(request, wire.UsageRevokeInputHttp)
            require_policy(value, SYNTHETIC_POLICY.reference)
            if value["entitlementId"] != value["accountId"]:
                raise BrowserDenied(403, "FORBIDDEN")
            result = await run_in_threadpool(
                control.assign,
                authority,
                UUID(value["accountId"]),
                operation,
                UUID(value["expectedRevision"]),
                allocation=0,
                revoked=True,
                reason=value["reasonKey"],
            )
            return wire.UsageEntitlement.model_validate(result).model_dump(mode="json")

        @router.post("/api/v2/c03/usage-read-plan")
        async def plan(request: Request):
            _, authority = await authenticated(request)
            await read_payload(request, wire.UsagePlanInputHttp)
            current = await run_in_threadpool(repository.inspect_assignment, authority)
            return wire.UsagePlanPresentation.model_validate(
                {
                    "accountId": str(authority.account_id),
                    "tierId": "synthetic-free",
                    "labelKey": "plan.syntheticFree",
                    "source": "mock"
                    if current["disposition"] == "unassigned"
                    else "administrative_assignment",
                    "revision": current["revision"],
                    "policyRef": SYNTHETIC_POLICY.reference,
                    "paymentOccurred": False,
                }
            ).model_dump(mode="json")

    return router
