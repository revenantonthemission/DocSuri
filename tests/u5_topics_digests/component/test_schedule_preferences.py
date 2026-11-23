"""Calendar occurrence rules use one explicit instant and the real store.

`topics.next_occurrence` honours a boundary stamped by the realm's clock
(`clock_timestamp()`): the follow, the settings save and the zone confirmation. So every
date here is derived from one reading of that same clock, `now`: the next autumn fold and
spring gap of America/New_York after it, the next Sunday, and the next calendar days. No
date is pinned, and each case keeps its meaning on any run date. The instant handed to
`next_occurrence` is the explicit `p_now`, so the cases walk the clock forward without
waiting for it.
"""

import datetime as dt
from uuid import uuid4
from zoneinfo import ZoneInfo

from backend.modules.topics.repository import TopicsRepository
from backend.modules.topics.service import TopicsService

# The calendar helpers moved, unchanged, to `calendar_flow.py` (plan Step 46).
from tests.u5_topics_digests.calendar_flow import (
    FAR_AHEAD,
    NEW_YORK,
    first_valid_instant,
    next_transition,
    occurrence,
    run_clock,
    schedule,
    utc_date_after,
    wall_exists,
)


def test_fall_fold_uses_first_occurrence(transactions, authority, connect):
    now = run_clock(connect)
    day = next_transition(now, NEW_YORK, fold=True)
    topic = schedule(transactions, authority, "America/New_York", day)
    due = first_valid_instant(NEW_YORK, day, dt.time(1, 30))
    # The wall minute 01:30 happens twice that night; the second one is an hour later.
    second = dt.datetime.combine(day, dt.time(1, 30), NEW_YORK).replace(fold=1).astimezone(dt.UTC)
    assert second == due + dt.timedelta(hours=1)
    assert occurrence(connect, topic, due - dt.timedelta(minutes=1)) is None
    row = occurrence(connect, topic, due)
    assert row["due_at"] == due
    assert row["window_day"] == day
    # Through the repeated hour, still one occurrence for the local window.
    assert occurrence(connect, topic, second)["window_day"] == day
    assert occurrence(connect, topic, second)["due_at"] == due


def test_spring_gap_uses_first_valid_minute(transactions, authority, connect):
    now = run_clock(connect)
    day = next_transition(now, NEW_YORK, fold=False)
    topic = schedule(transactions, authority, "America/New_York", day, "02:30")
    assert not wall_exists(NEW_YORK, dt.datetime.combine(day, dt.time(2, 30)))
    due = first_valid_instant(NEW_YORK, day, dt.time(2, 30))
    assert due.astimezone(NEW_YORK).time() == dt.time(3, 0)
    assert occurrence(connect, topic, due - dt.timedelta(minutes=1)) is None
    row = occurrence(connect, topic, due)
    assert row["due_at"] == due
    assert row["window_day"] == day


def test_weekly_requires_wall_time_and_recovers_next_day(transactions, authority, connect):
    now = run_clock(connect)
    start = utc_date_after(now, 2)
    sunday = start + dt.timedelta(days=(6 - start.weekday()) % 7)
    topic = schedule(transactions, authority, "UTC", sunday, "08:00", "weekly")
    due = dt.datetime.combine(sunday, dt.time(8), dt.UTC)
    assert occurrence(connect, topic, due - dt.timedelta(minutes=1)) is None
    # A late tick on Monday still finds Sunday's occurrence and window.
    row = occurrence(connect, topic, due + dt.timedelta(days=1, hours=4))
    assert row["window_day"] == sunday
    assert row["due_at"] == due


def test_same_instant_respects_owner_local_dates(transactions, authority, authority_b, connect):
    now = run_clock(connect)
    day = utc_date_after(now, 2)
    tokyo = schedule(transactions, authority, "Asia/Tokyo", day, "00:00")
    la = schedule(transactions, authority_b, "America/Los_Angeles", day, "00:00")
    # One instant: already `day` in Tokyo, still the day before in Los Angeles.
    instant = dt.datetime.combine(day - dt.timedelta(days=1), dt.time(16), dt.UTC)
    assert instant.astimezone(ZoneInfo("Asia/Tokyo")).date() == day
    assert instant.astimezone(ZoneInfo("America/Los_Angeles")).date() == day - dt.timedelta(days=1)
    assert occurrence(connect, tokyo, instant)["window_day"] == day
    assert occurrence(connect, la, instant) is None


def test_unconfigured_owner_not_due(transactions, authority, connect):
    now = run_clock(connect)
    topic = TopicsService(transactions).follow(authority, str(uuid4()), "Unset")["topicId"]
    with connect("personalization") as conn:
        conn.execute(
            "UPDATE personalization.settings SET defaults=defaults-'timeZone' WHERE account_id=%s",
            (authority.account_id,),
        )
    assert occurrence(connect, topic, now + FAR_AHEAD) is None


def test_zone_confirmation_does_not_schedule_past(transactions, authority, connect):
    now = run_clock(connect)
    day = utc_date_after(now, 1)
    topic = schedule(transactions, authority, "UTC", day, "08:00")
    # Nothing before the confirmation boundary, however the window is pinned.
    assert occurrence(connect, topic, now - dt.timedelta(days=1)) is None
    assert occurrence(connect, topic, now) is None
    assert occurrence(connect, topic, dt.datetime.combine(day, dt.time(8), dt.UTC)) is not None


def test_due_filter_precedes_page_limit(transactions, authority, connect):
    # A future occurrence must not fill the bounded due page ahead of a due one.
    now = run_clock(connect)
    day = utc_date_after(now, 1)
    future = schedule(transactions, authority, "UTC", utc_date_after(now, FAR_AHEAD.days), "08:00")
    due = schedule(transactions, authority, "UTC", day, "08:00")
    page = dt.datetime.combine(day, dt.time(9), dt.UTC)
    rows = TopicsRepository(transactions).due_topics(page, 50)
    assert due in {str(row["id"]) for row in rows}
    assert future not in {str(row["id"]) for row in rows}
