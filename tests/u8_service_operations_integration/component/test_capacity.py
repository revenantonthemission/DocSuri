"""Storage admission with the production budget (U8 plan Step 12; BR6.6, scalability-design
§ 3.2-3.3, A10). The complete realms' parts are U8's `backend/u8_capacity.py` (the
person's decision of 2026-10-24, "Move, scope tools, test U2"); U2's `ControlCapacity`
keeps the built synthetic rule."""

from __future__ import annotations

import asyncio
import dataclasses
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from backend.control_runtime import ControlAdmission, ControlCapacity
from backend.u8_capacity import (
    BudgetedCapacity,
    CapacityBudget,
    CapacityRefresher,
    capacity_budget,
    complete_capacity,
)
from backend.u8_policy import GIB, MIB, PRODUCTION_OPERATIONS


@pytest.fixture
def budget(tmp_path):
    return CapacityBudget(PRODUCTION_OPERATIONS, tmp_path)


def test_the_production_budgets_thresholds(budget):
    plenty = 100 * GIB
    assert budget.judge(int(6.39 * GIB), plenty) == ("available", None)
    assert budget.judge(int(6.4 * GIB), plenty) == ("degraded", "capacity-approaching")
    assert budget.judge(8 * GIB - 256 * MIB - 1, plenty) == ("degraded", "capacity-approaching")
    assert budget.judge(8 * GIB - 256 * MIB, plenty) == ("unavailable", "capacity-exhausted")
    assert budget.judge(0, 20 * GIB) == ("available", None)
    assert budget.judge(0, 20 * GIB - 1) == ("degraded", "internal-disk-low")
    assert budget.judge(0, 10 * GIB - 1) == ("unavailable", "internal-disk-critical")
    # The critical floor wins over every footprint reading.
    assert budget.judge(int(6.5 * GIB), 1 * GIB)[1] == "internal-disk-critical"
    assert budget.free_bytes() > 0


def test_the_complete_realms_take_the_production_budget_and_earlier_realms_keep_theirs(realm):
    assert isinstance(capacity_budget(realm), CapacityBudget)
    assert capacity_budget(dataclasses.replace(realm, realm="production")) is not None
    for earlier in ("account-controls", "approved-export", "topics-digests"):
        assert capacity_budget(dataclasses.replace(realm, realm=earlier)) is None
    # Transactions without a profile (an earlier unit's test double) keep the built rule.
    assert capacity_budget(None) is None


class FootprintTransactions:
    """A fixed-answer stub for a refusal that real data cannot reach (your answer of
    2026-11-11, "Rewrite, keep two"): the one footprint U2's synthetic rule refuses,
    410 MiB, which a realm's own small database never holds. It is passed only to the
    refresh whose refusal the test asserts."""

    def run(self, owner, action):
        assert owner == "operations"
        return {"database_bytes": 410 * MIB, "wal_bytes": 0}


def test_the_synthetic_rule_is_unchanged_for_earlier_realms(realm, transactions):
    earlier = dataclasses.replace(realm, realm="approved-export", database_name="docsuri_u6")
    # A profile only: the choice and the refusal below read no store.
    capacity = complete_capacity(SimpleNamespace(profile=earlier))
    assert type(capacity) is ControlCapacity
    # U2's built rule on the realm's own footprint, read from its database.
    built = ControlCapacity(transactions)
    built.refresh()
    assert built.probes == 1 and built.last_bytes > 0 and not hasattr(built, "budget")
    assert built.admitting == (built.last_bytes < 512 * MIB * 4 // 5)
    above = ControlCapacity(FootprintTransactions())
    above.refresh()
    assert not above.admitting
    # The budgeted capacity refuses every realm but the two complete ones.
    with pytest.raises(ValueError):
        BudgetedCapacity(SimpleNamespace(profile=earlier))


def test_the_realm_refresh_reads_the_real_footprint_and_disk(transactions):
    capacity = complete_capacity(transactions)
    assert isinstance(capacity, BudgetedCapacity)
    assert capacity.admitting is False and capacity.state == "unknown"
    capacity.refresh()
    assert capacity.probes == 1 and capacity.last_bytes > 0 and capacity.last_free > 0
    assert (capacity.state, capacity.reason) == capacity.budget.judge(
        capacity.last_bytes, capacity.last_free
    )
    assert capacity.admitting == (capacity.state != "unavailable")


def admission_app(capacity) -> FastAPI:
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    app.post("/api/v2/c07/accept-research-turn")(lambda: {"accepted": True})
    app.get("/health/ready")(lambda: {"ready": True})
    app.post("/api/v2/c02/access-inspect-session")(lambda: {"recovery": True})
    app.add_middleware(ControlAdmission, capacity=capacity)
    return app


@pytest.mark.parametrize(
    ("change", "reason"),
    [("free", "internal-disk-critical"), ("footprint", "capacity-exhausted")],
)
async def test_admission_closes_with_capacity_exhausted_while_recovery_routes_stay_open(
    transactions, monkeypatch, change, reason
):
    capacity = complete_capacity(transactions)
    if change == "free":
        monkeypatch.setattr(capacity.budget, "free_bytes", lambda: 5 * GIB)
    else:
        monkeypatch.setattr(capacity.budget, "exhausted", 0)
    capacity.refresh()
    assert (capacity.state, capacity.reason, capacity.admitting) == ("unavailable", reason, False)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=admission_app(capacity)), base_url="http://127.0.0.1"
    ) as http:
        refused = await http.post("/api/v2/c07/accept-research-turn", json={})
        ready = await http.get("/health/ready")
        recovery = await http.post("/api/v2/c02/access-inspect-session", json={})
    assert refused.status_code == 503
    assert refused.json()["messageKey"] == "capacity.exhausted"
    assert ready.status_code == 200 and recovery.status_code == 200


