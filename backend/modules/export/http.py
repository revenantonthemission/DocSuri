"""C09 browser bindings for ApprovedExport (C09 2.1.0), table-driven like `research_router`.

Eleven POST routes at `/api/v2/c09/<operation>`: the nine frozen operations plus
`list-export-history` (A2) and `settle-export-effect` (A3). Each route:

1. runs `post_context`: origin, the bounded CSRF header, the Idempotency-Key and the
   server-derived principal (an anonymous caller is refused before any owner work);
2. reads the body through `read_payload` with the generated `*Http` model, so the
   declared contract shape is authoritative and FastAPI's own validation response, which
   echoes the input, is never used;
3. checks the private identifiers (a malformed one answers 422 before PostgreSQL);
4. calls the synchronous `ExportService` through `run_in_threadpool`, because every
   adapter operation runs in its own event loop and must never run inside this one.

Refusals: an `ExportError` maps through `ERROR_STATUS`; CAPACITY_EXHAUSTED carries its
wait as the body field `retryAfterSeconds` and never as a `Retry-After` header. A foreign
or absent record (`LookupError`) and a refused own session (`InsufficientPrivilege`) are
the shared boundary's NOT_FOUND. Every other platform answer (UNKNOWN_OUTCOME, RATE_LIMITED,
DEADLINE_EXCEEDED) stays exactly as the shared boundary produces it. Output goes through
the generated output model; a malformed service result is a 500, never a client error.
Nothing here logs a request body, a token or an exception object.
"""

from uuid import UUID

from docsuri_shared.workspace import wire
from fastapi import APIRouter, Request
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from backend.local_browser import BrowserDenied, boundary_route, post_context, read_payload

from .errors import ExportError, ProtectionUnavailable

PREFIX = "/api/v2/c09/"
ERROR_STATUS = {
    "INVALID_ARGUMENT": 422,
    "INVALID_TOKEN": 422,
    "UNAUTHENTICATED": 401,
    "FORBIDDEN": 403,
    "SOURCE_INELIGIBLE": 403,
    "NOT_FOUND": 404,
    "CONFLICT": 409,
    "IDEMPOTENCY_CONFLICT": 409,
    "APPROVAL_REQUIRED": 409,
    "OUTCOME_UNKNOWN": 409,
    "CAPACITY_EXHAUSTED": 429,
    "POLICY_UNRESOLVED": 503,
    "DEPENDENCY_UNAVAILABLE": 503,
}
# Local record identities that must be UUIDs before any owner transaction. Notion page
# identifiers (32 hex) and revisions are checked by the service itself.
PRIVATE_IDS = frozenset({"connectionId", "previewId", "approvalId", "effectId", "artifactId"})
# Operations that keep an idempotency record take the request's Idempotency-Key.
KEYED = frozenset({"configure", "approve", "execute", "settle"})
# (route name, request model, response model, service method name)
OPERATIONS = (
    (
        "configure-notion-connection",
        wire.ExportConnectionConfigureHttp,
        wire.ExportConnection,
        "configure",
    ),
    (
        "read-notion-connection",
        wire.ExportConnectionReadHttp,
        wire.ExportConnection,
        "read_connection",
    ),
    ("disconnect-notion", wire.ExportConnectionReadHttp, wire.ExportConnection, "disconnect"),
    (
        "list-export-destinations",
        wire.ExportConnectionReadHttp,
        wire.ExportDestinations,
        "list_destinations",
    ),
    (
        "prepare-export-preview",
        wire.ExportPreviewRequestHttp,
        wire.ExportPreview,
        "prepare_preview",
    ),
    ("approve-export-preview", wire.ExportApprovalRequestHttp, wire.ExportApproval, "approve"),
    ("execute-approved-export", wire.ExportExecuteHttp, wire.ExportEffect, "execute"),
    ("read-export-effect", wire.ExportEffectReadHttp, wire.ExportEffect, "read_effect"),
    ("cancel-export-approval", wire.ExportCancelHttp, wire.ExportApproval, "cancel"),
    ("list-export-history", wire.ExportHistoryListHttp, wire.ExportHistoryPage, "history"),
    ("settle-export-effect", wire.ExportSettleHttp, wire.ExportEffect, "settle"),
)
ROUTES = tuple(PREFIX + name for name, *_ in OPERATIONS)


def validate_private_ids(value) -> None:
    """Reject a malformed local identity before passing a value to PostgreSQL."""
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


def refusal(error: ExportError) -> BrowserDenied:
    """The browser answer for a domain refusal; an unmapped code is a server fault."""
    status = ERROR_STATUS.get(error.code)
    if status is None:
        return BrowserDenied(500, "INTERNAL_ERROR")
    if error.code == "CAPACITY_EXHAUSTED":
        return BrowserDenied(429, "CAPACITY_EXHAUSTED", retry_after=error.retry_after)
    return BrowserDenied(status, error.code)


def _invoke(service, method: str, authority, operation, value):
    call = getattr(service, method)
    if method in KEYED:
        return call(authority, value, operation=operation)
    return call(authority, value)


def export_router(transactions, *, entry, service) -> APIRouter:
    origin = transactions.profile.origin
    router = APIRouter(route_class=boundary_route(origin, missing=(404, "NOT_FOUND")))

    def route(name: str, schema, output, method: str) -> None:
        async def handler(request: Request):
            operation, _, authority = await post_context(
                request, origin=origin, entry=entry, anonymous=None
            )
            value = await read_payload(request, schema)
            validate_private_ids(value)
            denied = None
            try:
                result = await run_in_threadpool(
                    _invoke, service, method, authority, operation, value
                )
            except ExportError as error:
                denied = refusal(error)
            except ProtectionUnavailable:
                # Custody faults are reduced inside the service; one that escapes is
                # still the unresolved credential policy, never a 500 with its text.
                denied = BrowserDenied(503, "POLICY_UNRESOLVED")
            if denied is not None:
                # Raised after the except block has ended: no cause or context travels.
                raise denied
            try:
                return output.model_validate(result).model_dump(mode="json", exclude_unset=True)
            except ValidationError:
                # Malformed service output is never a client's invalid-input response.
                raise BrowserDenied(500, "INTERNAL_ERROR") from None

        handler.__name__ = name.replace("-", "_")
        router.add_api_route(PREFIX + name, handler, methods=["POST"])

    for name, schema, output, method in OPERATIONS:
        route(name, schema, output, method)
    return router
