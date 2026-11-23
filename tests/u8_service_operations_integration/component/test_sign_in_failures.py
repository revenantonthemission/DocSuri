"""Every refused password sign-in reaches the same email wait (U8 plan Step 54(t); your
answer of 2026-11-09 after build batch 2's review, L1-85 "Fix it now"; Step 53(l)).

D2's email wait (security-design § 3.2) follows five failed sign-ins within 15 minutes
"whether or not an account exists". Before Step 53(l), a reset-required account that the
admission or the forced reset's own checks refused counted nothing, so six tries told
whether an address was an imported v1 account. This test signs in five times, then a
sixth, on four addresses, each within one window of its entry's standing clock:

1. an unknown address, on an entry with no admission (`first_sign_in.py`'s wrong-password
   path);
2. a reset-required account made unverified, on that entry, so each try reaches the
   forced reset's own account checks;
3. a reset-required member, on an entry under `Admission("maintainer-only")`, so each
   try meets the admission;
4. a member with no reset mark signing in with its own password on the maintainer-only
   entry (L1-85's addition beyond the option).

Each case runs under a client address of its own, so D2's 20 a minute per address never
answers first. Every password is generated per run (L1-36). The accounts are restored by
`sign_in_account` afterwards, so the test adds no account to the realm's 20.
"""

from __future__ import annotations

import datetime as dt
from uuid import uuid4

import pytest

from backend.modules.accounts.entry_limits import EntryLimited, client_address
from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY, Admission
from backend.modules.accounts.u8_entry import CompleteControlEntryService
from tests.u8_service_operations_integration.conftest import Clock

EPOCH = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)
EMAIL_WAIT_SECONDS = 900
FAILURES_BEFORE_THE_WAIT = 5


def unused_minute() -> dt.datetime:
    """A past minute of the test's own (2020 to 2028), at its first second, drawn as
    `integration/test_sign_in_limits.py` draws it."""
    return EPOCH + dt.timedelta(minutes=uuid4().int % (8 * 365 * 24 * 60))


def nobody() -> str:
    return f"nobody-{uuid4().hex[:16]}@fixture.example.com"


def fresh_password() -> str:
    return "Synthetic-" + uuid4().hex[:12] + "-A1!"  # generated per run (L1-36)


def address_of_its_own() -> str:
    return f"198.19.{uuid4().int % 250 + 1}.{uuid4().int % 250 + 1}"


class NoDeliver:
    """An account mail that defines only a `deliver` that raises: a forced reset that got
    past its checks would fail the test."""

    def __init__(self) -> None:
        self.calls = 0

    def deliver(self, item):
        self.calls += 1
        raise RuntimeError("no account mail may be delivered in this test")


def entry_on_its_own_minute(transactions, admission) -> CompleteControlEntryService:
    entry = CompleteControlEntryService(transactions, U8_SYNTHETIC_POLICY,
                                        clock=Clock(unused_minute()), admission=admission)
    entry.account_mail = NoDeliver()
    return entry


def written(connect, account_ids) -> dict:
    """The rows a forced reset or a session would leave: the accounts' proofs and daily
    counts, every receipt and every outbox row."""
    ids = list(account_ids)
    with connect("accounts") as conn:
        return {
            "control_proof": conn.execute(
                "SELECT count(*) AS n FROM accounts.control_proof WHERE account_id=ANY(%s)",
                (ids,)).fetchone()["n"],
            "mail_account_limit": conn.execute(
                "SELECT count(*) AS n FROM accounts.mail_account_limit "
                "WHERE account_id=ANY(%s)", (ids,)).fetchone()["n"],
            "entry_receipt": conn.execute(
                "SELECT count(*) AS n FROM accounts.entry_receipt").fetchone()["n"],
            "mail_outbox": conn.execute(
                "SELECT count(*) AS n FROM accounts.mail_outbox").fetchone()["n"],
        }


def failures_of(connect, entry, email: str) -> int | None:
    with connect("accounts") as conn:
        row = conn.execute(
            "SELECT failures FROM accounts.entry_email_failure WHERE email_digest=%s",
            (entry.verifier("entry-email", email),)).fetchone()
    return None if row is None else row["failures"]


def test_every_refused_sign_in_reaches_the_same_email_wait(
    transactions, connect, sign_in_account, forget_waits,
):
    open_entry = entry_on_its_own_minute(transactions, None)
    maintainer_only = entry_on_its_own_minute(transactions, Admission("maintainer-only"))
    try:
        unknown = nobody()
        migrated, unverified = sign_in_account("sign-in-migrated", reset_required=True)
        member, reset_member = sign_in_account("sign-in-member", reset_required=True)
        admin, own_password_member = sign_in_account("sign-in-admin")
        own_password = fresh_password()
        with connect("accounts") as conn:
            conn.execute("UPDATE accounts.account SET verified=false WHERE id=%s",
                         (migrated.account_id,))
            conn.execute("UPDATE accounts.account SET password_hash=%s WHERE id=%s",
                         (open_entry._hash_password(own_password), admin.account_id))
        cases = (
            (open_entry, unknown, fresh_password),
            (open_entry, unverified, fresh_password),
            (maintainer_only, reset_member, fresh_password),
            (maintainer_only, own_password_member, lambda: own_password),
        )
        emails = [email for _, email, _ in cases]
        forget_waits.extend(emails)
        # No earlier failure shortens a count (Step 54(q)'s test leaves two on the
        # migrated account's address while it runs).
        with connect("accounts") as conn:
            for email in emails:
                conn.execute("DELETE FROM accounts.entry_email_failure WHERE email_digest=%s",
                             (open_entry.verifier("entry-email", email),))
        accounts = (migrated.account_id, member.account_id, admin.account_id)
        before = written(connect, accounts)

        for entry, email, password in cases:
            with client_address(address_of_its_own()):
                refusals = []
                for _ in range(FAILURES_BEFORE_THE_WAIT):
                    with pytest.raises(Exception) as raised:
                        entry.login(email, password(), flow_binding="sign-in-failures")
                    refusals.append((type(raised.value), str(raised.value)))
                assert refusals == [(PermissionError, "credentials unavailable")] * 5, (
                    email, refusals)
                with pytest.raises(EntryLimited) as waited:
                    entry.login(email, password(), flow_binding="sign-in-failures")
            assert waited.value.reason == "email-wait"
            assert waited.value.retry_after_seconds == EMAIL_WAIT_SECONDS
            assert failures_of(connect, entry, email) == FAILURES_BEFORE_THE_WAIT

        assert written(connect, accounts) == before
        assert open_entry.account_mail.calls == 0
        assert maintainer_only.account_mail.calls == 0
    finally:
        for suffix in ("sign-in-migrated", "sign-in-member", "sign-in-admin"):
            sign_in_account(suffix)