async def until(condition, seconds: float = 10.0) -> None:
    """Wait until `condition()` holds, re-read every 0.01 s for at most `seconds`: the
    wait ends on the refresher's own count, never after a fixed time."""
    deadline = asyncio.get_running_loop().time() + seconds
    while not condition():
        assert asyncio.get_running_loop().time() < deadline, "the refresher never got there"
        await asyncio.sleep(0.01)


async def test_the_refresher_keeps_the_hosts_capacity_current(transactions):
    capacity = complete_capacity(transactions)
    refresher = CapacityRefresher(capacity, interval=0.05)
    refresher.start()
    await until(lambda: refresher.status["refreshes"] >= 2)
    await refresher.close()
    assert refresher.status["refreshes"] >= 2 and refresher.status["state"] == "stopped"
    assert capacity.probes == refresher.status["refreshes"]
    with pytest.raises(ValueError):
        CapacityRefresher(capacity, interval=10)
    with pytest.raises(ValueError):
        refresher.start()
    # It refreshes only U8's capacity, never a built one.
    with pytest.raises(TypeError):
        CapacityRefresher(ControlCapacity(transactions))


async def test_a_failed_refresh_closes_admission_until_the_next_one(realm, monkeypatch):
    class Failing:
        profile = realm

        def run(self, owner, action):
            raise ValueError("store unavailable")

    capacity = BudgetedCapacity(Failing())
    capacity.admitting = True
    refresher = CapacityRefresher(capacity, interval=0.05)
    refresher.start()
    await until(lambda: refresher.status["failures"] >= 1)
    await refresher.close()
    assert refresher.status["failures"] >= 1 and capacity.admitting is False
    assert capacity.state == "unknown"


def test_the_host_runs_the_refresher_over_its_own_admission(realm):
    from backend.u8_host import compose, host_app

    composition = compose(realm)
    try:
        app = host_app(composition)
        assert isinstance(app.state.capacity_refresher, CapacityRefresher)
        assert isinstance(app.state.control_capacity, BudgetedCapacity)
        assert app.state.capacity_refresher.capacity is app.state.control_capacity
        assert any(item.cls is ControlAdmission for item in app.user_middleware)
    finally:
        composition.close()


# --- the free-space readers (U8 plan Step 69(c); S3) -------------------------------------------


def statvfs_stand_in(**fields):
    from types import SimpleNamespace

    calls: list[str] = []

    def statvfs(path):
        calls.append(str(path))
        return SimpleNamespace(**fields)

    return statvfs, calls


