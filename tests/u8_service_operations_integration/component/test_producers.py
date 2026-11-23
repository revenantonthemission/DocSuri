"""The capability producers (U8 plan Step 16; BR3.3, BR3.5, BR3.6, BR6.6, BR6.11).

Database reads run against the realm. The model runtime is a recorded `/api/tags`
answer (the plan's stand-in), the backup agent's status a recorded status, and
PlatformControl's evidence reader a recorder that can only inspect.
"""

from __future__ import annotations

import datetime as dt
import inspect
import json
import os
from uuid import uuid4

import httpx
import pytest

from backend.modules.operations import producers as p
from backend.modules.operations.ledger import Ledger
from backend.modules.operations.observation_store import ObservationStore
from backend.modules.operations.observations import Observations
from backend.u8_policy import SYNTHETIC_OPERATIONS
from backend.u8_registry import CAPABILITIES, MODEL_EVIDENCE

GIB = 1024**3
PINS = {model: digest for model, _, digest in MODEL_EVIDENCE}


@pytest.fixture
def component(tmp_path, clock):
    folder = tmp_path / "ledger"
    folder.mkdir(mode=0o700)
    ledger = Ledger.open(folder, clock=clock)
    yield ledger
    ledger.close()


# --- 1. At start, then every renewal interval ------------------------------------------


def test_each_producer_observes_at_start_then_on_its_interval(transactions, clock, component):
    observations = Observations(ObservationStore(transactions))
    schedule = p.ProducerSchedule(
        [p.OwnerProbe("library.saved-work", "library", transactions),
         p.LedgerProducer(component),
         p.ProviderProducer("provider.notion", component)],
        observations, SYNTHETIC_OPERATIONS, clock, Ticks(),
    )
    start = clock()
    assert schedule.run_due(start) == ["library.saved-work", "operations.ledger",
                                       "provider.notion"]
    assert schedule.run_due(start + dt.timedelta(seconds=1)) == []
    required = SYNTHETIC_OPERATIONS.required_renewal_seconds
    provider = SYNTHETIC_OPERATIONS.provider_renewal_seconds
    assert schedule.run_due(start + dt.timedelta(seconds=required)) == [
        "library.saved-work", "operations.ledger"]
    assert schedule.run_due(start + dt.timedelta(seconds=provider)) == [
        "library.saved-work", "operations.ledger", "provider.notion"]
    latest = ObservationStore(transactions).latest(["library.saved-work", "operations.ledger"])
    assert latest["library.saved-work"]["outcome"] == "available"
    assert latest["operations.ledger"]["producer"] == "ledger"


# Your decision of 2026-11-13 ("Renew on real time too"): renewal is also paced on a
# monotonic source, so a fixture clock held still (or stepped back) never stops it.


class Ticks:
    """A monotonic source the test moves by hand, never by sleeping."""

    def __init__(self) -> None:
        self.seconds = 1000.0

    def __call__(self) -> float:
        return self.seconds


def ledger_schedule(transactions, clock, component, ticks: Ticks):
    producer = p.LedgerProducer(component)
    schedule = p.ProducerSchedule([producer], Observations(ObservationStore(transactions)),
                                  SYNTHETIC_OPERATIONS, clock, ticks)
    return schedule, schedule.interval(producer)


def rows_at(transactions, at: dt.datetime) -> list[dict]:
    return transactions.run("operations", lambda conn: conn.execute(
        "SELECT revision FROM operations.observation_record "
        "WHERE capability='operations.ledger' AND observed_at=%s ORDER BY revision",
        (at,)).fetchall())


def test_a_held_clock_renews_once_real_time_passes_the_interval(transactions, clock,
                                                                  component):
    ticks = Ticks()
    schedule, interval = ledger_schedule(transactions, clock, component, ticks)
    held = clock() - dt.timedelta(hours=2)
    assert schedule.run_due(held) == ["operations.ledger"]
    ticks.seconds += interval - 0.5
    assert schedule.run_due(held) == []
    ticks.seconds += 0.5
    assert schedule.run_due(held) == ["operations.ledger"]
    # Stamped on the held clock: two rows at the one instant, the revision still rising.
    revisions = [row["revision"] for row in rows_at(transactions, held)]
    assert len(revisions) == 2 and revisions[0] < revisions[1]


def test_the_injected_clock_alone_still_makes_a_producer_due(transactions, clock, component):
    ticks = Ticks()
    schedule, interval = ledger_schedule(transactions, clock, component, ticks)
    start = clock() - dt.timedelta(hours=3)
    assert schedule.run_due(start) == ["operations.ledger"]
    assert schedule.run_due(start + dt.timedelta(seconds=interval - 1)) == []
    assert schedule.run_due(start + dt.timedelta(seconds=interval)) == ["operations.ledger"]
    assert ticks.seconds == 1000.0


def test_platform_status_renews_every_5_minutes(transactions, clock):
    """NFR9.2 (1): under the production policy platform.status renews every 300 s."""
    from backend.u8_policy import PRODUCTION_OPERATIONS

    ticks = Ticks()
    producer = p.PlatformStatusProducer(lambda: {"outcome": "pass"})
    schedule = p.ProducerSchedule([producer], Observations(ObservationStore(transactions)),
                                  PRODUCTION_OPERATIONS, clock, ticks)
    start = clock() - dt.timedelta(hours=6)
    assert schedule.interval(producer) == 300
    assert schedule.run_due(start) == ["platform.status"]
    assert schedule.run_due(start + dt.timedelta(seconds=299)) == []
    assert schedule.run_due(start + dt.timedelta(seconds=300)) == ["platform.status"]
    assert ticks.seconds == 1000.0


def test_a_clock_stepped_back_renews_after_the_real_interval(transactions, clock, component):
    ticks = Ticks()
    schedule, interval = ledger_schedule(transactions, clock, component, ticks)
    start = clock() - dt.timedelta(hours=4)
    assert schedule.run_due(start) == ["operations.ledger"]
    back = start - dt.timedelta(minutes=30)
    ticks.seconds += interval - 0.5
    assert schedule.run_due(back) == []
    ticks.seconds += 0.5
    assert schedule.run_due(back) == ["operations.ledger"]


def test_the_first_pass_and_a_refused_write_keep_their_rules(transactions, clock, component):
    class Unregistered(p.Producer):
        def observe(self, now):
            return p.Observed("unknown", "not-a-registered-reason")

    ticks = Ticks()
    refusing = Unregistered("usage.wallet")
    schedule = p.ProducerSchedule(
        [refusing, p.LedgerProducer(component)], Observations(ObservationStore(transactions)),
        SYNTHETIC_OPERATIONS, clock, ticks)
    held = clock() - dt.timedelta(hours=5)
    # The first pass runs every producer; the refused one is counted, not recorded.
    assert schedule.run_due(held) == ["operations.ledger"]
    assert schedule.refused == 1
    # A refusal still sets both stamps, so it waits for its interval like any other.
    assert schedule.last["usage.wallet"] == held and schedule.stamps["usage.wallet"] == 1000.0
    assert schedule.run_due(held) == [] and schedule.refused == 1
    ticks.seconds += schedule.interval(refusing)
    schedule.run_due(held)
    assert schedule.refused == 2


def test_a_producer_that_cannot_observe_records_unknown(transactions, clock):
    class Broken(p.Producer):
        def observe(self, now):
            raise RuntimeError("private detail")

    schedule = p.ProducerSchedule([Broken("usage.wallet")],
                                  Observations(ObservationStore(transactions)),
                                  SYNTHETIC_OPERATIONS, clock)
    assert schedule.run_due() == ["usage.wallet"]
    latest = ObservationStore(transactions).latest(["usage.wallet"])["usage.wallet"]
    assert (latest["outcome"], latest["reason_key"]) == ("unknown", "producer-failed")


def test_every_registry_capability_has_its_producer_class():
    produced = {
        "export": p.ExportProducer, "topics.digest": p.DigestProducer,
        "operations.ledger": p.LedgerProducer, "storage.capacity": p.CapacityProducer,
        "background.work": p.BackgroundWorkProducer, "platform.status":
        p.PlatformStatusProducer, "platform.isolation": p.IsolationProducer,
        "operations.cutover": p.CutoverProducer, "provider.models": p.ModelsProducer,
        "public.static": p.HostErrorRateProducer,
    }
    probes = {probe.capability for probe in p.owner_probes(None, lambda _: True)}
    providers = set(p.PROVIDERS) | {"assistance.summary", "assistance.translation"}
    assert {cap.capability_id for cap in CAPABILITIES} == set(produced) | probes | providers


# --- 2. Export and digests at their bounds ---------------------------------------------


def export_status(oldest_accepted, oldest_unknown=None, failed=0, succeeded=0) -> dict:
    return {
        "effects": {"accepted": 1, "executing": 0, "unknown": 0, "succeededLast24h": succeeded,
                    "failedLast24h": failed, "cancelledLast24h": 0, "invalidatedLast24h": 0},
        "oldestAcceptedSeconds": oldest_accepted, "oldestUnknownSeconds": oldest_unknown,
        "connections": {}, "lane": None,
    }


def test_export_and_digests_become_degraded_at_their_bounds(transactions, clock):
    bound = SYNTHETIC_OPERATIONS.export_degraded_after_seconds
    assert p.export_outcome(export_status(bound), SYNTHETIC_OPERATIONS).outcome == "available"
    late = p.export_outcome(export_status(bound + 1, failed=1, succeeded=3),
                            SYNTHETIC_OPERATIONS)
    assert (late.outcome, late.reason, late.error_count, late.total_count) == (
        "degraded", "export-effect-late", 1, 4)
    unclear = p.export_outcome(export_status(None, oldest_unknown=bound + 1),
                               SYNTHETIC_OPERATIONS)
    assert unclear.reason == "export-effect-late"
    # The oldest acceptance's age alone decides when it is the largest (L4-3).
    assert p.export_outcome(export_status(None), SYNTHETIC_OPERATIONS,
                            accepted_seconds=bound).outcome == "available"
    accepted = p.export_outcome(export_status(None, oldest_unknown=1), SYNTHETIC_OPERATIONS,
                                accepted_seconds=bound + 1)
    assert (accepted.outcome, accepted.reason) == ("degraded", "export-effect-late")
    late_by = SYNTHETIC_OPERATIONS.digest_late_seconds
    assert p.digest_outcome({"oldest": late_by, "unscheduled": 0, "failed": 0, "terminal": 0},
                            SYNTHETIC_OPERATIONS).outcome == "available"
    digest = p.digest_outcome({"oldest": late_by + 1, "unscheduled": 0, "failed": 2,
                               "terminal": 5}, SYNTHETIC_OPERATIONS)
    assert (digest.outcome, digest.reason, digest.error_count) == (
        "degraded", "digest-delivery-late", 2)
    # One pending run with no recorded instant, and no age at all, is late (L4-9).
    bare = p.digest_outcome({"oldest": None, "unscheduled": 1, "failed": 0, "terminal": 1},
                            SYNTHETIC_OPERATIONS)
    assert (bare.outcome, bare.reason, bare.limitations, bare.total_count) == (
        "degraded", "digest-delivery-late", ("digest-delivery-late",), 1)
    # The realm's own stores answer through each owner's login.
    for producer in (p.ExportProducer(transactions, SYNTHETIC_OPERATIONS),
                     p.DigestProducer(transactions, SYNTHETIC_OPERATIONS)):
        observed = producer.observe(clock())
        assert observed.outcome in ("available", "degraded")
        assert observed.total_count >= observed.error_count >= 0


PENDING = ("prepared", "sending", "unknown")  # the states `DIGEST_RUNS` names as pending
# From a new run to each pending state, and from each on to a terminal one.
STEPS_TO = {"prepared": (), "sending": ("sending",), "unknown": ("sending", "unknown")}
END_OF = {"prepared": ("sending", "sent"), "sending": ("sent",), "unknown": ("failed",)}


def write_digest_runs(conn, topic, runs, *, snapshot=None, instants=None,
                      no_instant=()) -> dict:
    """Each run inserted prepared on its own window and moved only as the run machine
    allows (`u5_schema.sql`), each move stamping `updated_at`; its id and stored times
    kept. `snapshot` is written as `preference_snapshot`; None keeps it NULL, the
    pre-repair form. `instants` gives a run's `scheduled_at` by its name: a run left
    pending must have one, unless `no_instant` names it as the no-instant case."""
    from psycopg.types.json import Jsonb

    instants, stored = instants or {}, {}
    for name, day, content, steps in runs:
        left_pending = (steps[-1] if steps else "prepared") in PENDING
        assert name in instants or name in no_instant or not left_pending, name
        run = uuid4()
        conn.execute(
            "INSERT INTO topics.digest_run(id,topic_id,window_start,window_end,state,"
            "digest_content,settings_revision,preference_snapshot,scheduled_at) "
            "VALUES(%s,%s,%s,%s,'prepared',%s::jsonb,1,%s,%s)",
            (run, topic, day, day, content, None if snapshot is None else Jsonb(snapshot),
             instants.get(name)))
        move_run(conn, run, *steps)
        stored[name] = conn.execute("SELECT id, created_at, updated_at FROM "
                                    "topics.digest_run WHERE id=%s", (run,)).fetchone()
    return stored


def move_run(conn, run, *steps) -> None:
    for step in steps:
        conn.execute("UPDATE topics.digest_run SET state=%s,"
                     "updated_at=clock_timestamp() WHERE id=%s", (step, run))


def zone_snapshot(zone: str) -> dict:
    return {"timeZone": zone, "languageId": "en", "presentationLevelId": "standard"}


