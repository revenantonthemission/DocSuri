"""Thin FastAPI router — POST /api/summarize (SummarizationController).

Request validation (SEC-5), trust the gateway-injected principal (SEC-8), delegate to the
gateway seam, and serialize the terminal response via its SEC-9-safe ``to_dict``. The
response is the buffer-validated result (Q5/BR-S8): the client renders progressively from
already-grounded fields. A global handler keeps internals out of error responses (INV-4).
"""

from __future__ import annotations

from typing import Any

from docsuri_shared.private_docs import is_private_paper_id
from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse, Response

from ..adapters._paper_ref import paper_version
from ..api.gateway_seam import run_summarization
from ..domain.models import (
    AuthSession,
    Persona,
    RequestContext,
    Scope,
    SummaryRequest,
    TargetLang,
    Task,
)
from ..service.orchestrator import SummarizationOrchestrationService

# REM-2 F01 (SECURITY-08) / FD-Q1: the private ``userdoc:`` namespace is served ONLY by the
# owner-verified private route below. Every PUBLIC corpus route refuses it with this single
# body — a 404 that is byte-identical whether or not the document exists, so a caller can use
# neither the status code nor the body as an existence oracle, and the refusal happens BEFORE
# any store/queue access so no cross-tenant read is even attempted.
_PRIVATE_NAMESPACE_404 = {"status": "not_found"}