def test_free_space_is_f_bavail_times_f_frsize(tmp_path, monkeypatch, transactions):
    import datetime as dt
    import os
    import shutil

    from backend.modules.operations.observation_store import ObservationStore
    from backend.modules.operations.observations import Observations
    from backend.modules.operations.producers import CapacityProducer, ProducerSchedule
    from docsuri_ops.backup_agent import status

    statvfs, _ = statvfs_stand_in(f_bsize=1048576, f_frsize=4096, f_blocks=10000,
                                  f_bfree=5000, f_bavail=1000)
    monkeypatch.setattr(os, "statvfs", statvfs)
    assert CapacityBudget(PRODUCTION_OPERATIONS, tmp_path).free_bytes() == 4_096_000
    assert shutil.disk_usage(tmp_path).free == 4_096_000
    assert status.free_bytes(tmp_path) == 4_096_000

    # The schedule half: 100 GiB available, the footprint injected.
    statvfs, calls = statvfs_stand_in(f_frsize=4096, f_bavail=26_214_400, f_bfree=26_214_400,
                                      f_blocks=52_428_800)
    monkeypatch.setattr(os, "statvfs", statvfs)
    producer = CapacityProducer(transactions, PRODUCTION_OPERATIONS, disk_path=tmp_path,
                                volume_state=lambda: "mounted", agent_status=None,
                                expected_volume=None, footprint=lambda: 1 * GIB)
    # An hour in the past, so the realm's own latest storage.capacity row stays newest.
    t0 = dt.datetime.now(dt.UTC).replace(microsecond=0) - dt.timedelta(hours=1)
    schedule = ProducerSchedule([producer], Observations(ObservationStore(transactions)),
                                PRODUCTION_OPERATIONS, lambda: t0)
    assert producer.observe(t0).outcome == "available"
    calls.clear()
    assert schedule.interval(producer) == 60
    assert schedule.run_due(t0) == ["storage.capacity"]
    assert schedule.run_due(t0 + dt.timedelta(seconds=59)) == []
    assert schedule.run_due(t0 + dt.timedelta(seconds=60)) == ["storage.capacity"]
    assert len(calls) == 2  # one statvfs call per observation
    rows = transactions.run("operations", lambda conn: conn.execute(
        "SELECT outcome FROM operations.observation_record WHERE capability="
        "'storage.capacity' AND observed_at IN (%s,%s)",
        (t0, t0 + dt.timedelta(seconds=60))).fetchall())
    assert [row["outcome"] for row in rows] == ["available", "available"]


def test_a_production_volume_that_is_missing_or_not_mounted_reads_unavailable(tmp_path):
    from types import SimpleNamespace

    from backend.u8_host import backup_volume_state

    plain = tmp_path / "plain"
    plain.mkdir()
    for mount in (tmp_path / "missing", plain):
        profile = SimpleNamespace(is_production=True, backup_mount=str(mount))
        assert backup_volume_state(profile) == "unavailable"
    assert backup_volume_state(SimpleNamespace(is_production=True, backup_mount="/")) == (
        "mounted")


def test_a_disk_guard_built_without_a_floor_takes_the_policys_critical_floor(monkeypatch):
    from backend import u8_policy
    from docsuri_ops.migration.disk_guard import CRITICAL, DiskGuard, DiskStopped

    guard = DiskGuard(lambda: 10 * GIB - 1, 20 * GIB)
    assert guard.critical_bytes == PRODUCTION_OPERATIONS.internal_disk_critical_bytes
    with pytest.raises(DiskStopped) as stopped:
        guard.boundary(to_write=0, held=lambda: 0)("paper")
    assert stopped.value.reason == CRITICAL
    # A changed policy reaches a guard built afterwards without the argument.
    changed = dataclasses.replace(PRODUCTION_OPERATIONS, internal_disk_critical_bytes=12 * GIB)
    monkeypatch.setattr(u8_policy, "PRODUCTION_OPERATIONS", changed)
    assert DiskGuard(lambda: 0, 20 * GIB).critical_bytes == 12 * GIB


def test_a_phase_boundary_reads_what_is_held_before_the_free_space():
    from docsuri_ops.migration.disk_guard import LOW, DiskGuard, DiskStopped

    order: list[str] = []

    def free() -> int:
        order.append("free")
        return 30 * GIB

    def held() -> int:
        order.append("held")
        return 0

    guard = DiskGuard(free, 20 * GIB, critical_bytes=10 * GIB)
    # A paper boundary reads the free space alone.
    guard.boundary(to_write=5 * GIB, held=held)("paper")
    assert order == ["free"]
    # A phase start reads what is held first, as `room`'s callers do.
    order.clear()
    guard.boundary(to_write=5 * GIB, held=held)("phase")
    assert order == ["held", "free"]
    # The same order when the room rule refuses: 30 GiB less 10 GiB to write is not
    # above the 20 GiB threshold.
    order.clear()
    with pytest.raises(DiskStopped) as stopped:
        guard.boundary(to_write=10 * GIB, held=held)("phase")
    assert stopped.value.reason == LOW
    assert order == ["held", "free"]
