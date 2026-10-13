"""Canonical PaperAssistance browser bindings: options, acceptance, progress and results."""

from __future__ import annotations

import asyncio
import json
import time
from uuid import UUID

from backend.local_browser import (
    BrowserDenied,
    boundary_route,
    optional_authority,
    post_context,
    read_payload,
)
from backend.modules.corpus.repository import CorpusRepository
from backend.modules.plans.guarded_repository import (
    GuardedUsageRepository,
    UsageQuotaExceeded,
)
from backend.modules.summarization.admission import AssistanceAdmission
from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository
from backend.modules.summarization.local_catalog import catalog_for, unavailable_options
from backend.modules.summarization.local_result import decode_result
from backend.modules.summarization.requests import AssistanceRequests, AssistanceUnavailable
from docsuri_shared.workspace import wire
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

FAILURE_CODES = {
    "dependency-unavailable": "DEPENDENCY_UNAVAILABLE",
    "deadline-exceeded": "DEADLINE_EXCEEDED",
    "execution-deadline-exceeded": "DEADLINE_EXCEEDED",
    "invalid-source": "SOURCE_INELIGIBLE",
    "execution-authority-revoked": "FORBIDDEN",
    "job-recovery-window-expired": "NOT_READY",
    "execution-attempts-exhausted": "NOT_READY",
    "insufficient-result": "INVALID_CONTENT",
}
TERMINAL = ("succeeded", "failed")
PROGRESS_SECONDS = 30.0
POLL_SECONDS = 0.25
PARTIAL_NOTE = "선택한 원문 구간에 대한 결과입니다. 논문 전체 요약이 아닙니다."
NORMALIZATION_POLICY = {"policyId": "local-glossary", "revision": "1"}


def _frame(identifier, name: str, payload: dict) -> bytes:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    header = f"id: {identifier}\n" if identifier is not None else ""
    return f"{header}event: {name}\ndata: {body}\n\n".encode()


def _progress(state: str) -> dict:
    if state in TERMINAL:
        return {"mode": "determinate", "current": 1, "total": 1}
    return {"mode": "indeterminate"}


def _failure_error(job: dict) -> dict | None:
    if job["state"] != "failed":
        return None
    reason = job["failure_code"] or "unknown"
    return wire.Error.model_validate(
        {
            "code": FAILURE_CODES.get(reason, "INTERNAL_ERROR"),
            "requestId": str(job["id"]),
            "retryable": reason == "dependency-unavailable",
            "messageKey": "job." + reason,
        }
    ).model_dump(mode="json", exclude_none=True)


def snapshot_dto(job: dict, result_ref: dict | None) -> dict:
    return wire.JobSnapshot.model_validate(
        {
            "jobId": str(job["id"]),
            "kind": "paper-assistance",
            "state": job["state"],
            "revision": str(job["revision"]),
            "seq": int(job["sequence"]),
            "ownerId": str(job["account_id"]),
            "progress": _progress(job["state"]),
            "result": result_ref,
            "error": _failure_error(job),
            "acceptedAt": job["accepted_at"].isoformat(),
        }
    ).model_dump(mode="json", exclude_none=True)


def assistance_router(
    transactions, *, entry, files, quality_ready: bool, corpus_repository: CorpusRepository
) -> APIRouter:
    origin = transactions.profile.origin
    repository = GuardedAssistanceRepository(transactions, files)
    usage = GuardedUsageRepository(transactions)
    admission = AssistanceAdmission(repository, usage)
    requests = AssistanceRequests(
        admission,
        corpus_repository,
        lambda source: catalog_for(source, quality_ready=quality_ready),
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
        authority = await optional_authority(request, entry=entry)
        if authority is None:
            raise BrowserDenied(401, "UNAUTHENTICATED")
        return authority

    async def read_job(authority, job_id: UUID) -> dict:
        job = await run_in_threadpool(repository.snapshot, authority, job_id)
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
        """One owner-bound read path shared by the POST and GET bindings."""
        job = await run_in_threadpool(repository.snapshot, authority, job_id)
        result_row = await run_in_threadpool(repository.result_metadata, authority, job_id)
        if result_row is None:
            if job["state"] == "failed":
                return wire.AssistanceResultRead.model_validate(
                    {
                        "availability": "failed",
                        "jobId": str(job_id),
                        "reasonKey": "result." + (job["failure_code"] or "failed"),
                    }
                ).model_dump(mode="json", exclude_none=True)
            return wire.AssistanceResultRead.model_validate(
                {"availability": "pending", "jobId": str(job_id), "reasonKey": "result.pending"}
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
                    "limitations": [PARTIAL_NOTE],
                    "methodRevision": accepted["optionsRevision"],
                },
            }
        ).model_dump(mode="json", exclude_none=True)

    @router.post("/api/v2/c06/read-assistance-options")
    async def options(request: Request):
        _, _ = await authenticated(request)
        value = await read_payload(request, wire.AssistanceOptionsReadHttp)
        source = await run_in_threadpool(corpus_repository.read, value["paper"]["versionId"])
        if source["paper_id"] != value["paper"]["paperId"]:
            raise BrowserDenied(404, "NOT_FOUND")
        catalog = catalog_for(source, quality_ready=quality_ready)
        if catalog is None:
            return unavailable_options(source)
        return catalog.options()

    @router.post("/api/v2/c06/read-glossary")
    async def read_glossary(request: Request):
        _, authority = await authenticated(request)
        await read_payload(request, wire.AssistanceGlossaryReadHttp)
        row = await run_in_threadpool(repository.current_glossary, authority)
        return wire.AssistanceGlossary.model_validate(
            {
                "ownerId": str(authority.account_id),
                "revision": row["revision"],
                "normalizationPolicy": NORMALIZATION_POLICY,
                "terms": row["snapshot"],
            }
        ).model_dump(mode="json", exclude_none=True)

    @router.post("/api/v2/c06/accept-assistance")
    async def accept(request: Request):
        operation, authority = await authenticated(request)
        value = await read_payload(request, wire.AssistanceRequestHttp)
        await run_in_threadpool(usage.ensure_entitlement, authority)
        try:
            job = await run_in_threadpool(requests.submit, authority, operation, value)
        except AssistanceUnavailable:
            raise BrowserDenied(503, "NOT_READY") from None
        except UsageQuotaExceeded:
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
        except ValueError:
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
        except ValueError:
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
            if (
                accepted is None
                or accepted["paper"]["versionId"] != row["version_id"]
                or row["version_id"] != wanted_version
            ):
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
        await run_in_threadpool(repository.snapshot, authority, identifier)

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
                        yield _frame(sequence, "progress", event["snapshot"])
                    snapshot = await read_job(authority, identifier)
                    if snapshot["seq"] > last_snapshot:
                        last_snapshot = snapshot["seq"]
                        # Reconnect resumes from this authoritative sequence.
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
