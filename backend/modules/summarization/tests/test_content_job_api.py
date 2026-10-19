"""Content job API routes — the durable receipt, state, events, and result endpoints.

REM-2 corrective, Phase 5 (items 20-26). The in-memory contract tests prove the job *shape*;
the RDS adapter tests prove the *durability properties*; these prove the *HTTP contract* that
the frontend consumes.

The routes are invoked directly with a fake Request (carrying ``state.principal`` and
``query_params``) — the gateway stand-in — matching the asset endpoint tests.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from summarization.adapters.in_memory_jobs import InMemoryJobStore
from summarization.api.router import build_router
from summarization.domain.job import JobError
from summarization.domain.models import AuthSession, RequestContext
from summarization.service.job_service import ContentJobService

pytestmark = pytest.mark.asyncio


class _FakeState:
    def __init__(self, principal: Any) -> None:
        self.principal = principal


class _FakeQuery:
    def __init__(self, params: dict[str, str]) -> None:
        self._p = params

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._p.get(key, default)


class _FakeRequest:
    def __init__(
        self,
        principal: Any,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> None:
        self.state = _FakeState(principal)
        self.headers = headers or {}
        self.query_params = _FakeQuery(query or {})
        self._json_body = json_body or {}

    async def json(self) -> dict[str, Any]:
        return self._json_body


class _FakeOrchestrator:
    """Minimal stand-in; the job routes don't call it."""

    pass


def _build(job_service: ContentJobService | None) -> dict[str, Any]:
    router = build_router(_FakeOrchestrator(), job_service=job_service)
    routes = {r.path: r.endpoint for r in router.routes}
    return routes


def _principal(user_id: str | None = None) -> AuthSession | None:
    return AuthSession(user_id=user_id) if user_id else None


def _svc() -> ContentJobService:
    return ContentJobService(
        store=InMemoryJobStore(),
        enqueue=lambda _j: None,
        result_ttl_seconds=3600.0,
        now=lambda: 1000.0,
    )


async def _consume_stream(resp) -> list[dict]:
    """Consume the StreamingResponse body (async iterator yielding text).

    SSE format: each event has an 'id:' line and a 'data:' line, separated by blank lines.
    """
    body = ""
    async for chunk in resp.body_iterator:
        body += chunk
    # Split into event blocks (separated by blank lines)
    blocks = body.strip().split("\n\n")
    events = []
    for block in blocks:
        if not block.strip():
            continue
        # Each block has 'id:' and 'data:' lines; extract the data line
        data_line = None
        for line in block.split("\n"):
            if line.startswith("data: "):
                data_line = line
                break
        if data_line:
            events.append(json.loads(data_line[6:]))  # skip "data: "
    return events


def _consume_stream_sync(resp) -> list[dict]:
    return asyncio.run(_consume_stream(resp))


# --- submit ---------------------------------------------------------------


async def test_submit_requires_auth() -> None:
    routes = _build(_svc())
    req = _FakeRequest(None, json_body={"taskType": "summarize", "input": {}})
    resp = await routes["/api/content-jobs/submit"](req)
    assert resp.status_code == 401
    assert resp.body == b'{"status":"unauthorized"}'


async def test_submit_rejects_invalid_task_type() -> None:
    routes = _build(_svc())
    req = _FakeRequest(_principal("u1"), json_body={"taskType": "invalid", "input": {}})
    resp = await routes["/api/content-jobs/submit"](req)
    assert resp.status_code == 400
    assert b"validation_error" in resp.body


async def test_submit_returns_durable_receipt_with_job_id_and_state() -> None:
    routes = _build(_svc())
    req = _FakeRequest(
        _principal("u1"), json_body={"taskType": "summarize", "input": {"paperId": "2401.1"}}
    )
    resp = await routes["/api/content-jobs/submit"](req)
    assert resp.status_code == 202
    body = json.loads(resp.body)
    assert "jobId" in body
    assert body["state"] == "ACCEPTED"
    assert body["jobId"].startswith("job-")


async def test_submit_idempotency_key_returns_same_job() -> None:
    routes = _build(_svc())
    payload = {"taskType": "summarize", "input": {"paperId": "2401.1"}, "idempotencyKey": "k1"}
    r1 = await routes["/api/content-jobs/submit"](_FakeRequest(_principal("u1"), json_body=payload))
    r2 = await routes["/api/content-jobs/submit"](_FakeRequest(_principal("u1"), json_body=payload))
    b1 = json.loads(r1.body)
    b2 = json.loads(r2.body)
    assert b2["jobId"] == b1["jobId"]


