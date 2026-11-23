"""Admitting and recording capability observations (U8 plan Step 16; BR3.4, O1).

Admitted rows are written to the realm's observation store as the operations owner.
The store-outage cases use a store that refuses every insert and every read, standing in
for the database being down, or the realm's store whose seed read fails while its inserts
reach the realm; nothing else is replaced.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import secrets
from uuid import uuid4

import pytest

from backend.modules.operations.observation_store import ObservationStore
from backend.modules.operations.observations import (
    BUFFER,
    ObservationRefused,
    Observations,
    registered_limitations,
    registered_reasons,
)
from backend.modules.operations.producers import (
    ExportProducer,
    OwnerProbe,
    ProducerSchedule,
)
from backend.u8_policy import SYNTHETIC_OPERATIONS
from backend.u8_registry import CAPABILITY_BY_ID


class DownStore:
    """The observation store while the database does not answer."""

    def __init__(self):
        self.attempts = 0

    def insert(self, rows):
        self.attempts += 1
        raise ConnectionError("store unavailable")

    def latest(self, capabilities):
        self.attempts += 1
        raise ConnectionError("store unavailable")


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def test_a_wrong_producer_an_unregistered_key_and_free_text_are_refused(transactions):
    observations = Observations(ObservationStore(transactions))
    cases = [
        (dict(capability="export", producer="topics", outcome="available"),
         "producer-differs"),
        (dict(capability="export", producer="export", outcome="degraded",
              reason="capacity-exhausted"), "reason-unregistered"),
        (dict(capability="export", producer="export", outcome="degraded",
              reason="export-effect-late", limitations=("semantic-search-unavailable",)),
         "limitation-unregistered"),
        (dict(capability="not.registered", producer="export", outcome="available"),
         "capability-unregistered"),
        (dict(capability="export", producer="export", outcome="fine"), "value-form"),
        (dict(capability="export", producer="export", outcome="degraded",
              reason="Paper title with spaces"), "reason-unregistered"),
        (dict(capability="export", producer="export", outcome="degraded",
              reason="person@example.com"), "reason-unregistered"),
        (dict(capability="export", producer="export", outcome="available",
              error_count=3, total_count=1), "value-form"),
    ]
    for values, category in cases:
        with pytest.raises(ObservationRefused) as refused:
            observations.make(observed_at=now(), **values)
        assert refused.value.category == category
        assert "example.com" not in str(refused.value) and "title" not in str(refused.value)
    row = observations.make("export", "export", "degraded", observed_at=now(),
                            reason="export-effect-late", limitations=("export-effect-late",),
                            error_count=1, total_count=4)
    assert observations.record("export", [row]) == {"written": 1, "buffered": 0, "dropped": 0}
    stored = transactions.run("operations", lambda conn: conn.execute(
        "SELECT * FROM operations.observation_record WHERE id=%s", (row.id,)).fetchone())
    assert (stored["outcome"], stored["reason_key"], stored["error_count"]) == (
        "degraded", "export-effect-late", 1)


def test_the_registered_keys_come_from_the_registry():
    isolation = CAPABILITY_BY_ID["platform.isolation"]
    assert "isolation-filter" in registered_limitations(isolation)
    assert "runtime-isolation-lapsed" in registered_reasons(isolation)
    assert "producer-failed" in registered_reasons(CAPABILITY_BY_ID["export"])
    assert "isolation-filter" not in registered_limitations(CAPABILITY_BY_ID["export"])


def test_the_61st_buffered_observation_drops_the_oldest_and_counts_it(transactions):
    store = DownStore()
    observations = Observations(store)
    # Times in the past, so the realm's latest export observation stays the newest.
    start = now() - dt.timedelta(hours=1)
    rows = [
        observations.make("export", "export", "available",
                          observed_at=start + dt.timedelta(seconds=index))
        for index in range(BUFFER + 1)
    ]
    for row in rows[:BUFFER]:
        result = observations.record("export", [row])
    assert result == {"written": 0, "buffered": BUFFER, "dropped": 0}
    result = observations.record("export", [rows[BUFFER]])
    assert result == {"written": 0, "buffered": BUFFER, "dropped": 1}
    buffered = list(observations.buffers["export"].items)
    assert buffered[0] is rows[1] and buffered[-1] is rows[BUFFER]
    assert observations.missing() == {"export": 1}
    # The store answers again: the whole buffer is written with the next record.
    observations.store = ObservationStore(transactions)
    later = observations.make("export", "export", "available",
                              observed_at=start + dt.timedelta(seconds=BUFFER + 1))
    # The 60 buffered rows and the new one, in inserts of at most 60 (Step 58(a)).
    assert observations.record("export", [later]) == {"written": 61, "buffered": 0,
                                                      "dropped": 1}


class CommitThenUnknown:
    """The real store, whose first `unknown` inserts commit and then lose their
    connection: the owner's transactions raise `UnknownCommit` although the rows are
    written."""

    def __init__(self, transactions, unknown: int = 1):
        self.inner, self.unknown, self.calls = ObservationStore(transactions), unknown, 0

    def insert(self, rows):
        from backend.transactions import UnknownCommit

        self.calls += 1
        written = self.inner.insert(rows)
        if self.unknown:
            self.unknown -= 1
            raise UnknownCommit("commit outcome unknown")
        return written

    def latest(self, capabilities):
        return self.inner.latest(capabilities)


def stored_rows(transactions, ids) -> list[dict]:
    return transactions.run("operations", lambda conn: conn.execute(
        "SELECT id,dropped_count FROM operations.observation_record WHERE id=ANY(%s)",
        (list(ids),)).fetchall())


def test_a_commit_whose_outcome_is_unknown_drops_nothing_and_blocks_nothing(transactions):
    store = CommitThenUnknown(transactions)
    observations = Observations(store)
    start = now() - dt.timedelta(hours=1)
    first = observations.make("export", "export", "available", observed_at=start)
    # Committed, but reported as unknown: the same row is written once more at once,
    # and the store skips the id it already holds.
    assert observations.record("export", [first]) == {"written": 1, "buffered": 0,
                                                      "dropped": 0}
    assert (store.unknown, store.calls) == (0, 2)
    second = observations.make("export", "export", "available",
                               observed_at=start + dt.timedelta(seconds=1))
    assert observations.record("export", [second]) == {"written": 1, "buffered": 0,
                                                       "dropped": 0}
    assert observations.missing() == {}
    rows = stored_rows(transactions, [first.id, second.id])
    assert sorted(str(row["id"]) for row in rows) == sorted([str(first.id), str(second.id)])
    assert {row["dropped_count"] for row in rows} == {0}


def test_an_unknown_commit_on_a_full_buffer_counts_no_stored_row_as_dropped(transactions):
    """The store refused for 60 renewals; the next record's first chunk of 60 commits
    and reports an unknown outcome. Its rows are written again before any trim, so the
    oldest is neither lost nor counted as dropped."""
    observations = Observations(DownStore())
    start = now() - dt.timedelta(hours=1)
    rows = [observations.make("export", "export", "available",
                              observed_at=start + dt.timedelta(seconds=index))
            for index in range(BUFFER + 1)]
    for row in rows[:BUFFER]:
        observations.record("export", [row])
    store = CommitThenUnknown(transactions)
    observations.store = store
    assert observations.record("export", [rows[BUFFER]]) == {
        "written": BUFFER + 1, "buffered": 0, "dropped": 0}
    # The first chunk twice (the unknown commit, then its repeat), then the last row.
    assert store.calls == 3
    assert observations.missing() == {}
    stored = stored_rows(transactions, [row.id for row in rows])
    assert len(stored) == BUFFER + 1 and {row["dropped_count"] for row in stored} == {0}


def test_two_unknown_commits_in_a_row_keep_the_rows_buffered(transactions):
    """When the repeat is unknown too, the chunk stays buffered with its ids, and the
    next record writes it harmlessly over what was stored."""
    store = CommitThenUnknown(transactions, unknown=2)
    observations = Observations(store)
    start = now() - dt.timedelta(hours=1)
    first = observations.make("export", "export", "available", observed_at=start)
    assert observations.record("export", [first]) == {"written": 0, "buffered": 1,
                                                      "dropped": 0}
    assert store.calls == 2
    second = observations.make("export", "export", "available",
                               observed_at=start + dt.timedelta(seconds=1))
    assert observations.record("export", [second]) == {"written": 2, "buffered": 0,
                                                       "dropped": 0}
    rows = stored_rows(transactions, [first.id, second.id])
    assert len(rows) == 2 and {row["dropped_count"] for row in rows} == {0}


def stored_dropped(transactions, row_id) -> int:
    return transactions.run("operations", lambda conn: conn.execute(
        "SELECT dropped_count FROM operations.observation_record WHERE id=%s",
        (row_id,)).fetchone()["dropped_count"])


def test_a_producers_dropped_observations_ride_on_the_rows_it_writes(transactions):
    """Step 59(a) (NFR9.2, L1-46). Its dashboard half is Step 61(g)."""
    from backend.modules.operations.readiness import Readiness
    from backend.u8_host import Activation
    from backend.u8_registry import CONTRIBUTIONS, MANIFEST

    store = DownStore()
    observations = Observations(store)
    # An hour in the past, so the realm's latest export row stays the newest.
    start = now() - dt.timedelta(hours=1)

    def make(capability: str, index: int):
        return observations.make(capability, CAPABILITY_BY_ID[capability].producer,
                                 "available", observed_at=start + dt.timedelta(seconds=index))

    exports = [make("export", index) for index in range(61)]
    for row in exports:
        result = observations.record("export", [row])
    assert result == {"written": 0, "buffered": 60, "dropped": 1}
    digests = [make("topics.digest", index) for index in range(60)]
    for row in digests:
        other = observations.record("topics", [row])
    assert other == {"written": 0, "buffered": 60, "dropped": 0}
    # The store answers again: 60 buffered and one new row, in inserts the real store
    # bounds at 60 rows, so 61 written shows the inserts held at most 60.
    observations.store = ObservationStore(transactions)
    newest = make("export", 61)
    assert observations.record("export", [newest]) == {"written": 61, "buffered": 0,
                                                       "dropped": 1}
    later = [make("export", 62), make("export", 63)]
    for row in later:
        assert observations.record("export", [row])["written"] == 1
    for row in [*exports[1:], newest, *later]:
        assert stored_dropped(transactions, row.id) == 1
    # The buffer kept the rows it could not write unchanged.
    assert all(row.dropped_count == 0 for row in exports)
    stored = transactions.run("operations", lambda conn: conn.execute(
        "SELECT * FROM operations.observation_record WHERE id=%s", (later[-1].id,)).fetchone())
    activations = {entry.contribution_id: Activation(entry.contribution_id, "active")
                   for entry in CONTRIBUTIONS}
    view = Readiness(MANIFEST, activations, {}, None, SYNTHETIC_OPERATIONS,
                     lambda: stored["observed_at"])
    state = view.derive({"export": stored}, stored["observed_at"])["export"]
    assert state.dropped_count == 1


def test_revisions_advance_per_capability(transactions):
    observations = Observations(ObservationStore(transactions))
    moment = now()
    first = observations.make("export", "export", "available", observed_at=moment)
    second = observations.make("export", "export", "available", observed_at=moment)
    assert second.revision == first.revision + 1


def test_a_failed_record_leaves_every_job_outcome_unchanged(transactions, clock, tmp_path):
    """Producers observe the owners while the store is down: no exception reaches
    them, and no job, effect or request changes (Step 59(b): lifecycle requests and a
    ledger's recovery request included)."""
    from backend.modules.operations.producers import LedgerProducer
    from backend.modules.operations.recovery import RecoveryRequests
    from tests.u8_service_operations_integration import recovery_flows as rf

    ledger = rf.open_ledger(tmp_path, clock)
    requests = RecoveryRequests(ledger, SYNTHETIC_OPERATIONS, clock=clock)
    requests.request(origin="schedule", operation="backup.create", environment="live",
                     target_id="docsuri_u8", expected_revision=requests.backup_revision("live"),
                     submission_id=uuid4())

    def outcomes():
        return {
            "lifecycle": transactions.run("accounts", lambda conn: conn.execute(
                "SELECT disposition, count(*) AS n FROM accounts.lifecycle_request "
                "GROUP BY disposition ORDER BY disposition").fetchall()),
            "recovery": ledger.records("recovery-request"),
            "research": transactions.run("research", lambda conn: conn.execute(
                "SELECT state, count(*) AS n FROM research.job GROUP BY state ORDER BY state"
            ).fetchall()),
            "export": transactions.run("export", lambda conn: conn.execute(
                "SELECT state, count(*) AS n FROM export.effect GROUP BY state ORDER BY state"
            ).fetchall()),
            "assistance": transactions.run("assistance", lambda conn: conn.execute(
                "SELECT state, count(*) AS n FROM assistance.job GROUP BY state ORDER BY state"
            ).fetchall()),
        }

    try:
        before = outcomes()
        assert len(before["recovery"]) == 1
        store = DownStore()
        schedule = ProducerSchedule(
            [OwnerProbe("research", "research", transactions),
             ExportProducer(transactions, SYNTHETIC_OPERATIONS), LedgerProducer(ledger)],
            Observations(store), SYNTHETIC_OPERATIONS, clock,
        )
        observed = schedule.run_due()
        assert observed == ["research", "export", "operations.ledger"]
        assert store.attempts == 3
        assert outcomes() == before
    finally:
        ledger.close()


# Decision 9222ed3d ("Renew on real time too") and the lead's option A of record 87
# (2026-11-13): a process seeds each capability's revisions from the newest stored one
# before its first write, so a renewal after a restart wins `latest`'s revision
# tie-break. Each test names its own capability (registered here like `export`), so rows
# other tests leave in the persistent realm never change its result.
PRODUCER = "test.producer"


def own_capability(label: str) -> tuple[str, dict]:
    name = f"test-{secrets.token_hex(4)}-{label}"
    capability = dataclasses.replace(CAPABILITY_BY_ID["export"], capability_id=name,
                                     producer=PRODUCER)
    return name, {name: capability}


def readiness_of(row: dict, at: dt.datetime):
    from backend.modules.operations.readiness import Readiness
    from backend.u8_host import Activation
    from backend.u8_registry import CONTRIBUTIONS, MANIFEST

    activations = {entry.contribution_id: Activation(entry.contribution_id, "active")
                   for entry in CONTRIBUTIONS}
    view = Readiness(MANIFEST, activations, {}, None, SYNTHETIC_OPERATIONS, lambda: at)
    return view.derive({"export": row}, at)["export"].brief()


def stamp_of(at: dt.datetime) -> int:
    return int(at.timestamp() * 1000)


def test_a_restarted_process_renews_above_the_rows_written_before_it(transactions, clock):
    """Two processes write one capability at one held instant; the second, restarted,
    seeds from the stored revision, so `latest` returns its renewal and readiness
    derives from it: an older available row, a newer unavailable renewal, unavailable."""
    name, registry = own_capability("restart")
    held = clock()
    store = ObservationStore(transactions)
    before = Observations(ObservationStore(transactions), registry=registry)
    for _ in range(2):
        row = before.make(name, PRODUCER, "available", observed_at=held)
        assert before.record(PRODUCER, [row])["written"] == 1
    assert store.latest([name])[name]["revision"] == stamp_of(held) + 1
    counting = CountingReads(transactions)
    restarted = Observations(counting, registry=registry)
    renewal = restarted.make(name, PRODUCER, "unavailable", observed_at=held,
                             reason="store-unavailable")
    # Before its seed it numbers from the same stamp the first process began with.
    assert renewal.revision == stamp_of(held)
    assert restarted.record(PRODUCER, [renewal]) == {"written": 1, "buffered": 0,
                                                     "dropped": 0}
    latest = store.latest([name])[name]
    assert latest["id"] == renewal.id and latest["outcome"] == "unavailable"
    assert latest["revision"] == stamp_of(held) + 2
    assert readiness_of(latest, held) == {"state": "unavailable",
                                          "reason": "store-unavailable"}
    # Its next renewal numbers on from the seeded revision and is written with no
    # second read: one seed read per capability per process.
    again = restarted.make(name, PRODUCER, "available", observed_at=held)
    assert again.revision == stamp_of(held) + 3
    assert restarted.record(PRODUCER, [again])["written"] == 1
    assert counting.reads == 1
    assert store.latest([name])[name]["id"] == again.id


class CountingReads:
    """The realm's store, counting the reads that reach it; every call goes through."""

    def __init__(self, transactions):
        self.inner, self.reads = ObservationStore(transactions), 0

    def latest(self, capabilities):
        self.reads += 1
        return self.inner.latest(capabilities)

    def insert(self, rows):
        return self.inner.insert(rows)


class SeedReadDown:
    """The realm's store while its read fails (the database still down after a crash);
    its inserts reach the realm, so a row written with an unseeded revision would show."""

    def __init__(self, transactions):
        self.inner, self.reads, self.inserts = ObservationStore(transactions), 0, 0

    def latest(self, capabilities):
        self.reads += 1
        raise ConnectionError("store unavailable")

    def insert(self, rows):
        self.inserts += 1
        return self.inner.insert(rows)


def test_a_failed_seed_read_writes_nothing_and_a_later_pass_seeds(transactions, clock):
    name, registry = own_capability("seed")
    held = clock()
    store = ObservationStore(transactions)
    before = Observations(ObservationStore(transactions), registry=registry)
    first = before.make(name, PRODUCER, "available", observed_at=held)
    assert before.record(PRODUCER, [first])["written"] == 1
    down = SeedReadDown(transactions)
    restarted = Observations(down, registry=registry)
    renewal = restarted.make(name, PRODUCER, "unavailable", observed_at=held,
                             reason="store-unavailable")
    # Two passes while the read fails: nothing written, nothing remembered as seeded.
    for rows in ([renewal], []):
        assert restarted.record(PRODUCER, rows) == {"written": 0, "buffered": 1,
                                                    "dropped": 0}
    assert (down.reads, down.inserts) == (2, 0)
    assert stored_rows(transactions, [renewal.id]) == []
    assert store.latest([name])[name]["id"] == first.id
    # The database answers again: the next pass seeds and writes the renewal above it.
    restarted.store = ObservationStore(transactions)
    assert restarted.record(PRODUCER, []) == {"written": 1, "buffered": 0, "dropped": 0}
    latest = store.latest([name])[name]
    assert latest["id"] == renewal.id and latest["revision"] == stamp_of(held) + 1
    assert readiness_of(latest, held) == {"state": "unavailable",
                                          "reason": "store-unavailable"}


def test_seeded_rows_with_different_instants_keep_their_order(transactions, clock):
    name, registry = own_capability("ordered")
    held = clock()
    later = held + dt.timedelta(seconds=1)
    store = ObservationStore(transactions)
    before = Observations(ObservationStore(transactions), registry=registry)
    first = before.make(name, PRODUCER, "available", observed_at=later)
    assert before.record(PRODUCER, [first])["written"] == 1
    restarted = Observations(ObservationStore(transactions), registry=registry)
    # Stamped earlier: seeded above the stored revision, and still behind the later row.
    earlier = restarted.make(name, PRODUCER, "unavailable", observed_at=held,
                             reason="store-unavailable")
    assert restarted.record(PRODUCER, [earlier])["written"] == 1
    # Without the seed it would keep stamp(held), below the later row's revision.
    assert earlier.revision == stamp_of(held) < first.revision
    stored_revision = transactions.run("operations", lambda conn: conn.execute(
        "SELECT revision FROM operations.observation_record WHERE id=%s",
        (earlier.id,)).fetchone())["revision"]
    assert stored_revision == first.revision + 1
    latest = store.latest([name])[name]
    assert latest["id"] == first.id and latest["outcome"] == "available"
    assert readiness_of(latest, later) == {"state": "available", "reason": None}
    newest = restarted.make(name, PRODUCER, "unavailable", observed_at=later
                            + dt.timedelta(seconds=1), reason="store-unavailable")
    assert restarted.record(PRODUCER, [newest])["written"] == 1
    assert store.latest([name])[name]["id"] == newest.id
