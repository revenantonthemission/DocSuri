"""Canonical Library browser bindings over the isolated owner schema."""

from __future__ import annotations

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
from backend.modules.library.repository.guarded import GuardedLibraryRepository

POLICY = {"policyId": "synthetic-local-library", "revision": "1"}


def _metadata(conn, version: str) -> dict | None:
    return conn.execute("SELECT corpus.reference_metadata(%s) AS value", (version,)).fetchone()[
        "value"
    ]


class _LibraryReads:
    """Library-owned metadata joins; no corpus content is exposed through this seam."""

    def __init__(self, transactions):
        self.transactions = transactions

    def metadata_for(self, versions: list[str]) -> dict[str, dict]:
        def read(conn):
            return {version: _metadata(conn, version) for version in versions}

        return self.transactions.run("library", read)


def _saved_paper(row: dict, metadata: dict | None) -> dict:
    disposition = (metadata or {}).get("disposition", "unavailable")
    return {
        "savedPaperId": row["paper_id"],
        "accountId": str(row["account_id"]),
        "revision": str(row["revision"]),
        "savedPaper": {
            "paperId": row["paper_id"],
            "versionId": row["version_id"],
            "eligibilityRevision": str(
                (metadata or {}).get("eligibilityRevision") or row["revision"]
            ),
        },
        "resolvedPaper": {
            "paperId": row["paper_id"],
            "versionId": row["version_id"],
            "eligibilityRevision": str(
                (metadata or {}).get("eligibilityRevision") or row["revision"]
            ),
        }
        if disposition == "available"
        else None,
        "savedTitle": (metadata or {}).get("title"),
        "sourceDisposition": {
            "available": "available",
            "withdrawn": "withdrawn",
            "unavailable": "unavailable",
        }[disposition],
        "reasonKey": "source." + disposition,
    }


