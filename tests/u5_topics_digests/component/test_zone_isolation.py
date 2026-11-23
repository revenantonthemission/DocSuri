"""Step 20 (c): an owner's zone decides only that owner's topics, to the instant.

Due evaluation reads one query over every owner (`TopicsRepository.due_topics`, which
calls `topics.next_occurrence` per topic). An owner whose zone is missing has no due
topics, and an invalid zone is refused where it would be stored, so that owner stays
unconfigured; another owner's topics stay due in the same query. A weekly topic falls
due exactly at its local wall time in its owner's zone, not a microsecond before.

All instants are taken from this run's clock, so no date here can fall behind the
calendar. Each owner's due page is read with the real-adapter recipient scope, which
the due query applies before its bounded page, so other checks' topics in the shared
realm cannot push these off the page.
"""

import datetime as dt
from uuid import uuid4
from zoneinfo import ZoneInfo

import psycopg
import pytest
from backend.modules.personalization.guarded_service import GuardedSettingsService
from backend.modules.topics.repository import TopicsRepository
from backend.modules.topics.scheduler import WEEKDAYS
from backend.modules.topics.service import TopicsService
from psycopg.types.json import Jsonb

from tests.u5_topics_digests.real_send import recipient_of


def set_zone(transactions, authority, zone):
    settings = GuardedSettingsService(transactions)
    state = settings.read(authority)
    return settings.update(authority, uuid4(), state["revision"], {"timeZone": zone})


def follow(transactions, authority, **settings):
    service = TopicsService(transactions)
    topic = service.follow(authority, f"u5-zone-{uuid4().hex[:10]}", "Zone check")["topicId"]
    if settings:
        service.save_settings(authority, topic, {"revision": 1, **settings})
    return topic


def due_for(transactions, recipient, instant):
    rows = TopicsRepository(transactions).due_topics(instant, 50, recipient=recipient)
    return {str(row["id"]) for row in rows}


def occurrence(connect, topic, instant):
    with connect("topics") as conn:
        return conn.execute(
            "SELECT * FROM topics.next_occurrence(%s,%s)", (topic, instant)
        ).fetchone()


def test_a_missing_or_refused_zone_leaves_other_owners_topics_due(
    transactions, authority, authority_b, connect
):
    set_zone(transactions, authority, "UTC")
    set_zone(transactions, authority_b, "Asia/Seoul")
    unconfigured = follow(transactions, authority)  # daily at 08:00 local, the defaults
    configured = follow(transactions, authority_b)
    owner, other = (recipient_of(transactions, a.account_id) for a in (authority, authority_b))
    instant = dt.datetime.now(dt.UTC) + dt.timedelta(days=2)
    # Control: with a zone, both owners' new topics are due.
    assert unconfigured in due_for(transactions, owner, instant)
    assert configured in due_for(transactions, other, instant)

    # The first owner's zone goes missing (an unconfigured real owner).
    with connect("personalization") as conn:
        conn.execute(
            "UPDATE personalization.settings SET defaults=defaults-'timeZone' WHERE account_id=%s",
            (authority.account_id,),
        )
    assert occurrence(connect, unconfigured, instant) is None
    assert due_for(transactions, owner, instant) == set()
    assert configured in due_for(transactions, other, instant)
    assert occurrence(connect, configured, instant) is not None
    # The unscoped query over every owner still answers, without the unconfigured topic.
    assert unconfigured not in {
        str(row["id"]) for row in TopicsRepository(transactions).due_topics(instant, 50)
    }

    # An invalid zone is refused by the settings owner and by its store, so the first
    # owner stays unconfigured rather than holding a zone the scheduler cannot read.
    with pytest.raises(ValueError):
        set_zone(transactions, authority, "Mars/Olympus")
    with pytest.raises(psycopg.errors.CheckViolation):
        with connect("personalization") as conn:
            conn.execute(
                "UPDATE personalization.settings SET defaults=defaults || %s WHERE account_id=%s",
                (Jsonb({"timeZone": "Mars/Olympus"}), authority.account_id),
            )
    assert GuardedSettingsService(transactions).read(authority)["timeZone"] is None
    assert due_for(transactions, owner, instant) == set()
    assert configured in due_for(transactions, other, instant)


def test_a_weekly_topic_falls_due_exactly_at_its_local_wall_time(
    transactions, authority_b, connect
):
    zone = ZoneInfo("Asia/Seoul")
    set_zone(transactions, authority_b, "Asia/Seoul")
    # Three days ahead in the owner's zone: the first matching weekday after following.
    day = dt.datetime.now(zone).date() + dt.timedelta(days=3)
    topic = follow(
        transactions,
        authority_b,
        cadence="weekly",
        deliveryTimeLocal="09:00",
        deliveryDay=WEEKDAYS[day.weekday()],
        contentWindowDays=7,
    )
    due_at = dt.datetime.combine(day, dt.time(9, 0), tzinfo=zone).astimezone(dt.UTC)
    just_before = due_at - dt.timedelta(microseconds=1)
    recipient = recipient_of(transactions, authority_b.account_id)
    assert occurrence(connect, topic, just_before) is None
    assert topic not in due_for(transactions, recipient, just_before)
    row = occurrence(connect, topic, due_at)
    assert row["due_at"] == due_at and row["window_day"] == day
    assert topic in due_for(transactions, recipient, due_at)
    # The same occurrence stays due when the tick runs late, to the next local day.
    late = occurrence(connect, topic, due_at + dt.timedelta(hours=26))
    assert (late["window_day"], late["due_at"]) == (day, due_at)
