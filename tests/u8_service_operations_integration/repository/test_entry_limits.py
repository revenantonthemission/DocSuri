"""AccountAccess's sign-in limit store (Step 8; D2, security-design § 3.2).

Each test runs at its own minute far in the future, so the shared per-minute count
belongs to that test alone; digests are random per test.
"""

from __future__ import annotations

import datetime as dt
import secrets

import psycopg
import pytest

from backend.modules.accounts.entry_limits import EntryLimited, EntryLimits


@pytest.fixture
def limits(transactions):
    return EntryLimits(transactions)


@pytest.fixture
def moment():
    """A unique, minute-aligned instant in 2100."""
    minute = secrets.randbelow(5_000_000)
    return dt.datetime(2100, 1, 1, tzinfo=dt.UTC) + dt.timedelta(minutes=minute)


def digest() -> str:
    return secrets.token_hex(32)


def attempt(transactions, limits, address, email, now):
    return transactions.run(
        "accounts",
        lambda conn: limits.check_and_count(
            conn, address_digest=address, email_digest=email, now=now),
    )


def counts(connect, address, minute):
    with connect("accounts") as conn:
        one = conn.execute(
            "SELECT attempts FROM accounts.entry_address_limit WHERE address_digest=%s "
            "AND minute=%s", (address, minute)).fetchone()
        shared = conn.execute(
            "SELECT attempts FROM accounts.entry_shared_limit WHERE minute=%s",
            (minute,)).fetchone()
    return (one or {}).get("attempts"), (shared or {}).get("attempts")


