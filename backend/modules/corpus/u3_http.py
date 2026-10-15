"""Canonical U3 CorpusContent browser bindings.

C04 operations: corpus-run acceptance/read/retry (maintenance authority),
source-eligibility change (maintenance authority), exact-version resolve/read
and opaque asset reads (current authenticated session; guests receive metadata
only through their separately authorized search response). Authority and
eligibility are derived from trusted server context; limits are validated
before expensive work.
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
    "source-permission-unresolved": "SOURCE_INELIGIBLE",
    "parsed-document-model-missing": "INVALID_CONTENT",
    "malformed-projection-chunk": "INVALID_CONTENT",
    "parsed-source-exceeds-the-finite-workspace-allocation": "INVALID_CONTENT",
    "immutable-source-identity-conflict": "CONFLICT",
    "immutable-parsed-content-conflict": "CONFLICT",
    "immutable-paper-metadata-conflict": "CONFLICT",
    "batch-receipts-missing": "NOT_READY",
    "publication-cas-conflict": "CONFLICT",
    "interrupted": "UNKNOWN_OUTCOME",
}


def _effect_error(run_id: str, code: str | None) -> dict | None:
    """A safe error envelope: unknown codes never echo raw evidence text."""
    if not code:
        return None
    if code not in _ERROR_CODES:
        return wire.Error.model_validate(
            {
                "code": "INTERNAL_ERROR",
                "requestId": run_id,
                "retryable": False,
                "messageKey": "run.unexpected",
            }
        ).model_dump(mode="json", exclude_none=True)
    return wire.Error.model_validate(
        {
            "code": _ERROR_CODES[code],
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


def corpus_router(transactions, *, entry, maintenance, reading) -> APIRouter:
    origin = transactions.profile.origin
    router = APIRouter(route_class=boundary_route(origin))

    async def authenticated(request: Request):
        operation, _, authority = await post_context(
            request, origin=origin, entry=entry, anonymous=None
        )
        if authority is None:
            raise BrowserDenied(401, "UNAUTHENTICATED")
        return operation, authority

    @router.post("/api/v2/c04/accept-corpus-run")
    async def accept_run(request: Request):
        operation, authority = await authenticated(request)
        value = await read_payload(request, wire.CorpusRunRequestHttp)
        result = await run_in_threadpool(maintenance.accept, authority, operation, value)
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

    @router.post("/api/v2/c04/retry-corpus-run")
    async def retry_run(request: Request):
        """C04 retryCorpusRun: reconciled retryable stages of the original run.

        The original run's authoritative inputs are re-read server-side; the
        request carries only the run identity, so retry can never change the
        intended inputs. Committed stages are carried forward, not re-executed.
        """
        operation, authority = await authenticated(request)
        value = await read_payload(request, wire.CorpusRunReadHttp)
        try:
            run_id = UUID(value["runId"])
        except (ValueError, TypeError):
            raise BrowserDenied(422, "INVALID_ARGUMENT") from None
        original = await run_in_threadpool(_original_run, maintenance, run_id)
        if original is None:
            raise BrowserDenied(404, "NOT_FOUND")
        result = await run_in_threadpool(
            maintenance.retry,
            authority,
            operation,
            {
                "operation": original["operation"],
                "sourceScopeIds": original["sourceScopeIds"],
                "authoritativeInputRevision": original["authoritativeInputRevision"],
                "inputManifestHash": original["inputManifestHash"],
                "retryOf": original["runId"],
            },
        )
        run = await run_in_threadpool(maintenance.read_run, authority, UUID(result["runId"]))
        return run_dto(run)

    @router.post("/api/v2/c04/change-source-eligibility")
    async def change_source_eligibility(request: Request):
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
        _, authority = await authenticated(request)
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
        _, authority = await authenticated(request)
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


def _original_run(maintenance, run_id) -> dict | None:
    """The original intended run's authoritative inputs, re-read server-side."""

    def read(conn):
        return conn.execute(
            "SELECT * FROM corpus.run WHERE id=%s", (run_id,)
        ).fetchone()

    row = maintenance.transactions.run("corpus", read)
    if row is None:
        return None
    return {
        "runId": str(row["id"]),
        "operation": row["operation"],
        "sourceScopeIds": [str(item) for item in row["source_scope"]],
        "authoritativeInputRevision": str(row["authoritative_input_revision"]),
        "inputManifestHash": row["input_manifest_hash"],
    }
