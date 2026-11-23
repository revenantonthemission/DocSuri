"""The digest scheduler over the real realm (`backend/modules/topics/scheduler.py`): due
windows and late firing, owner fairness past a blocked page, refire idempotence and
chronological order, orphan recovery and the consent stop.

Moved unchanged from `test_topics_logic.py` (plan Step 35, decision L3-1); the shared
helpers are in `topics_flow.py`. An autouse fixture quiets the persistent realm first:
earlier runs of this suite leave active topics and queued runs behind, so every test
starts with only the topic it creates in the due page."""

import datetime as dt
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from backend.modules.topics.repository import TopicsRepository

from tests.u5_topics_digests.calendar_flow import (
    NEW_YORK,
    first_valid_instant,
    next_transition,
    run_clock,
    schedule,
    wall_exists,
)
from tests.u5_topics_digests.topics_flow import (
    ITEM,
    W1,
    W2,
    build,
    follow_topic,
    make_due,
    quiet_realm_rows,
    revision_of,
    run_row,
    seed_corpus,
)


@pytest.fixture(autouse=True)
def quiet_realm(connect):
    quiet_realm_rows(connect)


def test_due_window_boundaries_and_late_firing(transactions):
    _, scheduler, _ = build(transactions)
    daily = {
        "id": uuid4(),
        "cadence": "daily",
        "delivery_time_local": dt.time(8, 0),
        "delivery_day": None,
        "content_window_days": 7,
        "preferences": {"timeZone": "UTC"},
    }
    # Before the scheduled minute the topic is not due (BR1.2).
    scheduler._now = lambda: dt.datetime(2026, 3, 10, 7, 59, tzinfo=scheduler.zone)
    assert scheduler._due_window(daily) is None
    # At the scheduled minute — and hours late — the window still delivers.
    scheduler._now = lambda: dt.datetime(2026, 3, 10, 8, 0, tzinfo=scheduler.zone)
    assert scheduler._due_window(daily) == (dt.date(2026, 3, 4), dt.date(2026, 3, 10))
    scheduler._now = lambda: dt.datetime(2026, 3, 10, 23, 0, tzinfo=scheduler.zone)
    assert scheduler._due_window(daily) == (dt.date(2026, 3, 4), dt.date(2026, 3, 10))
    # Weekly cadence fires only on its anchor day (BR1.2).
    weekly = dict(daily, cadence="weekly", delivery_day="tue")
    assert scheduler._due_window(weekly) == (dt.date(2026, 3, 4), dt.date(2026, 3, 10))
    monday = dict(weekly, delivery_day="mon")
    assert scheduler._due_window(monday) is None


@pytest.mark.parametrize("blocked_by", ["consent", "unknown"])
def test_blocked_page_cannot_starve_another_owner(
    transactions, authority, authority_b, connect, blocked_by
):
    service, scheduler, _ = build(transactions)
    repository = TopicsRepository(transactions)
    today = dt.datetime.now(dt.UTC).date()
    tomorrow = today + dt.timedelta(days=1)
    scheduler._now = lambda: dt.datetime.combine(tomorrow, dt.time(12), tzinfo=dt.UTC)
    seed_corpus(connect, [("v-fairness", "p-fairness", today, True)])
    blocked = []
    # More than one full page sorts before the later owner's 11:00 occurrences.
    # Seed only through the owner module; do not mock the due query or authority.
    for _ in range(51):
        _, topic = follow_topic(service, authority, "blocked-page")
        make_due(connect, topic)
        blocked.append(topic)
        if blocked_by == "unknown":
            run, _ = repository.prepare_run(
                topic, today - dt.timedelta(days=6), today, revision_of(connect, topic), [ITEM]
            )
            repository.begin_send(run["id"], "local-sink")
            repository.finish_send(run["id"], "unknown")
    eligible = []
    for _ in range(2):
        _, topic = follow_topic(service, authority_b, "eligible-later")
        service.save_settings(
            authority_b,
            topic,
            {
                "revision": 1,
                "cadence": "daily",
                "deliveryTimeLocal": "11:00",
                "deliveryDay": None,
                "contentWindowDays": 7,
            },
        )
        eligible.append(topic)
    if blocked_by == "consent":
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.consent SET granted=false WHERE account_id=%s "
                "AND purpose='local-research'",
                (authority.account_id,),
            )
    with connect("topics") as conn:
        attempts_before = conn.execute(
            "SELECT count(*) AS n FROM topics.send_log_entry l JOIN topics.digest_run r "
            "ON r.id=l.run_id WHERE r.topic_id=ANY(%s::uuid[])",
            (blocked,),
        ).fetchone()["n"]
    due = repository.due_topics(scheduler._now(), 50)
    assert not set(blocked).intersection(str(row["id"]) for row in due)
    assert set(eligible).issubset({str(row["id"]) for row in due})
    passes = [scheduler.run_once(1) for _ in range(3)]
    assert all(result["prepared"] <= 1 and result["sent"] <= 1 for result in passes)
    assert sum(result["sent"] for result in passes) >= 2
    for topic in eligible:
        assert any(run["state"] == "sent" for run in service.read_topic(authority_b, topic)["runs"])
    with connect("topics") as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM topics.send_log_entry l JOIN topics.digest_run r "
                "ON r.id=l.run_id WHERE r.topic_id=ANY(%s::uuid[])",
                (blocked,),
            ).fetchone()["n"]
            == attempts_before
        )
        if blocked_by == "unknown":
            assert (
                conn.execute(
                    "SELECT count(*) AS n FROM topics.digest_run WHERE topic_id=ANY(%s::uuid[]) "
                    "AND state='unknown'",
                    (blocked,),
                ).fetchone()["n"]
                == 51
            )


