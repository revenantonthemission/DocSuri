"""Real role permissions and reserved PostgreSQL capacity under normal load."""

import threading
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from backend.control_runtime import RECOVERY_REQUEST, ControlCapacity
from backend.transactions import Busy

pytestmark = pytest.mark.u2_operations


def test_capacity_aggregate_is_ops_only_and_observed_before_admission(transactions):
    capacity = ControlCapacity(transactions)
    assert not capacity.admitting
    capacity.refresh()
    assert 0 < capacity.last_bytes < 512 * 1024 * 1024 * 4 // 5
    assert capacity.admitting and capacity.probes == 1
    for owner in ("accounts", "library"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            transactions.run(
                owner,
                lambda conn: conn.execute(
                    "SELECT * FROM operations.capacity_footprint()"
                ).fetchone(),
            )


def test_five_normal_db_actions_cannot_consume_recovery_budget(transactions):
    release = threading.Event()
    started = [threading.Event() for _ in range(5)]
    owners = ["accounts", "library", "personalization", "usage", "discovery"]

    def hold(index):
        def action(conn):
            conn.execute("SELECT 1")
            started[index].set()
            if not release.wait(3):
                raise RuntimeError("test release deadline reached")
            return index

        return transactions.run(owners[index], action)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(hold, index) for index in range(5)]
        try:
            assert all(event.wait(1) for event in started)
            with pytest.raises(Busy, match="allocation exhausted"):
                transactions.run("operations", lambda conn: pytest.fail("normal request admitted"))
            token = RECOVERY_REQUEST.set(True)
            try:
                row = transactions.run(
                    "operations",
                    lambda conn: conn.execute(
                        "SELECT * FROM operations.capacity_footprint()"
                    ).fetchone(),
                )
                assert row["database_bytes"] > 0
            finally:
                RECOVERY_REQUEST.reset(token)
        finally:
            release.set()
        assert [future.result(timeout=1) for future in futures] == list(range(5))
