"""Canonical browser routes for the topics surface (literal REST, one origin).

Every route carries the owner's server-derived authority; denials surface as
plain refusals and a foreign or nonexistent identifier is indistinguishable
from a missing one (BR5.1: the boundary default is 404 FORBIDDEN). Mutations
demand the bounded CSRF and operation headers like every other POST surface.
"""

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from backend.local_browser import (
    BrowserDenied,
    boundary_route,
    post_context,
    read_payload,
    require_authority,
)

from .errors import TopicsError
from .service import TopicsService

ERROR_STATUS = {
    "INVALID_ARGUMENT": (422, "INVALID_ARGUMENT"),
    "NOT_FOUND": (404, "NOT_FOUND"),
    # The shared vocabulary has no DUPLICATE code: a duplicate follow is an
    # owner-declared conflict (BR1.1's duplicate notice).
    "DUPLICATE": (409, "CONFLICT"),
    # A revision-checked save refused on a stale revision surfaces as
    # STALE_REVISION so the client can reload and re-offer the change.
    "CONFLICT": (409, "STALE_REVISION"),
    "INVALID_STATE": (409, "CONFLICT"),
    "WINDOW_ORDER": (409, "CONFLICT"),
}


class TopicFollowHttp(BaseModel):
    topicKey: str
    displayName: str


class SettingsSaveHttp(BaseModel):
    revision: int
    cadence: str
    deliveryTimeLocal: str
    deliveryDay: str | None = None
    contentWindowDays: int


class ResolveHttp(BaseModel):
    decision: str
    assumption: str


class DigestSettingsView(BaseModel):
    cadence: str
    deliveryTimeLocal: str | None = None
    deliveryDay: str | None = None
    contentWindowDays: int
    revision: int


class DeliveryOutcomeView(BaseModel):
    observedState: str
    observedAt: str | None = None
    reconciledState: str | None = None
    reconciledAt: str | None = None
    failureReason: str | None = None


class SendLogView(BaseModel):
    pathKind: str
    transportReceipt: str | None = None
    acknowledgedAt: str | None = None


class DigestRunView(BaseModel):
    runId: str
    topicId: str
    windowStart: str
    windowEnd: str
    state: str
    settingsRevision: int
    digestContent: list = []
    createdAt: str | None = None
    outcome: DeliveryOutcomeView | None = None
    sendLog: SendLogView | None = None


class LastRunView(BaseModel):
    runId: str | None = None
    state: str | None = None
    windowEnd: str | None = None
    observedState: str | None = None


class TopicView(BaseModel):
    topicId: str
    topicKey: str
    displayName: str
    status: str
    followedAt: str | None = None
    settings: DigestSettingsView | None = None
    lastRun: LastRunView | None = None
    runs: list[DigestRunView] = []


class TopicList(BaseModel):
    topics: list[TopicView]


class FollowResult(BaseModel):
    topicId: str
    status: str
    reactivated: bool


class MutationResult(BaseModel):
    topicId: str
    status: str
    discardedRunIds: list[str] = []
    unchanged: bool


class SettingsSaveResult(BaseModel):
    settings: DigestSettingsView
    discardedRunIds: list[str] = []
    unchanged: bool


class ResolveResult(BaseModel):
    runId: str
    state: str
    decision: str
    assumption: str


def topics_router(transactions, *, entry, service: TopicsService) -> APIRouter:
    origin = transactions.profile.origin
    router = APIRouter(route_class=boundary_route(origin, missing=(404, "FORBIDDEN")))

    def denied(exc: TopicsError):
        mapping = ERROR_STATUS.get(exc.code)
        if mapping is None:
            raise BrowserDenied(500, "INTERNAL_ERROR") from None
        raise BrowserDenied(mapping[0], mapping[1]) from None

    def parse_identifier(value: str) -> UUID:
        try:
            return UUID(value)
        except (ValueError, AttributeError, TypeError):
            # A malformed identifier is indistinguishable from a missing one.
            raise BrowserDenied(404, "FORBIDDEN") from None

    @router.get("/api/v2/topics")
    async def list_topics(request: Request):
        authority = await require_authority(request, entry=entry)
        try:
            rows = await run_in_threadpool(service.list_topics, authority)
        except TopicsError as exc:
            denied(exc)
        return TopicList.model_validate({"topics": rows}).model_dump(
            mode="json", exclude_none=True
        )

    @router.post("/api/v2/topics")
    async def follow(request: Request):
        _, _, authority = await post_context(
            request, origin=origin, entry=entry, anonymous=None
        )
        value = await read_payload(request, TopicFollowHttp)
        try:
            result = await run_in_threadpool(
                service.follow, authority, value["topicKey"], value["displayName"]
            )
        except TopicsError as exc:
            denied(exc)
        return FollowResult.model_validate(result).model_dump(mode="json", exclude_none=True)

    @router.delete("/api/v2/topics/{topic_id}")
    async def unsubscribe(request: Request, topic_id: str):
        _, _, authority = await post_context(
            request, origin=origin, entry=entry, anonymous=None
        )
        identifier = parse_identifier(topic_id)
        try:
            result = await run_in_threadpool(service.unsubscribe, authority, identifier)
        except TopicsError as exc:
            denied(exc)
        return MutationResult.model_validate(result).model_dump(mode="json", exclude_none=True)

    @router.get("/api/v2/topics/{topic_id}/settings")
    async def read_settings(request: Request, topic_id: str):
        authority = await require_authority(request, entry=entry)
        identifier = parse_identifier(topic_id)
        try:
            result = await run_in_threadpool(service.read_topic, authority, identifier)
        except TopicsError as exc:
            denied(exc)
        return TopicView.model_validate(result).model_dump(mode="json", exclude_none=True)

    @router.put("/api/v2/topics/{topic_id}/settings")
    async def save_settings(request: Request, topic_id: str):
        _, _, authority = await post_context(
            request, origin=origin, entry=entry, anonymous=None
        )
        identifier = parse_identifier(topic_id)
        value = await read_payload(request, SettingsSaveHttp)
        try:
            result = await run_in_threadpool(service.save_settings, authority, identifier, value)
        except TopicsError as exc:
            denied(exc)
        return SettingsSaveResult.model_validate(result).model_dump(mode="json", exclude_none=True)

    @router.post("/api/v2/topics/{topic_id}/runs/{run_id}/resolve")
    async def resolve(request: Request, topic_id: str, run_id: str):
        _, _, authority = await post_context(
            request, origin=origin, entry=entry, anonymous=None
        )
        identifier = parse_identifier(topic_id)
        run_identifier = parse_identifier(run_id)
        value = await read_payload(request, ResolveHttp)
        try:
            result = await run_in_threadpool(
                service.resolve, authority, identifier, run_identifier, value
            )
        except TopicsError as exc:
            denied(exc)
        return ResolveResult.model_validate(result).model_dump(mode="json", exclude_none=True)

    return router
