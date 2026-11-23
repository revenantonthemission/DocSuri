"""AccountAccess's sign-in limits: data access (U8 plan Step 7; D2, security-design § 3.2).

Three limits, keyed only by the built verifier's HMAC digests:

- one client address: 20 attempts per minute (`accounts.entry_address_limit`);
- one email: after 5 failures within 15 minutes, a 15-minute wait
  (`accounts.entry_email_failure`);
- everyone together: 120 attempts per minute (`accounts.entry_shared_limit`).

`check_and_count` runs in the caller's transaction, before any password is checked: it
refuses an email that waits, then counts the address and the shared minute with one
conditional upsert each. A refusal raises, so the caller's transaction rolls back and no
count moves. The email limit is for sign-in only: every other entry operation passes no
email. A failed sign-in is counted against its email in its own short transaction.
`expire` removes finished rows in bounded passes. Every time comes from the caller's
clock (decision "One clock").

**The client address** (security-design § 3.2) reaches AccountAccess through
`CLIENT_ADDRESS`, a context variable that U8's browser boundary sets for each request
from `address_key`: exactly one `CF-Connecting-IP` that `ipaddress` parses, and only on
a request for the public origin, IPv6 counted by its /64; a missing or malformed header
counts in the shared `unknown` bucket; a loopback-origin request counts by its socket
peer. A call outside any request (an earlier assembly, a direct service call) also
counts as `unknown`, so the limit is never absent. A refusal leaves its wait in
`REFUSAL`, which the boundary turns into the answer's `Retry-After`.
"""

from __future__ import annotations

import contextlib
import contextvars
import datetime as dt
import ipaddress
import math
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from backend.transactions import Busy

OWNER = "accounts"
DIGEST = re.compile(r"[0-9a-f]{64}")
UNKNOWN_ADDRESS = "unknown"
MAX_ADDRESS_HEADER = 64

# Set by U8's browser boundary for each request: the address key the limits count.
CLIENT_ADDRESS: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "docsuri_entry_client_address", default=None
)
# Set by the boundary to a fresh dict per request; a refusal records its wait in it.
REFUSAL: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "docsuri_entry_refusal", default=None
)


def _normal(value: str) -> str | None:
    """One parsed address as its bucket: IPv4 as itself, IPv6 by its /64 prefix."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        return str(ipaddress.IPv6Network((address, 64), strict=False))
    return str(address)


def address_key(connecting: Sequence[str], *, public: bool, peer: str | None) -> str:
    """The bucket one request counts in. `connecting` holds every `CF-Connecting-IP`
    value the request carried; it is read only for the public origin."""
    if not public:
        return (_normal(peer) if isinstance(peer, str) else None) or UNKNOWN_ADDRESS
    if len(connecting) != 1:
        return UNKNOWN_ADDRESS
    value = connecting[0]
    if not isinstance(value, str) or not 0 < len(value) <= MAX_ADDRESS_HEADER:
        return UNKNOWN_ADDRESS
    if value != value.strip() or "," in value:
        return UNKNOWN_ADDRESS
    return _normal(value) or UNKNOWN_ADDRESS


def current_address() -> str:
    return CLIENT_ADDRESS.get() or UNKNOWN_ADDRESS


@contextlib.contextmanager
def client_address(value: str) -> Iterator[None]:
    """Count the enclosed entry operations under `value` (a direct service call)."""
    token = CLIENT_ADDRESS.set(value)
    try:
        yield
    finally:
        CLIENT_ADDRESS.reset(token)


@dataclass(frozen=True)
class EntryLimitPolicy:
    address_per_minute: int = 20
    shared_per_minute: int = 120
    email_failures: int = 5
    email_window_seconds: int = 900
    email_wait_seconds: int = 900

    def __post_init__(self) -> None:
        # The table checks hold these bounds; a policy beyond them could never count.
        if not (
            1 <= self.address_per_minute <= 20
            and 1 <= self.shared_per_minute <= 120
            and 1 <= self.email_failures <= 5
            and self.email_window_seconds > 0
            and self.email_wait_seconds > 0
        ):
            raise ValueError("sign-in limit policy outside its stored bounds")


SIGN_IN_LIMITS = EntryLimitPolicy()


class EntryLimited(Busy):
    """An entry attempt refused by a limit; `reason` is a fixed key. It is the built busy
    answer (a `Busy`, which every browser route answers 429 RATE_LIMITED), and its wait
    goes to the request's `REFUSAL` for the `Retry-After` header."""

    REASONS = ("address-limit", "email-wait", "shared-limit")

    def __init__(self, reason: str, retry_after_seconds: float):
        if reason not in self.REASONS:
            raise ValueError("unknown sign-in limit reason")
        super().__init__(reason)
        self.reason = reason
        self.retry_after_seconds = max(1, int(retry_after_seconds))
        holder = REFUSAL.get()
        if holder is not None:
            holder["retryAfterSeconds"] = self.retry_after_seconds


