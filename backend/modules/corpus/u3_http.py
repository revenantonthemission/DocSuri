"""Canonical U3 CorpusContent browser bindings.

C04 operations: corpus-run acceptance/read (maintenance authority), eligibility
change (maintenance authority), exact-version resolve/read (guest-allowed) and
opaque asset reads (authenticated). Authority and eligibility are derived from
trusted server context; limits are validated before expensive work.
"""

from __future__ import annotations

from uuid import UUID

from backend.local_browser import (
    BrowserDenied,
    boundary_route,
    post_context,
    read_payload,
)
from backend.modules.corpus.reading import ContentUnavailable
from docsuri_shared.workspace import wire
from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

_JOB_STATES = {
    "accepted": "accepted",
    "running": "running",
    "completed": "succeeded",
    "failed": "failed",
    "unknown": "failed",
}
_ERROR_CODES = {
    "source-unavailable": "NOT_FOUND",
    "permission-unresolved": "SOURCE_INELIGIBLE",
    "invalid-source": "INVALID_CONTENT",
    "batch-receipts-missing": "NOT_READY",
    "publication-cas-conflict": "CONFLICT",
    "interrupted": "UNKNOWN_OUTCOME",
}


def _effect_error(run_id: str, code: str | None) -> dict | None:
    if not code:
        return None
    return wire.Error.model_validate(
        {
            "code": _ERROR_CODES.get(code, "INTERNAL_ERROR"),
            "requestId": run_id,
            "retryable": code in ("interrupted",),
            "messageKey": "run." + code,
        }
    ).model_dump(mode="json", exclude_none=True)


def run_dto(run: dict) -> dict:
    run_id = run["runId"]
    state = _JOB_STATES.get(run["state"], "failed")
    job = wire.JobSnapshot.model_validate(
        {
            "jobId": run_id,
            "kind": "corpus-run",
            "state": state,
            "revision": run["revision"],
            "seq": run["attempts"],
            "ownerId": "corpus-maintenance",
            "progress": (
                {"mode": "determinate", "current": 1, "total": 1}
                if state in ("succeeded", "failed")
                else {"mode": "indeterminate"}
            ),
            "result": None,
            "error": _effect_error(run_id, "interrupted") if state == "failed" else None,
            "acceptedAt": run["acceptedAt"],
        }
    ).model_dump(mode="json", exclude_none=True)
    effects = [
        {
            "effectId": f"{effect['stage']}:{effect['subject']}"[:160],
            "stage": effect["stage"],
            "state": effect["state"],
            "evidenceHash": effect["evidenceHash"],
            "error": _effect_error(run_id, effect["error"]),
        }
        for effect in run["effects"]
    ]
    return {
        "runId": run_id,
        "revision": run["revision"],
        "job": job,
        "inputManifestHash": run["inputManifestHash"],
        "effects": effects,
        "committedWatermark": (
            run["watermark"]["generationId"] if run["watermark"] else None
        ),
        "publicationGeneration": (
            run["watermark"]["generationId"] if run["watermark"] else None
        ),
    }


def _change_kind(disposition: str, reason_key: str) -> str:
    """The C04 eligibility operation carries no explicit kind; derive deterministically."""
    for prefix, kind in (
        ("withdraw", "withdrawal"),
        ("license", "license-change"),
        ("access", "access-change"),
        ("canonical", "canonicalization"),
        ("version", "version-change"),
    ):
        if reason_key.lower().startswith(prefix):
            return kind
    if disposition == "withdrawn":
        return "withdrawal"
    if disposition in ("restricted", "unavailable"):
        return "access-change"
    return "canonicalization"


