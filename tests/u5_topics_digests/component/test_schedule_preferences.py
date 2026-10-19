"""Calendar occurrence rules use one explicit instant and the real store."""

import datetime as dt
from uuid import uuid4

from backend.modules.personalization.guarded_service import GuardedSettingsService
from backend.modules.topics.repository import TopicsRepository
from backend.modules.topics.service import TopicsService


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
    previous = day - dt.timedelta(days=1)
    revision = service.read_topic(authority, topic)["settings"]["revision"]
    repository.prepare_run(topic, previous, previous, revision, [])
    return topic


def occurrence(connect, topic, instant):
    with connect("topics") as conn:
        return conn.execute(
            "SELECT * FROM topics.next_occurrence(%s,%s)", (topic, instant)
        ).fetchone()


def test_fall_fold_uses_first_occurrence(transactions, authority, connect):
    topic = schedule(transactions, authority, "America/New_York", dt.date(2026, 11, 1))
    assert occurrence(connect, topic, dt.datetime(2026, 11, 1, 5, 29, tzinfo=dt.UTC)) is None
    row = occurrence(connect, topic, dt.datetime(2026, 11, 1, 5, 30, tzinfo=dt.UTC))
    assert row["due_at"] == dt.datetime(2026, 11, 1, 5, 30, tzinfo=dt.UTC)
    assert (
        occurrence(connect, topic, dt.datetime(2026, 11, 1, 6, 30, tzinfo=dt.UTC))["window_day"]
        == row["window_day"]
    )


def test_spring_gap_uses_first_valid_minute(transactions, authority, connect):
    topic = schedule(transactions, authority, "America/New_York", dt.date(2027, 3, 14), "02:30")
    row = occurrence(connect, topic, dt.datetime(2027, 3, 14, 7, tzinfo=dt.UTC))
    assert row["due_at"] == dt.datetime(2027, 3, 14, 7, tzinfo=dt.UTC)


def test_weekly_requires_wall_time_and_recovers_next_day(transactions, authority, connect):
    topic = schedule(transactions, authority, "UTC", dt.date(2026, 11, 1), "08:00", "weekly")
    assert occurrence(connect, topic, dt.datetime(2026, 11, 1, 7, 59, tzinfo=dt.UTC)) is None
    row = occurrence(connect, topic, dt.datetime(2026, 11, 2, 12, tzinfo=dt.UTC))
    assert row["window_day"] == dt.date(2026, 11, 1)
    assert row["due_at"].hour == 8


def test_same_instant_respects_owner_local_dates(transactions, authority, authority_b, connect):
    tokyo = schedule(transactions, authority, "Asia/Tokyo", dt.date(2026, 11, 2), "00:00")
    la = schedule(transactions, authority_b, "America/Los_Angeles", dt.date(2026, 11, 2), "00:00")
    instant = dt.datetime(2026, 11, 1, 16, tzinfo=dt.UTC)
    assert occurrence(connect, tokyo, instant)["window_day"] == dt.date(2026, 11, 2)
    assert occurrence(connect, la, instant) is None


def test_unconfigured_owner_not_due(transactions, authority, connect):
    topic = TopicsService(transactions).follow(authority, str(uuid4()), "Unset")["topicId"]
    with connect("personalization") as conn:
        conn.execute(
            "UPDATE personalization.settings SET defaults=defaults-'timeZone' WHERE account_id=%s",
            (authority.account_id,),
        )
    assert occurrence(connect, topic, dt.datetime(2027, 1, 1, tzinfo=dt.UTC)) is None


def test_zone_confirmation_does_not_schedule_past(transactions, authority, connect):
    topic = schedule(transactions, authority, "UTC", dt.date(2026, 11, 1), "08:00")
    assert occurrence(connect, topic, dt.datetime(2026, 1, 1, tzinfo=dt.UTC)) is None


def test_due_filter_precedes_page_limit(transactions, authority, connect):
    # A future occurrence must not fill the bounded due page ahead of a due one.
    future = schedule(transactions, authority, "UTC", dt.date(2027, 1, 1), "08:00")
    due = schedule(transactions, authority, "UTC", dt.date(2026, 11, 1), "08:00")
    rows = TopicsRepository(transactions).due_topics(dt.datetime(2026, 11, 1, 9, tzinfo=dt.UTC), 50)
    assert due in {str(row["id"]) for row in rows}
    assert future not in {str(row["id"]) for row in rows}
