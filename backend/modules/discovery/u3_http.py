"""Canonical U3 Discovery browser bindings.

C05 operations: search (guest-allowed, anonymous by construction), citation
exploration (authenticated, bounded and labelled) and the completed-search
checkpoint handoff. Dependency outages and expired snapshots never become empty
or success responses.
"""

from __future__ import annotations

from backend.local_browser import (
    BrowserDenied,
    boundary_route,
    post_context,
    read_payload,
)
from backend.modules.discovery.citations import BudgetExhausted
from backend.modules.discovery.local_search import validate_query
from backend.modules.discovery.u3_search import DependencyUnavailable, SnapshotExpired
from backend.u3_policy import QUERY_VOCABULARY, SEARCH_POLICY
from docsuri_shared.workspace import wire
from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool


def discovery_router(transactions, *, entry, anonymous, search, citations) -> APIRouter:
    origin = transactions.profile.origin
    router = APIRouter(route_class=boundary_route(origin))

    async def context(request: Request):
        operation, _, authority = await post_context(
            request, origin=origin, entry=entry, anonymous=anonymous
        )
        return operation, authority

    async def authenticated(request: Request):
        operation, _, authority = await post_context(
            request, origin=origin, entry=entry, anonymous=None
        )
        if authority is None:
            raise BrowserDenied(401, "UNAUTHENTICATED")
        return operation, authority

    @router.post("/api/v2/c05/search")
    async def search_route(request: Request):
        _, authority = await context(request)
        value = await read_payload(request, wire.SearchRequestHttp)
        try:
            validate_query(
                value["query"], vocabulary=QUERY_VOCABULARY, policy=SEARCH_POLICY
            )
        except ValueError:
            raise BrowserDenied(422, "INVALID_ARGUMENT") from None
        try:
            return await run_in_threadpool(search.search, authority, value)
        except SnapshotExpired:
            raise BrowserDenied(410, "SNAPSHOT_EXPIRED") from None
        except DependencyUnavailable:
            raise BrowserDenied(503, "DEPENDENCY_UNAVAILABLE") from None

    @router.post("/api/v2/c05/read-citations")
    async def read_citations(request: Request):
        _, authority = await authenticated(request)
        value = await read_payload(request, wire.CitationRequestHttp)
        try:
            result = await run_in_threadpool(citations.explore, authority, value)
        except BudgetExhausted:
            raise BrowserDenied(429, "RATE_LIMITED", retry_after=60) from None
        except ValueError:
            raise BrowserDenied(422, "INVALID_ARGUMENT") from None
        return wire.CitationResponse.model_validate(
            {
                "snapshotId": result["snapshotId"],
                "revision": result["snapshotId"],
                "root": result["root"],
                "nodes": result["nodes"],
                "edges": result["edges"],
                "freshness": {
                    "fresh": "current",
                    "stale": "stale",
                    "unknown": "unknown",
                }[result["freshness"]],
                "coverage": result["coverage"]
                if result["coverage"] in ("complete", "partial")
                else "partial",
                "limitations": result["limitations"],
                "page": {
                    "nextCursor": None,
                    "snapshotRevision": result["snapshotId"],
                },
            }
        ).model_dump(mode="json", exclude_none=True)

    return router