def digest_topic(conn, key: str, *, owner=None, cadence: str = "daily",
                 time: str = "09:00", day: str | None = None):
    """A followed topic with its settings, through the topics login. An owner id with
    no account or settings row behind it is listed by no due read."""
    topic = uuid4()
    conn.execute("INSERT INTO topics.followed_topic(id,account_id,topic_key,display_name)"
                 " VALUES(%s,%s,%s,%s)", (topic, owner or uuid4(), f"digest-{key}",
                                          f"Digest {key}"))
    conn.execute("INSERT INTO topics.digest_settings(id,topic_id,cadence,"
                 "delivery_time_local,delivery_day,content_window_days) "
                 "VALUES(%s,%s,%s,%s,%s,7)", (uuid4(), topic, cadence, time, day))
    return topic


def digest_seen(producer):
    def seen(now):
        observed = producer.observe(now)
        return observed.outcome, observed.reason, observed.error_count, \
            observed.total_count

    return seen


def utc(day: dt.date, hour: int = 0, minute: int = 0, second: int = 0) -> dt.datetime:
    return dt.datetime(day.year, day.month, day.day, hour, minute, second, tzinfo=dt.UTC)


HOUR, SECOND, DAY = dt.timedelta(hours=1), dt.timedelta(seconds=1), dt.timedelta(days=1)
MINUTE = dt.timedelta(minutes=1)
DIGEST_CONTENT = '[{"paperId": "digest-counts"}]'
ON_TIME, LATE = ("available", None), ("degraded", "digest-delivery-late")


def assert_late_bounds(seen, instant: dt.datetime, case=None) -> None:
    """Both bounds stand at `instant`: on time 2 hours after it, late one second later."""
    assert seen(instant + 2 * HOUR)[:2] == ON_TIME, case
    assert seen(instant + 2 * HOUR + SECOND)[:2] == LATE, case


# Every hand-written instant below is 07:30 or 06:10 on its day, never its window's day
# at the topic's delivery time (`digest_topic` writes 09:00, a re-set 10:00), so a time
# worked out from the current settings cannot equal it.


def test_digests_degrade_and_count_from_their_stored_runs(realm):
    """NFR9.2 (3)-(4): a pending run's lateness counts from the instant U5 recorded for
    it, the oldest first, and the failed and terminal counts from each run's last move
    within the 24 hours to `now`: a run moved after `now` is not counted."""
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from tests.u8_service_operations_integration.host_flows import production_stand_in

    ahead = dt.datetime.now(dt.UTC).date() + 30 * DAY
    utc_zone = zone_snapshot("UTC")
    older, younger = utc(ahead, 7, 30), utc(ahead + 5 * DAY, 6, 10)
    with production_stand_in(realm) as standin:
        with standin.connect("topics", autocommit=True) as conn:
            topics = {key: digest_topic(conn, key) for key in ("b", "a")}
            runs = write_digest_runs(conn, topics["b"], [
                ("B1", ahead, DIGEST_CONTENT, ("sending", "unknown"))],
                snapshot=utc_zone, instants={"B1": older})
            runs |= write_digest_runs(conn, topics["a"], [
                ("A1", ahead + DAY, DIGEST_CONTENT, ("sending", "failed")),
                ("A2", ahead + 2 * DAY, DIGEST_CONTENT, ("sending", "sent")),
                ("A3", ahead + 3 * DAY, "[]", ("empty",)),
                ("A4", ahead + 4 * DAY, DIGEST_CONTENT, ("sending", "failed")),
                ("A5", ahead + 5 * DAY, DIGEST_CONTENT, ())],
                snapshot=utc_zone, instants={"A5": younger})
        moved = [runs[name]["updated_at"] for name in ("A1", "A2", "A3", "A4")]
        assert moved == sorted(set(moved)) and len(moved) == 4
        seen = digest_seen(p.DigestProducer(standin.transactions, PRODUCTION_OPERATIONS))
        assert seen(older + 2 * HOUR) == ("available", None, 0, 0)
        assert seen(older + 2 * HOUR + SECOND) == ("degraded", "digest-delivery-late", 0, 0)
        # The window's lower edge: A1's move leaves it exactly 24 hours later.
        assert seen(moved[0] + 24 * HOUR - SECOND) == ("available", None, 2, 4)
        assert seen(moved[0] + 24 * HOUR)[2:] == (1, 3)
        # Its upper edge: at A2's move, A3 and the failed A4 have not moved yet.
        assert seen(moved[1])[2:] == (1, 2)


RESETS = {
    "delivery time": "UPDATE topics.digest_settings SET delivery_time_local='10:00',"
                     "revision=revision+1 WHERE topic_id=%s",
    "cadence": "UPDATE topics.digest_settings SET cadence='weekly',delivery_day='mon',"
               "revision=revision+1 WHERE topic_id=%s",
}


def test_a_re_set_run_counts_from_its_recorded_instant_in_every_pending_state(realm):
    """L4-9: a run whose topic's delivery time or cadence changed after it was prepared
    still counts from its recorded instant, in each pending state, whether the instant
    lies three days before the row was written or two days after it (run 5's cases)."""
    import itertools

    from backend.u8_policy import PRODUCTION_OPERATIONS
    from tests.u8_service_operations_integration.host_flows import production_stand_in

    today = dt.datetime.now(dt.UTC).date()
    instants = {"three days back": utc(today - 3 * DAY, 7, 30),
                "two days ahead": utc(today + 2 * DAY, 7, 30)}
    with production_stand_in(realm) as standin:
        seen = digest_seen(p.DigestProducer(standin.transactions, PRODUCTION_OPERATIONS))
        with standin.connect("topics", autocommit=True) as conn:
            for state, change, when in itertools.product(PENDING, RESETS, instants):
                case, instant = (state, change, when), instants[when]
                topic = digest_topic(conn, uuid4().hex[:12])
                run = write_digest_runs(
                    conn, topic, [("R", instant.date(), DIGEST_CONTENT, STEPS_TO[state])],
                    snapshot=zone_snapshot("UTC"), instants={"R": instant})["R"]
                conn.execute(RESETS[change], (topic,))
                assert (instant < run["created_at"]) == (when == "three days back"), case
                assert_late_bounds(seen, instant, case)
                move_run(conn, run["id"], *END_OF[state])
                assert seen(instant + 2 * HOUR + SECOND)[:2] == ON_TIME, case


def test_a_late_prepared_run_counts_from_its_scheduled_instant_not_its_preparation(realm):
    """L4-9: a run prepared days after its scheduled instant carries that lateness from
    the instant, so it is late the second it is written, and on time once it is sent."""
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from tests.u8_service_operations_integration.host_flows import production_stand_in

    instant = utc(dt.datetime.now(dt.UTC).date() - 3 * DAY, 7, 30)
    with production_stand_in(realm) as standin:
        seen = digest_seen(p.DigestProducer(standin.transactions, PRODUCTION_OPERATIONS))
        with standin.connect("topics", autocommit=True) as conn:
            late = write_digest_runs(
                conn, digest_topic(conn, "late"), [("L1", instant.date(), DIGEST_CONTENT, ())],
                snapshot=zone_snapshot("UTC"), instants={"L1": instant})["L1"]
            assert instant + 2 * HOUR + SECOND < late["created_at"]
            assert_late_bounds(seen, instant)
            assert seen(late["created_at"] + SECOND)[:2] == LATE
            move_run(conn, late["id"], "sending", "sent")
            assert seen(late["created_at"] + SECOND)[:2] == ON_TIME


def test_the_oldest_pending_run_is_the_one_counted(realm):
    """L4-9: of two pending runs the older instant decides, and the younger once the
    older run is sent."""
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from tests.u8_service_operations_integration.host_flows import production_stand_in

    today = dt.datetime.now(dt.UTC).date()
    older, younger = utc(today - 5 * DAY, 7, 30), utc(today - 2 * DAY, 6, 10)
    with production_stand_in(realm) as standin:
        seen = digest_seen(p.DigestProducer(standin.transactions, PRODUCTION_OPERATIONS))
        with standin.connect("topics", autocommit=True) as conn:
            # The younger run is written first, so neither insertion order decides.
            write_digest_runs(
                conn, digest_topic(conn, "younger"),
                [("Y", younger.date(), DIGEST_CONTENT, ("sending", "unknown"))],
                snapshot=zone_snapshot("UTC"), instants={"Y": younger})
            first = write_digest_runs(
                conn, digest_topic(conn, "older"), [("O", older.date(), DIGEST_CONTENT, ())],
                snapshot=zone_snapshot("UTC"), instants={"O": older})["O"]
            assert_late_bounds(seen, older)
            move_run(conn, first["id"], "sending", "sent")
            assert seen(older + 2 * HOUR + SECOND)[:2] == ON_TIME
            assert_late_bounds(seen, younger)


def test_a_pending_run_with_no_recorded_instant_is_never_hidden(realm):
    """L4-9: a pending run that holds no scheduled instant reads late at every `now`, in
    each pending state, and no longer once it is terminal."""
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from tests.u8_service_operations_integration.host_flows import production_stand_in

    past = dt.datetime.now(dt.UTC).date() - 3 * DAY
    with production_stand_in(realm) as standin:
        seen = digest_seen(p.DigestProducer(standin.transactions, PRODUCTION_OPERATIONS))
        with standin.connect("topics", autocommit=True) as conn:
            for state in PENDING:
                bare = write_digest_runs(
                    conn, digest_topic(conn, f"bare-{state}"),
                    [("N", past, DIGEST_CONTENT, STEPS_TO[state])],
                    snapshot=zone_snapshot("UTC"), no_instant=("N",))["N"]
                stored = conn.execute("SELECT state, scheduled_at FROM topics.digest_run "
                                      "WHERE id=%s", (bare["id"],)).fetchone()
                assert stored == {"state": state, "scheduled_at": None}
                written = bare["created_at"]
                for now in (written - 30 * DAY, written, written + 2 * HOUR + SECOND,
                            written + 30 * DAY):
                    assert seen(now)[:2] == LATE, (state, now)
                move_run(conn, bare["id"], *END_OF[state])
                assert seen(written + 30 * DAY)[:2] == ON_TIME, state


def recipient_of(conn, owner) -> str:
    return conn.execute("SELECT email FROM accounts.digest_recipient(%s)",
                        (owner,)).fetchone()["email"]


def next_due(conn, topic, now: dt.datetime) -> dt.datetime | None:
    row = conn.execute("SELECT due_at FROM topics.next_occurrence(%s,%s)",
                       (topic, now)).fetchone()
    return None if row is None else row["due_at"]


def test_a_due_delivery_with_no_run_is_late_from_its_scheduled_time(realm):
    """L3-2: the oldest due delivery with no run counts, through U5's own due read,
    scoped as the scheduler scopes it, and only for a consenting recipient (BR4.2)."""
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from tests.u8_service_operations_integration.host_flows import (
        production_stand_in,
        standin_account,
    )

    ahead = dt.datetime.now(dt.UTC).date() + 10 * DAY
    with production_stand_in(realm) as standin:
        owner = standin_account(standin, "digest-due", grant=False).account_id
        with standin.connect("topics", autocommit=True) as conn:
            topic = digest_topic(conn, "due", owner=owner)
            write_digest_runs(conn, topic, [("D0", ahead - DAY, "[]", ("empty",))],
                              snapshot=zone_snapshot("UTC"))
            due = utc(ahead, 9)
            assert next_due(conn, topic, due + 2 * HOUR) == due
            address = recipient_of(conn, owner)
        seen = digest_seen(p.DigestProducer(standin.transactions, PRODUCTION_OPERATIONS))
        assert seen(due - SECOND)[:2] == ("available", None)
        assert seen(due + 2 * HOUR)[:2] == ("available", None)
        assert seen(due + 2 * HOUR + SECOND) == ("degraded", "digest-delivery-late", 0, 0)
        for scope, expected in ((address, "degraded"),
                                ("someone-else@fixture.invalid", "available")):
            scoped = p.DigestProducer(standin.transactions, PRODUCTION_OPERATIONS,
                                      recipient=lambda scope=scope: scope)
            assert scoped.observe(due + 2 * HOUR + SECOND).outcome == expected, scope
        with standin.connect("accounts") as conn:
            conn.execute("UPDATE accounts.consent SET granted=false WHERE account_id=%s "
                         "AND purpose='local-research'", (owner,))
        assert seen(due + 2 * HOUR + SECOND)[:2] == ("available", None)


# --- The digest path: U5's own scheduler prepares the run (U8 plan Step 159(c)) -----------
#
# In these tests the owner follows and saves through U5's service, U5's built scheduler
# prepares the run from its own due read, and every state moves by one of U5's own
# transitions (`host_flows.digest_path`). They use future days, because U5's schedule
# boundary is stamped by the database's real clock; there a row is written before its
# instant. So the tests whose settings never change pass on a reading worked out from
# the window and the current settings too: they show that U5's scheduler stores the due
# instant. That the lateness fix works rests on the statement tests above and on
# `test_an_owners_later_change_leaves_a_started_runs_lateness`.


def prepared_by_the_scheduler(path, at: dt.datetime, case=None) -> dict:
    """One pass of U5's scheduler at `at`: the path's due delivery prepared and its
    send started, the recording delivery answering nothing. Returns the stored run."""
    from tests.u8_service_operations_integration.host_flows import digest_pass, digest_run_of

    assert digest_pass(path, at)["prepared"] == 1, case
    run = digest_run_of(path)
    assert run["state"] == "sending" and path.delivery.attempts == [run["id"]], case
    return run


def save_topic_settings(path, *, time: str, cadence: str = "daily",
                        weekday: str | None = None) -> None:
    """The owner's own save of the topic's settings, through U5's service."""
    revision = path.service.read_topic(path.owner, path.topic)["settings"]["revision"]
    saved = path.service.save_settings(path.owner, path.topic, {
        "revision": revision, "cadence": cadence, "deliveryTimeLocal": time,
        "deliveryDay": weekday, "contentWindowDays": 7})
    assert saved["unchanged"] is False and saved["discardedRunIds"] == []


