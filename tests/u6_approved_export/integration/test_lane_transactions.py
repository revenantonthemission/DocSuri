"""The export lane against the realm with its thread running: no database transaction
is open while the fake Notion answers a write (D8); a worker pass through the shared
control loop returns within its deadline while the lane runs a slow write (D9); and on
shutdown the lane stops taking items and finishes the one in hand (security design
§8.1, §8.2)."""

import threading
import time

from backend.control_runtime import ControlLoop
from backend.modules.export.fake_notion import Answer
from backend.modules.export.worker import ExportWorker

from tests.u6_approved_export import lane_flows as lf
from tests.u6_approved_export import notion_flows as nf

# The application name every runtime transaction pool of the realm sets.
RUNTIME_APPLICATIONS = "docsuri-approved-export-%"
SLOW_WRITE_SECONDS = 3


class Inherited:
    """The inherited bounded pass: nothing due in the earlier units."""

    def run_once(self, limit=1):
        return {}


def open_transactions(connect) -> list:
    """Runtime sessions of the export role holding a transaction right now."""
    with connect("export") as conn:
        return conn.execute(
            "SELECT pid,state,application_name FROM pg_stat_activity "
            "WHERE datname=current_database() AND pid<>pg_backend_pid() "
            "AND application_name LIKE %s AND xact_start IS NOT NULL",
            (RUNTIME_APPLICATIONS,),
        ).fetchall()


def test_no_transaction_is_open_while_notion_answers_a_write(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    seen: list = []
    lf.on_write(lr.fake, lambda: seen.append(open_transactions(connect)))
    step = lf.own_step(lr, lr.lane, [lf.effect_id(flow["effect"])])

    lr.lane.start()
    try:
        assert step.run_once()["handedOver"] == "execute"
        lf.wait_for(lambda: lf.row(connect, flow["effect"])["state"] == "succeeded")
    finally:
        assert lr.lane.stop()
    assert seen == [[]]
    assert len(lr.fake.writes) == 1


def test_a_pass_returns_within_its_deadline_while_the_lane_runs_a_slow_write(
    transactions, connect, authority, tmp_path
):
    policy = nf.policy(write_deadline_seconds=SLOW_WRITE_SECONDS * 3)
    lr = lf.build(transactions, connect, authority, tmp_path, policy=policy)
    flow = lf.pressed(lr)
    writing = threading.Event()
    lf.on_write(lr.fake, writing.set)
    lr.fake.queue("pages.create", Answer.slow(SLOW_WRITE_SECONDS))
    step = lf.own_step(lr, lr.lane, [lf.effect_id(flow["effect"])])
    loop = ControlLoop(ExportWorker(Inherited(), step))

    lr.lane.start()
    try:
        loop.pass_once()
        assert writing.wait(10)
        started = time.monotonic()
        loop.pass_once()
        elapsed = time.monotonic() - started
        assert not lr.lane.idle
        assert lf.row(connect, flow["effect"])["state"] == "executing"
        lf.wait_for(lambda: lf.row(connect, flow["effect"])["state"] == "succeeded")
    finally:
        assert lr.lane.stop()
    assert elapsed < loop.deadline
    assert elapsed < SLOW_WRITE_SECONDS
    assert len(lr.fake.writes) == 1


def test_shutdown_stops_taking_items_and_finishes_the_one_in_hand(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    writing = threading.Event()
    lf.on_write(lr.fake, writing.set)
    lr.fake.queue("pages.create", Answer.slow(1))
    step = lf.own_step(lr, lr.lane, [lf.effect_id(flow["effect"])])

    lr.lane.start()
    assert step.run_once()["handedOver"] == "execute"
    assert writing.wait(10)
    assert lr.lane.stop()
    # The write in hand finished and was recorded before the lane ended.
    assert lf.row(connect, flow["effect"])["state"] == "succeeded"
    assert not lr.lane.running and not lr.lane.idle
    later = lf.pressed(lr, configure=False)
    assert not lr.lane.offer(lf.item(later["effect"]))
    assert lf.row(connect, later["effect"])["state"] == "accepted"