def corpus_router(
    transactions, *, entry, anonymous, maintenance, reading
) -> APIRouter:
    origin = transactions.profile.origin
    router = APIRouter(route_class=boundary_route(origin))

    async def authenticated(request: Request):
        operation, _, authority = await post_context(
            request, origin=origin, entry=entry, anonymous=None
        )
        if authority is None:
            raise BrowserDenied(401, "UNAUTHENTICATED")
        return operation, authority

    async def optional(request: Request):
        operation, _, authority = await post_context(
            request, origin=origin, entry=entry, anonymous=anonymous
        )
        return operation, authority

    @router.post("/api/v2/c04/accept-corpus-run")
    async def accept_run(request: Request):
        operation, authority = await authenticated(request)
        value = await read_payload(request, wire.CorpusRunRequestHttp)
        if value["operation"] == "reprocess":
            digest_run = await run_in_threadpool(
                _latest_reconcilable, maintenance, authority, value
            )
            if digest_run is None:
                raise BrowserDenied(409, "CONFLICT")
            result = await run_in_threadpool(
                maintenance.retry,
                authority,
                operation,
                {
                    "operation": digest_run["operation"],
                    "sourceScopeIds": value["sourceScopeIds"],
                    "authoritativeInputRevision": value["authoritativeInputRevision"],
                    "inputManifestHash": value["inputManifestHash"],
                    "retryOf": digest_run["runId"],
                },
            )
        else:
            result = await run_in_threadpool(
                maintenance.accept, authority, operation, value
            )
        run = await run_in_threadpool(maintenance.read_run, authority, UUID(result["runId"]))
        return run_dto(run)

    @router.post("/api/v2/c04/read-corpus-run")
    async def read_run(request: Request):
        _, authority = await authenticated(request)
        value = await read_payload(request, wire.CorpusRunReadHttp)
        try:
            run_id = UUID(value["runId"])
        except (ValueError, TypeError):
            raise BrowserDenied(422, "INVALID_ARGUMENT") from None
        run = await run_in_threadpool(maintenance.read_run, authority, run_id)
        return run_dto(run)

    @router.post("/api/v2/c04/record-eligibility-change")
    async def record_change(request: Request):
        _, authority = await authenticated(request)
        value = await read_payload(request, wire.CorpusEligibilityChangeHttp)
        result = await run_in_threadpool(
            maintenance.record_change,
            authority,
            {
                "paperId": value["paper"]["paperId"],
                "versionId": value["paper"]["versionId"],
                "changeKind": _change_kind(value["disposition"], value["reasonKey"]),
                "disposition": value["disposition"],
                "reasonKey": value["reasonKey"],
                "evidenceHash": value["sourceEvidenceHash"],
                "policy": value["policy"],
            },
        )
        return wire.Ack.model_validate(
            {
                "resourceId": result["factId"],
                "revision": result["eligibilityRevision"],
                "requestId": result["factId"],
            }
        ).model_dump(mode="json")

    @router.post("/api/v2/c04/resolve-paper")
    async def resolve(request: Request):
        operation, authority = await optional(request)
        value = await read_payload(request, wire.CorpusResolveHttp)
        row = await run_in_threadpool(
            reading.resolve, authority, value["identifier"], value.get("versionLabel")
        )
        if row is None:
            raise BrowserDenied(404, "NOT_FOUND")
        return wire.CorpusIdentity.model_validate(
            {
                "paper": {
                    "paperId": row["paperId"],
                    "versionId": row["versionId"],
                    "eligibilityRevision": row["eligibilityRevision"],
                },
                "requestedIdentifier": value["identifier"],
                "canonicalDisposition": row["canonicalDisposition"],
                "metadataRevision": row["metadataRevision"],
                "title": row["title"],
                "sourceUrls": [row["sourceUrl"]],
                "policy": {"policyId": "u3-paper-reading", "revision": "1"},
            }
        ).model_dump(mode="json", exclude_none=True)

    @router.post("/api/v2/c04/read-content")
    async def read_content(request: Request):
        _, authority = await optional(request)
        value = await read_payload(request, wire.CorpusReadHttp)
        result = await run_in_threadpool(
            reading.read_content, authority, value["paper"], value["purpose"]
        )
        if result["availability"] == "available":
            return wire.CorpusContentRead.model_validate(
                {
                    "availability": "ready",
                    "content": {
                        "paper": {
                            "paperId": result["paperId"],
                            "versionId": result["versionId"],
                            "eligibilityRevision": result["eligibilityRevision"],
                        },
                        "contentRevision": result["contentRevision"],
                        "contentHash": result["contentHash"],
                        "sections": result["sections"],
                        "assets": result["assets"],
                        "sourceUrls": [result["sourceUrl"]],
                        "coverage": result["coverage"],
                        "limitations": result["limitations"],
                        "policy": {"policyId": "u3-paper-reading", "revision": "1"},
                    },
                }
            ).model_dump(mode="json", exclude_none=True)
        if result["availability"] == "absent":
            raise BrowserDenied(404, "NOT_FOUND")
        return wire.CorpusContentRead.model_validate(
            {
                "availability": result["availability"],
                "paper": {
                    "paperId": result["paperId"],
                    "versionId": result["versionId"],
                    "eligibilityRevision": result["eligibilityRevision"],
                },
                "reasonKey": "source." + result["availability"],
                "retryable": bool(result["retryable"]),
            }
        ).model_dump(mode="json", exclude_none=True)

    @router.post("/api/v2/c04/read-asset")
    async def read_asset(request: Request):
        _, authority = await authenticated(request)
        value = await read_payload(request, wire.CorpusAssetReadHttp)
        try:
            asset = await run_in_threadpool(
                reading.read_asset,
                authority,
                value["paper"],
                value["contentRevision"],
                value["assetId"],
            )
        except (ContentUnavailable, PermissionError):
            raise BrowserDenied(404, "NOT_FOUND") from None
        return wire.CorpusAsset.model_validate(
            {
                "paper": value["paper"],
                "asset": {
                    "assetId": asset["assetId"],
                    "mediaType": asset["mediaType"],
                    "contentHash": asset["contentHash"],
                    "altText": asset["altText"],
                    "sectionId": None,
                },
                "readHandle": asset["assetId"],
                "policy": asset["policy"],
            }
        ).model_dump(mode="json", exclude_none=True)

    return router


def _latest_reconcilable(maintenance, authority, value):
    """The original intended run matched by its authoritative inputs, if any."""

    from psycopg.types.json import Jsonb

    def read(conn):
        return conn.execute(
            "SELECT * FROM corpus.run WHERE input_manifest_hash=%s AND "
            "source_scope=%s::jsonb AND state IN ('failed','unknown','running') "
            "ORDER BY accepted_at DESC LIMIT 1",
            (value["inputManifestHash"], Jsonb(value["sourceScopeIds"])),
        ).fetchone()

    row = maintenance.transactions.run("corpus", read)
    if row is None:
        return None
    return {"runId": str(row["id"]), "operation": row["operation"]}
