"""U6:security-design:lifecycle-in-flight: withdraw and erase while the lane is working.

With `lane_flows.on_write` (or its children-request variant) a lifecycle ticket commits
while the fake answers the lane: an erase leaves the created Notion page but no rows, a
withdraw during a saved-but-busy create leaves one uncertain attempt and no read-back, a
plain create still succeeds against the withdrawn revision, and an erase during a scan
records no check (BR6.1, BR6.2, security design §13).
"""

import logging
from uuid import UUID

from backend.modules.export.control_lifecycle import ExportLifecycleParticipant
from backend.modules.export.fake_notion import SAVED_BUSY, Answer
from tests.u6_approved_export import export_rows as rows
from tests.u6_approved_export import lane_flows as lf
from tests.u6_approved_export import service_flows as sf
from tests.u6_approved_export import store_flows as flows

ACCOUNT_TABLES = ("connection", "preview_pair", "preview_revision", "approval", "effect",
                  "replay_record")


def participant(lr) -> ExportLifecycleParticipant:
    return ExportLifecycleParticipant(lr.rig.transactions)


def apply_erase(lr, tickets) -> None:
    participant(lr).apply(tickets["live_records"])
    participant(lr).apply(tickets["external_copies"])


def build(transactions, connect, authority, tmp_path):
    return lf.build(
        transactions, connect, authority, tmp_path, research=sf.real_research(transactions)
    )


def test_an_erase_during_a_write_leaves_the_page_but_no_rows(
    transactions, connect, authority, tmp_path, caplog
):
    lr = build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    tickets = rows.participant_tickets(
        connect, authority.account_id, "erase", ("live_records", "external_copies")
    )
    lr.repo.record_lane_status("baseline")
    baseline = lf.latest_lane_status(connect)
    caplog.set_level(logging.DEBUG, logger="docsuri.export.lane")
    lf.on_write(lr.fake, lambda: apply_erase(lr, tickets))
    step = lf.own_step(lr, lr.lane, [lf.effect_id(flow["effect"])])

    lr.lane.start()
    try:
        assert step.run_once()["handedOver"] == "execute"
        lf.wait_for(lambda: len(lr.fake.writes) == 1 and lr.lane.idle)
        # The lane survived the in-flight erase: still running and idle.
        assert lr.lane.running and lr.lane.idle
    finally:
        assert lr.lane.stop()

    assert len(lr.fake.pages_under(flow["page"])) == 1  # created, still in Notion
    with connect("export") as conn:
        for table in ACCOUNT_TABLES:
            if table == "preview_revision":
                count = conn.execute(
                    "SELECT count(*) AS n FROM export.preview_revision r "
                    "JOIN export.preview_pair p ON p.preview_id=r.preview_id "
                    "WHERE p.account_id=%s",
                    (authority.account_id,),
                ).fetchone()["n"]
            else:
                count = conn.execute(
                    f"SELECT count(*) AS n FROM export.{table} WHERE account_id=%s",
                    (authority.account_id,),
                ).fetchone()["n"]
            assert count == 0, table
        attempts = conn.execute(
            "SELECT count(*) AS n FROM export.attempt a JOIN export.effect e "
            "ON e.id=a.effect_id WHERE e.account_id=%s",
            (authority.account_id,),
        ).fetchone()["n"]
        recorded = conn.execute(
            "SELECT exports_in_flight,pages_possibly_created FROM export.lifecycle_counts "
            "WHERE request_id=%s AND scope='live_records'",
            (tickets["live_records"]["request_id"],),
        ).fetchone()
    status = lf.latest_lane_status(connect)
    assert attempts == 0
    assert status["outcome"] == "skipped"
    assert status["observed_at"] > baseline["observed_at"]
    assert recorded == {"exports_in_flight": 1, "pages_possibly_created": 1}
    assert "ended early" not in caplog.text


