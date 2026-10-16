"""Truthful U4 owner readiness and capability-gated shared navigation."""

import time

from fastapi.testclient import TestClient
from psycopg.errors import InsufficientPrivilege

from backend.local_host import navigation_items
from backend.local_observation import observe_all
from backend.transactions import OWNERS, OwnerTransactions
from backend.u4_host import assemble_u4


def test_legacy_observation_default_does_not_add_the_research_owner():
    class OwnerSelection:
        def __init__(self):
            self.called = set()

        def run(self, owner, action):
            self.called.add(owner)
            return {"count": 0}

    legacy = OwnerSelection()
    assert set(observe_all(legacy)) == set(OWNERS)
    assert legacy.called == set(OWNERS) and "research" not in legacy.called
    installed = OwnerSelection()
    assert set(observe_all(installed, set(OWNERS) | {"research"})) == set(OWNERS) | {"research"}
    assert installed.called == set(OWNERS) | {"research"}


def test_navigation_keeps_degraded_research_visible_only_when_installed_and_authenticated():
    assert not {"research", "novelty"}.intersection(
        item["routeId"] for item in navigation_items([], authenticated=True)
    )
    catalog = [{"id": name, "state": "degraded"} for name in ("research", "novelty")]
    for authenticated in (True, False):
        items = {
            row["routeId"]: row for row in navigation_items(catalog, authenticated=authenticated)
        }
        for name in ("research", "novelty"):
            assert items[name]["available"] is authenticated
            assert items[name]["reasonKey"] == (
                None if authenticated else "nav.authenticationRequired"
            )
    refused = [{"id": name, "state": "policy_pending"} for name in ("research", "novelty")]
    items = {row["routeId"]: row for row in navigation_items(refused, authenticated=True)}
    assert all(not items[name]["available"] for name in ("research", "novelty"))


def test_mounted_readiness_refuses_research_owner_fault_and_recovers(realm, monkeypatch):
    # Inject only the negative connection/permission boundary. Every successful
    # owner query and every recovery probe still uses the real PostgreSQL pools.
    original = OwnerTransactions.run
    fault = {"active": True}

    def deny_research(self, owner, action, *args, **kwargs):
        if owner == "research" and fault["active"]:
            raise InsufficientPrivilege("private-fault-detail-must-not-leak")
        return original(self, owner, action, *args, **kwargs)

    monkeypatch.setattr(OwnerTransactions, "run", deny_research)
    app = assemble_u4(realm)
    assert app.state.required_capabilities == set(OWNERS) | {"research"}
    assert app.state.capabilities["research"] is False
    tx = app.state.transactions
    before = original(
        tx,
        "accounts",
        lambda conn: conn.execute("SELECT count(*) AS n FROM accounts.account").fetchone(),
    )
    jobs = original(
        tx,
        "research",
        lambda conn: conn.execute("SELECT count(*) AS n FROM research.job").fetchone(),
    )
    with TestClient(app, base_url=realm.origin) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json()["ready"] is False
        assert response.json()["missing"] == ["research"]
        observations = {row["capability"]: row for row in response.json()["observations"]}
        assert observations["research"]["evidence"] == {"reasonKey": "observation.storeDenied"}
        assert "private-fault-detail" not in response.text
        fault["active"] = False
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            response = client.get("/health/ready")
            if response.status_code == 200:
                break
            time.sleep(0.05)
        assert response.status_code == 200, response.text
        observations = {row["capability"]: row for row in response.json()["observations"]}
        assert observations["research"]["status"] == "available"
        assert set(observations["research"]["evidence"]) == {
            "contexts",
            "jobs",
            "artifacts",
            "admissions",
        }
        assert all(type(n) is int and n >= 0 for n in observations["research"]["evidence"].values())
        assert (
            original(
                tx,
                "accounts",
                lambda conn: conn.execute("SELECT count(*) AS n FROM accounts.account").fetchone(),
            )
            == before
        )
        assert (
            original(
                tx,
                "research",
                lambda conn: conn.execute("SELECT count(*) AS n FROM research.job").fetchone(),
            )
            == jobs
        )
    assert app.state.control_loop.task.done()