MAIL_LIMITS = ("daily", "monthly")


def _seconds_to_next_reset(limit: str, now: dt.datetime) -> int:
    """Whole seconds, rounded up and at least 1, from `now` to the next 00:00 UTC (the
    day) or to 00:00 UTC on the 1st of the next UTC month (the month)."""
    moment = _aware(now).astimezone(dt.UTC)
    if limit == "daily":
        boundary = dt.datetime.combine(
            moment.date() + dt.timedelta(days=1), dt.time(), tzinfo=dt.UTC
        )
    else:
        year, month = (moment.year + 1, 1) if moment.month == 12 else (
            moment.year, moment.month + 1)
        boundary = dt.datetime(year, month, 1, tzinfo=dt.UTC)
    return max(1, math.ceil((boundary - moment).total_seconds()))


class AccountMailLimitReached(Busy):
    """Account mail refused at the email allowance's limit (U8 plan Step 53(c), L1-10):
    the built busy answer (429 RATE_LIMITED) with its own message key. For `daily` its
    wait runs to the next 00:00 UTC (09:00 in Seoul), for `monthly` to 00:00 UTC on the
    1st of the next UTC month, rounded up to whole seconds, and goes to the request's
    `REFUSAL` for `Retry-After`. `None` (the email change's late refusal) names no wait
    and records nothing."""

    message_key = "account-mail.allowance-exhausted"

    def __init__(self, limit: str | None, *, now: dt.datetime | None = None):
        if limit is not None and limit not in MAIL_LIMITS:
            raise ValueError("account mail limit is daily, monthly or None")
        super().__init__("account mail allowance exhausted")
        self.limit = limit
        if limit is None:
            self.retry_after_seconds = None
            return
        if now is None:
            raise ValueError("an account mail limit's wait needs the entry's clock")
        self.retry_after_seconds = _seconds_to_next_reset(limit, now)
        holder = REFUSAL.get()
        if holder is not None:
            holder["retryAfterSeconds"] = self.retry_after_seconds


class AccountMailUnavailable(Busy):
    """Account mail refused while none of it can be sent (U8 plan Step 53(g), L1-53):
    held, Resend unconfigured or Resend observed down. The built busy answer (429
    RATE_LIMITED) with its own message key and no wait: nothing goes to `REFUSAL`, so no
    `Retry-After` is sent, because neither a hold nor an outage has a known end."""

    message_key = "account-mail.unavailable"
    retry_after_seconds = None

    def __init__(self) -> None:
        super().__init__("account mail unavailable")


def _digest(value: str, name: str) -> str:
    if not isinstance(value, str) or DIGEST.fullmatch(value) is None:
        raise ValueError(f"{name} must be a keyed digest")
    return value


def _aware(now: dt.datetime) -> dt.datetime:
    if not isinstance(now, dt.datetime) or now.tzinfo is None:
        raise ValueError("the limit clock must give an aware time")
    return now


