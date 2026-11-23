"""A run's scheduled instant in `TopicsRepository` (Build and Test loop-back 4, L4-2).

`prepare_run` stores the instant it is handed, once, with a new row, and only beside the
preference fence; nothing changes it afterwards. Every test hands in an instant that is
not the window's last day at the topic's delivery time in the owner's zone, before or
after any settings change the test makes, so a reading worked out from the current
settings cannot pass by coincidence. Every read is through the topics login, and every
state move and settings change is the real one: `begin_send`, `finish_send`, the owner's
resolution and save, and `GuardedSettingsService.update`.
"""

import datetime as dt
from uuid import uuid4

import pytest
from backend.modules.personalization.guarded_service import GuardedSettingsService
from backend.modules.topics.errors import TopicsError
from backend.modules.topics.repository import TopicsRepository

WINDOW = (dt.date(2026, 1, 1), dt.date(2026, 1, 7))
ITEM = {"title": "Scheduled title", "publishedOn": "2026-01-03"}
# The followed topic's defaults: daily at 08:00, read in the owner's zone (UTC, as the
# owner fixtures leave it).
DEFAULT_DELIVERY = dt.time(8, 0)
CHANGED_DELIVERY = dt.time(21, 45)
INSTANT = dt.datetime(2026, 1, 7, 3, 17, tzinfo=dt.UTC)
OTHER_INSTANT = dt.datetime(2026, 1, 6, 19, 41, tzinfo=dt.UTC)
PENDING = ("prepared", "sending", "unknown")  # the states U8's statement names


def follow(repository, authority):
    return repository.follow(authority, str(uuid4()), "Scheduled")["topic"]["id"]


def preferences(connect, authority):
    """The owner's preferences as the due read sees them, for the fence."""
    with connect("topics") as conn:
        return conn.execute(
            "SELECT personalization.digest_preferences(%s) AS value", (authority.account_id,)
        ).fetchone()["value"]


def stored(connect, run_id):
    with connect("topics") as conn:
        return conn.execute(
            "SELECT state,scheduled_at FROM topics.digest_run WHERE id=%s", (run_id,)
        ).fetchone()


def pending_instant(connect, run_id):
    """The run's instant as a reader of pending runs finds it, or no row."""
    with connect("topics") as conn:
        return conn.execute(
            "SELECT scheduled_at FROM topics.digest_run WHERE id=%s AND state = ANY(%s)",
            (run_id, list(PENDING)),
        ).fetchone()


def runs_of(connect, topic):
    with connect("topics") as conn:
        return conn.execute(
            "SELECT id,state,scheduled_at FROM topics.digest_run WHERE topic_id=%s "
            "ORDER BY created_at,id",
            (topic,),
        ).fetchall()


def prepare(repository, connect, authority, *, topic=None, instant=INSTANT, content=(ITEM,)):
    topic = topic or follow(repository, authority)
    return repository.prepare_run(
        topic,
        *WINDOW,
        1,
        list(content),
        expected_preferences=preferences(connect, authority),
        scheduled_at=instant,
    )


def wall_instants(zone=dt.UTC):
    """The window's last day at each delivery time the tests use."""
    return {
        dt.datetime.combine(WINDOW[1], time, zone) for time in (DEFAULT_DELIVERY, CHANGED_DELIVERY)
    }


def test_a_prepared_run_keeps_the_scheduled_instant_it_is_handed(transactions, authority, connect):
    repository = TopicsRepository(transactions)
    assert INSTANT not in wall_instants()
    run, adopted = prepare(repository, connect, authority)
    assert not adopted
    assert run["scheduled_at"] == INSTANT
    assert stored(connect, run["id"]) == {"state": "prepared", "scheduled_at": INSTANT}
    # The same instant written at another offset is the same instant.
    seoul = INSTANT.astimezone(dt.timezone(dt.timedelta(hours=9)))
    assert seoul.hour == 12 and seoul.utcoffset() == dt.timedelta(hours=9)
    shifted, _ = prepare(repository, connect, authority, instant=seoul)
    assert shifted["id"] != run["id"]
    assert shifted["scheduled_at"] == INSTANT
    assert stored(connect, shifted["id"])["scheduled_at"] == INSTANT


def test_a_run_prepared_without_an_instant_holds_none(transactions, authority, connect):
    repository = TopicsRepository(transactions)
    topic = follow(repository, authority)
    run, adopted = repository.prepare_run(topic, *WINDOW, 1, [ITEM])
    assert not adopted
    assert run["scheduled_at"] is None
    row = stored(connect, run["id"])
    assert row == {"state": "prepared", "scheduled_at": None}


def _naive(connect, authority):
    return {
        "scheduled_at": INSTANT.replace(tzinfo=None),
        "expected_preferences": preferences(connect, authority),
    }


def _mistyped(connect, authority):
    return {
        "scheduled_at": INSTANT.isoformat(),
        "expected_preferences": preferences(connect, authority),
    }


def _unfenced(connect, authority):
    return {"scheduled_at": INSTANT}


@pytest.mark.parametrize(
    "arguments",
    [_naive, _mistyped, _unfenced],
    ids=["no_zone", "a_string", "no_preference_fence"],
)
def test_an_instant_that_is_naive_mistyped_or_unfenced_is_refused(
    transactions, authority, connect, arguments
):
    repository = TopicsRepository(transactions)
    topic = follow(repository, authority)
    with pytest.raises(TopicsError) as refused:
        repository.prepare_run(topic, *WINDOW, 1, [ITEM], **arguments(connect, authority))
    assert refused.value.code == "INVALID_ARGUMENT"
    assert refused.value.current == {"field": "scheduledAt"}
    assert runs_of(connect, topic) == []


