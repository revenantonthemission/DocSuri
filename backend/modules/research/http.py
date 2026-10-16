"""C07 browser bindings; trusted worker operations are never public routes."""

from uuid import UUID

from docsuri_shared.workspace import wire
from fastapi import APIRouter, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from backend.local_browser import BrowserDenied, boundary_route, post_context, read_payload

from .errors import ResearchError

ERROR_STATUS = {
    "INVALID_ARGUMENT": 422,
    "INVALID_CONTENT": 422,
    "UNAUTHENTICATED": 401,
    "FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "CONFLICT": 409,
    "IDEMPOTENCY_CONFLICT": 409,
    "SNAPSHOT_EXPIRED": 409,
    "POLICY_UNRESOLVED": 503,
    "DEPENDENCY_UNAVAILABLE": 503,
    "CAPACITY_EXHAUSTED": 429,
    "QUOTA_EXCEEDED": 429,
    "SOURCE_INELIGIBLE": 403,
    "OUTCOME_UNKNOWN": 409,
}
PRIVATE_IDS = {"contextId", "sessionId", "jobId", "turnId", "artifactId", "draftId"}


def validate_private_ids(value):
    """Reject malformed local identities before passing a value to PostgreSQL."""
    if isinstance(value, dict):
        for name, item in value.items():
            if name in PRIVATE_IDS and item is not None:
                try:
                    UUID(item)
                except (ValueError, TypeError, AttributeError):
                    raise BrowserDenied(422, "INVALID_ARGUMENT") from None
            validate_private_ids(item)
    elif isinstance(value, list):
        for item in value:
            validate_private_ids(item)


def research_router(transactions, *, entry, service) -> APIRouter:
    origin = transactions.profile.origin
    router = APIRouter(route_class=boundary_route(origin, missing=(404, "NOT_FOUND")))

    def cancel(authority, value):
        if value["kind"] != "novelty-analysis":
            raise ResearchError("INVALID_ARGUMENT")
        snapshot = service.read_job(authority, value)
        row = service.jobs.cancel(
            authority, value["jobId"], value["contextId"], snapshot["revision"]
        )
        return service.snapshot(authority, row)

    def invoke(name, method, authority, operation, value):
        if name in ("create-research-context", "create-research-session"):
            return method(authority, value, operation=operation)
        if name == "delete-research-sessions":
            # The generated model does not implement JSON Schema if/then.
            if (value["scope"] == "one-session") != ("sessionId" in value):
                raise ResearchError("INVALID_ARGUMENT")
            return method(authority, value, operation=operation)
        return method(authority, value)

    def route(name, schema, output, method):
        async def handler(request: Request):
            operation, _, authority = await post_context(
                request, origin=origin, entry=entry, anonymous=None
            )
            value = await read_payload(request, schema)
            validate_private_ids(value)
            try:
                result = await run_in_threadpool(invoke, name, method, authority, operation, value)
            except ResearchError as exc:
                if exc.code not in ERROR_STATUS:
                    raise BrowserDenied(500, "INTERNAL_ERROR") from None
                raise BrowserDenied(ERROR_STATUS[exc.code], exc.code) from None
            try:
                return output.model_validate(result).model_dump(mode="json", exclude_unset=True)
            except ValidationError:
                # Malformed service output is never a client's invalid-input response.
                raise BrowserDenied(500, "INTERNAL_ERROR") from None

        handler.__name__ = name.replace("-", "_")
        router.add_api_route("/api/v2/c07/" + name, handler, methods=["POST"])

    for name, schema, output, method in (
        (
            "create-research-context",
            wire.ResearchContextCreateHttp,
            wire.ResearchContext,
            service.create_context,
        ),
        (
            "create-research-session",
            wire.ResearchSessionCreateHttp,
            wire.ResearchSession,
            service.create_session,
        ),
        (
            "read-research-session",
            wire.ResearchSessionReadHttp,
            wire.ResearchSession,
            service.read_session,
        ),
        (
            "list-research-sessions",
            wire.ResearchSessionListHttp,
            wire.ResearchSessions,
            service.list_sessions,
        ),
        (
            "delete-research-sessions",
            wire.ResearchDeleteHttp,
            wire.ResearchDeletion,
            service.delete_sessions,
        ),
        ("read-research-turn", wire.ResearchTurnReadHttp, wire.ResearchTurn, service.read_turn),
        ("read-research-job", wire.ResearchJobReadHttp, wire.JobSnapshot, service.read_job),
        ("cancel-novelty-analysis", wire.ResearchJobReadHttp, wire.JobSnapshot, cancel),
        (
            "read-research-artifact",
            wire.ResearchArtifactReadHttp,
            wire.ResearchArtifactResponse,
            service.read_artifact,
        ),
        (
            "begin-private-attachment",
            wire.ResearchAttachmentStartHttp,
            wire.ResearchUploadPermit,
            service.suspended_private,
        ),
        (
            "finish-private-attachment",
            wire.ResearchAttachmentFinishHttp,
            wire.ResearchAttachment,
            service.suspended_private,
        ),
        (
            "read-private-attachment",
            wire.ResearchAttachmentReadHttp,
            wire.ResearchAttachment,
            service.suspended_private,
        ),
        (
            "read-private-asset",
            wire.ResearchPrivateAssetReadHttp,
            wire.ResearchPrivateAsset,
            service.suspended_private,
        ),
        ("save-draft", wire.DraftWriteHttp, wire.DraftWriteResult, service.suspended_private),
        ("restore-draft", wire.DraftReadHttp, wire.DraftRecovery, service.suspended_private),
        ("discard-draft", wire.DraftDiscardHttp, wire.Ack, service.suspended_private),
    ):
        route(name, schema, output, method)

    def accept_route(name, schema, kind):
        async def handler(request: Request):
            operation, _, authority = await post_context(
                request, origin=origin, entry=entry, anonymous=None
            )
            value = await read_payload(request, schema)
            validate_private_ids(value)
            try:
                result = await run_in_threadpool(service.accept, authority, operation, value, kind)
            except ResearchError as exc:
                if exc.code not in ERROR_STATUS:
                    raise BrowserDenied(500, "INTERNAL_ERROR") from None
                raise BrowserDenied(ERROR_STATUS[exc.code], exc.code) from None
            try:
                return wire.JobReceipt.model_validate(result).model_dump(mode="json")
            except ValidationError:
                raise BrowserDenied(500, "INTERNAL_ERROR") from None

        handler.__name__ = name.replace("-", "_")
        router.add_api_route("/api/v2/c07/" + name, handler, methods=["POST"])

    accept_route("accept-research-turn", wire.ResearchTurnRequestHttp, "research-turn")
    accept_route("accept-novelty-analysis", wire.ResearchNoveltyRequestHttp, "novelty-analysis")
    accept_route(
        "accept-novelty-discussion", wire.ResearchNoveltyDiscussionHttp, "novelty-discussion"
    )
    return router