def build_router(
    orchestrator: SummarizationOrchestrationService,
    *,
    assets_enabled: bool = False,
    docmodel_enabled: bool = False,
) -> Any:
    router = APIRouter()

    @router.post("/api/summarize")
    def summarize(request: Request, payload: dict = Body(...)) -> Any:  # noqa: B008
        user_id = _principal_user_id(request)
        if not user_id:
            return JSONResponse({"status": "unauthorized"}, status_code=401)

        parsed = _parse_request(payload)
        if parsed is None:
            # Gap #2: carry a message so the client maps this to the "check your input"
            # path instead of a generic error (BR-S17).
            return JSONResponse(
                {"status": "validation_error", "message": "요청을 확인해 주세요."},
                status_code=400,
            )
        # Summarization is a corpus capability. A private ``userdoc:`` id must never reach the
        # pipeline (F01: it would resolve a private doc-model as the summary source and cache a
        # derived artifact under a caller-supplied id), so it is refused here, not deeper down.
        if is_private_paper_id(parsed.paper_id):
            return JSONResponse(_PRIVATE_NAMESPACE_404, status_code=404)

        ctx = RequestContext(
            auth_session=AuthSession(user_id=user_id),
            request_id=request.headers.get("x-request-id", ""),
        )
        response = run_summarization(orchestrator, parsed, ctx)
        return JSONResponse(response.to_dict())

    @router.get("/api/glossary")
    def list_glossary(request: Request) -> Any:
        """The caller's saved personal terms (개인 용어집 Phase 2a) — pre-fills the badge editor.
        Owner-scoped (SEC-8): returns only the principal's own terms. Fails closed (INV-4)."""
        user_id = _principal_user_id(request)
        if not user_id:
            return JSONResponse({"status": "unauthorized"}, status_code=401)
        try:
            terms = orchestrator.list_glossary_terms(user_id)
        except Exception:  # noqa: BLE001 — fail-closed; client degrades to no pre-fill
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ok", "terms": terms})

    @router.post("/api/glossary")
    def upsert_glossary_term(request: Request, payload: dict = Body(...)) -> Any:  # noqa: B008
        """Add/override a personal term (개인 용어집 Phase 1). Owner-scoped (SEC-8): the
        gateway-injected principal is the only id trusted — the body never carries a user id.
        A state-changing request (CSRF is the gateway's concern). Validates input (SEC-5) and
        fails closed without surfacing internals (INV-4)."""
        user_id = _principal_user_id(request)
        if not user_id:
            return JSONResponse({"status": "unauthorized"}, status_code=401)
        term = _parse_glossary_term(payload)
        if term is None:
            return JSONResponse({"status": "validation_error"}, status_code=400)
        term_from, term_to, prompt_enforced = term
        try:
            glossary_ver = orchestrator.upsert_glossary_term(
                user_id, term_from, term_to, prompt_enforced=prompt_enforced
            )
        except Exception:  # noqa: BLE001 — fail-closed: never surface internals (INV-4/SEC-15)
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ok", "glossaryVer": glossary_ver}, status_code=201)

    @router.get("/api/papers/{paper_id}/doc-model")
    def doc_model(request: Request, paper_id: str) -> Any:
        """Structured doc-model for the rich view / summary input (BR-30, D4). OA-license-gated
        (BR-SF-11): the OA signal is the U1 ingestion gate — only OA papers (CC-BY/CC-BY-SA/CC0,
        BR-1) are stored, so any corpus paper is license-safe to render and this flag is an
        operational toggle (OFF by default → ``license_unavailable`` arXiv link-out until the team
        enables it at deploy). Returns the cached artifact when present; a
        miss (re)triggers U1's lazy build and surfaces ``building`` (client polls) when a build
        queue is wired, else ``source_unavailable`` (D6, boundary B). The doc-model is
        url-free (SEC-9): figure signed URLs come from the parallel ``/assets`` manifest,
        joined by ``assetId`` on the client."""
        user_id = _principal_user_id(request)
        if not user_id:
            return JSONResponse({"status": "unauthorized"}, status_code=401)
        # REM-2 F01: refuse the private namespace before ANY branch — including the license gate
        # below, whose 200 "license_unavailable" would otherwise make the private namespace
        # resolvable (existence/state) on a deployment with doc-model disabled (see the module
        # constant: the refusal must hold before any store/queue access).
        if is_private_paper_id(paper_id):
            return JSONResponse(_PRIVATE_NAMESPACE_404, status_code=404)
        if not docmodel_enabled:
            return JSONResponse({"status": "license_unavailable"})
        # FE sends ?version=<arXiv revision> (lib/arxivVersion.ts); if a client omits it, fall
        # back to the revision embedded in the path id rather than a hardcoded v1 — else a revised
        # paper (v2+) reads a non-existent v1 doc-model → perpetual "building"/source_unavailable.
        raw_version = request.query_params.get("version")
        try:
            version = int(raw_version) if raw_version is not None else paper_version(paper_id)
        except (TypeError, ValueError):
            version = paper_version(paper_id)
        try:
            result = orchestrator.doc_model(paper_id, version)
        except Exception:  # noqa: BLE001 — fail-closed: a store/queue fault must not surface as a
            # raw 500 (INV-4/SEC-15). A bare 500 here is also what the client retried in a tight
            # loop; a generic 503 keeps internals out and lets the client back off / show a retry.
            return JSONResponse({"status": "unavailable"}, status_code=503)
        if result.doc is not None:
            return JSONResponse(
                {
                    "status": "ok",
                    "cached": True,
                    "docModel": result.doc.model_dump(mode="json", exclude_none=True),
                }
            )
        if result.building:
            # Lazy build (re)triggered on a miss — client polls again after the hint (BR-30/D6).
            body: dict[str, Any] = {"status": "building"}
            if result.retry_after_ms is not None:
                body["retryAfterMs"] = result.retry_after_ms
            return JSONResponse(body)
        return JSONResponse({"status": "source_unavailable"})

    @router.get("/api/papers/{paper_id}/assets")
    def paper_assets(request: Request, paper_id: str) -> Any:
        """FR-17 figure/table manifest for the detail/viewer. OA-license-gated like
        full-text (BR-SF-11): disabled by default → ``license_unavailable``. Each entry carries a
        **same-origin** delivery path (SEC-9/F07) — no object key, no bucket, no storage host — and
        is served by the ``/assets/{asset_id}`` endpoint below, which re-checks before delivering.
        Independent of the full-text viewer (D1)."""
        user_id = _principal_user_id(request)
        if not user_id:
            return JSONResponse({"status": "unauthorized"}, status_code=401)
        # REM-2 F07/F01: the asset manifest is keyed on the same caller-supplied id, so it shares
        # the private-namespace refusal (an owner has no assets here; see the private route) — and
        # refuses before the license gate for the same reason as the doc-model route.
        if is_private_paper_id(paper_id):
            return JSONResponse(_PRIVATE_NAMESPACE_404, status_code=404)
        if not assets_enabled:
            return JSONResponse({"status": "license_unavailable"})
        # ?version fallback mirrors the doc-model handler: the path id's arXiv revision, not v1.
        raw_version = request.query_params.get("version")
        try:
            version = int(raw_version) if raw_version is not None else paper_version(paper_id)
        except (TypeError, ValueError):
            version = paper_version(paper_id)
        try:
            refs = orchestrator.list_assets(paper_id, version)
        except Exception:  # noqa: BLE001 — fail-closed (INV-4/SEC-15): an RDS/S3 fault returns a
            # generic 503, not a raw 500 leaking internals (parity with the doc-model handler).
            return JSONResponse({"status": "unavailable"}, status_code=503)
        if refs is None:
            return JSONResponse({"status": "license_unavailable"})
        return JSONResponse({"status": "ok", "assets": [r.to_dict() for r in refs]})

    @router.get("/api/papers/{paper_id}/assets/{asset_id}")
    def paper_asset_bytes(request: Request, paper_id: str, asset_id: str) -> Any:
        """Same-origin asset delivery (REM-2 F07 / SECURITY-08 / FR-17).

        The manifest used to hand the browser a presigned object-storage URL, which leaked the
        object key and the storage host (``AWS_ENDPOINT_URL_S3`` → MinIO locally) and moved the
        fetch outside every check this service makes. So the bytes are served here instead, and
        **every check is re-run at delivery**:

          * the principal (SEC-8) — an unauthenticated GET never reaches the object store;
          * the private ``userdoc:`` namespace (F01) — refused with the same 404, before the
            license gate, so it is not resolvable on a deployment with assets disabled;
          * the OA license gate (BR-SF-11) — re-read here, because a manifest entry outlives the
            decision that produced it;
          * the object itself — the reader resolves (paper, version, asset) through the manifest,
            so an ``asset_id`` on its own is not a capability.

        A miss is a 404 whether the asset does not exist or does not belong to this paper/version,
        so the endpoint cannot be used to enumerate ids.
        """
        user_id = _principal_user_id(request)
        if not user_id:
            return JSONResponse({"status": "unauthorized"}, status_code=401)
        if is_private_paper_id(paper_id):
            return JSONResponse(_PRIVATE_NAMESPACE_404, status_code=404)
        if not assets_enabled:
            return JSONResponse({"status": "license_unavailable"})
        # ?version fallback mirrors the manifest handler above: the path id's revision, not v1.
        raw_version = request.query_params.get("version")
        try:
            version = int(raw_version) if raw_version is not None else paper_version(paper_id)
        except (TypeError, ValueError):
            version = paper_version(paper_id)
        if version < 1:
            return JSONResponse(_PRIVATE_NAMESPACE_404, status_code=404)
        try:
            obj = orchestrator.get_asset_object(paper_id, version, asset_id)
        except Exception:  # noqa: BLE001 — fail-closed (INV-4/SEC-15), parity with the manifest
            return JSONResponse({"status": "unavailable"}, status_code=503)
        if obj is None:
            return JSONResponse(_PRIVATE_NAMESPACE_404, status_code=404)
        return Response(
            content=obj.payload,
            media_type=obj.content_type,
            headers={
                # Authenticated delivery: a shared cache must never hold these bytes for another
                # caller. Bounded reuse for the single caller's own repeat view.
                "cache-control": "private, max-age=60",
                "x-content-type-options": "nosniff",
            },
        )

    @router.get("/api/userdoc/{doc_id}/doc-model")
    def private_doc_model(request: Request, doc_id: str) -> Any:
        """Owner-verified read of a private (user-uploaded) doc-model — REM-2 F01 / FD-Q1.

        The dedicated private route the corpus routes refer to: the owner's own
        ``private/userdoc/{owner}/{docId}/`` prefix is the ONLY one probed, so a request for
        another tenant's ``docId`` misses and returns the SAME 404 a nonexistent id returns. No
        existence oracle, no cross-tenant read, no reliance on the caller being the owner.

        Read-only: it never triggers a build (the upload flow drives builds), so a miss surfaces
        as ``source_unavailable``. The response is url-free (SEC-9), matching the corpus route —
        private figure delivery is the F07 same-origin endpoint's job.
        """
        user_id = _principal_user_id(request)
        if not user_id:
            return JSONResponse({"status": "unauthorized"}, status_code=401)
        raw_version = request.query_params.get("version")
        try:
            version = int(raw_version) if raw_version is not None else 1
        except (TypeError, ValueError):
            version = 1
        if version < 1:
            return JSONResponse(_PRIVATE_NAMESPACE_404, status_code=404)
        try:
            result = orchestrator.private_doc_model(user_id, doc_id, version)
        except Exception:  # noqa: BLE001 — fail-closed (INV-4/SEC-15), parity with the corpus
            # route: a store fault is a generic 503, never a raw 500 leaking internals.
            return JSONResponse({"status": "unavailable"}, status_code=503)
        if result.doc is not None:
            return JSONResponse(
                {
                    "status": "ok",
                    "cached": True,
                    "docModel": result.doc.model_dump(mode="json", exclude_none=True),
                }
            )
        # A miss here is either "not built yet" or "not yours" — both are reported as the SAME
        # 404 the corpus route returns for a private id, so the status code cannot be used as an
        # existence oracle for another tenant's document. (Deliberately NOT the corpus route's
        # ``source_unavailable`` 200, which would itself distinguish "yours, not built yet".)
        return JSONResponse(_PRIVATE_NAMESPACE_404, status_code=404)

    return router