def test_refire_idempotence_and_chronological_ordering(transactions, authority, connect):
    service, scheduler, _ = build(transactions)
    repository = TopicsRepository(transactions)
    _, topic_id = follow_topic(service, authority)
    make_due(connect, topic_id)
    # BR2.4: a non-terminal earlier window blocks later preparation within a
    # pass; the send pass completes that window, and the next pass proceeds.
    revision = revision_of(connect, topic_id)
    earlier, _ = repository.prepare_run(topic_id, W1[0], W1[1], revision, [ITEM])
    blocked = scheduler.run_once(limit=1)
    assert blocked["prepared"] == 0
    assert run_row(connect, earlier["id"])["state"] == "sent"
    # The first unblocked evaluation prepares the rolling window.
    first = scheduler.run_once(limit=1)
    assert first["prepared"] == 1
    runs = service.read_topic(authority, topic_id)["runs"]
    today = scheduler._now().date()
    rolling = next(
        r for r in runs if r["windowStart"] == (today - dt.timedelta(days=6)).isoformat()
    )
    # The pass's send stage may already have carried it; the window is what matters.
    assert rolling["state"] in ("sent", "failed", "unknown", "empty", "prepared")
    # A repeated tick does not re-prepare the covered day (idempotence).
    assert scheduler.run_once(limit=1)["prepared"] == 0
    # BR1.3: a settings revision discards the queued (prepared) run.
    revision = revision_of(connect, topic_id)
    queued, _ = repository.prepare_run(topic_id, W2[0], W2[1], revision, [ITEM])
    saved = service.save_settings(
        authority,
        topic_id,
        {
            "revision": revision,
            "cadence": "daily",
            "deliveryTimeLocal": "00:00",
            "deliveryDay": None,
            "contentWindowDays": 30,
        },
    )
    assert str(queued["id"]) in saved["discardedRunIds"]


def test_orphan_sweep_via_scheduler(transactions, authority, connect):
    service, scheduler, _ = build(transactions)
    repository = TopicsRepository(transactions)
    _, topic_id = follow_topic(service, authority, base="orphan-topic")
    revision = revision_of(connect, topic_id)
    run, _ = repository.prepare_run(topic_id, W1[0], W1[1], revision, [ITEM])
    with connect("topics") as conn:
        conn.execute(
            "UPDATE topics.digest_run SET state='sending',updated_at=clock_timestamp() "
            "- interval '1000 seconds' WHERE id=%s",
            (run["id"],),
        )
    result = scheduler.run_once(limit=1)
    assert result["recovered"] >= 1
    assert service.read_run(authority, topic_id, run["id"])["state"] == "unknown"


def test_consent_stop_and_restore(transactions, authority, connect):
    service, scheduler, _ = build(transactions)
    repository = TopicsRepository(transactions)
    _, topic_id = follow_topic(service, authority, base="consent-topic")
    make_due(connect, topic_id)
    revision = revision_of(connect, topic_id)
    run, _ = repository.prepare_run(topic_id, W1[0], W1[1], revision, [ITEM])
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.consent SET granted=false WHERE account_id=%s "
            "AND purpose='local-research'",
            (authority.account_id,),
        )
    # The scheduler drops queued work while consent is stopped (BR4.2).
    scheduler.run_once(limit=1)
    assert run_row(connect, run["id"])["state"] == "discarded"
    assert repository.begin_send(run["id"], "local-sink") is None
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.consent SET granted=true WHERE account_id=%s "
            "AND purpose='local-research'",
            (authority.account_id,),
        )
    assert scheduler.run_once(limit=1)["prepared"] >= 1