async def test_submit_without_idempotency_key_is_always_new() -> None:
    routes = _build(_svc())
    payload = {"taskType": "summarize", "input": {"paperId": "2401.1"}}
    r1 = await routes["/api/content-jobs/submit"](_FakeRequest(_principal("u1"), json_body=payload))
    r2 = await routes["/api/content-jobs/submit"](_FakeRequest(_principal("u1"), json_body=payload))
    b1 = json.loads(r1.body)
    b2 = json.loads(r2.body)
    assert b2["jobId"] != b1["jobId"]


async def test_submit_different_owner_same_key_gets_different_job() -> None:
    routes = _build(_svc())
    payload = {"taskType": "summarize", "input": {"paperId": "2401.1"}, "idempotencyKey": "k1"}
    r1 = await routes["/api/content-jobs/submit"](_FakeRequest(_principal("u1"), json_body=payload))
    r2 = await routes["/api/content-jobs/submit"](_FakeRequest(_principal("u2"), json_body=payload))
    b1 = json.loads(r1.body)
    b2 = json.loads(r2.body)
    assert b2["jobId"] != b1["jobId"]


# --- state ----------------------------------------------------------------


async def test_state_requires_auth() -> None:
    routes = _build(_svc())
    req = _FakeRequest(None)
    resp = routes["/api/content-jobs/{job_id}/state"](req, job_id="j1")
    assert resp.status_code == 401


async def test_state_not_found_for_unknown_job() -> None:
    routes = _build(_svc())
    req = _FakeRequest(_principal("u1"))
    resp = routes["/api/content-jobs/{job_id}/state"](req, job_id="unknown")
    assert resp.status_code == 404


async def test_state_not_found_for_another_owners_job() -> None:
    svc = _svc()
    routes = _build(svc)
    r1 = await routes["/api/content-jobs/submit"](
        _FakeRequest(
            _principal("u1"), json_body={"taskType": "summarize", "input": {"paperId": "2401.1"}}
        )
    )
    job_id = json.loads(r1.body)["jobId"]
    resp = routes["/api/content-jobs/{job_id}/state"](_FakeRequest(_principal("u2")), job_id=job_id)
    assert resp.status_code == 404


async def test_state_returns_state_and_error_and_result_ref() -> None:
    svc = _svc()
    routes = _build(svc)
    r1 = await routes["/api/content-jobs/submit"](
        _FakeRequest(
            _principal("u1"), json_body={"taskType": "summarize", "input": {"paperId": "2401.1"}}
        )
    )
    job_id = json.loads(r1.body)["jobId"]
    svc.mark_queued(RequestContext(auth_session=_principal("u1"), request_id="r1"), job_id)
    svc.mark_running(RequestContext(auth_session=_principal("u1"), request_id="r1"), job_id)
    svc.mark_completed(
        RequestContext(auth_session=_principal("u1"), request_id="r1"),
        job_id,
        result_ref="summary/2401.1/v1",
    )
    r2 = routes["/api/content-jobs/{job_id}/state"](_FakeRequest(_principal("u1")), job_id=job_id)
    assert r2.status_code == 200
    body = json.loads(r2.body)
    assert body["jobId"] == job_id
    assert body["state"] == "COMPLETED"
    assert body["resultRef"] == "summary/2401.1/v1"

    # Error state
    job_id2 = svc.submit(
        RequestContext(auth_session=_principal("u1"), request_id="r1"),
        "summarize",
        {},
        idempotency_key="k2",
    ).job_id
    svc.mark_queued(RequestContext(auth_session=_principal("u1"), request_id="r1"), job_id2)
    svc.mark_running(RequestContext(auth_session=_principal("u1"), request_id="r1"), job_id2)
    svc.mark_failed(
        RequestContext(auth_session=_principal("u1"), request_id="r1"),
        job_id2,
        error=JobError("timeout", "시간이 초과되었습니다.", True, retry_after_seconds=30),
    )
    r3 = routes["/api/content-jobs/{job_id}/state"](_FakeRequest(_principal("u1")), job_id=job_id2)
    body3 = json.loads(r3.body)
    assert body3["state"] == "FAILED"
    assert body3["error"]["errorType"] == "timeout"
    assert body3["error"]["retryable"] is True


# --- events ---------------------------------------------------------------


async def test_events_requires_auth() -> None:
    routes = _build(_svc())
    req = _FakeRequest(None)
    resp = routes["/api/content-jobs/{job_id}/events"](req, job_id="j1")
    assert resp.status_code == 401


