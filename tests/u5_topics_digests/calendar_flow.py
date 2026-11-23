"""Calendar helpers over the real realm, shared by
`component/test_schedule_preferences.py` and `component/test_topics_scheduler.py` (plan
Step 46, decision L4-4), moved unchanged from `test_schedule_preferences.py`.

`topics.next_occurrence` honours a boundary stamped by the realm's clock
(`clock_timestamp()`): the follow, the settings save and the zone confirmation. So every
date is derived from one reading of that same clock (`run_clock`): the next autumn fold
and spring gap of a zone after it, and the next calendar days. No date is pinned, and
each case keeps its meaning on any run date. The clock-change days and the first valid
instant come from the zone database, not from the code under test."""

import datetime as dt
from uuid import uuid4
from zoneinfo import ZoneInfo

from backend.modules.personalization.guarded_service import GuardedSettingsService
from backend.modules.topics.repository import TopicsRepository
from backend.modules.topics.service import TopicsService

NEW_YORK = ZoneInfo("America/New_York")
# Far enough ahead to stay out of every bounded due window and realm expiry.
FAR_AHEAD = dt.timedelta(days=400)


def run_clock(connect):
    """One reading of the clock that stamps the follow, settings and zone boundary."""
    with connect("topics") as conn:
        return conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]


def utc_date_after(now, days):
    return now.astimezone(dt.UTC).date() + dt.timedelta(days=days)


def next_transition(now, zone, *, fold):
    """The first calendar date, two or more days after `now`, that starts with a changed
    offset: a fold when the offset shrinks (autumn), a gap when it grows (spring)."""
    day = now.astimezone(zone).date() + dt.timedelta(days=2)
    for _ in range(400):
        before = dt.datetime.combine(day - dt.timedelta(days=1), dt.time(12), zone).utcoffset()
        after = dt.datetime.combine(day, dt.time(12), zone).utcoffset()
        if (after < before) if fold else (after > before):
            return day
        day += dt.timedelta(days=1)
    raise AssertionError(f"{zone} has no {'fold' if fold else 'gap'} within 400 days")


def wall_exists(zone, wall):
    round_trip = wall.replace(tzinfo=zone, fold=0).astimezone(dt.UTC).astimezone(zone)
    return round_trip.replace(tzinfo=None) == wall


def first_valid_instant(zone, day, time):
    """`next_occurrence`'s rule: a missing wall minute is due at the first valid minute
    after the gap, and a repeated wall minute at its first occurrence."""
    wall = dt.datetime.combine(day, time)
    while not wall_exists(zone, wall):
        wall += dt.timedelta(minutes=1)
    return wall.replace(tzinfo=zone, fold=0).astimezone(dt.UTC)


def schedule(transactions, authority, zone, day, time="01:30", cadence="daily"):
    settings = GuardedSettingsService(transactions)
    state = settings.read(authority)
    settings.update(authority, uuid4(), state["revision"], {"timeZone": zone})
    service = TopicsService(transactions)
    topic = service.follow(authority, str(uuid4()), "Clock test")["topicId"]
    service.save_settings(
        authority,
        topic,
        {
            "revision": 1,
            "cadence": cadence,
            "deliveryTimeLocal": time,
            "deliveryDay": "sun" if cadence == "weekly" else None,
            "contentWindowDays": 7,
        },
    )
    repository = TopicsRepository(transactions)
    # A run ending the day before pins the next candidate window to `day`.
    previous = day - dt.timedelta(days=1)
    revision = service.read_topic(authority, topic)["settings"]["revision"]
    repository.prepare_run(topic, previous, previous, revision, [])
    return topic


def occurrence(connect, topic, instant):
    with connect("topics") as conn:
        return conn.execute(
            "SELECT * FROM topics.next_occurrence(%s,%s)", (topic, instant)
        ).fetchone()