def test_an_instant_from_a_due_read_made_before_a_zone_change_is_refused(
    transactions, authority, connect
):
    repository = TopicsRepository(transactions)
    topic = follow(repository, authority)
    read_before = preferences(connect, authority)
    settings = GuardedSettingsService(transactions)
    settings.update(
        authority, uuid4(), settings.read(authority)["revision"], {"timeZone": "Asia/Seoul"}
    )
    assert preferences(connect, authority)["timeZone"] == "Asia/Seoul" != read_before["timeZone"]
    with pytest.raises(TopicsError) as refused:
        repository.prepare_run(
            topic, *WINDOW, 1, [ITEM], expected_preferences=read_before, scheduled_at=INSTANT
        )
    assert refused.value.code == "CONFLICT"
    assert refused.value.current == {"field": "effectivePreferences"}
    assert runs_of(connect, topic) == []


def test_a_refire_adopts_the_run_and_keeps_its_first_instant(transactions, authority, connect):
    repository = TopicsRepository(transactions)
    first, _ = prepare(repository, connect, authority)
    again, adopted = prepare(
        repository, connect, authority, topic=first["topic_id"], instant=OTHER_INSTANT
    )
    assert adopted and again["id"] == first["id"]
    assert again["scheduled_at"] == INSTANT
    assert runs_of(connect, first["topic_id"]) == [
        {"id": first["id"], "state": "prepared", "scheduled_at": INSTANT}
    ]


def _a_new_delivery_time(transactions, authority, topic):
    saved = TopicsRepository(transactions).save_settings(
        authority, topic, 1, "daily", CHANGED_DELIVERY, None, 7
    )
    assert saved["settings"]["revision"] == 2 and not saved["unchanged"]
    return dt.UTC


def _a_weekly_cadence(transactions, authority, topic):
    saved = TopicsRepository(transactions).save_settings(
        authority, topic, 1, "weekly", DEFAULT_DELIVERY, "wed", 7
    )
    assert saved["settings"]["cadence"] == "weekly" and saved["settings"]["revision"] == 2
    return dt.UTC


def _another_zone(transactions, authority, topic):
    settings = GuardedSettingsService(transactions)
    changed = settings.update(
        authority, uuid4(), settings.read(authority)["revision"], {"timeZone": "Asia/Seoul"}
    )
    assert changed["timeZone"] == "Asia/Seoul"
    return dt.timezone(dt.timedelta(hours=9))


@pytest.mark.parametrize(
    "change",
    [_a_new_delivery_time, _a_weekly_cadence, _another_zone],
    ids=["a_new_delivery_time", "a_weekly_cadence", "another_zone"],
)
def test_a_later_change_leaves_a_started_runs_instant(transactions, authority, connect, change):
    """The run U8-A2 is about: its topic's settings, or its owner's zone, change after
    the send started, and the run is still counted from the instant it was prepared for."""
    repository = TopicsRepository(transactions)
    run, _ = prepare(repository, connect, authority)
    assert repository.begin_send(run["id"], "local-sink")["id"] == run["id"]
    zone = change(transactions, authority, run["topic_id"])
    assert INSTANT not in wall_instants(zone)
    assert stored(connect, run["id"]) == {"state": "sending", "scheduled_at": INSTANT}
    assert pending_instant(connect, run["id"]) == {"scheduled_at": INSTANT}
    unknown = repository.finish_send(run["id"], "unknown")
    assert unknown["scheduled_at"] == INSTANT
    assert stored(connect, run["id"]) == {"state": "unknown", "scheduled_at": INSTANT}
    assert pending_instant(connect, run["id"]) == {"scheduled_at": INSTANT}


def test_no_state_move_changes_the_instant(transactions, authority, connect):
    repository = TopicsRepository(transactions)
    run, _ = prepare(repository, connect, authority)
    topic = run["topic_id"]
    assert pending_instant(connect, run["id"]) == {"scheduled_at": INSTANT}
    sending = repository.begin_send(run["id"], "local-sink")
    assert sending["state"] == "sending" and sending["scheduled_at"] == INSTANT
    assert pending_instant(connect, run["id"]) == {"scheduled_at": INSTANT}
    assert repository.finish_send(run["id"], "unknown")["scheduled_at"] == INSTANT
    assert pending_instant(connect, run["id"]) == {"scheduled_at": INSTANT}
    resolved = repository.resolve_run(authority, topic, run["id"], "failed")
    assert resolved["state"] == "failed" and resolved["scheduled_at"] == INSTANT
    assert stored(connect, run["id"]) == {"state": "failed", "scheduled_at": INSTANT}
    assert pending_instant(connect, run["id"]) is None
    # A prepared run that is discarded keeps its instant too.
    queued, _ = prepare(repository, connect, authority, instant=OTHER_INSTANT)
    assert repository.discard_prepared_runs(queued["topic_id"]) == [queued["id"]]
    assert stored(connect, queued["id"]) == {"state": "discarded", "scheduled_at": OTHER_INSTANT}


def test_a_run_prepared_again_after_a_discard_holds_its_own_instant(
    transactions, authority, connect
):
    repository = TopicsRepository(transactions)
    first, _ = prepare(repository, connect, authority)
    topic = first["topic_id"]
    assert repository.discard_prepared_runs(topic) == [first["id"]]
    second, adopted = prepare(repository, connect, authority, topic=topic, instant=OTHER_INSTANT)
    assert not adopted and second["id"] != first["id"]
    assert second["scheduled_at"] == OTHER_INSTANT
    assert runs_of(connect, topic) == [
        {"id": first["id"], "state": "discarded", "scheduled_at": INSTANT},
        {"id": second["id"], "state": "prepared", "scheduled_at": OTHER_INSTANT},
    ]