def _principal_user_id(request: Any) -> str | None:
    """Extract the gateway-injected principal's user id (SEC-8). Trusts the gateway."""
    principal = getattr(request.state, "principal", None)
    if not principal:
        return None
    uid = getattr(principal, "user_id", None)
    if uid is None and isinstance(principal, dict):
        uid = principal.get("user_id")
    return str(uid) if uid else None


# Personal-term bounds (SEC-5). term_from mirrors a kept-as-is English term; term_to is the
# user's preferred rendering (matches the frontend input maxLength).
_MAX_TERM_FROM = 80
_MAX_TERM_TO = 40


def _parse_glossary_term(payload: dict) -> tuple[str, str, bool] | None:
    """Validate a personal-term upsert: both sides required, trimmed, length-bounded.
    Returns ``(term_from, term_to, prompt_enforced)`` or None on any violation (→ 400).
    ``promptEnforced`` is strict-boolean (only JSON ``true`` enables strong; missing/other → weak)
    so a stray truthy value can't silently escalate a term into the prompt."""
    if not isinstance(payload, dict):
        return None
    term_from = str(payload.get("termFrom", "")).strip()
    term_to = str(payload.get("termTo", "")).strip()
    if not term_from or not term_to:
        return None
    if len(term_from) > _MAX_TERM_FROM or len(term_to) > _MAX_TERM_TO:
        return None
    prompt_enforced = payload.get("promptEnforced") is True
    return term_from, term_to, prompt_enforced