def test_a_run_the_scheduler_prepared_counts_from_the_due_instant_u5_recorded(realm):
    """L4-9: U5's scheduler stores the due instant of the occurrence it prepares for,
    whether its pass runs 17 minutes or three days after it, and the producer gives the
    same two bounds for the due delivery before the pass and for its run after it."""
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from tests.u8_service_operations_integration.host_flows import (
        digest_path,
        end_digest_path,
        production_stand_in,
    )

    today = dt.datetime.now(dt.UTC).date()
    with production_stand_in(realm) as standin:
        seen = digest_seen(p.DigestProducer(standin.transactions, PRODUCTION_OPERATIONS))
        for suffix, ahead, lateness in (("path-prompt", 10, 17 * MINUTE),
                                        ("path-late", 20, 3 * DAY)):
            path = digest_path(standin, suffix, today + ahead * DAY)
            at = utc(path.day, 9) + lateness
            with standin.connect("topics") as conn:
                due = next_due(conn, path.topic, at)
            assert due == utc(path.day, 9), suffix
            assert_late_bounds(seen, due, suffix)
            run = prepared_by_the_scheduler(path, at, suffix)
            assert (run["scheduled_at"], run["window_end"]) == (due, path.day), suffix
            assert run["created_at"] < due < at
            assert_late_bounds(seen, due, suffix)
            end_digest_path(path)


def test_an_owners_later_change_leaves_a_started_runs_lateness(realm):
    """L4-9: once a run is sending or unknown, its owner's later saves of the delivery
    time, the cadence and the zone, each the real save, move neither bound: the run
    still counts from the instant U5 recorded when it prepared it."""
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from tests.u8_service_operations_integration.host_flows import (
        digest_path,
        digest_run_of,
        end_digest_path,
        production_stand_in,
        save_zone,
    )

    saves = (
        ("delivery time", lambda path: save_topic_settings(path, time="21:45")),
        ("cadence", lambda path: save_topic_settings(path, time="21:45", cadence="weekly",
                                                     weekday="wed")),
        ("zone", lambda path: save_zone(path.standin, path.owner, "Asia/Seoul")),
    )
    today = dt.datetime.now(dt.UTC).date()
    with production_stand_in(realm) as standin:
        seen = digest_seen(p.DigestProducer(standin.transactions, PRODUCTION_OPERATIONS))
        for state, ahead in (("sending", 10), ("unknown", 20)):
            path = digest_path(standin, f"path-{state}", today + ahead * DAY)
            due = utc(path.day, 9)
            run = prepared_by_the_scheduler(path, due + 5 * MINUTE, state)
            if state == "unknown":  # U5's orphan sweep's own retire
                assert path.repository.retire_orphan(run["id"])["state"] == "unknown"
            assert run["scheduled_at"] == due and digest_run_of(path)["state"] == state
            assert_late_bounds(seen, due, state)
            for change, save in saves:
                save(path)
                kept = digest_run_of(path)
                assert (kept["id"], kept["state"], kept["scheduled_at"]) == (
                    run["id"], state, due), (state, change)
                assert_late_bounds(seen, due, (state, change))
            end_digest_path(path)


def test_a_weekly_delivery_is_due_only_on_its_weekday(realm):
    """L3-2, L4-9: a weekly delivery is due on its weekday at its time in the owner's
    zone, whether it has no run yet or the run U5's scheduler prepared for it."""
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from tests.u8_service_operations_integration.host_flows import (
        digest_path,
        production_stand_in,
    )

    start = dt.datetime.now(dt.UTC).date() + 10 * DAY
    monday = start + ((7 - start.weekday()) % 7) * DAY
    with production_stand_in(realm) as standin:
        path = digest_path(standin, "digest-weekly", monday + 7 * DAY, cadence="weekly",
                           weekday="mon", zone="Asia/Seoul", previous=monday)
        due = utc(monday + 7 * DAY)  # Monday 09:00 in Seoul
        seen = digest_seen(p.DigestProducer(standin.transactions, PRODUCTION_OPERATIONS))
        assert seen(due - SECOND)[0] == "available"
        assert_late_bounds(seen, due)
        run = prepared_by_the_scheduler(path, due + 20 * MINUTE)
        assert (run["scheduled_at"], run["window_end"]) == (due, monday + 7 * DAY)
        assert_late_bounds(seen, due)


DAYLIGHT_CASES = (
    ("America/New_York", "02:30", dt.date(2027, 3, 14),
     dt.datetime(2027, 3, 14, 7, 0, tzinfo=dt.UTC)),
    ("America/New_York", "01:30", dt.date(2027, 11, 7),
     dt.datetime(2027, 11, 7, 5, 30, tzinfo=dt.UTC)),
    ("Australia/Lord_Howe", "02:15", dt.date(2027, 10, 3),
     dt.datetime(2027, 10, 2, 15, 30, tzinfo=dt.UTC)),
    ("Australia/Lord_Howe", "01:45", dt.date(2027, 4, 4),
     dt.datetime(2027, 4, 3, 14, 45, tzinfo=dt.UTC)),
)


def test_a_runs_scheduled_time_follows_its_zone_across_daylight_saving_changes(realm):
    """L3-2, L4-9: a gap's missing minute is due at the first valid minute after it, and
    a fold's repeated minute at its first occurrence (`u5_schedule.sql:24-38`). U5's
    scheduler records that instant on the run it prepares, and the producer counts from
    it. Each expected instant is a constant from outside the code under test."""
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from tests.u8_service_operations_integration.host_flows import (
        digest_path,
        end_digest_path,
        production_stand_in,
    )

    with production_stand_in(realm) as standin:
        seen = digest_seen(p.DigestProducer(standin.transactions, PRODUCTION_OPERATIONS))
        for index, (zone, wall, day, scheduled) in enumerate(DAYLIGHT_CASES):
            path = digest_path(standin, f"digest-dst-{index}", day, time=wall, zone=zone)
            run = prepared_by_the_scheduler(path, scheduled + 9 * MINUTE, (zone, day))
            assert run["scheduled_at"] == scheduled, (zone, day)
            assert_late_bounds(seen, scheduled, (zone, day))
            end_digest_path(path)


def nth_sunday(year: int, month: int, nth: int) -> dt.date:
    first = dt.date(year, month, 1)
    return first + ((6 - first.weekday()) % 7) * DAY + (nth - 1) * 7 * DAY


def new_york_change(month: int, nth: int, today: dt.date) -> dt.date:
    """America/New_York's change day (its rule since 2007), from the first year in
    which that day is at least 10 days after today, by date arithmetic only."""
    year = today.year
    while nth_sunday(year, month, nth) < today + 10 * DAY:
        year += 1
    return nth_sunday(year, month, nth)


def test_the_scheduled_time_matches_u5s_next_occurrence_on_new_yorks_next_two_changes(realm):
    """L3-2, L4-9: in a named zone, on both changes, U5's due rule gives the instant
    date arithmetic gives, U5's scheduler records it on the run it prepares, and the
    producer counts the due delivery and then its run from it."""
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from tests.u8_service_operations_integration.host_flows import (
        digest_path,
        end_digest_path,
        production_stand_in,
    )

    today = dt.datetime.now(dt.UTC).date()
    phases = (("gap", "02:30", new_york_change(3, 2, today), (7, 0)),
              ("fold", "01:30", new_york_change(11, 1, today), (5, 30)))
    with production_stand_in(realm) as standin:
        seen = digest_seen(p.DigestProducer(standin.transactions, PRODUCTION_OPERATIONS))
        for name, wall, day, (hour, minute) in phases:
            path = digest_path(standin, f"digest-ny-{name}", day, time=wall,
                               zone="America/New_York")
            due = utc(day, hour, minute)
            with standin.connect("topics") as conn:
                assert next_due(conn, path.topic, utc(day, 12)) == due, name
            assert_late_bounds(seen, due, name)
            run = prepared_by_the_scheduler(path, due + 9 * MINUTE, name)
            assert run["scheduled_at"] == due, name
            assert_late_bounds(seen, due, name)
            end_digest_path(path)


def test_terminal_runs_never_count_as_pending_however_many_there_are(realm):
    """L3-2, L4-9: 300 terminal runs months back, none with a recorded instant, count
    in the terminal total and neither as late nor as pending runs without an instant."""
    from backend.u8_policy import PRODUCTION_OPERATIONS
    from tests.u8_service_operations_integration.host_flows import production_stand_in

    past = dt.datetime.now(dt.UTC).date() - 3 * DAY
    with production_stand_in(realm) as standin:
        with standin.connect("topics", autocommit=True) as conn:
            moved = []
            for key in ("t1", "t2", "t3"):
                topic = digest_topic(conn, key)
                runs = write_digest_runs(conn, topic, [
                    (str(offset), past - offset * DAY, "[]", ("empty",))
                    for offset in range(103, 3, -1)], snapshot=zone_snapshot("UTC"))
                moved += [run["updated_at"] for run in runs.values()]
        assert len(moved) == 300
        seen = digest_seen(p.DigestProducer(standin.transactions, PRODUCTION_OPERATIONS))
        assert seen(max(moved) + SECOND) == ("available", None, 0, 300)


# --- 3. Capacity and 4. the backup volume ------------------------------------------------


def capacity(transactions, tmp_path, *, footprint, free, agent=None, volume="stand-in",
             expected="DocSuri_Backup", counts=None):
    return p.CapacityProducer(
        transactions, SYNTHETIC_OPERATIONS, disk_path=tmp_path,
        volume_state=lambda: volume, agent_status=agent, expected_volume=expected,
        footprint=lambda: footprint, free_bytes=lambda: free, counts=counts,
    )


def test_capacity_is_degraded_at_80_percent_and_unavailable_at_its_floors(transactions,
                                                                          tmp_path, clock):
    plenty = 100 * GIB
    cases = [
        (int(8 * GIB * 0.8) - 1, plenty, "available", None),
        (int(8 * GIB * 0.8), plenty, "degraded", "capacity-approaching"),
        (8 * GIB - 256 * 1024**2 - 1, plenty, "degraded", "capacity-approaching"),
        (8 * GIB - 256 * 1024**2, plenty, "unavailable", "capacity-exhausted"),
        (GIB, 20 * GIB - 1, "degraded", "internal-disk-low"),
        (GIB, 10 * GIB - 1, "unavailable", "internal-disk-critical"),
    ]
    for footprint, free, outcome, reason in cases:
        observed = capacity(transactions, tmp_path, footprint=footprint, free=free).observe(
            clock())
        assert (observed.outcome, observed.reason) == (outcome, reason), (footprint, free)
    real = p.CapacityProducer(transactions, SYNTHETIC_OPERATIONS, disk_path=tmp_path,
                              volume_state=lambda: "stand-in", agent_status=None,
                              expected_volume=None).observe(clock())
    assert real.outcome in ("available", "degraded", "unavailable")


def agent_status(**changes) -> dict:
    return {"volumeIdentity": "DocSuri_Backup", "available": True, "freeBytes": 200 * GIB,
            "sharedCleanupMarker": False, "catalogue": "intact",
            "lastGoodHeldPastRetention": False} | changes


def test_the_backup_volume_and_the_agents_status(transactions, tmp_path, clock):
    def observe(**options):
        return capacity(transactions, tmp_path, footprint=GIB, free=100 * GIB,
                        **options).observe(clock())

    assert observe(agent=lambda: agent_status()).outcome == "available"
    mismatch = observe(agent=lambda: agent_status(volumeIdentity="Another_Volume"))
    assert (mismatch.outcome, mismatch.reason) == ("degraded", "backup-volume-mismatch")
    assert observe(volume="unavailable").limitations == ("backup-volume-unavailable",)
    several = observe(agent=lambda: agent_status(freeBytes=GIB, catalogue="damaged",
                                                 sharedCleanupMarker=True,
                                                 lastGoodHeldPastRetention=True))
    assert set(several.limitations) == {"backup-volume-low", "backup-catalogue-damaged",
                                        "backup-volume-shared-cleanup", "last-backup-held"}

    def unreadable():
        raise OSError("no status")

    assert observe(agent=unreadable).reason == "backup-volume-unavailable"


# --- 5. Model evidence ------------------------------------------------------------------


class RecordedTags:
    """A recorded `/api/tags` answer and the re-pin calls."""

    def __init__(self, models, *, reachable=True):
        self.models, self.reachable, self.repins = models, reachable, []

    def tags(self):
        if not self.reachable:
            raise ConnectionError("runtime unreachable")
        return self.models

    def repin(self, model, *, keep_alive):
        self.repins.append((model, keep_alive))


def pinned(**changes):
    return [{"name": name, "model": name, "digest": changes.get(name, digest)}
            for name, digest in PINS.items()]


def test_a_model_digest_different_from_its_pin_makes_provider_models_unavailable(clock):
    good = RecordedTags(pinned())
    producer = p.ModelsProducer(good, SYNTHETIC_OPERATIONS)
    assert producer.observe(clock()).outcome == "available"
    assert good.repins == [("bge-m3:latest", -1)]
    assert producer.observe(clock() + dt.timedelta(seconds=1)).outcome == "available"
    assert len(good.repins) == 1
    repin = SYNTHETIC_OPERATIONS.search_model_repin_seconds
    producer.observe(clock() + dt.timedelta(seconds=repin))
    assert len(good.repins) == 2
    for tags in (pinned(**{"qwen3:8b": "0" * 64}), pinned()[:1],
                 [{**item, "remote_host": "elsewhere"} for item in pinned()]):
        observed = p.ModelsProducer(RecordedTags(tags), SYNTHETIC_OPERATIONS).observe(clock())
        assert (observed.outcome, observed.reason) == ("unavailable", "model-evidence-mismatch")
    down = p.ModelsProducer(RecordedTags([], reachable=False), SYNTHETIC_OPERATIONS)
    assert down.observe(clock()).reason == "runtime-unreachable"
    assert p.ModelsProducer(None, SYNTHETIC_OPERATIONS).observe(clock()).outcome == "unknown"


