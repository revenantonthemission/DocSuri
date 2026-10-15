"""Canonical U3 PaperAssistance browser bindings.

C06 operations: reconciled options, glossary read/replace with visible CAS,
durable acceptance with recoverable dispatch, the authoritative job snapshot
plus ordered progress through the real transport, and prepared-result reads
with distinct pending/ready/expired/failed states (closing Q-01–Q-04 in real
mounted behavior).
"""

from __future__ import annotations

import asyncio
import time
from uuid import UUID

from backend.local_browser import (
    BrowserDenied,
    boundary_route,
    post_context,
    read_payload,
)
from backend.modules.plans.guarded_repository import UsageQuotaExceeded as _UsageQuotaExceeded
from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository
from backend.modules.summarization.local_http import (
    PARTIAL_NOTE,
    TERMINAL,
    _frame,
    snapshot_dto,
)
from backend.modules.summarization.local_result import decode_result
from backend.modules.summarization.requests import AssistanceRequests, AssistanceUnavailable
from backend.modules.summarization.u3_catalog import catalog_for, unavailable_options
from backend.modules.summarization.u3_glossary import (
    GlossaryConflict,
    GlossaryInvalid,
    GlossaryService,
)
from docsuri_shared.workspace import wire
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

PROGRESS_SECONDS = 30.0
POLL_SECONDS = 0.25


