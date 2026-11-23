"""The email allowance on the operations ledger (U8 plan Step 14; D12, BR7.4, NFR6.2).

The production policy's limits are used unchanged (60, 90, 2,700), with a real ledger in
a private temporary folder and the injected clock.
"""

from __future__ import annotations

import datetime as dt
from uuid import uuid4

import pytest

from backend.modules.accounts.integrations.email_allowance import (
    AllowanceExhausted,
    EmailAllowance,
    Reservation,
)
from backend.modules.operations.allowance import KIND, LedgerAllowance
from backend.modules.operations.ledger import Ledger
from backend.modules.operations.producers import ProviderProducer
from backend.u8_policy import PRODUCTION_OPERATIONS, SYNTHETIC_OPERATIONS


@pytest.fixture
def allowance(tmp_path, clock):
    folder = tmp_path / "ledger"
    folder.mkdir(mode=0o700)
    clock.now = dt.datetime(2026, 10, 22, 6, 0, tzinfo=dt.UTC)
    ledger = Ledger.open(folder, clock=clock)
    yield LedgerAllowance(ledger, PRODUCTION_OPERATIONS)
    ledger.close()


def reserve(allowance, kind: str, count: int) -> list[Reservation]:
    return [allowance.reserve(kind, str(uuid4())) for _ in range(count)]


def test_the_policy_rows_are_the_limits_in_every_profile():
    for policy in (PRODUCTION_OPERATIONS, SYNTHETIC_OPERATIONS):
        assert (policy.digest_daily_limit, policy.account_mail_daily_limit,
                policy.mail_monthly_limit) == (60, 90, 2700)


def resend_producer(allowance) -> ProviderProducer:
    """provider.resend's producer on the allowance's own ledger and clock (Step 54(a))."""
    return ProviderProducer("provider.resend", allowance.ledger, allowance=allowance)


def reads(producer, clock) -> tuple:
    observed = producer.observe(clock.now)
    return observed.outcome, observed.reason, observed.limitations


DEGRADED = ("degraded", "allowance-exhausted", ("allowance-exhausted",))


def test_the_61st_digest_of_a_utc_day_waits_while_account_mail_continues_to_90(
    allowance, clock,
):
    assert isinstance(allowance, EmailAllowance)
    producer = resend_producer(allowance)
    counted = reserve(allowance, "digest", 59)
    assert reads(producer, clock)[0] == "available"
    counted += reserve(allowance, "digest", 1)
    assert reads(producer, clock) == DEGRADED
    with pytest.raises(AllowanceExhausted) as waiting:
        allowance.reserve("digest", str(uuid4()))
    assert waiting.value.limit == "daily"
    assert allowance.limit_reached("digest", str(uuid4())) == "daily"
    assert not allowance.exhausted("account")  # at 60
    counted += reserve(allowance, "account", 29)
    assert not allowance.exhausted("account")  # at 89
    assert allowance.limit_reached("account", str(uuid4())) is None
    assert allowance.limit_reached("digest", str(uuid4())) == "daily"
    counted += reserve(allowance, "account", 1)
    assert allowance.counts()["daily"] == 90
    assert reads(producer, clock) == DEGRADED
    with pytest.raises(AllowanceExhausted):
        allowance.reserve("account", str(uuid4()))
    assert allowance.exhausted("digest") and allowance.exhausted("account")
    assert allowance.limit_reached("account", str(uuid4())) == "daily"
    # A message whose reservation is counted keeps its place at either limit.
    for item in counted[:1] + counted[-1:]:
        assert allowance.limit_reached(item.kind, item.message_key) is None
    assert allowance.remaining() == {"daily": 0, "monthly": 2700 - 90}