def test_the_runtime_source_reads_tags_and_repins_with_keep_alive_minus_one():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": pinned()})
        return httpx.Response(200, json={"embeddings": []})

    source = p.OllamaTags(transport=httpx.MockTransport(handler))
    assert [item["name"] for item in source.tags()] == list(PINS)
    source.repin("bge-m3:latest", keep_alive=-1)
    body = json.loads(requests[-1].content)
    assert requests[-1].url.path == "/api/embed"
    assert body == {"model": "bge-m3:latest", "input": "", "keep_alive": -1}
    assert str(requests[0].url).startswith("http://127.0.0.1:11434/")


# --- 6. Platform reads are read-only ------------------------------------------------------


def write_result(folder, name: str, value: dict) -> None:
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream)


def test_platform_reads_execute_no_operation(tmp_path, clock):
    asked = []

    def inspect_evidence():
        asked.append("inspectEvidence")
        return {"outcome": "pass"}

    assert p.PlatformStatusProducer(inspect_evidence).observe(clock()).outcome == "available"
    assert asked == ["inspectEvidence"]
    assert p.PlatformStatusProducer(None).observe(clock()).outcome == "unknown"
    source = inspect.getsource(p)
    for operation in ("executeControlled", "run_effect", "begin_operation", "dispatch("):
        assert operation not in source

    folder = tmp_path / "evidence" / "isolation"
    producer = p.IsolationProducer(folder)
    assert producer.observe(clock()).reason == "evidence-unavailable"
    checked = "2026-10-22T05:00:00Z"
    items = [{"item": item, "passed": True} for item in ("programs", "files", "filter")]
    write_result(folder, "2026-10-22T05-00-00Z.json",
                 {"resultId": str(uuid4()), "checkedAt": checked, "items": items,
                  "stopRecords": [], "passed": True, "digest": "a" * 64})
    passed = producer.observe(clock())
    assert passed.outcome == "available"
    assert passed.observed_at == dt.datetime(2026, 10, 22, 5, tzinfo=dt.UTC)
    failing = [*items[:2], {"item": "filter", "passed": False, "reasonKey": "rule-missing"}]
    write_result(folder, "2026-10-22T05-05-00Z.json",
                 {"resultId": str(uuid4()), "checkedAt": "2026-10-22T05:05:00Z",
                  "items": failing, "stopRecords": [], "passed": False, "digest": "b" * 64})
    lapsed = producer.observe(clock())
    assert (lapsed.outcome, lapsed.reason, lapsed.limitations) == (
        "unavailable", "runtime-isolation-lapsed", ("isolation-filter",))


# --- The others -----------------------------------------------------------------------------


def test_the_ledger_loop_provider_cutover_assistance_and_host_producers(
    component, realm, clock, tmp_path,
):
    now = clock()
    assert p.LedgerProducer(component).observe(now).outcome == "available"
    status = {"state": "idle", "timeouts": 0}
    loop = p.BackgroundWorkProducer(lambda: status)
    assert loop.observe(now).outcome == "available"
    status.update(state="idle", timeouts=1)
    assert loop.observe(now).reason == "lane-behind-deadline"
    assert loop.observe(now).outcome == "available"
    assert p.BackgroundWorkProducer(None).observe(now).outcome == "unknown"

    assert p.ProviderProducer("provider.resend", component).observe(now).outcome == "available"
    component.append("provider-activation", {"provider": "resend", "outward": True,
                                             "state": "held", "limitations": []},
                     expect_revision=0)
    held = p.ProviderProducer("provider.resend", component).observe(now)
    assert (held.outcome, held.reason) == ("degraded", "first-effect-pending")
    component.append("provider-activation", {"provider": "google", "outward": False,
                                             "state": "held", "limitations": []},
                     expect_revision=0)
    assert p.ProviderProducer("provider.google", component).observe(now).reason == (
        "sign-in-unverified")
    assert p.ProviderProducer("provider.orcid", component,
                              reachable=lambda: False).observe(now).reason == (
        "provider-unreachable")

    cutover = p.CutoverProducer(component, routing=None)
    assert cutover.observe(now).outcome == "available"  # no CutoverRecord yet
    component.append("cutover-record", {
        "cutoverId": str(uuid4()), "releaseTag": "v2.0.0", "state": "preparing",
        "soakPeriodSeconds": 604800, "soakClean": False, "switchTimeBoundSeconds": 14400,
        "rollbackWindowSeconds": 1209600, "effectReceipts": [], "approvals": [],
    }, expect_revision=0)
    assert cutover.observe(now).reason == "evidence-unavailable"
    assert p.CutoverProducer(component, lambda: {"route": "v1-web"}).observe(now).outcome == (
        "available")
    assert p.CutoverProducer(component, lambda: {"route": "v2-host"}).observe(now).reason == (
        "cutover-route-differs")
    assert p.CutoverProducer(component, lambda: {"route": "v1-web", "unknownEffects": 1}
                             ).observe(now).reason == "cutover-effect-unknown"

    assistance = p.AssistanceProducer("assistance.summary", realm)
    assert assistance.observe(now).outcome in ("available", "degraded")
    assert p.AssistanceProducer("assistance.summary", realm, lambda: "unavailable").observe(
        now).reason == "model-runtime-unavailable"

    # The host's 24-hour rate (Step 59(d), L1-47), at a literal now.
    host_now = dt.datetime(2026, 11, 2, 1, 0, tzinfo=dt.UTC)

    def rate(files: dict[str, list[tuple[str, int, int, str]]]) -> tuple:
        folder = tmp_path / f"latency-{uuid4().hex[:8]}"
        for day, lines in files.items():
            write_latency(folder, day, lines)
        observed = p.HostErrorRateProducer(folder).observe(host_now)
        return observed.outcome, observed.error_count, observed.total_count

    assert rate({
        "2026-11-01": [("read", 3, 100, "2026-11-01T02:00:00Z"),
                       ("health", 9, 9, "2026-11-01T00:59:59Z")],  # 24 h and 1 s before
        "2026-11-02": [("search", 1, 5, "2026-11-02T00:55:00Z")],
    }) == ("available", 1, 5)
    assert rate({"2026-11-01": [("read", 1, 5, "2026-11-01T02:00:00Z")],
                 "2026-11-02": [("read", 1, 5, "2026-11-02T00:55:00Z")]}) == (
        "available", 2, 10)
    assert rate({"2026-11-01": [("read", 3, 10, "2026-11-01T02:00:00Z")]}) == (
        "available", 3, 10)
    assert rate({"2026-11-02": [("read", 2, 10, "2026-11-02T00:10:00Z"),
                                ("search", 1, 5, "2026-11-02T00:10:00Z")]}) == (
        "available", 2, 10)  # equal shares go to the larger count
    assert rate({"2026-11-02": [("read", 0, 0, "2026-11-02T00:10:00Z"),
                                ("search", 0, 0, "2026-11-02T00:10:00Z")]}) == (
        "available", 0, 0)
    assert rate({}) == ("available", 0, 0)  # no file
    # A write cut short: its fragment, the next flush's first line glued onto it, a line
    # missing a key and a non-JSON line are skipped; the whole lines still count.
    cut = tmp_path / f"latency-{uuid4().hex[:8]}"
    write_latency(cut, "2026-11-02", [("read", 1, 4, "2026-11-02T00:10:00Z")])
    with open(cut / "2026-11-02.jsonl", "a") as stream:
        stream.write('{"window": "2026-11-02T00:20:00Z", "class": "read", "cou')
        stream.write('{"window": "2026-11-02T00:30:00Z", "class": "read", "count": 50, '
                     '"errors5xx": 50}\n')
        stream.write('{"window": "2026-11-02T00:31:00Z", "class": "read", "count": 7}\n')
        stream.write("not-json\n")
    write_latency(cut, "2026-11-02", [("read", 2, 6, "2026-11-02T00:40:00Z")])
    observed = p.HostErrorRateProducer(cut).observe(host_now)
    assert (observed.outcome, observed.error_count, observed.total_count) == (
        "available", 3, 10)
    # A linked day file is not read.
    linked = tmp_path / f"latency-{uuid4().hex[:8]}"
    linked.mkdir(mode=0o700)
    (linked / "2026-11-02.jsonl").symlink_to(cut / "2026-11-02.jsonl")
    observed = p.HostErrorRateProducer(linked).observe(host_now)
    assert (observed.error_count, observed.total_count) == (0, 0)