def _parse_request(payload: dict) -> SummaryRequest | None:
    try:
        task = Task(str(payload["task"]))
        paper_id = str(payload["paperId"])
        version = int(payload.get("version", 1))
    except (KeyError, ValueError, TypeError):
        return None
    if not paper_id:
        return None
    persona = _enum_or_default(Persona, payload.get("persona"), Persona.EXPERT)
    lang = _enum_or_default(TargetLang, payload.get("targetLang"), TargetLang.KO)
    scope = _enum_or_default(Scope, payload.get("scope"), Scope.ABSTRACT)
    # REM-2 F02 (FD-Q2): the client ``abstract`` field is DEPRECATED and dropped at the boundary.
    # It is still accepted (so an older client is not broken by a 400) but never carried onto the
    # request — ``SourceSelector`` sources the abstract from the server-side store, and leaving it
    # on the request invited exactly the contamination SECURITY-13 is about. The worker/SQS
    # payload keeps the key so an already-enqueued job still deserializes.
    return SummaryRequest(
        paper_id=paper_id,
        version=version,
        task=task,
        target_lang=lang,
        persona=persona,
        scope=scope,
        abstract=None,
    )


def _enum_or_default(enum_cls: Any, value: Any, default: Any) -> Any:
    if value is None:
        return default
    try:
        return enum_cls(str(value))
    except ValueError:
        return default
