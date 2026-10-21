"""`assemble_u6` over the realm, under a `TestClient` context as U5's assembly test runs:
the C09 routes, the capability row, the navigation entry, readiness with the export
probe, one control worker pass through the inherited chain, and the shutdown order.

The realm persists across phases and holds due effects of synthetic owners that have no
account; the pass's hand-over is kept to this test's own effects (it has none), so the
lane never acts on rows outside this test's fixtures. Housekeeping runs as the real pass
runs it, as `lane_flows.drain` does.
"""

from uuid import uuid4

from backend import control_runtime
from backend.modules.export.repository import ExportRepository
from backend.u6_host import assemble_u6
from docsuri_shared.workspace import wire
from fastapi.testclient import TestClient

from tests.u6_approved_export import lane_flows as lf


def spy_method(monkeypatch, owner, name: str, calls: list, label: str) -> None:
    original = getattr(owner, name)

    def spy(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(label)
        return result

    monkeypatch.setattr(owner, name, spy)


def test_assemble_u6_mounts_export_and_stops_in_order(realm, monkeypatch):
    order: list[str] = []
    passes: list[str] = []
    loop_close = control_runtime.ControlLoop.close

    async def close(self):
        await loop_close(self)
        order.append("control-loop")

    monkeypatch.setattr(control_runtime.ControlLoop, "close", close)
    monkeypatch.setattr(ExportRepository, "due_items", lambda self, now, limit=None: [])

    app = assemble_u6(realm)
    lane, worker = app.state.export_lane, app.state.control_worker
    spy_method(monkeypatch, lane, "stop", order, "export-lane")
    spy_method(monkeypatch, app.state.transactions, "close", order, "transactions")
    spy_method(monkeypatch, worker.inherited, "run_once", passes, "inherited")
    spy_method(monkeypatch, worker.export_pass, "run_once", passes, "export")

    with TestClient(app, base_url=realm.origin) as client:
        app.state.control_capacity.refresh()
        catalog = client.get("/api/v2/capabilities")
        lf.wait_for(lambda: app.state.control_loop.status["passes"] >= 1, seconds=20)
        running = lane.running
        ready = client.get("/health/ready").json()
        csrf = client.get("/api/v2/session").json()["csrfToken"]
        navigation = client.post(
            "/api/v2/c01/host-resolve-navigation",
            json={"routeId": "export"},
            headers={"Origin": realm.origin, "X-CSRF-Token": csrf, "Idempotency-Key": str(uuid4())},
        )
        route = client.post(
            "/api/v2/c09/read-notion-connection",
            json={},
            headers={
                "Origin": realm.origin,
                "X-CSRF-Token": "0" * 64,
                "Idempotency-Key": str(uuid4()),
            },
        )
        status = dict(app.state.control_loop.status)

    assert catalog.status_code == 200
    rows = {row["id"]: row for row in wire.CapabilityCatalog.model_validate(
        catalog.json()
    ).model_dump(mode="json")["capabilities"]}
    assert rows["export"]["modeIds"] == ["synthetic-only"]
    assert rows["export"]["levelIds"] == [] and rows["export"]["state"] == "degraded"
    assert {"research", "novelty", "topics.digest"} <= set(rows)
    assert passes[:2] == ["inherited", "export"] and status["failures"] == 0
    assert running is True and lane.running is False
    probes = {item["capability"]: item for item in ready["observations"]}
    assert probes["export"]["status"] == "available"
    assert probes["export"]["evidence"]["guard_functions"] == 1
    assert "export" in app.state.required_capabilities
    assert navigation.status_code == 200, navigation.json()
    items = {item["routeId"]: item for item in navigation.json()["items"]}
    assert items["export"]["path"] == "/export" and items["export"]["capabilityId"] == "export"
    assert (items["export"]["available"], items["export"]["reasonKey"]) == (
        False,
        "nav.authenticationRequired",
    )
    assert (route.status_code, route.json()["code"]) == (401, "UNAUTHENTICATED")
    assert order == ["control-loop", "export-lane", "transactions"]