def assistance_router(
    transactions, *, entry, files, dispatch, corpus_repository
) -> APIRouter:
    origin = transactions.profile.origin
    repository = GuardedAssistanceRepository(transactions, files)
    glossary = GlossaryService(transactions)
    requests = AssistanceRequests(
        dispatch.admission,
        corpus_repository,
        lambda source: catalog_for(source, provider_ready=True),
    )
    router = APIRouter(route_class=boundary_route(origin))

    async def authenticated(request: Request):
        operation, _, authority = await post_context(
            request, origin=origin, entry=entry, anonymous=None
        )
        if authority is None:
            raise BrowserDenied(401, "UNAUTHENTICATED")
        return operation, authority

    async def get_authority(request: Request):
        from backend.local_browser import optional_authority

        authority = await optional_authority(request, entry=entry)
        if authority is None:
            raise BrowserDenied(401, "UNAUTHENTICATED")
        return authority

    async def read_job(authority, job_id: UUID) -> dict:
        job = await run_in_threadpool(repository.disposition_snapshot, authority, job_id)
        result_ref = await run_in_threadpool(repository.result_reference, authority, job_id)
        return snapshot_dto(job, result_ref)

    def result_ref(result_row: dict | None) -> dict | None:
        if result_row is None or result_row["availability"] != "retained":
            return None
        return {
            "resultId": str(result_row["id"]),
            "revision": str(result_row["revision"]),
            "contentHash": result_row["output_hash"],
            "mediaType": "application/json",
        }

    async def prepared_result(authority, job_id: UUID) -> dict:
        job = await run_in_threadpool(repository.disposition_snapshot, authority, job_id)
        result_row = await run_in_threadpool(repository.result_metadata, authority, job_id)
        if result_row is None:
            availability = "failed" if job["state"] == "failed" else "pending"
            return wire.AssistanceResultRead.model_validate(
                {
                    "availability": availability,
                    "jobId": str(job_id),
                    "reasonKey": "result." + availability,
                }
            ).model_dump(mode="json", exclude_none=True)
        metadata = await run_in_threadpool(repository.source_metadata, authority, job["version_id"])
        disposition = (metadata or {}).get("disposition", "unavailable")
        if result_row["availability"] != "retained":
            availability = result_row["availability"]
        elif disposition != "available":
            availability = "withdrawn" if disposition == "withdrawn" else "restricted"
        else:
            availability = "ready"
        accepted = job["payload"].get("acceptedInput")
        if availability != "ready":
            return wire.AssistanceResultRead.model_validate(
                {
                    "availability": availability,
                    "jobId": str(job_id),
                    "reasonKey": "result." + availability,
                }
            ).model_dump(mode="json", exclude_none=True)
        if accepted is None:
            return wire.AssistanceResultRead.model_validate(
                {"availability": "failed", "jobId": str(job_id), "reasonKey": "result.legacy"}
            ).model_dump(mode="json", exclude_none=True)
        try:
            raw = await run_in_threadpool(repository.result, authority, result_row["id"])
            document = decode_result(raw)
        except (ValueError, UnicodeError):
            return wire.AssistanceResultRead.model_validate(
                {"availability": "failed", "jobId": str(job_id), "reasonKey": "result.invalid"}
            ).model_dump(mode="json", exclude_none=True)
        provenance = result_row.get("provenance") or {}
        limitations = [PARTIAL_NOTE]
        if provenance.get("synthetic") is True:
            limitations.append(
                "합성(synthetic) 실행기 출력입니다. 실제 모델 결과가 아닙니다."
            )
        return wire.AssistanceResultRead.model_validate(
            {
                "availability": "ready",
                "prepared": {
                    "result": result_ref(result_row),
                    "ownerId": str(job["account_id"]),
                    "jobId": str(job_id),
                    "paper": {
                        "paperId": metadata["paperId"],
                        "versionId": metadata["versionId"],
                        "eligibilityRevision": str(metadata["eligibilityRevision"]),
                    },
                    "sourceContentHash": job["source_hash"],
                    "operation": accepted["operation"],
                    "optionId": accepted["optionId"],
                    "glossaryRevision": accepted["glossaryRevision"],
                    "sections": document["sections"],
                    "coverage": (result_row["coverage"] or {}).get("coverage", "partial"),
                    "limitations": limitations,
                    "methodRevision": accepted["optionsRevision"],
                },
            }
        ).model_dump(mode="json", exclude_none=True)

    @router.post("/api/v2/c06/read-assistance-options")
    async def options(request: Request):
        _, _ = await authenticated(request)
        value = await read_payload(request, wire.AssistanceOptionsReadHttp)
        try:
            source = await run_in_threadpool(
                corpus_repository.read, value["paper"]["versionId"]
            )
        except (PermissionError, LookupError):
            raise BrowserDenied(404, "NOT_FOUND") from None
        if source["paper_id"] != value["paper"]["paperId"]:
            raise BrowserDenied(404, "NOT_FOUND")
        catalog = catalog_for(source, provider_ready=True)
        if catalog is None:
            return unavailable_options(source)
        return catalog.options()

    @router.post("/api/v2/c06/read-glossary")
    async def read_glossary(request: Request):
        _, authority = await authenticated(request)
        await read_payload(request, wire.AssistanceGlossaryReadHttp)
        return await run_in_threadpool(glossary.read, authority)

    @router.post("/api/v2/c06/replace-glossary")
    async def replace_glossary(request: Request):
        _, authority = await authenticated(request)
        value = await read_payload(request, wire.AssistanceGlossaryWriteHttp)
        try:
            return await run_in_threadpool(glossary.replace, authority, value)
        except GlossaryConflict:
            raise BrowserDenied(409, "CONFLICT") from None
        except GlossaryInvalid:
            raise BrowserDenied(422, "INVALID_ARGUMENT") from None

    @router.post("/api/v2/c06/accept-assistance")
    async def accept(request: Request):
        operation, authority = await authenticated(request)
        value = await read_payload(request, wire.AssistanceRequestHttp)
        await run_in_threadpool(dispatch.usage.ensure_entitlement, authority)
        try:
            job = await run_in_threadpool(requests.submit, authority, operation, value)
        except AssistanceUnavailable:
            raise BrowserDenied(503, "NOT_READY") from None
        except _UsageQuotaExceeded:
            raise BrowserDenied(429, "QUOTA_EXCEEDED") from None
        return wire.JobReceipt.model_validate(
            {
                "jobId": str(job["id"]),
                "revision": str(job["revision"]),
                "seq": int(job["sequence"]),
                "state": job["state"],
                "requestId": str(operation),
                "acceptedAt": job["accepted_at"].isoformat(),
            }
        ).model_dump(mode="json")

    @router.post("/api/v2/c06/read-assistance-job")
    async def read_assistance_job(request: Request):
        _, authority = await authenticated(request)
        value = await read_payload(request, wire.AssistanceJobReadHttp)
        try:
            job_id = UUID(value["jobId"])
        except (ValueError, TypeError):
            raise BrowserDenied(422, "INVALID_ARGUMENT") from None
        return await read_job(authority, job_id)

    @router.get("/api/v2/jobs/{job_id}")
    async def job_snapshot(request: Request, job_id: str):
        authority = await get_authority(request)
        try:
            identifier = UUID(job_id)
        except ValueError:
            raise BrowserDenied(422, "INVALID_ARGUMENT") from None
        return await read_job(authority, identifier)

    @router.post("/api/v2/c06/read-prepared-assistance")
    async def read_prepared_assistance(request: Request):
        _, authority = await authenticated(request)
        value = await read_payload(request, wire.AssistanceResultRequestHttp)
        try:
            job_id = UUID(value["jobId"])
        except (ValueError, TypeError):
            raise BrowserDenied(422, "INVALID_ARGUMENT") from None
        return await prepared_result(authority, job_id)

    @router.get("/api/v2/jobs/{job_id}/result")
    async def job_result(request: Request, job_id: str):
        authority = await get_authority(request)
        try:
            identifier = UUID(job_id)
        except ValueError:
            raise BrowserDenied(422, "INVALID_ARGUMENT") from None
        return await prepared_result(authority, identifier)

    @router.post("/api/v2/c06/read-assistance-history")
    async def read_history(request: Request):
        _, authority = await authenticated(request)
        value = await read_payload(request, wire.AssistanceHistoryReadHttp)
        limit = value["page"].get("limit") or 20
        if type(limit) is not int or not 1 <= limit <= 100:
            raise BrowserDenied(422, "INVALID_ARGUMENT")
        rows = await run_in_threadpool(repository.history, authority, limit)
        wanted_version = value["paper"]["versionId"]
        items = []
        for row in rows:
            accepted = row["payload"].get("acceptedInput")
            if accepted is None or row["version_id"] != wanted_version:
                continue
            metadata = await run_in_threadpool(
                repository.source_metadata, authority, row["version_id"]
            )
            disposition = (metadata or {}).get("disposition", "unavailable")
            stored = row["result"]
            if stored and stored["availability"] != "retained":
                availability = stored["availability"]
            elif row["state"] == "failed":
                availability = "failed"
            elif row["state"] in ("accepted", "running"):
                availability = "pending"
            elif disposition == "withdrawn":
                availability = "withdrawn"
            elif disposition != "available":
                availability = "restricted"
            elif stored:
                availability = "ready"
            else:
                availability = "pending"
            items.append(
                {
                    "jobId": str(row["id"]),
                    "paper": {
                        "paperId": metadata["paperId"],
                        "versionId": metadata["versionId"],
                        "eligibilityRevision": str(metadata["eligibilityRevision"]),
                    },
                    "contentRevision": accepted["contentRevision"],
                    "contentHash": accepted["contentHash"],
                    "operation": accepted["operation"],
                    "optionId": accepted["optionId"],
                    "optionsRevision": accepted["optionsRevision"],
                    "glossaryRevision": accepted["glossaryRevision"],
                    "state": row["state"],
                    "revision": str(row["revision"]),
                    "seq": int(row["sequence"]),
                    "createdAt": row["accepted_at"].isoformat(),
                    "availability": availability,
                    "result": result_ref(stored),
                }
            )
        return wire.AssistanceHistoryPage.model_validate(
            {
                "items": items,
                "page": {
                    "nextCursor": None,
                    "snapshotRevision": str(rows[0]["revision"]) if rows else "synthetic-empty",
                },
            }
        ).model_dump(mode="json", exclude_none=True)

    @router.get("/api/v2/jobs/{job_id}/events")
    async def job_events(request: Request, job_id: str):
        authority = await get_authority(request)
        try:
            identifier = UUID(job_id)
        except ValueError:
            raise BrowserDenied(422, "INVALID_ARGUMENT") from None
        header = request.headers.get("last-event-id", "")
        cursor = int(header) if header.isdigit() else 0
        # Confirm access before the stream opens; later revocation ends it safely.
        await run_in_threadpool(repository.disposition_snapshot, authority, identifier)

        async def frames():
            sequence = cursor
            last_snapshot = -1
            deadline = time.monotonic() + PROGRESS_SECONDS
            try:
                while time.monotonic() < deadline:
                    if await request.is_disconnected():
                        return
                    for event in await run_in_threadpool(
                        repository.events, authority, identifier, sequence
                    ):
                        sequence = int(event["sequence"])
                        # Progress events carry the owner-allocated sequence in a
                        # single JSON line; frames are valid SSE without escaped
                        # newline artifacts.
                        yield _frame(sequence, "progress", event["snapshot"])
                    snapshot = await read_job(authority, identifier)
                    if snapshot["seq"] > last_snapshot:
                        last_snapshot = snapshot["seq"]
                        yield _frame(snapshot["seq"], "snapshot", snapshot)
                    if snapshot["state"] in TERMINAL:
                        return
                    await asyncio.sleep(POLL_SECONDS)
            except (PermissionError, ValueError):
                yield _frame(
                    None,
                    "error",
                    {
                        "code": "FORBIDDEN",
                        "requestId": str(identifier),
                        "retryable": False,
                        "messageKey": "job.forbidden",
                    },
                )

        return StreamingResponse(frames(), media_type="text/event-stream")

    return router
