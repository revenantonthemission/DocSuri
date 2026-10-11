"""Finite diagnostic inventory refuses before any reconciliation mutation."""

import json
from uuid import UUID

import pytest

from tests.u1_integrated_paper_journey.fixtures.history import BYTE_LIMIT, HistoryBudget, inventory

pytestmark = pytest.mark.u1_component


class Snapshot:
    def __init__(self, rows, *, count=None, size=None):
        self.rows = [(json.dumps(row),) for row in rows]
        self.count = len(rows) if count is None else count
        self.size = sum(len(row[0].encode()) for row in self.rows) if size is None else size
        self.calls = []
        self.offset = 0

    def execute(self, query, params):
        self.calls.append((query, params))
        return self

    def fetchone(self):
        return self.count, self.size

    def fetchall(self):
        result = self.rows[self.offset : self.offset + 256]
        self.offset += 256
        return result


def test_snapshot_pages_are_bounded_and_all_rows_retained():
    rows = [{"id": str(UUID(int=n + 1)), "payload": "진단"} for n in range(257)]
    conn = Snapshot(rows)
    budget = HistoryBudget()
    assert inventory(conn, "SELECT id,payload FROM fixture", (), "id", budget) == rows
    assert len(conn.calls) == 4  # size, 256, 1, empty
    assert all(params[-1] == 256 for _, params in conn.calls[1:])
    assert budget.selected_bytes == conn.size


@pytest.mark.parametrize("count,size", [(2049, 100), (1, BYTE_LIMIT + 1)])
def test_preflight_overflow_refuses_before_payload_fetch(count, size):
    conn = Snapshot([], count=count, size=size)
    with pytest.raises(AssertionError, match="allocation"):
        inventory(conn, "SELECT id FROM fixture", (), "id", HistoryBudget())
    assert len(conn.calls) == 1 and conn.offset == 0


def test_aggregate_budget_includes_other_owner_selections():
    budget = HistoryBudget()
    budget.reserve(1, BYTE_LIMIT)
    conn = Snapshot([{"id": str(UUID(int=1))}])
    with pytest.raises(AssertionError, match="allocation"):
        inventory(conn, "SELECT id FROM fixture", (), "id", budget)
    assert conn.offset == 0


def test_changed_snapshot_refuses_without_accepting_partial_inventory():
    conn = Snapshot([{"id": str(UUID(int=1))}], count=2)
    with pytest.raises(AssertionError, match="changed"):
        inventory(conn, "SELECT id FROM fixture", (), "id", HistoryBudget())