def minute_of(now: dt.datetime) -> int:
    return int(_aware(now).timestamp() // 60)


def day_of(now: dt.datetime) -> int:
    """The UTC day's number from the epoch, as `minute_of` numbers D2's minutes."""
    return int(_aware(now).timestamp() // 86400)


def count_account_mail(conn, *, account_id, now: dt.datetime, per_day: int) -> bool:
    """Count one account email against its account's UTC day (U8 plan Step 53(i), L1-71),
    in the caller's transaction, in D2's conditional-upsert pattern: False at the limit,
    and then nothing changes."""
    if type(per_day) is not int or per_day < 1:
        raise ValueError("account mail per day must be a positive integer")
    counted = conn.execute(
        "INSERT INTO accounts.mail_account_limit(account_id,day,messages) VALUES(%s,%s,1) "
        "ON CONFLICT(account_id,day) DO UPDATE SET "
        "messages=accounts.mail_account_limit.messages+1 "
        "WHERE accounts.mail_account_limit.messages<%s RETURNING messages",
        (account_id, day_of(now), per_day),
    ).fetchone()
    return counted is not None


class EntryLimits:
    def __init__(self, transactions, policy: EntryLimitPolicy = SIGN_IN_LIMITS):
        self.transactions = transactions
        self.policy = policy

    def check_and_count(
        self, conn, *, address_digest: str, email_digest: str | None, now: dt.datetime
    ) -> None:
        """In the caller's transaction: refuse, or count this attempt against all three.
        `email_digest` is None for every operation but sign-in, which the email limit
        does not cover."""
        address = _digest(address_digest, "address")
        email = None if email_digest is None else _digest(email_digest, "email")
        minute = minute_of(now)
        retry = 60 - int(now.timestamp()) % 60
        waiting = None if email is None else conn.execute(
            "SELECT wait_until FROM accounts.entry_email_failure WHERE email_digest=%s "
            "FOR UPDATE",
            (email,),
        ).fetchone()
        if waiting and waiting["wait_until"] is not None and waiting["wait_until"] > now:
            raise EntryLimited("email-wait", (waiting["wait_until"] - now).total_seconds())
        counted = conn.execute(
            "INSERT INTO accounts.entry_address_limit(address_digest,minute,attempts) "
            "VALUES(%s,%s,1) ON CONFLICT(address_digest,minute) DO UPDATE SET "
            "attempts=accounts.entry_address_limit.attempts+1 "
            "WHERE accounts.entry_address_limit.attempts<%s RETURNING attempts",
            (address, minute, self.policy.address_per_minute),
        ).fetchone()
        if counted is None:
            raise EntryLimited("address-limit", retry)
        shared = conn.execute(
            "INSERT INTO accounts.entry_shared_limit(minute,attempts) VALUES(%s,1) "
            "ON CONFLICT(minute) DO UPDATE SET attempts=accounts.entry_shared_limit.attempts+1 "
            "WHERE accounts.entry_shared_limit.attempts<%s RETURNING attempts",
            (minute, self.policy.shared_per_minute),
        ).fetchone()
        if shared is None:
            raise EntryLimited("shared-limit", retry)

    def record_failure(self, *, email_digest: str, now: dt.datetime) -> dict:
        """Count one failed sign-in against its email, in its own short transaction."""
        email = _digest(email_digest, "email")
        _aware(now)
        window = dt.timedelta(seconds=self.policy.email_window_seconds)
        wait = dt.timedelta(seconds=self.policy.email_wait_seconds)

        def write(conn):
            row = conn.execute(
                "SELECT * FROM accounts.entry_email_failure WHERE email_digest=%s FOR UPDATE",
                (email,),
            ).fetchone()
            if row is not None and row["wait_until"] is not None and row["wait_until"] > now:
                return {"failures": row["failures"], "waitUntil": row["wait_until"]}
            if (
                row is None
                or row["window_started_at"] <= now - window
                or row["window_started_at"] > now  # a clock that moved back starts afresh
                or row["wait_until"]
            ):
                failures, started = 1, now
            else:
                failures, started = row["failures"] + 1, row["window_started_at"]
            wait_until = now + wait if failures >= self.policy.email_failures else None
            conn.execute(
                "INSERT INTO accounts.entry_email_failure(email_digest,window_started_at,"
                "failures,last_failure_at,wait_until) VALUES(%s,%s,%s,%s,%s) "
                "ON CONFLICT(email_digest) DO UPDATE SET window_started_at=excluded."
                "window_started_at,failures=excluded.failures,last_failure_at=excluded."
                "last_failure_at,wait_until=excluded.wait_until",
                (email, started, failures, now, wait_until),
            )
            return {"failures": failures, "waitUntil": wait_until}

        return self.transactions.run(OWNER, write)

    def expire(self, *, now: dt.datetime, limit: int = 1000) -> dict:
        """Remove finished rows, at most `limit` of each table per pass."""
        if type(limit) is not int or not 1 <= limit <= 10_000:
            raise ValueError("expiry outside its bound")
        minute = minute_of(now)
        window = dt.timedelta(seconds=self.policy.email_window_seconds)

        def write(conn):
            address = conn.execute(
                "DELETE FROM accounts.entry_address_limit WHERE ctid IN (SELECT ctid FROM "
                "accounts.entry_address_limit WHERE minute<%s LIMIT %s)",
                (minute, limit),
            ).rowcount
            shared = conn.execute(
                "DELETE FROM accounts.entry_shared_limit WHERE ctid IN (SELECT ctid FROM "
                "accounts.entry_shared_limit WHERE minute<%s LIMIT %s)",
                (minute, limit),
            ).rowcount
            email = conn.execute(
                "DELETE FROM accounts.entry_email_failure WHERE ctid IN (SELECT ctid FROM "
                "accounts.entry_email_failure WHERE (wait_until IS NOT NULL AND wait_until<=%s) "
                "OR (wait_until IS NULL AND last_failure_at<=%s) LIMIT %s)",
                (now, now - window, limit),
            ).rowcount
            # Finished days of the per-account mail count (Step 53(i), L1-71), and, by the
            # addition to L1-71, every erased account's rows within one pass.
            mail = conn.execute(
                "DELETE FROM accounts.mail_account_limit WHERE ctid IN (SELECT ctid FROM "
                "accounts.mail_account_limit WHERE day<%s LIMIT %s)",
                (day_of(now), limit),
            ).rowcount
            mail += conn.execute(
                "DELETE FROM accounts.mail_account_limit WHERE ctid IN (SELECT l.ctid FROM "
                "accounts.mail_account_limit l JOIN accounts.account a ON a.id=l.account_id "
                "WHERE a.lifecycle_state='erased' LIMIT %s)",
                (limit,),
            ).rowcount
            # Provider sign-in flows, with their address digests, are AccountAccess's own
            # pass (`u8_identity.expire_flows`), not the sign-in limits'.
            return {"address": address, "shared": shared, "email": email, "mail": mail}

        return self.transactions.run(OWNER, write)
