"""Capacity admission for the two complete realms (A10, BR6.6; U8 plan Steps 11 and 44).

U2's `ControlCapacity` keeps the built synthetic rule (512 MiB × 0.8) behind its one
hook, `_admits`. The composed realm and production judge the footprint against
scalability-design § 3.2's budget instead, through `BudgetedCapacity`, which exists only
in those two realms. `complete_capacity` gives each realm its capacity, and the host's
`CapacityRefresher` refreshes only U8's (the person's decision of 2026-10-24, "Move,
scope tools, test U2").
"""

from __future__ import annotations

import asyncio
import os

from backend.control_runtime import ControlCapacity

COMPLETE_REALMS = frozenset({"service-operations", "production"})


class CapacityBudget:
    """scalability-design § 3.2–3.3 for the production and composed profiles (BR6.6).

    The footprint (A10: the current database plus the instance's WAL) is degraded with
    `capacity-approaching` from 80% of the 8 GiB budget and unavailable with
    `capacity-exhausted` from the budget less 256 MiB of headroom. The internal disk is
    unavailable below its 10 GiB critical floor (`internal-disk-critical`). Admission
    closes only when one of them is unavailable."""

    def __init__(self, policy, disk_path):
        self.budget = policy.footprint_budget_bytes
        self.warning = int(policy.footprint_budget_bytes * policy.footprint_warning_ratio)
        self.exhausted = policy.footprint_budget_bytes - policy.footprint_headroom_bytes
        self.disk_threshold = policy.internal_disk_threshold_bytes
        self.disk_critical = policy.internal_disk_critical_bytes
        self.disk_path = disk_path

    def free_bytes(self) -> int:
        """The space macOS reports to programs: `f_bavail × f_frsize` (S3)."""
        info = os.statvfs(self.disk_path)
        return info.f_bavail * info.f_frsize

    def judge(self, footprint: int, free: int) -> tuple[str, str | None]:
        """(state, reason key) for one footprint and one free-space reading."""
        if free < self.disk_critical:
            return "unavailable", "internal-disk-critical"
        if footprint >= self.exhausted:
            return "unavailable", "capacity-exhausted"
        if footprint >= self.warning:
            return "degraded", "capacity-approaching"
        if free < self.disk_threshold:
            return "degraded", "internal-disk-low"
        return "available", None


def capacity_budget(profile):
    """The profile's budget: U8's for the composed and production realms, None (the
    synthetic 512 MiB rule) for every earlier realm, and for transactions that carry no
    profile at all."""
    if getattr(profile, "realm", None) not in COMPLETE_REALMS:
        return None
    from backend.u8_policy import PRODUCTION_OPERATIONS

    return CapacityBudget(PRODUCTION_OPERATIONS, profile.root)


class BudgetedCapacity(ControlCapacity):
    """`ControlCapacity` judged against the complete realms' budget. It refuses every
    realm but the two complete ones, so no earlier realm can take it. A failed refresh
    closes admission and leaves the state unknown until the next one succeeds."""

    def __init__(self, transactions):
        budget = capacity_budget(getattr(transactions, "profile", None))
        if budget is None:
            raise ValueError("the budgeted capacity runs only in the two complete realms")
        if not callable(getattr(ControlCapacity, "_admits", None)):
            raise TypeError("U2's ControlCapacity lacks its admission hook")
        super().__init__(transactions)
        self.budget = budget
        self.state, self.reason, self.last_free = "unknown", None, None

    def _admits(self, footprint: int) -> bool:
        self.last_free = self.budget.free_bytes()
        self.state, self.reason = self.budget.judge(footprint, self.last_free)
        return self.state != "unavailable"

    def refresh(self):
        try:
            return super().refresh()
        except Exception:
            self.state, self.reason = "unknown", None
            raise


def complete_capacity(transactions):
    """The capacity a realm's host and workers admit by: `BudgetedCapacity` in the two
    complete realms, U2's built `ControlCapacity` everywhere else."""
    if getattr(getattr(transactions, "profile", None), "realm", None) in COMPLETE_REALMS:
        return BudgetedCapacity(transactions)
    return ControlCapacity(transactions)


class CapacityRefresher:
    """The host's own refresh of U8's capacity on the control loop's interval.

    The host runs no lane, so no loop pass refreshes its capacity; without this its
    admission would stay closed (U8 plan Step 11). A failed refresh closes admission
    until the next one succeeds. It refreshes only a `BudgetedCapacity`."""

    def __init__(self, capacity, *, interval=2.0):
        if not isinstance(capacity, BudgetedCapacity):
            raise TypeError("the refresher refreshes only the complete realms' capacity")
        if not 0 < interval <= 4:
            raise ValueError("bounded refresh cadence required")
        self.capacity, self.interval = capacity, interval
        self.stopping = asyncio.Event()
        self.task = None
        self.status = {"state": "stopped", "refreshes": 0, "failures": 0}

    async def run(self):
        try:
            while not self.stopping.is_set():
                try:
                    await asyncio.to_thread(self.capacity.refresh)
                    self.status["refreshes"] += 1
                    self.status["state"] = "running"
                except Exception:
                    self.status["failures"] += 1
                    self.status["state"] = "degraded"
                try:
                    await asyncio.wait_for(self.stopping.wait(), self.interval)
                except TimeoutError:
                    pass
        finally:
            self.status["state"] = "stopped"

    def start(self):
        if self.task is not None:
            raise ValueError("capacity refresher already started")
        self.task = asyncio.create_task(self.run())

    async def close(self):
        self.stopping.set()
        if self.task is not None:
            await self.task
