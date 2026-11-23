"""Latency summaries and route classes (U8 plan Step 10; P10, performance-design § 10)."""

from __future__ import annotations

import datetime as dt
import json
import stat
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from backend.request_context import (
    BUCKETS_MS,
    LatencyRecorder,
    RequestContext,
    RouteClasses,
)
from backend.u8_policy import ROUTE_CLASSES, SYNTHETIC_OPERATIONS


class Clock:
    def __init__(self):
        self.now = dt.datetime(2026, 10, 22, 3, 0, tzinfo=dt.UTC)

    def __call__(self):
        return self.now


@pytest.fixture
def recorder(tmp_path):
    clock = Clock()
    return LatencyRecorder(tmp_path, policy=SYNTHETIC_OPERATIONS, clock=clock), clock, tmp_path


def test_each_request_lands_in_its_fixed_bucket(recorder):
    latency, _, _ = recorder
    for milliseconds in (3, 5, 6, 40, 40, 999, 45_000):
        latency.observe("read", milliseconds / 1000, 200)
    summary = latency.summary("read")
    assert summary["count"] == 7 and summary["maxMs"] == 45_000
    assert summary["medianMs"] == 50  # the fourth of seven falls in (25, 50]
    assert BUCKETS_MS[-1] == 30_000
    with pytest.raises(ValueError):
        latency.observe("unclassified", 0.01, 200)


def test_the_95th_percentile_and_the_5xx_count(recorder):
    latency, _, _ = recorder
    for _ in range(95):
        latency.observe("search", 0.08, 200)
    for _ in range(5):
        latency.observe("search", 2.5, 503)
    summary = latency.summary("search")
    assert summary["p95Ms"] == 100 and summary["medianMs"] == 100
    assert summary["errors5xx"] == 5
    latency.observe("accept", 0.5, 200)
    assert latency.summary("accept")["p95Ms"] == 500


def test_the_window_file_holds_one_line_per_class_and_no_identifier_or_path(recorder):
    latency, clock, root = recorder
    planted = str(uuid4())
    latency.observe("read", 0.02, 200)
    clock.now += dt.timedelta(seconds=SYNTHETIC_OPERATIONS.latency_window_seconds)
    path = latency.flush()
    assert path == root / "evidence" / "latency" / "2026-10-22.jsonl"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    assert [line["class"] for line in lines] == list(ROUTE_CLASSES)
    assert all(
        set(line) == {"window", "class", "count", "medianMs", "p95Ms", "maxMs", "errors5xx"}
        for line in lines
    )
    read = next(line for line in lines if line["class"] == "read")
    assert read["count"] == 1 and read["window"] == "2026-10-22T03:00:00Z"
    assert next(line for line in lines if line["class"] == "health")["medianMs"] is None
    assert planted not in path.read_text() and "/" not in path.read_text().replace(
        "T03:00:00Z", ""
    )
    # The next window starts empty.
    assert latency.summary("read")["count"] == 0


def test_files_are_kept_fourteen_days(tmp_path):
    clock = Clock()
    clock.now = dt.datetime(2026, 10, 1, tzinfo=dt.UTC)
    latency = LatencyRecorder(tmp_path, policy=SYNTHETIC_OPERATIONS, clock=clock)
    for day in range(1, 21):
        # Each flush closes the window that began a day earlier.
        clock.now = dt.datetime(2026, 10, 1, tzinfo=dt.UTC) + dt.timedelta(days=day)
        latency.flush()
    names = sorted(path.name for path in (tmp_path / "evidence" / "latency").iterdir())
    assert names[0] == "2026-10-07.jsonl" and names[-1] == "2026-10-20.jsonl"
    assert len(names) == 14


def test_a_route_without_a_class_fails_the_assembly_check():
    classes = RouteClasses()
    classes.register("/health/live", "health", methods=("GET",))
    classes.register("/api/v2/c07/list-research-jobs", "read", methods=("POST",))
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    app.get("/health/live")(lambda: {})
    app.post("/api/v2/c07/list-research-jobs")(lambda: {})
    classes.check(app.router.routes[-2:])
    app.post("/api/v2/unclassified")(lambda: {})
    with pytest.raises(ValueError, match="without a route class"):
        classes.check(app.router.routes)
    with pytest.raises(ValueError):
        classes.register("/x", "unknown-class")
    assert classes.classify("POST", "/api/v2/c07/list-research-jobs") == "read"
    assert classes.classify("GET", "/api/v2/c07/list-research-jobs") is None


async def test_the_request_context_records_each_request_under_its_class(recorder):
    latency, _, _ = recorder
    classes = RouteClasses()
    classes.register("/health/live", "health", methods=("GET",))
    app = FastAPI()
    app.get("/health/live")(lambda: {"process": "alive"})
    wrapped = RequestContext(latency, classes).wrap(app)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=wrapped), base_url="http://127.0.0.1:18109"
    ) as http:
        assert (await http.get("/health/live")).status_code == 200
        assert (await http.get("/elsewhere")).status_code == 404
    assert latency.summary("health")["count"] == 1
    # An unmatched path counts as the static shell's class.
    assert latency.summary("static")["count"] == 1