def test_an_attempt_counts_the_address_and_the_shared_minute_together(
        transactions, limits, connect, moment):
    address = digest()
    minute = int(moment.timestamp() // 60)
    attempt(transactions, limits, address, digest(), moment)
    attempt(transactions, limits, address, digest(), moment + dt.timedelta(seconds=10))
    assert counts(connect, address, minute) == (2, 2)


def test_the_twenty_first_attempt_from_one_address_is_refused_and_nothing_moves(
        transactions, limits, connect, moment):
    address = digest()
    minute = int(moment.timestamp() // 60)
    for _ in range(20):
        attempt(transactions, limits, address, digest(), moment)
    with pytest.raises(EntryLimited) as refused:
        attempt(transactions, limits, address, digest(), moment)
    assert refused.value.reason == "address-limit"
    assert counts(connect, address, minute) == (20, 20)


def test_the_hundred_twenty_first_attempt_in_a_minute_is_refused_for_everyone(
        transactions, limits, connect, moment):
    minute = int(moment.timestamp() // 60)
    for _ in range(120):
        attempt(transactions, limits, digest(), digest(), moment)
    fresh = digest()
    with pytest.raises(EntryLimited) as refused:
        attempt(transactions, limits, fresh, digest(), moment)
    assert refused.value.reason == "shared-limit"
    # The refused attempt counted nothing, not even for its own address.
    assert counts(connect, fresh, minute) == (None, 120)


def test_five_failures_make_an_email_wait_and_the_wait_refuses_before_counting(
        transactions, limits, connect, moment):
    email, address = digest(), digest()
    minute = int(moment.timestamp() // 60)
    for index in range(5):
        state = limits.record_failure(email_digest=email,
                                      now=moment + dt.timedelta(seconds=index))
    assert state["failures"] == 5 and state["waitUntil"] is not None
    with pytest.raises(EntryLimited) as refused:
        attempt(transactions, limits, address, email, moment + dt.timedelta(minutes=5))
    assert refused.value.reason == "email-wait"
    assert counts(connect, address, minute + 5) == (None, None)
    later = moment + dt.timedelta(minutes=16)
    attempt(transactions, limits, address, email, later)
    assert limits.record_failure(email_digest=email, now=later)["failures"] == 1


def test_failures_outside_the_fifteen_minute_window_start_a_new_window(limits, moment):
    email = digest()
    for index in range(4):
        limits.record_failure(email_digest=email, now=moment + dt.timedelta(minutes=index))
    restarted = limits.record_failure(email_digest=email, now=moment + dt.timedelta(minutes=20))
    assert restarted == {"failures": 1, "waitUntil": None}


def test_expiry_removes_finished_rows_only(transactions, limits, connect, moment):
    old_address, current_address, email = digest(), digest(), digest()
    attempt(transactions, limits, old_address, digest(), moment)
    later = moment + dt.timedelta(minutes=3)
    attempt(transactions, limits, current_address, digest(), later)
    limits.record_failure(email_digest=email, now=moment)
    limits.expire(now=later + dt.timedelta(minutes=16), limit=10_000)
    with connect("accounts") as conn:
        rows = conn.execute(
            "SELECT address_digest FROM accounts.entry_address_limit WHERE "
            "address_digest=ANY(%s)", ([old_address, current_address],)).fetchall()
        failures = conn.execute(
            "SELECT 1 FROM accounts.entry_email_failure WHERE email_digest=%s",
            (email,)).fetchall()
    assert rows == [] and failures == []


def test_an_operation_other_than_sign_in_passes_no_email_and_still_counts(
        transactions, limits, connect, moment):
    """Step 19: the email limit is for sign-in only; registration, verification, reset
    and reactivation count against the address and the shared minute alone."""
    address = digest()
    minute = int(moment.timestamp() // 60)
    attempt(transactions, limits, address, None, moment)
    attempt(transactions, limits, address, None, moment + dt.timedelta(seconds=5))
    assert counts(connect, address, minute) == (2, 2)


def test_a_clock_that_moved_back_starts_a_fresh_failure_window(limits, moment):
    """A failure recorded before an earlier `now` (a clock set back) never breaks the
    stored window's order; the next failure starts a window of its own."""
    email = digest()
    limits.record_failure(email_digest=email, now=moment)
    earlier = moment - dt.timedelta(days=1)
    assert limits.record_failure(email_digest=email, now=earlier) == {
        "failures": 1, "waitUntil": None}


def test_only_keyed_digests_are_accepted_and_stored(transactions, limits, moment, connect):
    for address, email in (("203.0.113.7", digest()), (digest(), "person@example.invalid")):
        with pytest.raises(ValueError):
            attempt(transactions, limits, address, email, moment)
    with pytest.raises(ValueError):
        limits.record_failure(email_digest="Person@Example.invalid", now=moment)
    with connect("accounts") as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("INSERT INTO accounts.entry_shared_limit VALUES(%s,121)",
                         (int(moment.timestamp() // 60) + 1,))


def email_row_kept(connect, email) -> bool:
    with connect("accounts") as conn:
        return conn.execute(
            "SELECT 1 FROM accounts.entry_email_failure WHERE email_digest=%s",
            (email,)).fetchone() is not None


def test_rows_go_when_their_minute_ends_and_an_email_15_minutes_after_its_last_failure_or_when_its_wait_ends(  # noqa: E501
        transactions, limits, connect, moment):
    """Step 118 (D2, security-design § 3.2 line 99; L2-17): the store's deletion times,
    on injected moments. `expire` is realm-wide, so one key is recorded and checked at a
    time: a later key recorded first would be swept by an earlier key's pass."""
    second = dt.timedelta(seconds=1)
    minutes = dt.timedelta(minutes=1)

    # 1. The address row and the minute's shared row go when their minute ends.
    address = digest()
    minute = int(moment.timestamp() // 60)
    attempt(transactions, limits, address, None, moment + 10 * second)
    limits.expire(now=moment + 59 * second, limit=10_000)
    assert counts(connect, address, minute) == (1, 1)
    limits.expire(now=moment + 60 * second, limit=10_000)
    assert counts(connect, address, minute) == (None, None)

    # 2. An email with no wait goes 15 minutes after its last failure, not its first.
    quiet = digest()
    limits.record_failure(email_digest=quiet, now=moment)
    limits.record_failure(email_digest=quiet, now=moment + 5 * minutes)
    limits.expire(now=moment + 15 * minutes, limit=10_000)
    assert email_row_kept(connect, quiet)
    limits.expire(now=moment + 20 * minutes - second, limit=10_000)
    assert email_row_kept(connect, quiet)
    limits.expire(now=moment + 20 * minutes, limit=10_000)
    assert not email_row_kept(connect, quiet)

    # 3. A waiting email goes when its wait ends.
    waiting = digest()
    for index in range(5):
        state = limits.record_failure(email_digest=waiting, now=moment + index * second)
    assert state["waitUntil"] == moment + 15 * minutes + 4 * second
    limits.expire(now=moment + 15 * minutes + 3 * second, limit=10_000)
    assert email_row_kept(connect, waiting)
    limits.expire(now=moment + 15 * minutes + 4 * second, limit=10_000)
    assert not email_row_kept(connect, waiting)