async def test_events_not_found_for_unknown_job() -> None:
    routes = _build(_svc())
    req = _FakeRequest(_principal("u1"))
    resp = routes["/api/content-jobs/{job_id}/events"](req, job_id="unknown")
    assert resp.status_code == 404


async def test_events_streams_from_after_seq() -> None:
    svc = _svc()
    routes = _build(svc)
    r1 = await routes["/api/content-jobs/submit"](
        _FakeRequest(
            _principal("u1"), json_body={"taskType": "summarize", "input": {"paperId": "2401.1"}}
        )
    )
    job_id = json.loads(r1.body)["jobId"]
    svc.mark_queued(RequestContext(auth_session=_principal("u1"), request_id="r1"), job_id)
    svc.mark_running(RequestContext(auth_session=_principal("u1"), request_id="r1"), job_id)
    svc.mark_completed(
        RequestContext(auth_session=_principal("u1"), request_id="r1"),
        job_id,
        result_ref="summary/2401.1/v1",
    )

    resp = routes["/api/content-jobs/{job_id}/events"](
        _FakeRequest(_principal("u1")), job_id=job_id
    )
    events = await _consume_stream(resp)
    states = [e["state"] for e in events]
    assert states == ["ACCEPTED", "QUEUED", "RUNNING", "COMPLETED"]
    assert all("eventId" in e for e in events)
    assert events[-1].get("payload", {}).get("resultReady") is True


async def test_events_resume_from_last_event_id_header() -> None:
    svc = _svc()
    routes = _build(svc)
    r1 = await routes["/api/content-jobs/submit"](
        _FakeRequest(
            _principal("u1"), json_body={"taskType": "summarize", "input": {"paperId": "2401.1"}}
        )
    )
    job_id = json.loads(r1.body)["jobId"]
    svc.mark_queued(RequestContext(auth_session=_principal("u1"), request_id="r1"), job_id)
    svc.mark_running(RequestContext(auth_session=_principal("u1"), request_id="r1"), job_id)
    svc.mark_completed(
        RequestContext(auth_session=_principal("u1"), request_id="r1"),
        job_id,
        result_ref="summary/2401.1/v1",
    )

    resp = routes["/api/content-jobs/{job_id}/events"](
        _FakeRequest(_principal("u1"), headers={"last-event-id": f"{job_id}:3"}), job_id=job_id
    )
    events = await _consume_stream(resp)
    states = [e["state"] for e in events]
    assert states == ["COMPLETED"]


async def test_events_resume_from_last_event_id_query_param() -> None:
    svc = _svc()
    routes = _build(svc)
    r1 = await routes["/api/content-jobs/submit"](
        _FakeRequest(
            _principal("u1"), json_body={"taskType": "summarize", "input": {"paperId": "2401.1"}}
        )
    )
    job_id = json.loads(r1.body)["jobId"]
    svc.mark_queued(RequestContext(auth_session=_principal("u1"), request_id="r1"), job_id)
    svc.mark_running(RequestContext(auth_session=_principal("u1"), request_id="r1"), job_id)
    svc.mark_completed(
        RequestContext(auth_session=_principal("u1"), request_id="r1"),
        job_id,
        result_ref="summary/2401.1/v1",
    )

    resp = routes["/api/content-jobs/{job_id}/events"](
        _FakeRequest(_principal("u1"), query={"lastEventId": f"{job_id}:3"}), job_id=job_id
    )
    events = await _consume_stream(resp)
    states = [e["state"] for e in events]
    assert states == ["COMPLETED"]


# --- result ---------------------------------------------------------------


async def test_result_requires_auth() -> None:
    routes = _build(_svc())
    req = _FakeRequest(None)
    resp = routes["/api/content-jobs/{job_id}/result"](req, job_id="j1")
    assert resp.status_code == 401


async def test_result_not_found_for_unknown_job() -> None:
    routes = _build(_svc())
    req = _FakeRequest(_principal("u1"))
    resp = routes["/api/content-jobs/{job_id}/result"](req, job_id="unknown")
    assert resp.status_code == 404


async def test_result_not_found_for_another_owners_job() -> None:
    svc = _svc()
    routes = _build(svc)
    r1 = await routes["/api/content-jobs/submit"](
        _FakeRequest(
            _principal("u1"), json_body={"taskType": "summarize", "input": {"paperId": "2401.1"}}
        )
    )
    job_id = json.loads(r1.body)["jobId"]
    svc.mark_completed(
        RequestContext(auth_session=_principal("u1"), request_id="r1"),
        job_id,
        result_ref="summary/2401.1/v1",
    )
    r2 = routes["/api/content-jobs/{job_id}/result"](_FakeRequest(_principal("u2")), job_id=job_id)
    assert r2.status_code == 404


