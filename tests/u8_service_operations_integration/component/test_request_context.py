"""Request identifiers (U8 plan Step 10; D13, NFR9.11).

The application is the shared host (`local_host.assemble`) behind D7's boundary with
the request context inside it, called in-process; one probe route of the built route
class stands for a browser route.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import logging
from uuid import UUID

import httpx
import pytest
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.local_browser import CURRENT_REQUEST_ID, BrowserDenied, boundary_route
from backend.local_host import assemble
from backend.log_events import EVENTS_LOGGER, EventLog
from backend.modules.operations.observation_store import ObservationRow, ObservationStore
from backend.production_boundary import BoundaryHosts, BuildManifest, ProductionBoundary
from backend.request_context import RequestContext
from backend.u8_transactions import CompleteTransactions

CAPABILITY = "test.request-context"


@pytest.fixture
def application(realm, transactions, tmp_path):
    router = APIRouter(route_class=boundary_route(realm.origin))
    events = EventLog(strict=True)
    store = ObservationStore(transactions)

    @router.get("/probe/denied")
    async def denied():
        events.event("test", "probe.denied")
        raise BrowserDenied(404, "NOT_FOUND")

    @router.get("/probe/observed")
    async def observed():
        row = ObservationRow(
            capability=CAPABILITY, producer="test", outcome="available",
            observed_at=dt.datetime.now(dt.UTC), revision=1,
        )
        store.insert([row])
        return JSONResponse(
            {
                "current": CURRENT_REQUEST_ID.get(),
                "observation": str(row.request_id),
                "log": events.line("test", "probe.observed")["requestId"],
            }
        )

    boundary = ProductionBoundary(
        BoundaryHosts.for_profile(realm), BuildManifest.empty(tmp_path),
        context=RequestContext(None, None),
    )
    return assemble(realm, routers=(router,), boundary=boundary), store


def client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://127.0.0.1:18110"
    )


async def test_each_request_gets_a_fresh_identifier(application):
    app, _ = application
    async with client(app) as http:
        first = (await http.get("/probe/observed")).json()
        second = (await http.get("/probe/observed")).json()
    assert UUID(first["current"]) and UUID(second["current"])
    assert first["current"] != second["current"]
    # Outside a request no identifier is current.
    assert CURRENT_REQUEST_ID.get() is None


async def test_a_supplied_request_id_is_ignored(application):
    app, _ = application
    planted = "11111111-1111-4111-8111-111111111111"
    async with client(app) as http:
        answer = await http.get(
            "/probe/denied", headers={"x-request-id": planted, "request-id": planted}
        )
    assert answer.status_code == 404
    assert answer.json()["requestId"] != planted
    assert planted not in answer.text


async def test_the_identifier_reaches_the_error_body_and_the_log_line(application, caplog):
    app, _ = application
    caplog.set_level(logging.INFO, logger=EVENTS_LOGGER)
    async with client(app) as http:
        answer = await http.get("/probe/denied")
    identifier = answer.json()["requestId"]
    UUID(identifier)
    lines = [record.getMessage() for record in caplog.records if record.name == EVENTS_LOGGER]
    assert any(f'"requestId": "{identifier}"' in line for line in lines)


async def test_the_identifier_reaches_an_observation(application):
    app, store = application
    async with client(app) as http:
        value = (await http.get("/probe/observed")).json()
    assert value["observation"] == value["current"] == value["log"]
    latest = store.latest([CAPABILITY])[CAPABILITY]
    assert str(latest["request_id"]) == value["current"]


def test_an_observation_outside_a_request_carries_none():
    row = ObservationRow(
        capability=CAPABILITY, producer="test", outcome="available",
        observed_at=dt.datetime.now(dt.UTC), revision=1,
    )
    assert row.request_id is None


async def test_the_fixed_assembly_values_become_the_request_identifier(application):
    """The built `"assembly"` and `"boundary"` values are replaced by the identifier."""
    app, _ = application
    async with client(app) as http:
        missing = await http.get("/api/unknown")
        foreign = await http.get("/probe/observed", headers={"origin": "https://elsewhere"})
    assert missing.status_code == 503 and UUID(missing.json()["requestId"])
    assert foreign.status_code == 403 and UUID(foreign.json()["requestId"])


# --- Step 52(e): an owner transaction inside a request carries its identifier (L1-6) ----


def read_setting(conn):
    return conn.execute(
        "SELECT current_setting('docsuri.request_id', true) AS value").fetchone()["value"]


@pytest.fixture
def setting_application(realm, transactions, tmp_path):
    complete = CompleteTransactions(realm)
    router = APIRouter(route_class=boundary_route(realm.origin))

    @router.get("/probe/owner-setting")
    async def owner_setting():
        return JSONResponse({
            "current": CURRENT_REQUEST_ID.get(),
            "complete": complete.run("operations", read_setting),
            "built": transactions.run("operations", read_setting),
        })

    boundary = ProductionBoundary(
        BoundaryHosts.for_profile(realm), BuildManifest.empty(tmp_path),
        context=RequestContext(None, None),
    )
    yield assemble(realm, routers=(router,), boundary=boundary), complete
    complete.close()


async def test_an_owner_transaction_inside_a_request_carries_its_identifier(
        setting_application, realm, tmp_path):
    app, complete = setting_application
    async with client(app) as http:
        value = (await http.get("/probe/owner-setting")).json()
    assert UUID(value["current"]) and value["complete"] == value["current"]
    # OwnerTransactions as built sets nothing, inside the same request.
    assert value["built"] is None
    # Outside any request nothing is set, and each transaction opens its own connection.
    assert CURRENT_REQUEST_ID.get() is None
    assert complete.run("operations", read_setting) is None
    rebound = dataclasses.replace(realm, database_name="docsuri_u2", realm="account-controls")
    with pytest.raises(ValueError, match="not a complete realm"):
        CompleteTransactions(rebound)
    # It refuses before OwnerTransactions reads anything: this root holds no credentials.
    assert not (tmp_path / "owner-credentials.json").exists()
    with pytest.raises(ValueError, match="not a complete realm"):
        CompleteTransactions(dataclasses.replace(rebound, root=tmp_path))


def test_window_summaries_keeps_only_the_windows_inside_its_bounds(tmp_path):
    """U8 plan Step 71(i): the soak's latency summary counts a window only when it starts
    at or after `start` and ends at or before `end`, across UTC day files."""
    import json
    import os

    from backend.request_context import window_summaries

    folder = tmp_path / "latency"
    folder.mkdir()
    start = dt.datetime(2026, 11, 9, 23, 50, tzinfo=dt.UTC)
    end = dt.datetime(2026, 11, 10, 0, 10, tzinfo=dt.UTC)
    length = 300

    def line(route_class: str, begun: dt.datetime, p95: float, count: int) -> str:
        window = begun.isoformat(timespec="seconds").replace("+00:00", "Z")
        return json.dumps({"window": window, "class": route_class, "count": count,
                           "medianMs": p95, "p95Ms": p95, "maxMs": p95, "errors5xx": 0})

    before_midnight = [
        line("read", start, 100, 2),  # starts exactly at `start`
        line("read", start - dt.timedelta(seconds=1), 9000, 1),  # starts 1 s before
        "not json at all",  # malformed: skipped
        json.dumps({"window": "yesterday", "class": "read", "count": 1}),
    ]
    after_midnight = [
        line("search", end - dt.timedelta(seconds=length), 700, 3),  # ends exactly at `end`
        line("search", end - dt.timedelta(seconds=length - 1), 8000, 4),  # ends 1 s after
        line("health", end - dt.timedelta(seconds=length), 5, 0),  # no request
    ]
    (folder / "2026-11-09.jsonl").write_text("\n".join(before_midnight) + "\n")
    (folder / "2026-11-10.jsonl").write_text("\n".join(after_midnight) + "\n")
    summary = window_summaries(folder, start=start, end=end, window_seconds=length)
    assert summary["windows"] == 2
    assert summary["p95Ms"]["read"] == 100 and summary["p95Ms"]["search"] == 700
    assert summary["p95Ms"]["health"] is None and summary["p95Ms"]["stream"] is None
    assert summary["requests"]["read"] == 2 and summary["requests"]["search"] == 3
    # A missing day file reads as empty.
    later = window_summaries(folder, start=end + dt.timedelta(days=3),
                             end=end + dt.timedelta(days=4), window_seconds=length)
    assert later["windows"] == 0 and later["requests"]["read"] == 0
    # A linked day file is refused.
    (folder / "2026-11-10.jsonl").unlink()
    os.symlink(folder / "2026-11-09.jsonl", folder / "2026-11-10.jsonl")
    with pytest.raises(OSError):
        window_summaries(folder, start=start, end=end, window_seconds=length)