# Build and Test loop-back 4 (plan Step 46, decision L4-2): the run a pass prepares keeps
# the due instant of its occurrence. Each test runs the real pass on the real store with
# only the pass's clock injected, and compares the stored instant with one worked out
# from the zone database (`calendar_flow.first_valid_instant`), never from the scheduler.


def pass_at(transactions, connect, topic, pass_clock):
    """One bounded pass at `pass_clock`; the topic's runs afterwards, oldest window first."""
    _, scheduler, _ = build(transactions)
    scheduler._now = lambda: pass_clock
    result = scheduler.run_once(limit=1)
    assert result["prepared"] == 1, result
    with connect("topics") as conn:
        return conn.execute(
            "SELECT window_end,scheduled_at FROM topics.digest_run WHERE topic_id=%s "
            "ORDER BY window_end",
            (topic,),
        ).fetchall()


def assert_recorded(runs, day, due, pass_clock):
    """`calendar_flow.schedule` leaves one run ending the day before, prepared by a direct
    call that hands in no instant; the pass adds exactly the delivery day's run."""
    assert due < pass_clock
    message = f"stored {runs[-1]['scheduled_at']}, occurrence {due}, pass clock {pass_clock}"
    assert runs == [
        {"window_end": day - dt.timedelta(days=1), "scheduled_at": None},
        {"window_end": day, "scheduled_at": due},
    ], message


def test_a_daily_run_records_its_occurrence_not_the_pass_clock(transactions, authority, connect):
    zone = ZoneInfo("Asia/Seoul")
    day = run_clock(connect).astimezone(zone).date() + dt.timedelta(days=2)
    topic = schedule(transactions, authority, "Asia/Seoul", day, "08:00")
    due = first_valid_instant(zone, day, dt.time(8))
    assert due == dt.datetime.combine(day, dt.time(8), zone)
    pass_clock = due + dt.timedelta(minutes=17)
    assert_recorded(pass_at(transactions, connect, topic, pass_clock), day, due, pass_clock)


@pytest.mark.parametrize(
    ("cadence", "late"),
    [("daily", dt.timedelta(days=3, hours=2)), ("weekly", dt.timedelta(days=1, hours=4))],
    ids=["a_daily_topic_three_days_late", "a_weekly_topic_on_the_next_local_day"],
)
def test_a_late_pass_records_the_occurrence_it_catches_up(
    transactions, authority, connect, cadence, late
):
    zone = ZoneInfo("Asia/Seoul")
    day = run_clock(connect).astimezone(zone).date() + dt.timedelta(days=2)
    if cadence == "weekly":
        day += dt.timedelta(days=(6 - day.weekday()) % 7)  # the next Sunday
    topic = schedule(transactions, authority, "Asia/Seoul", day, "08:00", cadence)
    due = first_valid_instant(zone, day, dt.time(8))
    pass_clock = due + late
    # The pass runs on a later local day; the run is still the delivery day's.
    assert pass_clock.astimezone(zone).date() == day + dt.timedelta(days=late.days)
    assert_recorded(pass_at(transactions, connect, topic, pass_clock), day, due, pass_clock)


@pytest.mark.parametrize(
    ("fold", "wall", "recorded_wall"),
    [(False, dt.time(2, 30), dt.time(3, 0)), (True, dt.time(1, 30), dt.time(1, 30))],
    ids=["the_day_with_no_0230", "the_day_with_two_0130s"],
)
def test_a_run_due_in_a_clock_change_records_the_first_valid_minute(
    transactions, authority, connect, fold, wall, recorded_wall
):
    day = next_transition(run_clock(connect), NEW_YORK, fold=fold)
    topic = schedule(transactions, authority, "America/New_York", day, wall.strftime("%H:%M"))
    due = first_valid_instant(NEW_YORK, day, wall)
    assert due.astimezone(NEW_YORK).time() == recorded_wall
    if fold:
        # 01:30 happens twice; the pass runs after the second one, an hour later.
        second = dt.datetime.combine(day, wall, NEW_YORK).replace(fold=1).astimezone(dt.UTC)
        assert second == due + dt.timedelta(hours=1)
        pass_clock = second + dt.timedelta(minutes=5)
    else:
        # 02:30 does not exist; the pass runs ten minutes after 03:00.
        assert not wall_exists(NEW_YORK, dt.datetime.combine(day, wall))
        pass_clock = due + dt.timedelta(minutes=10)
    assert_recorded(pass_at(transactions, connect, topic, pass_clock), day, due, pass_clock)
