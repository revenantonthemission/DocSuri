"""U6:NFR4.10/check-schedule: the unknown effect's check cadence, as the store records it.

`next_check_time` places checks at the policy's offsets after the attempt's `deadlineAt`;
every recorded scan derives its next point from the same policy fields, so these tests
pin the sequence (L1-5) and the stop conditions (BR4.4) exactly as the code reads them.
"""

import datetime as dt

from backend.modules.export.repository import CheckResult
from tests.u6_approved_export import export_rows as rows
from tests.u6_approved_export import store_flows as flows


def seconds(count: float) -> dt.timedelta:
    return dt.timedelta(seconds=count)


def scan(result: str, base: dt.datetime, instant: dt.datetime) -> CheckResult:
    return CheckResult(
        result=result,
        window_start=base,
        evidence_hash=rows.hex_digest(result, instant.isoformat()),
    )


def unknown_effect(repo, connect, authority, start):
    """A fresh owner's effect taken to unknown; its attempt's deadline is start + 90 s."""
    connection = flows.connected(repo, connect, authority, start)
    effect = flows.bound(repo, authority, connection, start)["effect"]
    return flows.uncertain(repo, effect, start)


def test_listing_incomplete_checks_follow_the_schedule_and_due_items_see_them(
    transactions, connect, authority
):
    repo = flows.repository(transactions)
    start = dt.datetime.now(dt.UTC)
    effect = unknown_effect(repo, connect, authority, start)
    deadline = start + seconds(90)
    current = flows.effect_row(connect, effect["id"])
    assert current["next_check_at"] == deadline + seconds(180)
    for recorded_at, expected in ((180, 600), (600, 1800), (1800, 5400)):
        at = deadline + seconds(recorded_at)
        moved = repo.record_check(
            effect["id"], current["revision"], scan("listing-incomplete", start, at), now=at
        )
        assert moved is not None
        current = flows.effect_row(connect, effect["id"])
        assert (
            current["state"],
            current["next_check_at"],
            current["scanning_stopped_at"],
        ) == ("unknown", deadline + seconds(expected), None)
    due = repo.due_items(deadline + seconds(5400), limit=100)
    assert effect["id"] in [item["id"] for item in due]
    not_due = repo.due_items(deadline + seconds(5399), limit=100)
    assert effect["id"] not in [item["id"] for item in not_due]
    at = deadline + seconds(19800)
    moved = repo.record_check(
        effect["id"], current["revision"], scan("listing-incomplete", start, at), now=at
    )
    assert moved is not None
    current = flows.effect_row(connect, effect["id"])
    assert (
        current["state"],
        current["next_check_at"],
        current["scanning_stopped_at"],
    ) == ("unknown", deadline + seconds(30600), None)


def test_the_schedule_runs_out_and_a_clean_scan_stops_the_wait(transactions, connect, authority):
    repo = flows.repository(transactions)
    start = dt.datetime.now(dt.UTC)
    effect = unknown_effect(repo, connect, authority, start)
    deadline = start + seconds(90)
    current = flows.effect_row(connect, effect["id"])
    near_end = deadline + seconds(73800)
    moved = repo.record_check(
        effect["id"], current["revision"], scan("listing-incomplete", start, near_end), now=near_end
    )
    assert moved is not None
    current = flows.effect_row(connect, effect["id"])
    assert (current["state"], current["next_check_at"]) == ("unknown", deadline + seconds(84600))
    last = deadline + seconds(84600)
    moved = repo.record_check(
        effect["id"], current["revision"], scan("not-found", start, last), now=last
    )
    assert moved is not None
    current = flows.effect_row(connect, effect["id"])
    assert current["state"] == "unknown"
    assert current["next_check_at"] is None
    assert current["scanning_stopped_at"] == last
    view = repo.read_effect(authority, effect["id"], now=last)
    assert view["settlementOffered"] is True
    later = repo.due_items(last + seconds(5400), limit=100)
    assert effect["id"] not in [item["id"] for item in later]
    further = last + seconds(5400)
    moved = repo.record_check(
        effect["id"], current["revision"], scan("listing-unavailable", start, further), now=further
    )
    assert moved is not None
    current = flows.effect_row(connect, effect["id"])
    assert current["next_check_at"] is None and current["scanning_stopped_at"] == last
    with connect("export") as conn:
        checks = conn.execute(
            "SELECT count(*) AS n FROM export.reconciliation_check WHERE effect_id=%s",
            (effect["id"],),
        ).fetchone()["n"]
    assert checks == 3


def test_two_clean_scans_a_settling_interval_apart_fail_the_effect(
    transactions, connect, authority
):
    repo = flows.repository(transactions)
    start = dt.datetime.now(dt.UTC)
    effect = unknown_effect(repo, connect, authority, start)
    deadline = start + seconds(90)
    first_at = deadline + seconds(180)
    current = flows.effect_row(connect, effect["id"])
    moved = repo.record_check(
        effect["id"], current["revision"], scan("not-found", start, first_at), now=first_at
    )
    assert moved is not None
    current = flows.effect_row(connect, effect["id"])
    assert current["state"] == "unknown"
    second_at = first_at + seconds(120)
    moved = repo.record_check(
        effect["id"], current["revision"], scan("not-found", start, second_at), now=second_at
    )
    assert moved is not None
    current = flows.effect_row(connect, effect["id"])
    assert current["state"] == "unknown"
    third_at = second_at + seconds(180)
    moved = repo.record_check(
        effect["id"], current["revision"], scan("not-found", start, third_at), now=third_at
    )
    assert moved is not None
    current = flows.effect_row(connect, effect["id"])
    assert current["state"] == "failed"
    assert current["outcome_reason"] == "not-found-after-checks"
    assert current["settled_by"] == "reconciliation"
    assert current["ended_at"] == third_at
    view = repo.read_effect(authority, effect["id"], now=third_at)
    assert view["settlementOffered"] is False
