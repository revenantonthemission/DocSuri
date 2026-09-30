"""Content Jobs API routes — submit, status, events, assets."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from ops.platform_integrity.content_job_service import ContentJobService
from pydantic import BaseModel, Field

from docsuri_platform_integrity.adapters.assets import AssetService
from docsuri_platform_integrity.adapters.authz import AuthorizationService, AuthorizationServiceImpl

# ruff: noqa: B008

router = APIRouter(prefix="/content-jobs", tags=["content-jobs"])

# Dependency injection (in production, use proper DI container)
_job_service: ContentJobService | None = None
_asset_service: AssetService | None = None
_authz_service: AuthorizationServiceImpl | None = None


def get_job_service() -> ContentJobService:
    if _job_service is None:
        raise HTTPException(503, "Job service not initialized")
    return _job_service


def get_asset_service() -> AssetService:
    if _asset_service is None:
        raise HTTPException(503, "Asset service not initialized")
    return _asset_service


def get_authz_service() -> AuthorizationService:
    if _authz_service is None:
        raise HTTPException(503, "Authz service not initialized")
    return _authz_service


async def get_current_user(request: Request) -> str:
    return request.headers.get("X-User-ID", "anonymous")


class SubmitJobRequest(BaseModel):
    task_type: str = Field(..., pattern="^(translate|summarize|novelty|evidence|ingest_userdoc)$")
    input: dict
    idempotency_key: str | None = None


class SubmitJobResponse(BaseModel):
    job_id: str
    state: str


class JobStateResponse(BaseModel):
    job_id: str
    state: str
    asset_id: str | None = None
    error: dict | None = None
    abstain_reason: str | None = None


class TranslateRequest(BaseModel):
    paper_id: str
    version: int = 1
    target_lang: str = "ko"
    persona: dict = {}
    source: str | None = None


class TranslateResponse(BaseModel):
    asset_id: str | None = None
    job_id: str | None = None
    state: str
    source: str


class AssetTokenRequest(BaseModel):
    asset_id: str
    action: str = "view"


@router.post("/submit", response_model=SubmitJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_job(
    request: Request,
    body: SubmitJobRequest,
    user_id: str = Depends(get_current_user),
    job_service: ContentJobService = Depends(get_job_service),
    authz: AuthorizationService = Depends(get_authz_service),
):
    if not await authz.recheck(user_id, "global", "SUBMIT"):
        raise HTTPException(403, "Not authorized to submit jobs")

    job_id = await job_service.submit(
        task_type=body.task_type,
        input_data=body.input,
        owner=user_id,
        idempotency_key=body.idempotency_key,
    )
    return SubmitJobResponse(job_id=job_id, state="ACCEPTED")


@router.get("/{job_id}/state", response_model=JobStateResponse)
async def get_job_state(
    job_id: str,
    job_service: ContentJobService = Depends(get_job_service),
):
    state = await job_service.get_state(job_id)
    if "error" in state:
        raise HTTPException(404, state["error"])
    return JobStateResponse(**state)


@router.get("/{job_id}/events")
async def subscribe_job_events(
    job_id: str,
    last_event_id: str | None = None,
    job_service: ContentJobService = Depends(get_job_service),
):
    from fastapi.responses import StreamingResponse

    async def event_generator():
        async for event in job_service.subscribe_events(job_id, None):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/translate", response_model=TranslateResponse)
async def translate(
    body: TranslateRequest,
    user_id: str = Depends(get_current_user),
    job_service: ContentJobService = Depends(get_job_service),
):
    job_id = await job_service.submit(
        task_type="TRANSLATE",
        input_data=body.model_dump(),
        owner=user_id,
    )
    return TranslateResponse(
        job_id=job_id,
        state="ACCEPTED",
        source="job",
    )


@router.get("/assets/{asset_id}")
async def get_asset(
    asset_id: str,
    token: str,
    asset_service: AssetService = Depends(get_asset_service),
    authz: AuthorizationService = Depends(get_authz_service),
):
    presigned_url = f"http://127.0.0.1:9000/docsuri/assets/{asset_id}?token=mock"
    return RedirectResponse(url=presigned_url, status_code=307)


@router.post("/assets/{asset_id}/token")
async def issue_asset_token(
    asset_id: str,
    body: AssetTokenRequest,
    user_id: str = Depends(get_current_user),
    asset_service: AssetService = Depends(get_asset_service),
):
    token = "mock-jwt-token"
    return {"token": token, "expires_in": 60}
