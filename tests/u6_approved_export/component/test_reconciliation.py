"""Reconciliation scans run by the lane: every scan result and possible duplicates, the
connection facts of a marker found, the settling interval between two clean scans, the
end of scanning, scans after a disconnect, and the writer identity taken from the
attempts (BR4.4, BR4.5, BR1.4, NFR4.7; security design §9.4)."""

import datetime as dt

from backend.modules.export.fake_notion import LOST_AFTER_SUCCESS, Answer

from tests.u6_approved_export import lane_flows as lf


def unknown(lr, *, with_page: bool) -> dict:
    """A pressed export whose write ended unclear: with the page created in the fake (a
    lost response) or with nothing created (a 500)."""
    flow = lf.pressed(lr)
    answer = Answer.of(LOST_AFTER_SUCCESS) if with_page else Answer.error(500)
    lr.fake.queue("pages.create", answer)
    assert lr.lane.run_item(lf.item(flow["effect"])) == "unknown"
    flow["marker"] = lr.repo.effect_binding(lf.effect_id(flow["effect"]))["effect"]["marker"]
    flow["created"] = lr.fake.pages_under(flow["page"])
    assert len(flow["created"]) == (1 if with_page else 0)
    return flow


def scan(lr, connect, flow) -> str:
    return lr.lane.run_item(lf.item(lf.row(connect, flow["effect"]), "scan"))


def test_a_marker_found_succeeds_with_the_earliest_page_and_keeps_the_others(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = unknown(lr, with_page=True)
    [original] = flow["created"]
    later = lr.clock.now + dt.timedelta(minutes=2)
    duplicate = lr.fake.add_page(
        title="copy", parent_id=flow["page"], created_by=lr.rig.bot, created_time=later
    )
    lr.fake.add_block(duplicate, text=flow["marker"])

    assert scan(lr, connect, flow) == "scan-marker-found"
    row = lf.row(connect, flow["effect"])
    assert (row["state"], row["settled_by"]) == ("succeeded", "reconciliation")
    assert row["remote_url"].endswith(original)
    [check] = lf.checks(connect, flow["effect"])
    assert check["remote_reference"] == original
    assert [page["remoteReference"] for page in check["other_marked_pages"]] == [duplicate]
    effect = lr.repo.read_effect(authority, lf.effect_id(flow["effect"]), now=lr.clock.now)
    assert [page["remoteReference"] for page in effect["possibleDuplicates"]] == [duplicate]
    connection = lf.connection(connect, lr.rig)
    assert connection["last_destination_id"] == flow["page"]
    assert connection["creation_capability"] == "confirmed"


def test_the_second_clean_scan_must_follow_the_first_by_a_settling_interval(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = unknown(lr, with_page=False)
    settling = lr.rig.policy.settling_wait_seconds

    assert scan(lr, connect, flow) == "scan-not-found"
    lr.clock.advance(settling - 1)
    assert scan(lr, connect, flow) == "scan-not-found"
    assert lf.row(connect, flow["effect"])["state"] == "unknown"

    lr.clock.advance(1)
    assert scan(lr, connect, flow) == "scan-not-found"
    row = lf.row(connect, flow["effect"])
    assert (row["state"], row["outcome_reason"], row["settled_by"]) == (
        "failed",
        "not-found-after-checks",
        "reconciliation",
    )
    assert [check["result"] for check in lf.checks(connect, flow["effect"])] == [
        "not-found"
    ] * 3


def test_partial_and_unreadable_scans_keep_the_effect_unknown(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = unknown(lr, with_page=False)

    lr.fake.queue("blocks.children", Answer.error(500), target=flow["page"])
    assert scan(lr, connect, flow) == "scan-listing-incomplete"
    lr.clock.advance(1)
    lr.fake.page(flow["page"]).readable = False
    assert scan(lr, connect, flow) == "scan-listing-unavailable"

    row = lf.row(connect, flow["effect"])
    assert row["state"] == "unknown" and row["next_check_at"] is not None
    assert [check["result"] for check in lf.checks(connect, flow["effect"])] == [
        "listing-incomplete",
        "listing-unavailable",
    ]


def test_after_a_disconnect_scans_record_listing_unavailable(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = unknown(lr, with_page=True)
    lr.rig.service.disconnect(authority, {})
    reads_before = len(lr.fake.requests)

    assert scan(lr, connect, flow) == "scan-listing-unavailable"
    row = lf.row(connect, flow["effect"])
    assert row["state"] == "unknown"
    # No token exists any more, so nothing was asked of Notion.
    assert len(lr.fake.requests) == reads_before


def test_scanning_stops_once_the_check_period_is_spent(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = unknown(lr, with_page=False)
    policy = lr.rig.policy
    lr.clock.advance(policy.write_deadline_seconds + policy.check_total_seconds + 1)

    assert scan(lr, connect, flow) == "scan-not-found"
    row = lf.row(connect, flow["effect"])
    assert row["state"] == "unknown"
    assert row["next_check_at"] is None
    assert row["scanning_stopped_at"] == lr.clock.now
    assert lr.rig.read_effect(flow["effect"])["settlementOffered"] is True


def test_the_writer_identity_comes_from_the_attempts_not_the_current_connection(
    transactions, connect, authority, tmp_path
):
    lr = lf.build(transactions, connect, authority, tmp_path)
    flow = unknown(lr, with_page=True)
    [original] = flow["created"]
    token, new_bot = lr.rig.new_token()
    lr.rig.configure(token=token, expected=lr.rig.connection()["revision"])
    # A page by the new integration carrying the marker is not a candidate.
    decoy = lr.fake.add_page(title="decoy", parent_id=flow["page"], created_by=new_bot)
    lr.fake.add_block(decoy, text=flow["marker"])

    assert scan(lr, connect, flow) == "scan-marker-found"
    [check] = lf.checks(connect, flow["effect"])
    assert check["remote_reference"] == original
    assert check["other_marked_pages"] == []
    [attempt] = lf.attempts(connect, flow["effect"])
    assert attempt["writer_identity"] == lr.rig.bot != new_bot
    assert lf.connection(connect, lr.rig)["creation_capability"] == "unknown"