def test_at_2700_in_a_month_all_mail_stops(allowance, clock):
    producer = resend_producer(allowance)
    for day in range(1, 31):
        clock.now = dt.datetime(2026, 10, day, 1, 0, tzinfo=dt.UTC)
        reserve(allowance, "account", 90)
    assert allowance.counts()["monthly"] == 2700
    clock.now = dt.datetime(2026, 10, 31, 1, 0, tzinfo=dt.UTC)
    assert allowance.counts()["daily"] == 0
    assert reads(producer, clock) == DEGRADED
    assert allowance.limit_reached("account", str(uuid4())) == "monthly"
    for kind in ("digest", "account"):
        with pytest.raises(AllowanceExhausted) as stopped:
            allowance.reserve(kind, str(uuid4()))
        assert stopped.value.limit == "monthly"
    clock.now = dt.datetime(2026, 11, 1, 0, 0, tzinfo=dt.UTC)
    assert reads(producer, clock)[0] == "available"
    assert allowance.reserve("digest", str(uuid4())).kind == "digest"


def test_a_refused_send_releases_its_place_and_an_unknown_outcome_keeps_it(allowance):
    refused = allowance.reserve("digest", str(uuid4()))
    unknown = allowance.reserve("digest", str(uuid4()))
    accepted = allowance.reserve("account", str(uuid4()))
    assert allowance.counts()["daily"] == 3
    allowance.release(refused)
    allowance.settle(accepted)
    assert allowance.counts()["daily"] == 2  # the unknown one keeps its reservation
    states = {item["reservationId"]: item["state"]
              for item in allowance.ledger.records(KIND)}
    assert states == {refused.reservation_id: "released", unknown.reservation_id: "reserved",
                      accepted.reservation_id: "settled"}
    with pytest.raises(ValueError):
        allowance.release(Reservation(str(uuid4()), "digest", str(uuid4())))


def test_a_retry_reuses_its_messages_key_and_reservation(allowance):
    key = str(uuid4())
    first = allowance.reserve("digest", key)
    head = allowance.ledger.head
    assert allowance.reserve("digest", key) == first and allowance.ledger.head == head
    allowance.release(first)
    again = allowance.reserve("digest", key)
    assert again == first and allowance.counts()["daily"] == 1
    assert allowance.reserve("account", key) != first  # another kind is another message
    with pytest.raises(ValueError):
        allowance.reserve("digest", "not-a-message-key")
    with pytest.raises(ValueError):
        allowance.reserve("newsletter", str(uuid4()))


def test_the_day_resets_at_midnight_utc(allowance, clock):
    producer = resend_producer(allowance)
    clock.now = dt.datetime(2026, 10, 22, 23, 59, 59, tzinfo=dt.UTC)
    reserve(allowance, "digest", 60)
    assert reads(producer, clock) == DEGRADED
    with pytest.raises(AllowanceExhausted):
        allowance.reserve("digest", str(uuid4()))
    clock.now = dt.datetime(2026, 10, 23, 0, 0, tzinfo=dt.UTC)  # 09:00 in Seoul
    assert reads(producer, clock)[0] == "available"
    assert allowance.reserve("digest", str(uuid4())).kind == "digest"
    assert allowance.counts() == {"day": "2026-10-23", "month": "2026-10", "daily": 1,
                                  "monthly": 61}
    # One day count covers all mail: 58 account places leave it available (59), and
    # the 59th makes it degraded (60).
    reserve(allowance, "account", 58)
    assert reads(producer, clock)[0] == "available"
    reserve(allowance, "account", 1)
    assert reads(producer, clock) == DEGRADED


def test_a_restore_of_the_database_leaves_the_count(allowance, tmp_path, clock):
    """The count lives in the ledger, so nothing a database restore does reaches it."""
    reserve(allowance, "digest", 5)
    allowance.ledger.close()
    reopened = Ledger.open(tmp_path / "ledger", clock=clock)
    try:
        assert LedgerAllowance(reopened, PRODUCTION_OPERATIONS).counts()["daily"] == 5
    finally:
        reopened.close()
