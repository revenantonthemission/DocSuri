"""D6, security design §9.2: one pace record per connection, on the database clock."""

import datetime as dt
from uuid import uuid4

from backend.transactions import OwnerTransactions

from tests.u6_approved_export import export_rows as rows
from tests.u6_approved_export import store_flows as flows

INTERVAL = dt.timedelta(milliseconds=500)


def pace_connection(connect):
    with connect("export") as conn:
        connection, _, _ = rows.reserve(conn)
    return connection


def test_two_transaction_pools_share_one_pace(realm, transactions, connect):
    """Two pools (two processes' worth of transactions) never get slots closer than 500 ms."""
    connection = pace_connection(connect)
    second_pool = OwnerTransactions(realm)
    try:
        first = flows.repository(transactions)
        second = flows.repository(second_pool)
        slots = []
        for repo in (first, second, first, second):
            slot = repo.reserve_pace_slot(connection, remaining_seconds=30)
            assert slot is not None and slot.within_budget
            slots.append(slot)
    finally:
        second_pool.close()
    starts = [slot.slot_at for slot in slots]
    gaps = [later - earlier for earlier, later in zip(starts, starts[1:], strict=False)]
    assert len(gaps) == 3 and all(gap >= INTERVAL for gap in gaps)
    assert starts[0] >= slots[0].database_now - INTERVAL
    assert slots[-1].wait_seconds >= 1.0  # three slots queued ahead on the shared clock


def test_a_slot_past_the_remaining_budget_is_reported_and_left_used(transactions, connect):
    repo = flows.repository(transactions)
    connection = pace_connection(connect)
    first = repo.reserve_pace_slot(connection, remaining_seconds=30)
    late = repo.reserve_pace_slot(connection, remaining_seconds=0)
    assert late is not None and late.within_budget is False and late.wait_seconds > 0
    after = repo.reserve_pace_slot(connection, remaining_seconds=30)
    assert late.slot_at - first.slot_at >= INTERVAL
    assert after.slot_at - late.slot_at >= INTERVAL  # the abandoned slot stays spent


def test_a_busy_or_missing_reservation_reports_could_not_check(transactions, connect):
    """A held pace row makes the bounded statement time out: could-not-check, no loop."""
    repo = flows.repository(transactions)
    connection = pace_connection(connect)
    assert repo.reserve_pace_slot(uuid4(), remaining_seconds=30) is None
    holder = connect("export")
    holder.execute(
        "SELECT next_slot_at FROM export.connection_pace WHERE connection_id=%s FOR UPDATE",
        (connection,),
    )
    try:
        assert repo.reserve_pace_slot(connection, remaining_seconds=30) is None
    finally:
        holder.rollback()
    assert repo.reserve_pace_slot(connection, remaining_seconds=30) is not None