def write_latency(folder, day: str, lines) -> None:
    """Latency summary lines `(class, errors5xx, count, window)` in `<day>.jsonl`."""
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(folder / f"{day}.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                         0o600)
    with os.fdopen(descriptor, "a") as stream:
        for route, errors, count, window in lines:
            stream.write(json.dumps({"window": window, "class": route, "count": count,
                                     "errors5xx": errors, "medianMs": 1, "p95Ms": 1,
                                     "maxMs": 1}) + "\n")


class KeptObservations(Observations):
    """The realm's observations, remembering the rows it records so a test reads each
    back by id."""

    def __init__(self, store):
        super().__init__(store)
        self.rows: list = []

    def record(self, producer, rows):
        rows = list(rows)
        self.rows.extend(rows)
        return super().record(producer, rows)


def stored_row(transactions, row_id) -> dict:
    return transactions.run("operations", lambda conn: conn.execute(
        "SELECT * FROM operations.observation_record WHERE id=%s", (row_id,)).fetchone())


def record_once(transactions, producer, at: dt.datetime, policy=SYNTHETIC_OPERATIONS) -> dict:
    """One observation recorded through `ProducerSchedule` into the realm's store at
    `at`, read back by id."""
    observations = KeptObservations(ObservationStore(transactions))
    schedule = p.ProducerSchedule([producer], observations, policy, lambda: at)
    assert schedule.run_due(at) == [producer.capability]
    return stored_row(transactions, observations.rows[-1].id)


def test_the_hosts_24_hour_rate_reaches_its_capability_item(transactions, clock, tmp_path,
                                                            component):
    """Step 59(d): the stored rate, then public.static's state and its 운영 item."""
    from backend.modules.operations.dashboard import Dashboard
    from backend.modules.operations.readiness import Readiness
    from backend.u8_host import Activation
    from backend.u8_registry import CONTRIBUTIONS, MANIFEST

    now = clock()
    window = (now - dt.timedelta(minutes=5)).astimezone(dt.UTC)
    folder = tmp_path / "latency"
    write_latency(folder, f"{window:%Y-%m-%d}",
                  [("search", 1, 5, window.isoformat(timespec="seconds").replace(
                      "+00:00", "Z"))])
    row = record_once(transactions, p.HostErrorRateProducer(folder), now)
    assert (row["outcome"], row["error_count"], row["total_count"]) == ("available", 1, 5)
    activations = {entry.contribution_id: Activation(entry.contribution_id, "active")
                   for entry in CONTRIBUTIONS}
    readiness = Readiness(MANIFEST, activations, {}, ObservationStore(transactions),
                          SYNTHETIC_OPERATIONS, lambda: now)
    state = readiness.states()["public.static"]
    assert (state.state, state.reason, state.error_count, state.total_count) == (
        "available", None, 1, 5)
    dashboard = Dashboard(readiness, component, environment="live", clock=lambda: now)
    [item] = [item for item in dashboard.items() if item.get("capability") == "public.static"]
    assert "error-rate-permille:200" in item["limitations"]


# --- 7. Provider probes and failure counts (Step 57; L1-11, L1-12) ----------------------------

REFUSED = "tests never build a network transport"
PROVIDER_CAPABILITIES = ("provider.google", "provider.orcid", "provider.resend",
                         "provider.notion")


class ProbeClock:
    """The injected monotonic clock: it moves only when a waiter or a handler moves it."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


class ProbeWaiter:
    """One waiter for every case: it waits, at most 5 s of real time, until the request
    ends or a never-answering handler sets `entered`; only once `entered` is set does a
    call move the clock 0.5 s."""

    def __init__(self, clock: ProbeClock, entered):
        self.clock, self.entered = clock, entered
        self.calls = self.moves = 0

    def __call__(self, done, step) -> None:
        import time

        self.calls += 1
        deadline = time.monotonic() + 5.0
        while not (done.is_set() or self.entered.is_set()) and time.monotonic() < deadline:
            done.wait(0.01)
        if self.entered.is_set():
            self.moves += 1
            self.clock.now += 0.5


class ProbeCase:
    """A probe's clock, waiter and handlers, with a never-answering handler released at
    teardown."""

    def __init__(self):
        import threading

        self.clock, self.entered = ProbeClock(), threading.Event()
        self.release = threading.Event()
        self.waiter = ProbeWaiter(self.clock, self.entered)
        self.requests: list[httpx.Request] = []

    def answering(self, status: int, *, move: float = 0.0, body=None):
        def handler(request):
            self.requests.append(request)
            self.clock.now += move
            return httpx.Response(status, json=body if body is not None else {})

        return handler

    def never(self, request):
        self.requests.append(request)
        self.entered.set()
        self.release.wait(30)
        return httpx.Response(200, json={})

    def factory(self, capability: str, handler):
        if capability == "provider.notion":
            return lambda: httpx.MockTransport(handler)
        return lambda **options: httpx.AsyncClient(transport=httpx.MockTransport(handler),
                                                   **options)

    def probe(self, capability: str, handler):
        from backend.u8_provider_probes import ProviderProbe

        return ProviderProbe(capability, self.factory(capability, handler),
                             clock=self.clock, waiter=self.waiter)


@pytest.fixture
def probe_case():
    cases = []

    def make() -> ProbeCase:
        cases.append(ProbeCase())
        return cases[-1]

    yield make
    for case in cases:
        case.release.set()


def test_each_provider_probe_has_five_seconds(probe_case, clock, component):
    from backend import u8_provider_probes as probes

    assert (probes.PROBE_SECONDS, probes.REPIN_SECONDS, probes.POLL_SECONDS) == (
        5.0, 10.0, 0.1)
    for capability in PROVIDER_CAPABILITIES:
        url, rule = probes.PROBE_REQUESTS[capability]
        discovery = rule == probes.DISCOVERY
        # An answer: 200 for a discovery document, 401 for Resend and Notion.
        case = probe_case()
        assert case.probe(capability, case.answering(200 if discovery else 401))() is True
        assert len(case.requests) == 1 and case.clock.now == 1000.0
        request = case.requests[0]
        assert (request.method, str(request.url)) == ("GET", url)
        assert "authorization" not in request.headers  # no credential is carried
        # A discovery document answering 404, and a 503 from any of the four.
        for status in ((404, 503) if discovery else (503,)):
            case = probe_case()
            assert case.probe(capability, case.answering(status))() is False
        # A handler that never answers: unavailable at 5.0 s, after ten waiter calls.
        case = probe_case()
        observed = p.ProviderProducer(capability, component,
                                      probe=case.probe(capability, case.never)).observe(clock())
        assert (observed.outcome, observed.reason) == ("unavailable", "provider-unreachable")
        assert case.clock.now == 1005.0 and case.waiter.calls == 10
        # Production's own base factory, under the test-wide guard: its error on the
        # calling thread, and the probe unavailable with no waiter call.
        case = probe_case()
        production = probes.production_probe(capability, clock=case.clock,
                                             waiter=case.waiter)
        with pytest.raises(RuntimeError, match=REFUSED):
            production._client()
        observed = p.ProviderProducer(capability, component,
                                      probe=production).observe(clock())
        assert (observed.outcome, observed.reason) == ("unavailable", "provider-unreachable")
        assert case.waiter.calls == 0

    def models(case, tags_handler, embed_handler=None):
        def handler(request):
            if request.url.path == "/api/tags":
                return tags_handler(request)
            return embed_handler(request)

        source = p.OllamaTags(transport=httpx.MockTransport(handler), clock=case.clock,
                              waiter=case.waiter)
        return p.ModelsProducer(source, SYNTHETIC_OPERATIONS).observe(clock())

    pinned_tags = {"models": pinned()}
    # `/api/tags` never answers: unreachable at 5.0 s.
    case = probe_case()
    observed = models(case, case.never)
    assert observed.reason == "runtime-unreachable" and case.clock.now == 1005.0
    assert case.waiter.calls == 10
    # `/api/tags` moves the clock 7 s, then answers: an answer past the deadline is none.
    case = probe_case()
    assert models(case, case.answering(200, move=7.0, body=pinned_tags)).reason == (
        "runtime-unreachable")
    # The re-pin moves the clock 7 s, then answers: within its own 10.0 s bound.
    case = probe_case()
    assert models(case, case.answering(200, body=pinned_tags),
                  case.answering(200, move=7.0, body={"embeddings": []})).outcome == (
        "available")
    # A re-pin that never answers: unreachable at 10.0 s past its start, after twenty
    # waiter calls that moved the clock, not ten (the tags read answered at once, its one
    # possible wait moving nothing).
    case = probe_case()
    observed = models(case, case.answering(200, body=pinned_tags), case.never)
    assert observed.reason == "runtime-unreachable" and case.clock.now == 1010.0
    assert case.waiter.moves == 20 and case.waiter.calls - case.waiter.moves <= 1
    # No transport, under the guard: unreachable with no waiter call.
    case = probe_case()
    source = p.OllamaTags(clock=case.clock, waiter=case.waiter)
    assert p.ModelsProducer(source, SYNTHETIC_OPERATIONS).observe(clock()).reason == (
        "runtime-unreachable")
    assert case.waiter.calls == 0


def test_a_failed_provider_probe_waits_for_the_next_renewal(transactions, clock, component):
    from backend.u8_policy import PRODUCTION_OPERATIONS

    def read_back(at: dt.datetime) -> dict:
        return transactions.run("operations", lambda conn: conn.execute(
            "SELECT outcome, reason_key FROM operations.observation_record "
            "WHERE capability='provider.google' AND observed_at=%s", (at,)).fetchone())

    producer = p.ProviderProducer("provider.google", component, probe=lambda: False)
    observations = Observations(ObservationStore(transactions))
    # One hour behind the clock, so the realm's own latest row stays the newest.
    t0 = clock() - dt.timedelta(hours=1)
    schedule = p.ProducerSchedule([producer], observations, PRODUCTION_OPERATIONS, clock,
                                  Ticks())
    assert schedule.run_due(t0) == ["provider.google"]
    row = read_back(t0)
    assert (row["outcome"], row["reason_key"]) == ("unavailable", "provider-unreachable")
    assert schedule.run_due(t0 + dt.timedelta(seconds=299)) == []
    assert schedule.run_due(t0 + dt.timedelta(seconds=300)) == ["provider.google"]
    synthetic = p.ProducerSchedule([producer], observations, SYNTHETIC_OPERATIONS, clock,
                                   Ticks())
    t1 = t0 + dt.timedelta(minutes=10)
    assert synthetic.run_due(t1) == ["provider.google"]
    assert synthetic.run_due(t1 + dt.timedelta(seconds=4)) == []
    assert synthetic.run_due(t1 + dt.timedelta(seconds=5)) == ["provider.google"]


def count_line(folder, process: str, day: str, failed: int, total: int, window: str) -> None:
    path = folder / f"{process}-counts-{day}.jsonl"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "a") as stream:
        stream.write(json.dumps({"failed": failed, "kind": "provider.resend", "total": total,
                                 "window": window}, sort_keys=True) + "\n")


class Exhausted:
    """An allowance at its limit: it answers one question and receives no statement."""

    def exhausted(self, kind):
        return True


def test_each_provider_carries_its_refusals_and_over_limit_answers(tmp_path, clock, caplog):
    import asyncio
    import logging
    import secrets

    from backend.log_events import EVENTS_LOGGER
    from backend.modules.accounts.integrations.identity_providers import (
        GoogleIdentityProvider,
    )
    from backend.u8_counts import ProcessCounts, counts_over
    from backend.u8_provider_probes import (
        count_reader,
        counting_client_factory,
        counting_transport_factory,
        identity_client,
    )

    moment = dt.datetime(2026, 11, 10, 12, 0, 30, tzinfo=dt.UTC)
    folder = tmp_path / "evidence"
    counts = ProcessCounts(folder, "workers", policy=SYNTHETIC_OPERATIONS,
                           clock=lambda: moment)
    # The transport-factory wrapper: 200, 403, 400 and 429 answered, then a ConnectError.
    answers = iter([200, 403, 400, 429, httpx.ConnectError("refused")])

    def handler(request):
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return httpx.Response(answer, json={})

    notion = counting_transport_factory(lambda: httpx.MockTransport(handler),
                                        "provider.notion", counts)
    built = []

    async def five_operations() -> None:
        for _ in range(5):
            built.append(notion())  # a new counting transport for every operation
            async with httpx.AsyncClient(transport=built[-1]) as client:
                try:
                    await client.get("https://api.notion.com/v1/users/me")
                except httpx.ConnectError:
                    pass

    asyncio.run(five_operations())
    assert len({id(item) for item in built}) == 5
    # The client-factory wrapper for Resend, with one 200.
    resend = counting_client_factory(
        lambda **options: httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
            **options), "provider.resend", counts)

    async def one_send() -> None:
        async with resend(timeout=3.0) as client:
            await client.post("https://api.resend.com/emails", json={})

    asyncio.run(one_send())
    # A sign-in the person cancels runs only the authorization address.
    google = GoogleIdentityProvider(
        client_id="docsuri-test.apps.example", client_secret=secrets.token_hex(16),
        origin="https://docsuri.test",
        client_factory=counting_client_factory(identity_client, "provider.google", counts))
    address = google.authorization_url(state=secrets.token_hex(8), nonce=secrets.token_hex(8),
                                       verifier=secrets.token_urlsafe(48))
    assert address.startswith("https://accounts.google.com/")
    # The wrapper over the module's own builder still meets the guard and counts nothing.
    with pytest.raises(RuntimeError, match=REFUSED):
        google.exchange("code", verifier=secrets.token_urlsafe(48), nonce="nonce")
    counts.close()
    assert counts_over(folder, PROVIDER_CAPABILITIES, moment + dt.timedelta(minutes=5)) == {
        "provider.google": (0, 0), "provider.orcid": (0, 0), "provider.resend": (0, 1),
        "provider.notion": (3, 4)}

    # Two processes' lines, and one from a window 25 hours old, which is left out.
    second = tmp_path / "second"
    second.mkdir(mode=0o700)
    now = dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.UTC)
    count_line(second, "host", "2026-11-10", 1, 2, "2026-11-10T11:00:00Z")
    count_line(second, "workers", "2026-11-10", 2, 3, "2026-11-10T11:30:00Z")
    count_line(second, "workers", "2026-11-09", 4, 4, "2026-11-09T11:00:00Z")
    reader = count_reader(second, "provider.resend", lambda: now)
    assert reader() == (3, 5)

    # Each outcome carries 3 of 5 from that folder's reader.
    assert [counted for _, counted in provider_outcomes(tmp_path, clock, reader)] == [
        (3, 5)] * 6

    # A count reader that raises leaves each outcome as it was, at 0 of 0, and logs one
    # `counts.unread` line with `state` `provider.resend` for each read.
    def unreadable():
        raise ValueError("a count line names an unregistered kind")

    unread: list[list[dict]] = []

    def logged() -> None:
        lines = [json.loads(record.getMessage()) for record in caplog.records
                 if record.name == EVENTS_LOGGER]
        unread.append([line for line in lines if line.get("event") == "counts.unread"])
        caplog.clear()

    with caplog.at_level(logging.WARNING, logger=EVENTS_LOGGER):
        caplog.clear()
        found = provider_outcomes(tmp_path, clock, unreadable, after_each=logged)
    assert [counted for _, counted in found] == [(0, 0)] * 6
    assert len(unread) == 6
    assert all(len(lines) == 1 and lines[0]["state"] == "provider.resend"
               and lines[0]["component"] == "operations" for lines in unread)


def provider_outcomes(tmp_path, clock, reader, *, after_each=None) -> list:
    """`provider.resend`'s six outcomes, each on a ledger of its own: a failed probe,
    unreachable, held, an unavailable activation, allowance exhausted and available, each
    with the counts it carried."""
    import secrets

    cases = [
        ({"probe": lambda: False}, None, ("unavailable", "provider-unreachable")),
        ({"reachable": lambda: False}, None, ("unavailable", "provider-unreachable")),
        ({}, "held", ("degraded", "first-effect-pending")),
        ({}, "unavailable", ("unavailable", "provider-unreachable")),
        ({"allowance": Exhausted()}, None, ("degraded", "allowance-exhausted")),
        ({}, None, ("available", None)),
    ]
    found = []
    for options, state, expected in cases:
        folder = tmp_path / f"ledger-{secrets.token_hex(4)}"
        folder.mkdir(mode=0o700)
        ledger = Ledger.open(folder, clock=clock)
        try:
            if state is not None:
                ledger.append("provider-activation", {"provider": "resend", "outward": True,
                                                      "state": state, "limitations": []},
                              expect_revision=0)
            observed = p.ProviderProducer("provider.resend", ledger, counts=reader,
                                          **options).observe(clock())
        finally:
            ledger.close()
        if after_each is not None:
            after_each()
        assert (observed.outcome, observed.reason) == expected
        found.append(((observed.outcome, observed.reason),
                      (observed.error_count, observed.total_count)))
    return found


def test_a_synthetic_composition_probes_no_provider(realm, monkeypatch, clock):
    from backend.modules.accounts.integrations import digest_email, identity_providers
    from backend.modules.export import notion_session
    from backend.modules.summarization import model_runtime
    from backend.u8_host import PROVIDER_ENVIRONMENT, compose, worker_producers
    from tests.u8_service_operations_integration import host_flows

    path = realm.root / PROVIDER_ENVIRONMENT
    host_flows.write_private(path, json.dumps(host_flows.PROVIDER_ENVIRONMENT).encode())
    try:
        composition = compose(realm, process="workers")
    finally:
        path.unlink()
    try:
        producers = worker_producers(composition)
        providers = [item for item in producers if isinstance(item, p.ProviderProducer)]
        assert sorted(item.capability for item in providers) == sorted(PROVIDER_CAPABILITIES)
        assert all(item.probe is None for item in providers)
        [models] = [item for item in producers if isinstance(item, p.ModelsProducer)]
        assert models.source is None
        # Every network builder is a recorder that refuses.
        recorded: dict[str, list] = {}

        def recorder(name: str):
            recorded[name] = []

            def refuse(*args, **kwargs):
                recorded[name].append((args, kwargs))
                raise RuntimeError(REFUSED)

            return refuse

        monkeypatch.setattr(identity_providers, "network_transport",
                            recorder("identity_providers.network_transport"))
        monkeypatch.setattr(digest_email, "network_client", recorder("digest_email.network_client"))
        monkeypatch.setattr(notion_session, "network_transport",
                            recorder("notion_session.network_transport"))
        monkeypatch.setattr(model_runtime, "network_transport",
                            recorder("model_runtime.network_transport"))
        now = clock()
        for producer in producers:
            try:
                producer.observe(now)  # no store: nothing is recorded
            except Exception:  # noqa: BLE001 - a producer that raises is passed over
                pass
        assert recorded == {name: [] for name in recorded} and len(recorded) == 4
    finally:
        composition.close()


# --- 8. Producers' error counts and the scheduler pass (Step 59; L1-29, L1-30, L1-41) -----

H = dt.timedelta(hours=1)


class At:
    """An injected clock a test sets to each record's time before it is written."""

    def __init__(self, now: dt.datetime):
        self.now = now

    def __call__(self) -> dt.datetime:
        return self.now


def unread_lines(caplog, event: str = "counts.unread") -> list[dict]:
    from backend.log_events import EVENTS_LOGGER

    lines = [json.loads(record.getMessage()) for record in caplog.records
             if record.name == EVENTS_LOGGER]
    return [line for line in lines if line.get("event") == event]


def backup_request(requests, environment: str, outcome: str) -> str:
    """A scheduled `backup.create` request taken through the machine to `outcome`."""
    request = requests.request(
        origin="schedule", operation="backup.create", environment=environment,
        target_id="docsuri_u8", expected_revision=requests.backup_revision(environment),
        submission_id=uuid4())
    identity = request["recoveryRequestId"]
    requests.admit(identity)
    requests.start(identity)
    if outcome == "succeeded":
        requests.advance(identity, "verifying", allowed_from=("running",))
        requests.advance(identity, "succeeded", allowed_from=("verifying",))
    else:
        requests.advance(identity, "failed", allowed_from=("running",))
    return identity


def version(ledger, kind: str, key: str, **fields) -> None:
    current = ledger.get(kind, key)
    ledger.append(kind, {**current, **fields}, expect_revision=ledger.revision(kind, key))


def agent_ledger(tmp_path, t: dt.datetime, name: str):
    """A component ledger, its recovery requests and copies on one injected clock."""
    from backend.modules.operations.recovery import RecoveryRequests
    from backend.modules.operations.retained_copies import RetainedCopies

    at = At(t)
    folder = tmp_path / name
    folder.mkdir(mode=0o700)
    ledger = Ledger.open(folder, clock=at)
    return (at, ledger, RecoveryRequests(ledger, SYNTHETIC_OPERATIONS, clock=at),
            RetainedCopies(ledger, SYNTHETIC_OPERATIONS, clock=at))


def live_agent_ledger(tmp_path, t: dt.datetime):
    """Step 59(c)'s live ledger: 3 failed writes and disposals of 6 in (t − 24 h, t]."""
    from backend.modules.operations.ledger import utc_text
    from tests.u8_service_operations_integration import recovery_flows as rf

    at, ledger, requests, _ = agent_ledger(tmp_path, t - dt.timedelta(days=30), "live-ledger")
    disposed = rf.set_record(ledger, now=at())  # taken at t − 30 days
    at.now = t - dt.timedelta(days=20)
    stuck = rf.set_record(ledger, now=at())
    at.now = t - 25 * H
    backup_request(requests, "live", "failed")  # outside the window
    at.now = t - 5 * H
    version(ledger, "backup-set", stuck["backupId"], lastDisposalFailedAt=utc_text(at()))
    at.now = t - 3 * H
    facts = rf.receipt(now=at())
    ledger.append("ledger-copy", {  # a lone copy whose chain check failed: no verifiedAt
        "ledgerCopyId": str(uuid4()), "takenAt": utc_text(at()),
        "location": "archives/ledger-copy-lone.archive", "stagingLocation": "staging/lone",
        "digest": "a" * 64, "headSequence": 3, "headDigest": "b" * 64,
        "retainUntil": utc_text(at() + dt.timedelta(days=14)),
        "operatorReceiptRef": facts["receiptId"],
    }, expect_revision=0, receipts=(facts,))
    at.now = t - 2 * H
    succeeded = backup_request(requests, "live", "succeeded")
    rf.set_record(ledger, now=at(), recoveryRequestId=succeeded)
    rf.set_record(ledger, now=at(), trigger="first-live")
    failed = backup_request(requests, "live", "failed")
    rf.set_record(ledger, now=at(), integrity="failed", recoveryRequestId=failed)
    backup_request(requests, "rehearsal", "failed")  # another environment's
    at.now = t - H
    version(ledger, "backup-set", disposed["backupId"], disposedAt=utc_text(at()))
    return ledger


def rehearsal_agent_ledger(tmp_path, t: dt.datetime):
    """Step 59(c)'s rehearsal ledger: 1 failed of 3 with the waiting-set rule, 2 of 4
    without it."""
    from backend.modules.operations.ledger import utc_text
    from tests.u8_service_operations_integration import recovery_flows as rf

    at, ledger, requests, copies = agent_ledger(tmp_path, t - 3 * H, "rehearsal-ledger")
    database = "docsuri_u8_rehearsal_" + uuid4().hex[:8]
    waiting = rf.set_record(ledger, environment="rehearsal", now=at(), database=database)
    snapshot = copies.record("dry-run-snapshot", "run:1", ["backup-volume/archives/snap"])
    version(ledger, "retained-copy", snapshot["copyId"], lastDisposalFailedAt=utc_text(at()))
    rehearsal = copies.record("rehearsal-database", "run:1", [f"database/{database}"])
    at.now = t - 2 * H
    succeeded = backup_request(requests, "rehearsal", "succeeded")
    rf.set_record(ledger, environment="rehearsal", now=at(), recoveryRequestId=succeeded)
    copies.disposed_by_agent(rehearsal["copyId"], f"agent-disposed:database/{database}")
    at.now = t - H
    # Written directly: the disposal pass never writes it for a waiting set (Step 64(i)).
    version(ledger, "backup-set", waiting["backupId"], lastDisposalFailedAt=utc_text(at()))
    return ledger


def test_platform_status_carries_the_agents_status_and_failed_writes(transactions, clock,
                                                                    tmp_path, monkeypatch):
    """Step 59(c) (NFR9.7's backup-agent row)."""
    from docsuri_ops.backup_agent.status import EvidenceStatus

    t = clock() - H  # so the realm's own latest platform.status row stays the newest
    live = live_agent_ledger(tmp_path, t)
    try:
        def producer(inspect, agent=None, ledger=live, environment="live"):
            return p.PlatformStatusProducer(inspect, agent_status=agent, ledger=ledger,
                                            environment=environment,
                                            policy=SYNTHETIC_OPERATIONS)

        passing, degraded = (lambda: {"outcome": "pass"}), (lambda: {"outcome": "degraded"})
        low = lambda: {"available": False, "findings": ["backup-volume-low"]}  # noqa: E731
        healthy = lambda: {"available": True, "findings": []}  # noqa: E731
        cases = [
            (producer(passing, low), ("degraded", "backup-volume-low", ["backup-volume-low"])),
            (producer(degraded, low), ("degraded", "backup-volume-low", ["backup-volume-low"])),
            (producer(passing, healthy), ("available", None, [])),
            (producer(degraded, healthy), ("degraded", "evidence-unavailable", [])),
            (producer(None, healthy), ("unknown", "evidence-unavailable", [])),
            (producer(passing), ("available", None, [])),
            (producer(degraded), ("degraded", "evidence-unavailable", [])),
            (producer(passing, EvidenceStatus(lambda target: None)),
             ("unknown", "evidence-unavailable", [])),
        ]
        for built, expected in cases:
            row = record_once(transactions, built, t)
            assert (row["outcome"], row["reason_key"], list(row["limitation_keys"])) == (
                expected), expected
            assert (row["error_count"], row["total_count"]) == (3, 6), expected
    finally:
        live.close()
    rehearsal = rehearsal_agent_ledger(tmp_path, t)
    try:
        built = p.PlatformStatusProducer(lambda: {"outcome": "pass"},
                                         agent_status=lambda: {"available": True,
                                                               "findings": []},
                                         ledger=rehearsal, environment="rehearsal",
                                         policy=SYNTHETIC_OPERATIONS)
        row = record_once(transactions, built, t)
        assert (row["outcome"], row["error_count"], row["total_count"]) == ("available", 1, 3)
        # Without the waiting-set rule it would be 2 of 4.
        import docsuri_ops.cutover.disposal as disposal

        monkeypatch.setattr(disposal, "waiting_rehearsal_sets", lambda ledger: [])
        assert p.platform_counts(rehearsal, "rehearsal", t, 24 * H) == (2, 4)
        # One closed rule with 운영's standing-job line (retained_copies.CLOSED): a copy
        # whose disposal failed counts while open, and not once retired with its volume.
        from backend.modules.operations.ledger import utc_text
        from backend.modules.operations.retained_copies import RetainedCopies

        at = At(t - H)
        copies = RetainedCopies(rehearsal, SYNTHETIC_OPERATIONS, clock=at)
        retired = copies.record("dry-run-snapshot", "run:2", ["backup-volume/archives/snap-2"])
        version(rehearsal, "retained-copy", retired["copyId"],
                lastDisposalFailedAt=utc_text(at()))
        assert p.platform_counts(rehearsal, "rehearsal", t, 24 * H) == (3, 5)
        copies.retire(retired["copyId"])
        assert p.platform_counts(rehearsal, "rehearsal", t, 24 * H) == (2, 4)
    finally:
        rehearsal.close()


# --- the model jobs' production stand-in (Steps 59(e), (g) and (l)) ----------------------


def model_answer(body: dict) -> httpx.Response:
    """Paper assistance's answer (citing the first allowed anchor) or research's."""
    from tests.u8_service_operations_integration import research_flows as rf

    properties = (body.get("format") or {}).get("properties", {})
    if "citations" in properties:
        anchors = properties["citations"]["items"]["enum"]
        content = json.dumps({"text": f"요약입니다 [{anchors[0]}]", "citations": anchors[:1]},
                             ensure_ascii=False)
        return httpx.Response(200, json={
            "model": body["model"], "message": {"role": "assistant", "content": content},
            "done": True, "done_reason": "stop", "prompt_eval_count": 40, "eval_count": 20})
    return rf.grounded(body)


def cut_off_answer(body: dict) -> httpx.Response:
    """An answer cut at its length: a typed content failure for either kind of job."""
    return httpx.Response(200, json={
        "model": body["model"], "done": True, "done_reason": "length",
        "prompt_eval_count": 900, "eval_count": 1280,
        "message": {"role": "assistant", "content": "{}"}})


def assistance_job(env, owner) -> dict:
    """One accepted paper assistance job through production's own catalog and admission."""
    from backend.modules.summarization.guarded_repository import GuardedAssistanceRepository
    from backend.modules.summarization.requests import AssistanceRequests
    from tests.u8_service_operations_integration import research_flows as rf
    from tests.u8_service_operations_integration.host_flows import import_paper

    corpus = env.parts["paper-corpus"]
    ref = import_paper(env.standin, rf.PAPER_CHUNKS)
    source = corpus["corpus_repository"].read(ref["versionId"])
    catalog = corpus["assistance_rule"].catalog(source)
    option = catalog.options()["options"][0]
    glossary = GuardedAssistanceRepository(env.standin.transactions, corpus["files"]
                                           ).current_glossary(owner)["revision"]
    requests = AssistanceRequests(corpus["dispatch"].admission, corpus["corpus_repository"],
                                  corpus["assistance_rule"].catalog)
    return requests.submit(owner, uuid4(), {
        "paper": catalog.paper, "contentRevision": catalog.content_revision,
        "contentHash": source["source_hash"], "operation": option["operation"],
        "optionId": option["optionId"], "optionsRevision": catalog.revision,
        "glossaryRevision": str(glossary), "processingPolicy": catalog.options()["policy"],
    })


def assistance_state(env, job_id) -> str:
    with env.standin.connect("assistance") as conn:
        return conn.execute("SELECT state FROM assistance.job WHERE id=%s",
                            (job_id,)).fetchone()["state"]


@pytest.fixture(scope="module")
def model_jobs(realm):
    """The production stand-in whose model jobs ran once through their owners' own paths,
    the model stand-in scripted to fail some: a research turn that failed first, a failed
    and a succeeded turn, a cancelled novelty analysis, and a failed and a succeeded
    assistance job. `now` is 24 hours and 1 µs after the first failure's `updated_at`."""
    from types import SimpleNamespace

    from tests.u8_service_operations_integration import research_flows as rf

    with rf.production_research(realm) as env:
        env.model.chat = model_answer

        def turn(chat) -> str:
            owner = rf.member(env)
            accepted = rf.accept_turn(env, owner, rf.paper_scope(env, owner))
            env.model.chat = chat
            try:
                outcome = rf.run_next(env)
            finally:
                env.model.chat = model_answer
            assert rf.job_row(env, accepted["jobId"])["state"] == outcome
            return accepted["jobId"]

        first = turn(cut_off_answer)
        turn(cut_off_answer)
        turn(model_answer)
        owner = rf.member(env)
        analysis = rf.accept_analysis(env, owner, rf.paper_scope(env, owner, purpose="novelty"))
        row = rf.job_row(env, analysis["jobId"])
        env.service.jobs.cancel(owner, row["id"], row["context_id"], row["revision"])
        assert env.execution.step()["cancelled"] == 1
        dispatch = env.parts["paper-corpus"]["dispatch"]
        for chat, expected in ((cut_off_answer, "failed"), (model_answer, "succeeded")):
            job = assistance_job(env, rf.member(env))
            env.model.chat = chat
            try:
                dispatch.run_once(limit=1)
            finally:
                env.model.chat = model_answer
            assert assistance_state(env, job["id"]) == expected
        first_failed = rf.job_row(env, first)
        assert first_failed["state"] == "failed"
        now = first_failed["updated_at"] + dt.timedelta(hours=24, microseconds=1)
        yield SimpleNamespace(env=env, now=now, transactions=env.standin.transactions,
                              store=env.store)


def test_provider_models_counts_failed_model_jobs_over_24_hours(model_jobs):
    """Step 59(e): 2 of 5 on every outcome; the cancelled analysis in the total only, the
    first failure left out."""
    from docsuri_ops.local_models import MODEL_PINS

    env, now = model_jobs.env, model_jobs.now
    lanes = p.LaneCounts(model_jobs.transactions, SYNTHETIC_OPERATIONS)

    def observed(source) -> p.Observed:
        return p.ModelsProducer(source, SYNTHETIC_OPERATIONS, lane_counts=lanes).observe(now)

    source = p.OllamaTags(transport=env.model.factory())
    available = observed(source)
    assert (available.outcome, available.error_count, available.total_count) == (
        "available", 2, 5)
    env.model.down = httpx.ConnectError("the runtime is stopped")
    try:
        down = observed(p.OllamaTags(transport=env.model.factory()))
    finally:
        env.model.down = None
    assert (down.outcome, down.reason, down.error_count, down.total_count) == (
        "unavailable", "runtime-unreachable", 2, 5)
    unknown = observed(None)
    assert (unknown.outcome, unknown.error_count, unknown.total_count) == ("unknown", 2, 5)
    name = next(iter(MODEL_PINS))
    env.model.digests = {**MODEL_PINS, name: "0" * 64}
    try:
        mismatch = observed(p.OllamaTags(transport=env.model.factory()))
    finally:
        env.model.digests = dict(MODEL_PINS)
    assert (mismatch.outcome, mismatch.reason, mismatch.error_count,
            mismatch.total_count) == ("unavailable", "model-evidence-mismatch", 2, 5)
    observations = KeptObservations(model_jobs.store)
    schedule = p.ProducerSchedule(
        [p.ModelsProducer(None, SYNTHETIC_OPERATIONS, lane_counts=lanes)], observations,
        SYNTHETIC_OPERATIONS, lambda: now)
    assert schedule.run_due(now) == ["provider.models"]
    row = stored_row(model_jobs.transactions, observations.rows[-1].id)
    assert (row["error_count"], row["total_count"]) == (2, 5)


def availability_line(record, at: dt.datetime, reason: str) -> None:
    assert record.append(at, reason == "ok", reason) is True


def test_operations_cutover_counts_failed_heartbeat_probes(tmp_path, component):
    """Step 59(f) (L1-30): 2 of 9 on every outcome, across two Seoul month files, the
    first line per slot kept."""
    from docsuri_ops.standing.availability import AvailabilityRecord

    now = dt.datetime(2026, 10, 31, 15, 30, tzinfo=dt.UTC)  # 00:30 on 1 November in Seoul
    folder = tmp_path / "availability"
    record = AvailabilityRecord(folder)
    reasons = ["ok", "maintenance", "public-not-ready", "local-unreachable",
               "local-not-ready", "local-timeout", "probe-timeout", "public-unreachable",
               "public-timeout"]
    # Six slots in October's file (before 15:00Z, Seoul's midnight), three in November's.
    slots = [now - dt.timedelta(hours=hours) for hours in (20, 16, 12, 8, 4, 1)]
    slots += [now - dt.timedelta(minutes=minutes) for minutes in (25, 15, 5)]
    for at, reason in zip(slots, reasons, strict=True):
        availability_line(record, at, reason)
    availability_line(record, dt.datetime(2026, 10, 30, 15, 25, tzinfo=dt.UTC),
                      "public-unreachable")  # outside the 24 hours
    # A second, raw line for the `ok` slot: the first line per slot is kept.
    with open(folder / "2026-10.jsonl", "a") as stream:
        stream.write(json.dumps({"slot": slots[0].strftime("%Y-%m-%dT%H:%M:%SZ"),
                                 "up": False, "reason": "public-unreachable"}) + "\n")
    assert sorted(path.name for path in folder.iterdir()) == ["2026-10.jsonl", "2026-11.jsonl"]

    def counted(producer) -> tuple:
        observed = producer.observe(now)
        return observed.outcome, observed.reason, observed.error_count, observed.total_count

    assert counted(p.CutoverProducer(component, None, availability=folder)) == (
        "available", None, 2, 9)
    component.append("cutover-record", {
        "cutoverId": str(uuid4()), "releaseTag": "v2.0.0", "state": "preparing",
        "soakPeriodSeconds": 604800, "soakClean": False, "switchTimeBoundSeconds": 14400,
        "rollbackWindowSeconds": 1209600, "effectReceipts": [], "approvals": [],
    }, expect_revision=0)
    assert counted(p.CutoverProducer(component, None, availability=folder)) == (
        "unknown", "evidence-unavailable", 2, 9)
    assert counted(p.CutoverProducer(component, lambda: {"route": "v2-host"},
                                     availability=folder)) == (
        "unavailable", "cutover-route-differs", 2, 9)
    assert counted(p.CutoverProducer(component, lambda: {"route": "v1-web",
                                                         "unknownEffects": 1},
                                     availability=folder)) == (
        "unavailable", "cutover-effect-unknown", 2, 9)


def loop_statuses():
    """A control loop status the test moves: available, then behind its deadline."""
    status = {"state": "idle", "timeouts": 0}
    return status, (lambda: dict(status))


def test_background_work_counts_failed_jobs_per_lane_over_24_hours(model_jobs):
    """Step 59(g) (L1-41): per-lane counts and their sum, the first failure left out."""
    from tests.u6_approved_export import export_rows

    env, now, transactions = model_jobs.env, model_jobs.now, model_jobs.transactions
    lanes = p.LaneCounts(transactions, SYNTHETIC_OPERATIONS)
    assert lanes.read(now) == {"research": (1, 3), "assistance": (1, 2), "topics": (0, 0),
                               "export": (0, 0), "corpus": (0, 0), "lifecycle": (0, 0)}
    status, reader = loop_statuses()
    models = p.ModelsProducer(None, SYNTHETIC_OPERATIONS, lane_counts=lanes).observe(now)
    unknown = p.BackgroundWorkProducer(None, lane_counts=lanes).observe(now)
    assert (unknown.outcome, unknown.error_count, unknown.total_count) == ("unknown", 2, 5)
    loop = p.BackgroundWorkProducer(reader, lane_counts=lanes)
    observations = KeptObservations(model_jobs.store)
    schedule = p.ProducerSchedule([loop], observations, SYNTHETIC_OPERATIONS, lambda: now)
    assert schedule.run_due(now) == ["background.work"]
    row = stored_row(transactions, observations.rows[-1].id)
    assert (row["outcome"], row["error_count"], row["total_count"]) == ("available", 2, 5)
    assert (row["error_count"], row["total_count"]) == (models.error_count,
                                                        models.total_count)
    status["timeouts"] = 1
    behind = loop.observe(now)
    assert (behind.outcome, behind.reason, behind.error_count, behind.total_count) == (
        "degraded", "lane-behind-deadline", 2, 5)

    # One failure and one terminal success in each of topics, export and corpus, written
    # through their owners' logins inside the window (after the first failure).
    member = env.standin
    with member.connect("topics", autocommit=True) as conn:
        topic = uuid4()
        conn.execute("INSERT INTO topics.followed_topic(id,account_id,topic_key,display_name)"
                     " VALUES(%s,%s,'counts-topic','Counts topic')", (topic, uuid4()))
        conn.execute("INSERT INTO topics.digest_settings(id,topic_id,cadence,"
                     "delivery_time_local,delivery_day,content_window_days) "
                     "VALUES(%s,%s,'daily','09:00',NULL,7)", (uuid4(), topic))
        # Each run starts prepared and moves as the digest machine allows.
        for state, day in (("failed", "2026-11-01"), ("sent", "2026-11-02")):
            run = uuid4()
            conn.execute(
                "INSERT INTO topics.digest_run(id,topic_id,window_start,window_end,state,"
                "digest_content,settings_revision) VALUES(%s,%s,%s,%s,'prepared',"
                "'[{\"paperId\": \"counts\"}]'::jsonb,1)", (run, topic, day, day))
            for step in ("sending", state):
                conn.execute("UPDATE topics.digest_run SET state=%s,"
                             "updated_at=clock_timestamp() WHERE id=%s", (step, run))
    # One transaction, so the deferred attempt check sees the claim's attempt.
    with member.connect("export") as conn:
        failed = export_rows.exported(conn)["effect"]
        conn.execute("UPDATE export.effect SET state='failed',revision=revision+1,"
                     "ended_at=clock_timestamp(),outcome_reason='dependency-unavailable' "
                     "WHERE id=%s", (failed,))
        done = export_rows.exported(conn)["effect"]
        export_rows.claim(conn, done)  # accepted -> executing with its attempt
        conn.execute("UPDATE export.effect SET state='succeeded',revision=revision+1,"
                     "ended_at=clock_timestamp(),remote_reference='page-1',"
                     "settled_by='reconciliation' WHERE id=%s", (done,))
    with member.connect("corpus", autocommit=True) as conn:
        for state in ("failed", "completed"):
            conn.execute(
                "INSERT INTO corpus.run(id,operation,source_scope,source_policy,"
                "compatibility_revision,authoritative_input_revision,input_manifest_hash,"
                "intent_hash,idempotency_key,state,completed_at) VALUES(%s,'ingest',"
                "'[\"counts\"]'::jsonb,'{}'::jsonb,'counts','counts',%s,%s,%s,%s,"
                "clock_timestamp())",
                (uuid4(), "a" * 64, "b" * 64, uuid4(), state))
    after = lanes.read(now)
    assert {lane: after[lane] for lane in ("topics", "export", "corpus")} == {
        "topics": (1, 2), "export": (1, 2), "corpus": (1, 2)}
    assert (after["research"], after["assistance"]) == ((1, 3), (1, 2))

    # One lifecycle request with three scopes: complete, blocked at 3 attempts, and
    # pending at 3 attempts with its last lease ended inside the window.
    from tests.u8_service_operations_integration import research_flows as rf

    owner = rf.member(env)
    request = uuid4()
    with member.connect("accounts", autocommit=True) as conn:
        conn.execute(
            "INSERT INTO accounts.lifecycle_request(id,account_id,revision,action,policy_ref,"
            "manifest_revision,manifest,disposition,reason_key) VALUES(%s,%s,%s,'withdraw',"
            "'{}'::jsonb,'counts-test',%s,'pending','pending')",
            (request, owner.account_id, uuid4(),
             json.dumps([["ApprovedExport", "live_records"], ["ApprovedExport", "pending_work"],
                         ["ApprovedExport", "external_copies"]])))
        conn.execute(
            "INSERT INTO accounts.lifecycle_scope(request_id,participant,scope,generation,"
            "attempts,disposition,evidence_ref,reason_key) VALUES"
            "(%s,'ApprovedExport','live_records',1,1,'complete',%s,'complete'),"
            "(%s,'ApprovedExport','pending_work',1,3,'blocked',NULL,'pending'),"
            "(%s,'ApprovedExport','external_copies',1,3,'pending',NULL,'pending')",
            (request, uuid4(), request, request))
        conn.execute("UPDATE accounts.lifecycle_scope SET lease_until=clock_timestamp() "
                     "WHERE request_id=%s AND scope='external_copies'", (request,))
    assert lanes.read(now, lanes=("lifecycle",)) == {"lifecycle": (2, 3)}
    with member.connect("accounts", autocommit=True) as conn:
        conn.execute("UPDATE accounts.lifecycle_scope SET lease_until=%s "
                     "WHERE request_id=%s AND scope='external_copies'", (now + H, request))
    assert lanes.read(now, lanes=("lifecycle",)) == {"lifecycle": (1, 2)}


def test_background_work_degrades_when_the_scheduler_misses_its_pass(tmp_path, caplog):
    """Step 59(g) (L1-41, L1-68): the pass file and its check on the wall clock."""
    import logging

    from backend.log_events import EVENTS_LOGGER
    from backend.u8_host import record_scheduler_pass

    w0 = dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.UTC)
    folder = tmp_path / "evidence"
    folder.mkdir(mode=0o700)
    p.write_scheduler_pass(folder, w0)
    path = folder / p.SCHEDULER_PASS_FILE
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert json.loads(path.read_text()) == {"passedAt": "2026-11-10T12:00:00Z"}
    assert p.read_scheduler_pass(folder) == w0
    linked = tmp_path / "linked"
    linked.mkdir(mode=0o700)
    os.symlink(tmp_path / "elsewhere.json", linked / p.SCHEDULER_PASS_FILE)
    with pytest.raises(ValueError):
        p.write_scheduler_pass(linked, w0)
    assert p.read_scheduler_pass(linked) is None
    # record_scheduler_pass: a missing folder made at 0700; a link refused and logged.
    missing = tmp_path / "missing"
    assert record_scheduler_pass(missing, wall_clock=lambda: w0) is True
    assert os.stat(missing).st_mode & 0o777 == 0o700
    assert p.read_scheduler_pass(missing) == w0
    folder_link = tmp_path / "folder-link"
    os.symlink(missing, folder_link)
    with caplog.at_level(logging.INFO, logger=EVENTS_LOGGER):
        for target in (linked, folder_link):
            caplog.clear()
            before = sorted(item.name for item in missing.iterdir())
            assert record_scheduler_pass(target, wall_clock=lambda: w0 + H) is False
            assert len(unread_lines(caplog, "pass.unrecorded")) == 1
            assert unread_lines(caplog, "pass.unrecorded")[0]["component"] == "scheduler"
            assert sorted(item.name for item in missing.iterdir()) == before
    assert p.read_scheduler_pass(missing) == w0  # changed nothing
    assert os.path.islink(linked / p.SCHEDULER_PASS_FILE)

    def producer(passed, status=None):
        wall = At(w0)
        built = p.BackgroundWorkProducer(status or (lambda: {"state": "idle", "timeouts": 0}),
                                         wall_clock=wall, scheduler_pass=lambda: passed[0])
        assert built.observe(w0).outcome in ("available", "degraded", "unknown")
        return built, wall

    def at(built, wall, seconds, now=None):
        wall.now = w0 + dt.timedelta(seconds=seconds)
        observed = built.observe(now or wall.now)
        return observed.outcome, observed.reason

    passed = [w0 + dt.timedelta(seconds=110)]
    built, wall = producer(passed)
    assert at(built, wall, 200) == ("available", None)  # a pass 90 s old
    passed[0] = w0 + dt.timedelta(seconds=109)
    assert at(built, wall, 200) == ("degraded", "lane-behind-deadline")  # 91 s old
    none = [None]
    built, wall = producer(none)
    assert at(built, wall, 90) == ("available", None)
    assert at(built, wall, 91) == ("unknown", "scheduler-pass-unrecorded")
    malformed = tmp_path / "malformed"
    malformed.mkdir(mode=0o700)
    (malformed / p.SCHEDULER_PASS_FILE).write_text('{"passedAt": 1}')
    assert p.read_scheduler_pass(malformed) is None
    (malformed / p.SCHEDULER_PASS_FILE).write_text("not json")
    assert p.read_scheduler_pass(malformed) is None
    old = [w0 - dt.timedelta(days=1)]
    built, wall = producer(old)
    assert at(built, wall, 90) == ("available", None)
    assert at(built, wall, 91) == ("degraded", "lane-behind-deadline")
    # The producer's `now` a day ahead of the wall clock (a journey moved the fixture
    # clock), with a fresh pass on the wall clock: available.
    fresh = [w0 + dt.timedelta(seconds=150)]
    built, wall = producer(fresh)
    assert at(built, wall, 200, now=w0 + dt.timedelta(days=1)) == ("available", None)
    # A degraded or unknown outcome of the loop stands whatever the pass.
    for status, expected in (({"state": "deadline"}, ("degraded", "lane-behind-deadline")),
                             ({"state": "stopped"}, ("unknown", "evidence-unavailable"))):
        built, wall = producer([w0], status=lambda value=status: dict(value))
        assert at(built, wall, 300) == expected
    # A producer built without a pass reader stays as built.
    plain = p.BackgroundWorkProducer(lambda: {"state": "idle", "timeouts": 0},
                                     wall_clock=At(w0 + dt.timedelta(days=3)))
    assert plain.observe(w0).outcome == "available"


