"""ServiceOperations' observation records (Step 8; BR3.1-BR3.6, O1).

Each test observes capabilities named for that test only, so records other tests leave
in the persistent realm never change its result.
"""

from __future__ import annotations

import datetime as dt
import secrets

import psycopg
import pytest

from backend.modules.operations.observation_store import ObservationRow, ObservationStore


@pytest.fixture
def store(transactions):
    return ObservationStore(transactions)


@pytest.fixture
def names():
    token = secrets.token_hex(4)
    return [f"test-{token}-{index}" for index in range(3)]


def row(capability: str, observed_at: dt.datetime, *, outcome: str = "available",
        revision: int = 1) -> ObservationRow:
    return ObservationRow(
        capability=capability, producer="test.producer", outcome=outcome,
        reason_key=None if outcome == "available" else "test-reason",
        observed_at=observed_at, revision=revision, error_count=0, total_count=1,
    )


def test_latest_returns_the_newest_record_of_each_capability(store, names, clock):
    now = clock()
    rows = [
        row(names[0], now - dt.timedelta(minutes=5), revision=1),
        row(names[0], now - dt.timedelta(minutes=1), outcome="degraded", revision=2),
        row(names[1], now - dt.timedelta(minutes=3), revision=1),
    ]
    assert store.insert(rows) == 3
    latest = store.latest(names)
    assert set(latest) == {names[0], names[1]}
    assert latest[names[0]]["revision"] == 2 and latest[names[0]]["outcome"] == "degraded"
    assert latest[names[1]]["revision"] == 1
    assert names[2] not in latest


def test_bounded_deletion_removes_only_records_older_than_fourteen_days(
        store, names, clock, connect):
    now = clock()
    store.insert([
        row(names[0], now - dt.timedelta(days=15)),
        row(names[1], now - dt.timedelta(days=13)),
    ])
    removed = store.delete_old(now, limit=10_000)
    assert removed >= 1
    with connect("operations") as conn:
        left = {r["capability"] for r in conn.execute(
            "SELECT capability FROM operations.observation_record WHERE capability=ANY(%s)",
            (names,)).fetchall()}
    assert left == {names[1]}


def test_the_deletion_bound_is_enforced(store, clock):
    with pytest.raises(ValueError):
        store.delete_old(clock(), limit=10_001)
    with pytest.raises(ValueError):
        store.delete_old(clock().replace(tzinfo=None))


@pytest.mark.parametrize("owner", ["accounts", "corpus", "discovery", "library", "research"])
def test_a_write_as_any_role_but_the_operations_owner_is_refused(connect, names, clock, owner):
    with connect(owner) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO operations.observation_record(id,capability,producer,outcome,"
                "revision,observed_at) VALUES(gen_random_uuid(),%s,'test.producer',"
                "'available',1,%s)",
                (names[0], clock()),
            )


def test_the_runtime_login_cannot_delete_outside_the_bounded_function(store, names, clock,
                                                                      connect):
    store.insert([row(names[0], clock())])
    with connect("operations") as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "DELETE FROM operations.observation_record WHERE capability=%s", (names[0],))


def test_private_text_and_unregistered_keys_are_refused(clock):
    with pytest.raises(ValueError):
        row("Has Spaces", clock())
    with pytest.raises(ValueError):
        ObservationRow(capability="test-x", producer="test.producer", outcome="degraded",
                       observed_at=clock(), revision=1)
    with pytest.raises(ValueError):
        ObservationRow(capability="test-x", producer="test.producer", outcome="available",
                       observed_at=clock(), revision=1,
                       limitation_keys=("person@example.invalid",))


def test_an_insert_beyond_one_buffer_is_refused(store, names, clock):
    with pytest.raises(ValueError):
        store.insert([row(names[0], clock())] * 61)


def test_the_dropped_count_round_trips(store, names, clock, connect):
    """Step 49 (L1-46): the producer's running dropped count is stored and read back; an
    absent count is 0; anything but an int of at least 0 is refused before any write."""
    now = clock()
    counted = ObservationRow(
        capability=names[0], producer="test.producer", outcome="available",
        observed_at=now, revision=1, error_count=0, total_count=1, dropped_count=3,
    )
    store.insert([counted, row(names[1], now)])
    latest = store.latest(names[:2])
    assert latest[names[0]]["dropped_count"] == 3
    assert latest[names[1]]["dropped_count"] == 0
    for bad in (-1, 1.5, True):
        with pytest.raises(ValueError, match="observation counts outside their bounds"):
            ObservationRow(
                capability=names[2], producer="test.producer", outcome="available",
                observed_at=now, revision=1, error_count=0, total_count=1,
                dropped_count=bad,
            )
    with connect("operations") as conn:
        written = conn.execute(
            "SELECT count(*) AS n FROM operations.observation_record WHERE capability=%s",
            (names[2],)).fetchone()["n"]
    assert written == 0