def test_a_withdraw_during_a_saved_but_busy_create(
    transactions, connect, authority, tmp_path
):
    lr = build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    connection_id = UUID(lr.rig.connection()["connectionId"])
    tickets = rows.participant_tickets(
        connect, authority.account_id, "withdraw", ("live_records",)
    )
    seen = {}

    def withdraw_now():
        seen["requests"] = len(lr.fake.requests)
        participant(lr).apply(tickets["live_records"])

    lr.fake.queue("pages.create", Answer.of(SAVED_BUSY))
    lf.on_write(lr.fake, withdraw_now)
    step = lf.own_step(lr, lr.lane, [lf.effect_id(flow["effect"])])

    lr.lane.start()
    try:
        assert step.run_once()["handedOver"] == "execute"
        lf.wait_for(
            lambda: lf.row(connect, flow["effect"])["state"] == "unknown" and lr.lane.idle
        )
    finally:
        assert lr.lane.stop()

    # The hook fires as the create arrives (before the fake logs it), so the only
    # request after the ticket is that one in-flight create; no read-back followed.
    assert len(lr.fake.requests) == seen["requests"] + 1
    attempts = lf.attempts(connect, flow["effect"])
    assert [attempt["response_class"] for attempt in attempts] == ["uncertain"]
    connection = flows.connection_row(connect, connection_id)
    assert connection["state"] == "disconnected"
    assert lr.repo.open_token_envelope(authority.account_id, connection_id) is None
    row = lf.row(connect, flow["effect"])
    assert row["state"] == "unknown"
    view = lr.rig.service.read_effect(authority, {"effectId": flow["effect"]["effectId"]})
    assert view["settlementOffered"] is False


def test_a_plain_create_in_flight_survives_a_withdraw(
    transactions, connect, authority, tmp_path
):
    lr = build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    connection_id = UUID(lr.rig.connection()["connectionId"])
    tickets = rows.participant_tickets(
        connect, authority.account_id, "withdraw", ("live_records",)
    )
    lf.on_write(lr.fake, lambda: participant(lr).apply(tickets["live_records"]))
    step = lf.own_step(lr, lr.lane, [lf.effect_id(flow["effect"])])

    lr.lane.start()
    try:
        assert step.run_once()["handedOver"] == "execute"
        lf.wait_for(
            lambda: lf.row(connect, flow["effect"])["state"] == "succeeded" and lr.lane.idle
        )
    finally:
        assert lr.lane.stop()

    row = lf.row(connect, flow["effect"])
    assert (row["state"], row["settled_by"]) == ("succeeded", "provider")
    connection = flows.connection_row(connect, connection_id)
    assert connection["state"] == "disconnected"
    assert connection["creation_capability"] == "unknown"
    assert connection["last_destination_id"] is not None
    approval = flows.approval_row(connect, UUID(flow["approval"]["approvalId"]))
    assert approval["state"] == "consumed"


def test_an_erase_during_a_scan_records_no_check(
    transactions, connect, authority, tmp_path
):
    lr = build(transactions, connect, authority, tmp_path)
    flow = lf.pressed(lr)
    effect = lr.rig.uncertain(flow["effect"])
    lr.rig.clock.advance(300)
    tickets = rows.participant_tickets(
        connect, authority.account_id, "erase", ("live_records", "external_copies")
    )
    lf.on_write(
        lr.fake,
        lambda: apply_erase(lr, tickets),
        method="GET",
        path=f"/v1/blocks/{flow['page']}/children",
    )
    step = lf.own_step(lr, lr.lane, [lf.effect_id(effect)])

    lr.lane.start()
    try:
        assert step.run_once()["handedOver"] == "scan"
        lf.wait_for(lambda: lr.lane.idle)
    finally:
        assert lr.lane.stop()

    assert lf.checks(connect, effect) == []
    with connect("export") as conn:
        remaining = conn.execute(
            "SELECT count(*) AS n FROM export.effect WHERE account_id=%s",
            (authority.account_id,),
        ).fetchone()["n"]
    assert remaining == 0
    assert lf.latest_lane_status(connect)["outcome"] == "skipped"