def postgresql_lines(folder, process: str, moment: dt.datetime, failed: int,
                     total: int) -> None:
    from backend.u8_counts import ProcessCounts

    counts = ProcessCounts(folder, process, policy=SYNTHETIC_OPERATIONS, clock=lambda: moment)
    for index in range(total):
        counts.record("postgresql.connection", failed=index < failed)
    counts.close()


def test_storage_capacity_carries_failed_connections_and_transactions(transactions,
                                                                      tmp_path, clock):
    """Step 59(h) (L1-29): 2 of 50 on every outcome; a line 25 hours old left out."""
    from backend.u8_host import POSTGRESQL_KINDS, counts_reader

    now = dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.UTC)
    folder = tmp_path / "evidence"
    postgresql_lines(folder, "host", now - dt.timedelta(minutes=30), 1, 30)
    postgresql_lines(folder, "workers", now - 2 * H, 1, 20)
    postgresql_lines(folder, "workers", now - 25 * H, 5, 5)
    reader = counts_reader(folder, POSTGRESQL_KINDS)
    plenty = 100 * GIB
    for footprint, outcome, reason in (
        (GIB, "available", None),
        (int(8 * GIB * 0.8), "degraded", "capacity-approaching"),
        (8 * GIB - 256 * 1024**2, "unavailable", "capacity-exhausted"),
    ):
        observed = capacity(transactions, tmp_path, footprint=footprint, free=plenty,
                            counts=reader).observe(now)
        assert (observed.outcome, observed.reason, observed.error_count,
                observed.total_count) == (outcome, reason, 2, 50)