async def test_result_returns_result_ref_when_ready() -> None:
    svc = _svc()
    routes = _build(svc)
    r1 = await routes["/api/content-jobs/submit"](
        _FakeRequest(
            _principal("u1"), json_body={"taskType": "summarize", "input": {"paperId": "2401.1"}}
        )
    )
    job_id = json.loads(r1.body)["jobId"]
    svc.mark_queued(RequestContext(auth_session=_principal("u1"), request_id="r1"), job_id)
    svc.mark_running(RequestContext(auth_session=_principal("u1"), request_id="r1"), job_id)
    svc.mark_completed(
        RequestContext(auth_session=_principal("u1"), request_id="r1"),
        job_id,
        result_ref="summary/2401.1/v1",
    )
    resp = routes["/api/content-jobs/{job_id}/result"](
        _FakeRequest(_principal("u1")), job_id=job_id
    )
    assert resp.status_code == 200
    body = json.loads(resp.body)
    assert body["resultRef"] == "summary/2401.1/v1"


async def test_result_not_found_for_uncompleted_job() -> None:
    svc = _svc()
    routes = _build(svc)
    r1 = await routes["/api/content-jobs/submit"](
        _FakeRequest(
            _principal("u1"), json_body={"taskType": "summarize", "input": {"paperId": "2401.1"}}
        )
    )
    job_id = json.loads(r1.body)["jobId"]
    resp = routes["/api/content-jobs/{job_id}/result"](
        _FakeRequest(_principal("u1")), job_id=job_id
    )
    assert resp.status_code == 404


async def test_result_not_found_for_failed_job() -> None:
    svc = _svc()
    routes = _build(svc)
    r1 = await routes["/api/content-jobs/submit"](
        _FakeRequest(
            _principal("u1"), json_body={"taskType": "summarize", "input": {"paperId": "2401.1"}}
        )
    )
    job_id = json.loads(r1.body)["jobId"]
    svc.mark_failed(
        RequestContext(auth_session=_principal("u1"), request_id="r1"),
        job_id,
        error=JobError("internal", "x", True),
    )
    resp = routes["/api/content-jobs/{job_id}/result"](
        _FakeRequest(_principal("u1")), job_id=job_id
    )
    assert resp.status_code == 404


async def test_result_expired_after_ttl() -> None:
    clock = {"t": 1000.0}
    svc = ContentJobService(
        store=InMemoryJobStore(),
        enqueue=lambda _j: None,
        result_ttl_seconds=60.0,
        now=lambda: clock["t"],
    )
    routes = _build(svc)
    r1 = await routes["/api/content-jobs/submit"](
        _FakeRequest(
            _principal("u1"), json_body={"taskType": "summarize", "input": {"paperId": "2401.1"}}
        )
    )
    job_id = json.loads(r1.body)["jobId"]
    svc.mark_queued(RequestContext(auth_session=_principal("u1"), request_id="r1"), job_id)
    svc.mark_running(RequestContext(auth_session=_principal("u1"), request_id="r1"), job_id)
    svc.mark_completed(
        RequestContext(auth_session=_principal("u1"), request_id="r1"),
        job_id,
        result_ref="summary/2401.1/v1",
    )
    resp = routes["/api/content-jobs/{job_id}/result"](
        _FakeRequest(_principal("u1")), job_id=job_id
    )
    assert resp.status_code == 200
    clock["t"] += 120.0
    resp2 = routes["/api/content-jobs/{job_id}/result"](
        _FakeRequest(_principal("u1")), job_id=job_id
    )
    assert resp2.status_code == 404


async def test_job_service_unavailable_returns_503() -> None:
    routes = _build(None)
    req = _FakeRequest(_principal("u1"))
    r1 = await routes["/api/content-jobs/submit"](req)
    assert r1.status_code == 503
    r2 = routes["/api/content-jobs/{job_id}/state"](req, job_id="j1")
    assert r2.status_code == 503
    r3 = routes["/api/content-jobs/{job_id}/events"](req, job_id="j1")
    assert r3.status_code == 503
    r4 = routes["/api/content-jobs/{job_id}/result"](req, job_id="j1")
    assert r4.status_code == 503