def library_router(transactions, *, entry) -> APIRouter:
    origin = transactions.profile.origin
    repository = GuardedLibraryRepository(transactions)
    reads = _LibraryReads(transactions)
    router = APIRouter(route_class=boundary_route(origin))

    async def authenticated(request: Request):
        operation, _, authority = await post_context(
            request, origin=origin, entry=entry, anonymous=None
        )
        if authority is None:
            raise BrowserDenied(401, "UNAUTHENTICATED")
        return operation, authority

    def page_limit(value: dict) -> int:
        if value["page"].get("cursor"):
            raise BrowserDenied(410, "SNAPSHOT_EXPIRED")
        limit = value["page"].get("limit") or 20
        if type(limit) is not int or not 1 <= limit <= 100:
            raise BrowserDenied(422, "INVALID_ARGUMENT")
        return limit

    @router.post("/api/v2/c03/library-save-paper")
    async def save_paper(request: Request):
        operation, authority = await authenticated(request)
        value = await read_payload(request, wire.LibrarySavePaperInputHttp)
        require_policy(value, POLICY)
        paper = value["paper"]
        receipt = await run_in_threadpool(
            repository.save,
            authority,
            paper["paperId"],
            paper["versionId"],
            operation,
            None,
        )
        metadata = (await run_in_threadpool(reads.metadata_for, [paper["versionId"]]))[
            paper["versionId"]
        ]
        row = {
            "paper_id": receipt["paperId"],
            "version_id": receipt["paperVersionId"],
            "revision": receipt["revision"],
            "account_id": authority.account_id,
        }
        return wire.LibrarySavedPaper.model_validate(_saved_paper(row, metadata)).model_dump(
            mode="json", exclude_none=True
        )

    @router.post("/api/v2/c03/library-list-saved-papers")
    async def list_saved_papers(request: Request):
        _, authority = await authenticated(request)
        value = await read_payload(request, wire.LibraryPaperListInputHttp)
        limit = page_limit(value)
        rows = await run_in_threadpool(repository.list_saved, authority, limit=limit)
        metadata = await run_in_threadpool(reads.metadata_for, [row["version_id"] for row in rows])
        boundary = await run_in_threadpool(repository.history_boundary, authority)
        return wire.LibraryPaperPage.model_validate(
            {
                "items": [_saved_paper(row, metadata[row["version_id"]]) for row in rows],
                "page": {"nextCursor": None, "snapshotRevision": str(boundary["revision"])},
                "appliedLimit": limit,
                "policyRef": POLICY,
            }
        ).model_dump(mode="json", exclude_none=True)

    @router.post("/api/v2/c03/library-read-saved-paper")
    async def read_saved_paper(request: Request):
        _, authority = await authenticated(request)
        value = await read_payload(request, wire.LibrarySavedPaperInputHttp)
        rows = await run_in_threadpool(repository.list_saved, authority, limit=100)
        row = next((item for item in rows if item["paper_id"] == value["savedPaperId"]), None)
        if row is None:
            raise BrowserDenied(404, "FORBIDDEN")
        metadata = await run_in_threadpool(reads.metadata_for, [row["version_id"]])
        return wire.LibrarySavedPaper.model_validate(
            _saved_paper(row, metadata[row["version_id"]])
        ).model_dump(mode="json", exclude_none=True)

    @router.post("/api/v2/c03/library-remove-saved-paper")
    async def remove_saved_paper(request: Request):
        operation, authority = await authenticated(request)
        value = await read_payload(request, wire.LibraryRemoveSavedPaperInputHttp)
        try:
            expected = UUID(value["expectedRevision"])
        except ValueError:
            raise BrowserDenied(422, "INVALID_ARGUMENT") from None
        await run_in_threadpool(
            repository.remove_paper, authority, value["savedPaperId"], operation, expected
        )
        return wire.Ack.model_validate(
            {
                "resourceId": value["savedPaperId"],
                "revision": value["expectedRevision"],
                "requestId": str(operation),
            }
        ).model_dump(mode="json")

    @router.post("/api/v2/c03/library-save-search")
    async def save_search(request: Request):
        operation, authority = await authenticated(request)
        value = await read_payload(request, wire.LibrarySaveSearchInputHttp)
        receipt = await run_in_threadpool(
            repository.save_query,
            authority,
            operation,
            value["queryContext"],
            label=value.get("label"),
        )
        return wire.LibrarySavedSearch.model_validate(
            {
                "savedSearchId": receipt["savedSearchId"],
                "accountId": str(authority.account_id),
                "revision": str(receipt["revision"]),
                "queryContext": value["queryContext"],
                "label": value.get("label"),
            }
        ).model_dump(mode="json", exclude_none=True)

    @router.post("/api/v2/c03/library-list-saved-searches")
    async def list_saved_searches(request: Request):
        _, authority = await authenticated(request)
        value = await read_payload(request, wire.LibrarySearchListInputHttp)
        limit = page_limit(value)
        rows = await run_in_threadpool(repository.list_queries, authority, limit=limit)
        boundary = await run_in_threadpool(repository.history_boundary, authority)
        items = [
            {
                "savedSearchId": str(row["id"]),
                "accountId": str(row["account_id"]),
                "revision": str(row["revision"]),
                "queryContext": row["query"]["queryContext"],
                "label": row["query"].get("label"),
            }
            for row in rows
        ]
        return wire.LibrarySearchPage.model_validate(
            {
                "items": items,
                "page": {"nextCursor": None, "snapshotRevision": str(boundary["revision"])},
                "appliedLimit": limit,
                "policyRef": POLICY,
            }
        ).model_dump(mode="json", exclude_none=True)

    @router.post("/api/v2/c03/library-remove-saved-search")
    async def remove_saved_search(request: Request):
        operation, authority = await authenticated(request)
        value = await read_payload(request, wire.LibraryRemoveSavedSearchInputHttp)
        try:
            expected = UUID(value["expectedRevision"])
            identifier = UUID(value["savedSearchId"])
        except ValueError:
            raise BrowserDenied(422, "INVALID_ARGUMENT") from None
        await run_in_threadpool(repository.remove_query, authority, identifier, operation, expected)
        return wire.Ack.model_validate(
            {
                "resourceId": value["savedSearchId"],
                "revision": value["expectedRevision"],
                "requestId": str(operation),
            }
        ).model_dump(mode="json")

    def history_record(row: dict, boundary: dict) -> dict:
        return {
            "historyId": str(row["execution_id"]),
            "accountId": str(row["account_id"]),
            "searchExecutionId": str(row["execution_id"]),
            "queryContext": row["query"],
            "recordedAt": row["completed_at"].isoformat(),
            "admissionSequence": int(row["captured_generation"]),
            "completionSequence": int(row["sequence"]),
            "clearBoundary": str(boundary["revision"]),
        }

    @router.post("/api/v2/c03/library-list-history")
    async def list_history(request: Request):
        _, authority = await authenticated(request)
        value = await read_payload(request, wire.LibraryHistoryListInputHttp)
        limit = page_limit(value)
        rows = await run_in_threadpool(repository.list_history, authority, limit=limit)
        boundary = await run_in_threadpool(repository.history_boundary, authority)
        return wire.LibraryHistoryPage.model_validate(
            {
                "items": [history_record(row, boundary) for row in rows],
                "page": {"nextCursor": None, "snapshotRevision": str(boundary["revision"])},
                "appliedLimit": limit,
                "policyRef": POLICY,
                "clearBoundary": str(boundary["revision"]),
            }
        ).model_dump(mode="json", exclude_none=True)

    @router.post("/api/v2/c03/library-read-history")
    async def read_history(request: Request):
        _, authority = await authenticated(request)
        value = await read_payload(request, wire.LibraryHistoryInputHttp)
        rows = await run_in_threadpool(repository.list_history, authority, limit=100)
        row = next((item for item in rows if str(item["execution_id"]) == value["historyId"]), None)
        if row is None:
            raise BrowserDenied(404, "FORBIDDEN")
        boundary = await run_in_threadpool(repository.history_boundary, authority)
        return wire.LibraryHistoryRecord.model_validate(history_record(row, boundary)).model_dump(
            mode="json", exclude_none=True
        )

    @router.post("/api/v2/c03/library-clear-history")
    async def clear_history(request: Request):
        operation, authority = await authenticated(request)
        value = await read_payload(request, wire.LibraryClearHistoryInputHttp)
        require_policy(value, POLICY)
        try:
            expected = UUID(value["expectedRevision"])
        except ValueError:
            raise BrowserDenied(422, "INVALID_ARGUMENT") from None
        receipt = await run_in_threadpool(repository.clear_history, authority, operation, expected)
        revision = str(receipt["revision"])
        return wire.LibraryClearHistoryResult.model_validate(
            {
                "ack": {
                    "resourceId": str(authority.account_id),
                    "revision": revision,
                    "requestId": str(operation),
                },
                "checkpoint": {
                    "ownerId": str(authority.account_id),
                    "admissionSequence": int(receipt["generation"]),
                    "revision": revision,
                },
                "clearBoundary": revision,
            }
        ).model_dump(mode="json", exclude_none=True)

    return router