class RaiseOnly:
    """A count source that raises on every read."""

    def read(self, *args, **kwargs):
        raise RuntimeError("an owner login is busy")

    def __call__(self, *args, **kwargs):
        raise RuntimeError("an unreadable count file")


def test_a_failed_count_read_leaves_each_outcome(transactions, clock, tmp_path, caplog):
    """Step 59(k) (Step 58(i)): a count never changes an outcome."""
    import logging

    from backend.log_events import EVENTS_LOGGER

    t = clock() - H

    def recorded(producer, expected, capability):
        caplog.clear()
        row = record_once(transactions, producer, t)
        assert (row["outcome"], row["reason_key"]) == expected, capability
        assert (row["error_count"], row["total_count"]) == (0, 0)
        lines = unread_lines(caplog)
        assert len(lines) == 1 and lines[0]["state"] == capability
        assert lines[0]["component"] == "operations"

    with caplog.at_level(logging.WARNING, logger=EVENTS_LOGGER):
        status, reader = loop_statuses()
        loop = p.BackgroundWorkProducer(reader, lane_counts=RaiseOnly())
        recorded(loop, ("available", None), "background.work")
        status["timeouts"] = 1
        recorded(loop, ("degraded", "lane-behind-deadline"), "background.work")
        for footprint, expected in ((GIB, ("available", None)),
                                    (int(8 * GIB * 0.8),
                                     ("degraded", "capacity-approaching"))):
            recorded(capacity(transactions, tmp_path, footprint=footprint, free=100 * GIB,
                              counts=RaiseOnly()), expected, "storage.capacity")
        for tags, expected in ((pinned(), ("available", None)),
                               (pinned(**{"qwen3:8b": "0" * 64}),
                                ("unavailable", "model-evidence-mismatch"))):
            recorded(p.ModelsProducer(RecordedTags(tags), SYNTHETIC_OPERATIONS,
                                      lane_counts=RaiseOnly()), expected, "provider.models")
        caplog.clear()
        lanes = p.LaneCounts(transactions, SYNTHETIC_OPERATIONS)

        def raise_only(now, since):
            raise RuntimeError("export.status_counts failed")

        lanes._export = raise_only
        answered = lanes.read(clock())
        assert answered["export"] is None
        assert all(answered[lane] is not None for lane in p.LANES if lane != "export")
        lines = unread_lines(caplog)
        assert len(lines) == 1 and lines[0]["state"] == "export"


def test_background_work_degrades_when_the_account_mail_sender_stops(
    transactions, connect, sign_in_account, own_address, empty_outbox, tmp_path, caplog,
    model_jobs,
):
    """Step 59(l) (Step 53(h), L1-69, L1-70): the sender's beat on the wall clock, and its
    failed runs on background.work's figure."""
    import logging

    from backend.log_events import EVENTS_LOGGER
    from backend.modules.accounts.integrations.account_mail import LocalAccountMail
    from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
    from backend.modules.accounts.u8_entry import CompleteControlEntryService
    from backend.modules.accounts.u8_mail_outbox import beat_reader
    from backend.modules.operations.allowance import LedgerAllowance
    from backend.u8_counts import ProcessCounts
    from backend.u8_host import counts_reader
    from tests.u8_service_operations_integration.conftest import Clock

    w0 = dt.datetime(2026, 11, 10, 12, 0, tzinfo=dt.UTC)

    def producer(beat, status=None, **options):
        wall = At(w0)
        calls = []

        def read():
            calls.append(True)
            if isinstance(beat[0], Exception):
                raise beat[0]
            return beat[0]

        built = p.BackgroundWorkProducer(status or (lambda: {"state": "idle", "timeouts": 0}),
                                         sender_beat=read, wall_clock=wall, **options)
        built.observe(w0)
        return built, wall, calls

    def at(built, wall, seconds, now=None):
        wall.now = w0 + dt.timedelta(seconds=seconds)
        observed = built.observe(now or wall.now)
        return observed.outcome, observed.reason

    beat = [w0 + dt.timedelta(seconds=110)]
    built, wall, _ = producer(beat)
    assert at(built, wall, 200) == ("available", None)  # a beat 90 s old
    beat[0] = w0 + dt.timedelta(seconds=109)
    assert at(built, wall, 200) == ("degraded", "lane-behind-deadline")
    built, wall, _ = producer([w0 - dt.timedelta(days=1)])
    assert at(built, wall, 90) == ("available", None)
    assert at(built, wall, 91) == ("degraded", "lane-behind-deadline")
    built, wall, _ = producer([None])
    assert at(built, wall, 500) == ("available", None)
    with caplog.at_level(logging.WARNING, logger=EVENTS_LOGGER):
        caplog.clear()
        built, wall, _ = producer([RuntimeError("the accounts login is busy")])
        assert at(built, wall, 100) == ("available", None)
        assert at(built, wall, 200) == ("available", None)
        lines = unread_lines(caplog, "sender.unread")
        assert len(lines) == 1 and lines[0]["component"] == "operations"
    built, wall, _ = producer([w0 + dt.timedelta(seconds=91)], scheduler_pass=lambda: None)
    assert at(built, wall, 91) == ("unknown", "scheduler-pass-unrecorded")
    for status, expected in (({"state": "deadline"}, ("degraded", "lane-behind-deadline")),
                             ({"state": "stopped"}, ("unknown", "evidence-unavailable"))):
        built, wall, calls = producer([w0], status=lambda value=status: dict(value))
        calls.clear()
        assert at(built, wall, 300) == expected
        assert calls == []  # the beat reader is not called
    built, wall, _ = producer([w0 + dt.timedelta(seconds=150)])
    assert at(built, wall, 200, now=w0 + dt.timedelta(days=1)) == ("available", None)

    # Over the realm: the outbox module's beat reader reads only the beat row.
    read_beat = beat_reader(transactions)
    assert read_beat() is None
    _, email = sign_in_account("sign-in-member")
    # Step 54(k)'s entry, on a past minute of the test's own (D2's limits unshared).
    entry_clock = Clock(dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
                        + dt.timedelta(minutes=uuid4().int % (300 * 24 * 60)))
    w = entry_clock() + dt.timedelta(days=1)
    try:
        with connect("accounts", autocommit=True) as conn:
            conn.execute("INSERT INTO accounts.mail_sender_beat(singleton,beat_at) "
                         "VALUES(true,%s) ON CONFLICT (singleton) DO UPDATE SET "
                         "beat_at=excluded.beat_at", (w,))
        assert read_beat() == w
        wall = At(w - dt.timedelta(seconds=200))
        real = p.BackgroundWorkProducer(lambda: {"state": "idle", "timeouts": 0},
                                        sender_beat=read_beat, wall_clock=wall)
        assert real.observe(wall.now).outcome == "available"  # the first observation
        wall.now = w
        assert real.observe(w).outcome == "available"
        folder = tmp_path / "operations-ledger"
        folder.mkdir(mode=0o700)
        ledger = Ledger.open(folder, clock=entry_clock)
        try:
            entry = CompleteControlEntryService(transactions, U8_SYNTHETIC_POLICY,
                                                clock=entry_clock)
            entry.account_mail = LocalAccountMail(
                entry.mail, allowance=LedgerAllowance(ledger, SYNTHETIC_OPERATIONS))
            operation = uuid4()
            assert entry.request_password_reset(operation, email, "flow-" + uuid4().hex) == (
                entry._ack(operation))
        finally:
            ledger.close()
        assert read_beat() == w
        assert real.observe(w).outcome == "available"
    finally:
        with connect("accounts", autocommit=True) as conn:
            conn.execute("DELETE FROM accounts.mail_sender_beat")

    # Your answer of 2026-11-08 (L1-70): the sender's failed runs join the lanes' sum.
    now = model_jobs.now
    lanes = p.LaneCounts(model_jobs.transactions, SYNTHETIC_OPERATIONS)
    evidence = tmp_path / "evidence"
    for moment in (now - H, now - 2 * H, now - 25 * H):
        counts = ProcessCounts(evidence, "host", policy=SYNTHETIC_OPERATIONS,
                               clock=lambda moment=moment: moment)
        counts.record("mail.sender", failed=True)
        counts.close()
    sender = counts_reader(evidence, ("mail.sender",))
    assert sender(now) == (2, 2)
    failed, terminal = p.lane_sum(lanes.read(now))
    status, reader = loop_statuses()
    loop = p.BackgroundWorkProducer(reader, lane_counts=lanes, sender_counts=sender)
    observations = KeptObservations(model_jobs.store)
    schedule = p.ProducerSchedule([loop], observations, SYNTHETIC_OPERATIONS, lambda: now)
    assert schedule.run_due(now) == ["background.work"]
    row = stored_row(model_jobs.transactions, observations.rows[-1].id)
    assert (row["outcome"], row["error_count"], row["total_count"]) == (
        "available", failed + 2, terminal + 2)
    status["timeouts"] = 1
    schedule = p.ProducerSchedule([loop], observations, SYNTHETIC_OPERATIONS, lambda: now)
    assert schedule.run_due(now) == ["background.work"]
    row = stored_row(model_jobs.transactions, observations.rows[-1].id)
    assert (row["outcome"], row["reason_key"], row["error_count"], row["total_count"]) == (
        "degraded", "lane-behind-deadline", failed + 2, terminal + 2)
    with caplog.at_level(logging.WARNING, logger=EVENTS_LOGGER):
        caplog.clear()
        raising = p.BackgroundWorkProducer(reader, lane_counts=lanes,
                                           sender_counts=RaiseOnly())
        schedule = p.ProducerSchedule([raising], observations, SYNTHETIC_OPERATIONS,
                                      lambda: now)
        assert schedule.run_due(now) == ["background.work"]
        row = stored_row(model_jobs.transactions, observations.rows[-1].id)
        assert (row["outcome"], row["error_count"], row["total_count"]) == (
            "available", failed, terminal)
        lines = unread_lines(caplog)
        assert len(lines) == 1 and lines[0]["state"] == "background.work"
