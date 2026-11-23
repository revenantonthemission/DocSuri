"""Account mail through Resend (U8 plan Step 22; A7, D12, BR7.4, BR7.5).

`ResendAccountMail` runs over a fake Resend client (the adapter's own client seam) and
ServiceOperations' allowance on a ledger in a private folder. It reads the gate, reserves
before anything leaves, keeps one idempotency key and one reservation per message, tries
a timeout, a 429 or a 5xx again up to 3 times within 30 seconds, releases the place of a
send Resend definitely refused and keeps the place of an unknown outcome.

Steps 53-54 (L1-10, L1-53): every 5xx is tried again; at the allowance's limit, and while
no account mail can be sent (held, unconfigured or Resend observed down), every mail
request is refused before any account read, alike for every address. Those tests run on
the composed realm through a complete entry whose allowance is a private ledger's, so no
later test meets a full day.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import re
import threading
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import httpx
import pytest
from cryptography.exceptions import InvalidTag

from backend.modules.accounts import u8_mail_outbox
from backend.modules.accounts.entry_limits import (
    REFUSAL,
    AccountMailLimitReached,
    AccountMailUnavailable,
    client_address,
)
from backend.modules.accounts.integrations import account_mail
from backend.modules.accounts.integrations.account_mail import (
    AccountMessage,
    HeldAccountMail,
    LocalAccountMail,
    ResendAccountMail,
    gated,
)
from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
from backend.modules.accounts.u8_entry import CompleteControlEntryService
from backend.modules.accounts.u8_mail_outbox import AccountMailSender
from backend.modules.operations.allowance import KIND, LedgerAllowance, reservation_id
from backend.modules.operations.ledger import Ledger
from backend.transactions import Authority, Busy
from backend.u8_policy import SYNTHETIC_OPERATIONS
from tests.u8_service_operations_integration.conftest import SIGN_IN_PASSWORD, Clock

ORIGIN = "https://127.0.0.1:18110"
MAINTAINER, SOMEONE = uuid4(), uuid4()


class Resend:
    """The recorded Resend answers, one per attempt, through the adapter's client seam."""

    def __init__(self, *answers, check=None):
        self.answers, self.check = list(answers), check
        self.posts: list[dict] = []
        self.options: list[dict] = []  # each attempt's client options (Step 54(b))

    def __call__(self, **options):
        self.options.append(options)
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, endpoint, *, headers, json):
        self.posts.append({"endpoint": endpoint, "headers": headers, "json": json})
        if self.check is not None:
            self.check(headers["Idempotency-Key"])
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return httpx.Response(answer, json={"id": str(uuid4())} if answer < 300 else {
            "name": "validation_error"})


class Gate:
    def __init__(self, state="active", mode="live"):
        self._state, self.mode = state, mode

    def state(self, provider):
        return self._state


class Recipients:
    def is_maintainer_account(self, account_id):
        return account_id == MAINTAINER

    def is_maintainer_connection(self, connection_id):
        return False


@pytest.fixture
def operations_ledger(tmp_path, clock):
    folder = tmp_path / "operations-ledger"
    folder.mkdir(mode=0o700)
    value = Ledger.open(folder, clock=clock)
    yield value
    value.close()


def message(account=MAINTAINER, key=None) -> AccountMessage:
    return AccountMessage("password-reset", key or str(uuid4()), account, {
        "challengeId": str(uuid4()), "proof": "proof-" + uuid4().hex,
        "flowBinding": "flow-binding", "email": "maintainer@fixture.example.com",
        "purpose": "password-reset",
    })


def mail(ledger, resend, *, gate=None, policy=SYNTHETIC_OPERATIONS, clock=None):
    return ResendAccountMail(
        api_key="re_" + uuid4().hex,  # generated per run (L1-36)
        sender="DocSuri <mail@fixture.example.com>",
        origin=ORIGIN, allowance=LedgerAllowance(ledger, policy), gate=gate,
        recipients=Recipients(), client_factory=resend,
        **({"clock": clock} if clock else {}),
    )


def state_of(ledger, item: AccountMessage) -> str | None:
    record = ledger.get(KIND, reservation_id("account", item.message_key))
    return record["state"] if record else None


# 1. It reserves before sending ------------------------------------------------------------


def test_it_reserves_before_sending(operations_ledger):
    item = message()
    seen = []
    resend = Resend(200, check=lambda key: seen.append(state_of(operations_ledger, item)))
    assert mail(operations_ledger, resend).deliver(item) == "accepted"
    assert seen == ["reserved"]  # the place was taken before the request left
    assert state_of(operations_ledger, item) == "settled"


# 2. A retry reuses the key and the reservation --------------------------------------------


def test_a_retry_reuses_its_key_and_its_reservation(operations_ledger):
    item = message()
    resend = Resend(200, 200)
    adapter = mail(operations_ledger, resend)
    assert adapter.deliver(item) == adapter.deliver(item) == "accepted"
    keys = {post["headers"]["Idempotency-Key"] for post in resend.posts}
    assert keys == {item.message_key}
    mine = [record for record in operations_ledger.records(KIND)
            if record["messageKey"] == item.message_key]
    assert len(mine) == 1


# 3. Three attempts within 30 seconds on 429 and 5xx ----------------------------------------


@pytest.mark.parametrize(("answers", "posts", "result"), [
    ((503, 502, 200), 3, "accepted"),
    ((429, 200), 2, "accepted"),
    ((httpx.ReadTimeout("slow"), 200), 2, "accepted"),
    ((429, 429, 429), 3, "held"),
    ((500, 500, 500, 200), 3, "held"),
])
def test_a_timeout_a_429_or_a_5xx_is_tried_again_up_to_three_times(
    operations_ledger, answers, posts, result,
):
    resend = Resend(*answers)
    assert mail(operations_ledger, resend).deliver(message()) == result
    assert len(resend.posts) == posts


def test_no_attempt_starts_after_thirty_seconds(operations_ledger):
    moments = iter([0.0, 31.0, 31.0])
    resend = Resend(httpx.ReadTimeout("slow"), 200)
    adapter = mail(operations_ledger, resend, clock=lambda: next(moments))
    assert adapter.deliver(message()) == "held"
    assert len(resend.posts) == 1
    assert not adapter.reachable()


# 4. A definite refusal releases; an unknown outcome keeps ---------------------------------


def test_a_definite_refusal_releases_its_place_and_an_unknown_outcome_keeps_it(
    operations_ledger,
):
    refused, unknown = message(), message()
    adapter = mail(operations_ledger, Resend(422, 503, 503, 503))
    assert adapter.deliver(refused) == "held"
    assert state_of(operations_ledger, refused) == "released"
    assert adapter.deliver(unknown) == "held"
    assert state_of(operations_ledger, unknown) == "reserved"


# The gate and the allowance come first ---------------------------------------------------


def test_a_held_provider_or_a_rehearsal_recipient_takes_no_place_and_sends_nothing(
    operations_ledger,
):
    resend = Resend()
    for gate, item in ((Gate("held"), message()), (Gate("unavailable"), message()),
                       (Gate("active", "rehearsal"), message(account=SOMEONE))):
        assert mail(operations_ledger, resend, gate=gate).deliver(item) == "held"
        assert state_of(operations_ledger, item) is None
    assert resend.posts == []
    # The maintainer's own message passes in rehearsal.
    assert mail(operations_ledger, Resend(200), gate=Gate("active", "rehearsal")).deliver(
        message()) == "accepted"


def test_over_the_allowance_nothing_is_sent(operations_ledger):
    tight = dataclasses.replace(SYNTHETIC_OPERATIONS, digest_daily_limit=1,
                                account_mail_daily_limit=1)
    resend = Resend(200)
    adapter = mail(operations_ledger, resend, policy=tight)
    assert adapter.deliver(message()) == "accepted"
    assert adapter.deliver(message()) == "over_allowance"
    assert len(resend.posts) == 1


def test_the_message_links_the_workspace_page_with_the_proof_in_its_fragment(
    operations_ledger,
):
    item = message()
    resend = Resend(200)
    mail(operations_ledger, resend).deliver(item)
    sent = resend.posts[0]["json"]
    assert sent["to"] == ["maintainer@fixture.example.com"]
    assert sent["subject"] == "DocSuri 비밀번호 재설정"
    link = next(line for line in sent["text"].splitlines() if line.startswith("https://"))
    address = urlsplit(link)
    assert address.scheme + "://" + address.netloc == ORIGIN
    assert address.path == "/account/password-reset" and address.query == ""
    assert parse_qs(address.fragment)["proof"] == [item.payload["proof"]]
    assert resend.posts[0]["endpoint"] == "https://api.resend.com/emails"


# Reactivation, the fourth purpose (your decision of 2026-10-23) ---------------------------


def reactivation(account=MAINTAINER, key=None) -> AccountMessage:
    return AccountMessage("reactivation", key or str(uuid4()), account, {
        "challengeId": str(uuid4()), "proof": "proof-" + uuid4().hex,
        "flowBinding": "flow-binding", "email": "maintainer@fixture.example.com",
        "purpose": "reactivate",
    })


def test_a_reactivation_message_reserves_once_and_links_the_reactivation_page(
    operations_ledger,
):
    item = reactivation()
    seen = []
    resend = Resend(503, 200, 200,
                    check=lambda key: seen.append(state_of(operations_ledger, item)))
    adapter = mail(operations_ledger, resend)
    assert adapter.deliver(item) == "accepted"  # a 5xx, then accepted on the retry
    assert adapter.deliver(item) == "accepted"  # a caller's retry gets the same place
    # Reserved before the first attempt, under one key, through the same retry rule.
    assert seen[0] == "reserved"
    assert {post["headers"]["Idempotency-Key"] for post in resend.posts} == {item.message_key}
    assert len([record for record in operations_ledger.records(KIND)
                if record["messageKey"] == item.message_key]) == 1
    sent = resend.posts[1]["json"]
    assert sent["subject"] == "DocSuri 계정 재활성화"
    link = next(line for line in sent["text"].splitlines() if line.startswith("https://"))
    address = urlsplit(link)
    assert (address.path, address.query) == ("/account/reactivate", "")
    fragment = parse_qs(address.fragment)
    assert fragment["proof"] == [item.payload["proof"]]
    assert fragment["challenge"] == [item.payload["challengeId"]]


def test_a_reactivation_message_waits_for_the_gate_and_the_allowance(operations_ledger):
    resend = Resend(200)
    assert mail(operations_ledger, resend, gate=Gate("held")).deliver(reactivation()) == "held"
    tight = dataclasses.replace(SYNTHETIC_OPERATIONS, digest_daily_limit=1,
                                account_mail_daily_limit=1)
    adapter = mail(operations_ledger, resend, policy=tight)
    assert adapter.deliver(reactivation()) == "accepted"
    assert adapter.deliver(reactivation()) == "over_allowance"
    assert len(resend.posts) == 1


class Mailbox:
    """The local mailbox's publishing seam (`PrivateArtifacts.publish`), in memory."""

    def __init__(self):
        self.files: dict[str, bytes] = {}

    def publish(self, content: bytes):
        import hashlib

        from backend.artifacts import Artifact

        name = uuid4().hex + ".blob"
        self.files[name] = content
        return Artifact(name, hashlib.sha256(content).hexdigest(), len(content))


def test_the_local_mailbox_keeps_the_reactivation_message_and_says_where(operations_ledger):
    import json

    mailbox = Mailbox()
    local = LocalAccountMail(mailbox, allowance=LedgerAllowance(operations_ledger,
                                                                SYNTHETIC_OPERATIONS))
    item = reactivation()
    assert local.deliver(item) == "accepted"
    assert state_of(operations_ledger, item) == "settled"
    name = local.delivery_of(item.message_key)
    assert json.loads(mailbox.files[name]) == item.payload
    assert local.delivery_of(str(uuid4())) is None
    # A held gate keeps the mailbox empty too.
    held = LocalAccountMail(Mailbox(), gate=Gate("held"))
    assert held.deliver(reactivation()) == "held"
    assert held.mailbox.files == {}


# Step 54(b): ten seconds an attempt, and every 5xx tried again ----------------------------


def test_every_attempt_has_ten_seconds_and_every_5xx_is_tried_again(operations_ledger):
    resend = Resend(503, 503, 503)
    mail(operations_ledger, resend).deliver(message())
    assert resend.options == [{"timeout": 10.0}] * 3
    for status in (500, 501, 505, 599):
        item, resend = message(), Resend(status, status, status)
        assert mail(operations_ledger, resend).deliver(item) == "held"
        assert [post["headers"]["Idempotency-Key"] for post in resend.posts] == (
            [item.message_key] * 3)
    unknown, throttled, slow = message(), message(), message()
    assert mail(operations_ledger, Resend(599, 599, 599)).deliver(unknown) == "held"
    assert state_of(operations_ledger, unknown) == "reserved"
    assert mail(operations_ledger, Resend(429, 429, 429)).deliver(throttled) == "held"
    assert state_of(operations_ledger, throttled) == "released"
    timeouts = Resend(*(httpx.ReadTimeout("slow") for _ in range(3)))
    assert mail(operations_ledger, timeouts).deliver(slow) == "held"
    assert len(timeouts.posts) == 3 and state_of(operations_ledger, slow) == "reserved"
    # An attempt still starts at 29.999 s; none starts at 30.0 s.
    inside = iter([0.0, 29.999, 29.999])
    late = Resend(httpx.ReadTimeout("slow"), httpx.ReadTimeout("slow"), 200)
    assert mail(operations_ledger, late, clock=lambda: next(inside)).deliver(
        message()) == "accepted"
    assert len(late.posts) == 3
    outside = iter([0.0, 30.0])
    cut = Resend(httpx.ReadTimeout("slow"), 200)
    assert mail(operations_ledger, cut, clock=lambda: next(outside)).deliver(
        message()) == "held"
    assert len(cut.posts) == 1
    assert account_mail.ATTEMPT_SECONDS == 10.0
    assert account_mail.TOTAL_SECONDS == 30.0
    assert account_mail.MAX_ATTEMPTS == 3


# Account mail at its limit, and while none can be sent (Step 54(j)-(m); L1-10, L1-53) -----


class RaiseOnly:
    """A client factory that must never be called; it records whether it was."""

    def __init__(self):
        self.called = False

    def __call__(self, **options):
        self.called = True
        raise AssertionError("no Resend client may be built")


def api_key() -> str:
    return "re_" + uuid4().hex  # generated per run (L1-36)


def resend_mail(allowance, *, gate=None, client_factory=None, **options) -> ResendAccountMail:
    return ResendAccountMail(
        api_key=api_key(), sender="DocSuri <mail@fixture.example.com>", origin=ORIGIN,
        allowance=allowance, gate=gate, recipients=Recipients(),
        client_factory=client_factory or RaiseOnly(), **options,
    )


def take(allowance, count: int) -> list:
    """Places taken with `reserve()` in a private ledger, never by sending."""
    return [allowance.reserve("account", str(uuid4())) for _ in range(count)]


def one_pass(entry, **options) -> None:
    """One pass of Step 53(h)'s sender over the test's entry, on the test's thread."""
    AccountMailSender(entry, **options).run_once()


def outbox(connect, key=None) -> list[dict]:
    """The outbox's rows, oldest first, or the one row under `key`."""
    with connect("accounts") as conn:
        if key is None:
            return conn.execute(
                "SELECT * FROM accounts.mail_outbox ORDER BY queued_at,message_key").fetchall()
        return conn.execute("SELECT * FROM accounts.mail_outbox WHERE message_key=%s",
                            (key,)).fetchall()


def unused_minute() -> dt.datetime:
    """A past minute of the test's own, so neither of D2's per-minute limits is shared with
    another test. It falls in 2020-2025, before any real run: a proof stamped from this
    clock (the forced reset's) is then never live in real time."""
    return EPOCH + dt.timedelta(minutes=uuid4().int % (6 * 365 * 24 * 60))


EPOCH = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)
ACCOUNT_READ = re.compile(r"accounts\.account\b")


def nobody() -> str:
    return f"nobody-{uuid4().hex[:16]}@fixture.example.com"


def flow() -> str:
    return "flow-" + uuid4().hex


def fresh_password() -> str:
    return "Synthetic-" + uuid4().hex[:12] + "-A1!"  # generated per run (L1-36)


def test_account_mail_at_its_limit_names_when_mail_can_be_sent_again(operations_ledger):
    moment = dt.datetime(2026, 11, 1, 14, 30, tzinfo=dt.UTC)
    holder = {}
    token = REFUSAL.set(holder)
    try:
        daily = AccountMailLimitReached("daily", now=moment)
    finally:
        REFUSAL.reset(token)
    assert isinstance(daily, Busy)
    assert daily.message_key == "account-mail.allowance-exhausted"
    assert daily.retry_after_seconds == 34200  # to 2026-11-02T00:00:00Z, 09:00 in Seoul
    assert holder == {"retryAfterSeconds": 34200}
    assert AccountMailLimitReached("monthly", now=moment).retry_after_seconds == 2539800
    last = dt.datetime(2026, 12, 31, 23, 59, 59, 500000, tzinfo=dt.UTC)
    assert AccountMailLimitReached("daily", now=last).retry_after_seconds == 1
    assert AccountMailLimitReached("monthly", now=last).retry_after_seconds == 1
    holder = {}
    token = REFUSAL.set(holder)
    try:
        late = AccountMailLimitReached(None, now=moment)
    finally:
        REFUSAL.reset(token)
    assert late.message_key == "account-mail.allowance-exhausted"
    assert late.retry_after_seconds is None and holder == {}
    assert REFUSAL.get() is None  # outside a request nothing is recorded
    with pytest.raises(ValueError):
        AccountMailLimitReached("weekly", now=moment)
    allowance = LedgerAllowance(operations_ledger, SYNTHETIC_OPERATIONS)
    factory = RaiseOnly()
    resend = resend_mail(allowance, client_factory=factory)
    local = LocalAccountMail(Mailbox(), allowance=allowance)
    take(allowance, 89)
    assert resend.limit_reached(str(uuid4())) is None
    assert local.limit_reached(str(uuid4())) is None
    take(allowance, 1)
    assert resend.limit_reached(str(uuid4())) == "daily"
    assert local.limit_reached(str(uuid4())) == "daily"
    assert not factory.called and local.mailbox.files == {}
    assert HeldAccountMail().limit_reached(str(uuid4())) is None
    assert LocalAccountMail(Mailbox()).limit_reached(str(uuid4())) is None


class Published:
    """The realm mailbox behind a pass-through recorder of the files it publishes."""

    def __init__(self, inner):
        self.inner, self.names = inner, []

    def publish(self, content: bytes):
        artifact = self.inner.publish(content)
        self.names.append(artifact.name)
        return artifact


class InjectedFault(RuntimeError):
    """The recorder's one fault, raised right after a chosen statement has run."""


class RecordingConnection:
    def __init__(self, conn, seen: list[str], owner=None):
        self._conn, self._seen, self._owner = conn, seen, owner

    def execute(self, query, *args, **kwargs):
        text = " ".join(str(query).split())
        self._seen.append(text)
        result = self._conn.execute(query, *args, **kwargs)
        owner = self._owner
        if owner is not None and owner.fail_after and owner.fail_after in text:
            owner.fail_after = None  # once
            raise InjectedFault("injected after " + text[:40])
        return result

    def __getattr__(self, name):
        return getattr(self._conn, name)


class Statements:
    """A pass-through recorder of the accounts transactions' statements, one list a run.
    With `fail_after` set, it raises once right after a statement holding that text has
    run, so the transaction rolls back (Step 54(n), (q))."""

    def __init__(self, inner):
        self.inner, self.runs = inner, []
        self.fail_after: str | None = None

    def run(self, owner, action):
        seen: list[str] = []
        self.runs.append(seen)
        return self.inner.run(
            owner, lambda conn: action(RecordingConnection(conn, seen, self)))

    def __getattr__(self, name):
        return getattr(self.inner, name)


@dataclasses.dataclass
class MailEntry:
    entry: CompleteControlEntryService
    mailbox: Published
    statements: Statements
    allowance: LedgerAllowance
    local: LocalAccountMail

    def refused(self, call, *args, error=AccountMailLimitReached):
        """One refused call: the refusal, its prepare's statements and every statement
        the call made."""
        before = len(self.statements.runs)
        with pytest.raises(error) as refusal:
            call(*args)
        runs = self.statements.runs[before:]
        return refusal.value, runs[-1], [item for seen in runs for item in seen]


def mail_entry(transactions, ledger, moment_clock, policy=U8_SYNTHETIC_POLICY) -> MailEntry:
    """Step 54(k)'s entry: a complete entry built as the conftest's `d1_entry` is, its
    account mail the realm mailbox behind a private ledger's allowance."""
    entry = CompleteControlEntryService(transactions, policy, clock=moment_clock)
    mailbox = Published(entry.mail)
    allowance = LedgerAllowance(ledger, SYNTHETIC_OPERATIONS)
    local = LocalAccountMail(mailbox, allowance=allowance)
    entry.account_mail = local
    statements = Statements(transactions)
    entry.transactions = statements
    return MailEntry(entry, mailbox, statements, allowance, local)


SIGNED_OUT = (
    ("request_password_reset", "password-reset"),
    ("request_verification", "verification"),
    ("request_reactivation", "reactivation"),
)


def nothing_written(connect, entry, kind: str, operation) -> bool:
    identifier, _, key = entry._mail_identity(kind, operation)
    with connect("accounts") as conn:
        return not any((
            conn.execute("SELECT 1 FROM accounts.mail_outbox WHERE message_key=%s",
                         (key,)).fetchone(),
            conn.execute("SELECT 1 FROM accounts.entry_receipt WHERE operation_id=%s",
                         (operation,)).fetchone(),
            conn.execute("SELECT 1 FROM accounts.control_proof WHERE id=%s",
                         (identifier,)).fetchone(),
            conn.execute("SELECT 1 FROM accounts.challenge WHERE id=%s",
                         (identifier,)).fetchone(),
        ))


def assert_refused_before_any_account_read(prepare: list[str], every: list[str]) -> None:
    assert len(prepare) == 1 and "accounts.entry_receipt" in prepare[0]
    assert not any(ACCOUNT_READ.search(statement) for statement in every)


def test_at_the_limit_every_mail_request_is_refused_before_any_account_read(
    transactions, connect, sign_in_account, own_address, operations_ledger, empty_outbox,
):
    _, email = sign_in_account("sign-in-member")
    limited = mail_entry(transactions, operations_ledger, Clock(unused_minute()))
    entry, allowance = limited.entry, limited.allowance
    take(allowance, 89)
    first, first_flow = uuid4(), flow()
    answered = entry.request_password_reset(first, email, first_flow)
    assert answered == entry._ack(first)
    # The reset answers and writes its outbox row (Step 53(h), L1-69); one sender pass
    # mails it once and takes the 90th place.
    _, _, first_key = entry._mail_identity("password-reset", first)
    assert len(outbox(connect, first_key)) == 1 and limited.mailbox.names == []
    one_pass(entry)
    assert len(limited.mailbox.names) == 1 and allowance.counts()["daily"] == 90
    assert outbox(connect) == []
    waits = set()
    for name, kind in SIGNED_OUT:
        for address in (email, nobody()):
            operation = uuid4()
            refusal, prepare, every = limited.refused(
                getattr(entry, name), operation, address, flow())
            waits.add(refusal.retry_after_seconds)
            assert_refused_before_any_account_read(prepare, every)
            assert nothing_written(connect, entry, kind, operation)
    assert len(waits) == 1 and None not in waits
    # The refused calls wrote no outbox row, and a sender pass after them sends nothing.
    one_pass(entry)
    assert len(limited.mailbox.names) == 1
    records = len(operations_ledger.records(KIND))
    # The reset answered at 89 replays its first answer and writes nothing new, and a
    # sender pass after the replay adds no file or reservation.
    assert entry.request_password_reset(first, email, first_flow) == answered
    assert outbox(connect) == []
    one_pass(entry)
    assert len(limited.mailbox.names) == 1
    assert len(operations_ledger.records(KIND)) == records

    class OnlyDeliver:
        def deliver(self, item):
            return limited.local.deliver(item)

    entry.account_mail = OnlyDeliver()
    operation = uuid4()
    assert entry.request_password_reset(operation, email, flow()) == entry._ack(operation)


def signed_in(entry, email: str) -> Authority:
    session = entry.login(email, SIGN_IN_PASSWORD, flow_binding="d1").public["session"]
    return Authority(UUID(session["accountId"]), UUID(session["sessionId"]))


class TakesLastPlace:
    """Passes through to the real account mail, but first takes a place with
    `reserve()`; with `release`, gives it back once `deliver()` returns."""

    def __init__(self, inner: LocalAccountMail, allowance, *, release: bool = False):
        self.inner, self.allowance, self.release = inner, allowance, release
        self.taken = []

    def deliver(self, item):
        reservation = self.allowance.reserve("account", str(uuid4()))
        self.taken.append(reservation)
        answer = self.inner.deliver(item)
        if self.release:
            self.allowance.release(reservation)
        return answer

    def limit_reached(self, key):
        return self.inner.limit_reached(key)

    def held_for_all(self):
        return self.inner.held_for_all()

    def artifact_of(self, key):
        return self.inner.artifact_of(key)


def email_change_refused(limited, authority, operation, new_email, flow_binding, *,
                         error=AccountMailLimitReached):
    return limited.refused(limited.entry.request_email_change, authority, operation,
                           SIGN_IN_PASSWORD, new_email, flow_binding, error=error)


def assert_change_prepare(prepare: list[str]) -> None:
    """The session guard, the caller's own account row and the receipt read: nothing is
    read by the new address."""
    assert len(prepare) == 3
    assert "accounts.guard_session" in prepare[0]
    assert ACCOUNT_READ.search(prepare[1]) and "WHERE id=" in prepare[1]
    assert "accounts.control_receipt" in prepare[2]
    assert not any("email=" in statement for statement in prepare)


def change_written(connect, entry, authority, operation) -> dict:
    identifier, _, key = entry._mail_identity("email-change", operation)
    with connect("accounts") as conn:
        return {
            "proof": conn.execute("SELECT 1 FROM accounts.control_proof WHERE id=%s",
                                  (identifier,)).fetchone() is not None,
            "receipt": conn.execute(
                "SELECT 1 FROM accounts.control_receipt WHERE account_id=%s AND "
                "kind='email-request' AND key=%s", (authority.account_id, operation),
            ).fetchone() is not None,
            "key": key,
        }


def test_a_signed_in_email_change_at_the_limit_is_refused_with_its_wait(
    transactions, connect, sign_in_account, own_address, operations_ledger, clock,
    empty_outbox,
):
    _, email = sign_in_account("sign-in-member")
    # The conftest's clock: a session's expiry is checked on the database's clock.
    limited = mail_entry(transactions, operations_ledger, clock)
    entry, allowance = limited.entry, limited.allowance
    authority = signed_in(entry, email)
    places = take(allowance, 90)
    waits = set()
    for new_email in (nobody(), nobody()):
        operation = uuid4()
        refusal, prepare, _ = email_change_refused(limited, authority, operation, new_email,
                                                   flow())
        waits.add(refusal.retry_after_seconds)
        assert_change_prepare(prepare)
        written = change_written(connect, entry, authority, operation)
        assert not written["proof"] and not written["receipt"]
        assert operations_ledger.get(KIND, reservation_id("account", written["key"])) is None
    assert len(waits) == 1 and None not in waits

    # With 89 taken, a place taken while the message is on its way: the daily wait.
    allowance.release(places[-1])
    assert allowance.counts()["daily"] == 89
    late = TakesLastPlace(limited.local, allowance)
    entry.account_mail = late
    daily_operation, daily_new, daily_flow = uuid4(), nobody(), flow()
    with pytest.raises(AccountMailLimitReached) as daily:
        entry.request_email_change(authority, daily_operation, SIGN_IN_PASSWORD, daily_new,
                                   daily_flow)
    assert daily.value.limit == "daily"
    assert daily.value.retry_after_seconds == AccountMailLimitReached(
        "daily", now=clock()).retry_after_seconds
    allowance.release(late.taken[-1])
    # When the place is given back before the second read, the refusal names no wait.
    entry.account_mail = TakesLastPlace(limited.local, allowance, release=True)
    freed_operation = uuid4()
    with pytest.raises(AccountMailLimitReached) as freed:
        entry.request_email_change(authority, freed_operation, SIGN_IN_PASSWORD, nobody(),
                                   flow())
    assert freed.value.limit is None and freed.value.retry_after_seconds is None
    for operation in (daily_operation, freed_operation):
        written = change_written(connect, entry, authority, operation)
        assert written["proof"] and not written["receipt"]  # the proof stays for a retry
    # A retry of the same operation with places free mails once and answers.
    entry.account_mail = limited.local
    before = len(limited.mailbox.names)
    assert entry.request_email_change(authority, daily_operation, SIGN_IN_PASSWORD,
                                      daily_new, daily_flow) == entry._ack(daily_operation)
    assert len(limited.mailbox.names) == before + 1


# Step 54(m): L1-53, "Refuse up front when held" -------------------------------------------


def test_only_a_hold_of_all_mail_is_read_up_front(operations_ledger):
    allowance = LedgerAllowance(operations_ledger, SYNTHETIC_OPERATIONS)
    mailbox = Mailbox()
    assert HeldAccountMail().held_for_all() is True
    for state in ("held", "unavailable"):
        assert resend_mail(allowance, gate=Gate(state)).held_for_all() is True
        assert LocalAccountMail(mailbox, allowance=allowance,
                                gate=Gate(state)).held_for_all() is True
    for gate in (Gate("active"), Gate("active", "rehearsal"), None):
        assert resend_mail(allowance, gate=gate).held_for_all() is False
        assert LocalAccountMail(mailbox, allowance=allowance, gate=gate,
                                recipients=Recipients()).held_for_all() is False
    assert operations_ledger.records(KIND) == [] and mailbox.files == {}
    assert gated(Gate("held"), None, message()) and gated(Gate("unavailable"), None, message())
    rehearsal = Gate("active", "rehearsal")
    assert gated(rehearsal, Recipients(), message(account=SOMEONE))
    assert not gated(rehearsal, Recipients(), message())
    assert not gated(None, None, message())
    unavailable = AccountMailUnavailable()
    assert isinstance(unavailable, Busy) and not isinstance(unavailable,
                                                            AccountMailLimitReached)
    assert unavailable.message_key == "account-mail.unavailable"
    assert unavailable.retry_after_seconds is None
    holder = {}
    token = REFUSAL.set(holder)
    try:
        AccountMailUnavailable()
    finally:
        REFUSAL.reset(token)
    assert holder == {} and REFUSAL.get() is None


class Observed:
    """An `observed_state` reader that answers a set state and counts its calls."""

    def __init__(self, state: str = "unavailable"):
        self.state, self.calls = state, 0

    def __call__(self) -> str:
        self.calls += 1
        return self.state


def test_an_observed_resend_outage_holds_all_mail_up_front(operations_ledger):
    allowance = LedgerAllowance(operations_ledger, SYNTHETIC_OPERATIONS)
    resend, reader = Resend(200), Observed()
    adapter = resend_mail(allowance, gate=Gate("active"), client_factory=resend,
                          observed_state=reader)
    assert adapter.held_for_all() is True
    for state in ("available", "degraded", "unknown", "stale"):
        reader.state = state
        assert adapter.held_for_all() is False
    assert resend_mail(allowance, gate=Gate("active"), client_factory=resend).held_for_all() \
        is False
    gated_first = Observed()
    assert resend_mail(allowance, gate=Gate("held"), client_factory=resend,
                       observed_state=gated_first).held_for_all() is True
    assert gated_first.calls == 0  # the gate is read first
    assert resend.posts == [] and operations_ledger.records(KIND) == []
    reader.state = "unavailable"
    calls = reader.calls
    assert adapter.deliver(message()) == "accepted"
    assert len(resend.posts) == 1 and reader.calls == calls  # only the check reads it


def holds(realm_mail: LocalAccountMail, allowance):
    """(m)'s four holds: each account mail and, for the outage, its raise-only factory."""
    outage_factory = RaiseOnly()
    return [
        ("held", LocalAccountMail(realm_mail.mailbox, allowance=allowance,
                                  gate=Gate("held")), None),
        ("unavailable", LocalAccountMail(realm_mail.mailbox, allowance=allowance,
                                         gate=Gate("unavailable")), None),
        ("unconfigured", HeldAccountMail(), None),
        ("outage", resend_mail(allowance, gate=Gate("active"), client_factory=outage_factory,
                               observed_state=Observed()), outage_factory),
    ]


def address_of_its_own() -> str:
    return f"198.19.{uuid4().int % 250 + 1}.{uuid4().int % 250 + 1}"


def test_while_all_mail_is_held_every_mail_request_is_refused_before_any_account_read(
    transactions, connect, sign_in_account, own_address, operations_ledger, empty_outbox,
):
    _, email = sign_in_account("sign-in-member")
    limited = mail_entry(transactions, operations_ledger, Clock(unused_minute()))
    entry, allowance = limited.entry, limited.allowance
    free_addresses: list[str] = []
    # A reset answered while the gate was active, and sent by one sender pass (Step
    # 53(h), L1-69).
    sent, sent_flow = uuid4(), flow()
    answered = entry.request_password_reset(sent, email, sent_flow)
    one_pass(entry)
    assert len(limited.mailbox.names) == 1 and outbox(connect) == []
    files, records = len(limited.mailbox.names), len(operations_ledger.records(KIND))
    try:
        for name, hold, factory in holds(limited.local, allowance):
            entry.account_mail = hold
            with client_address(address_of_its_own()):
                answers = {}
                for method, kind in SIGNED_OUT:
                    for who, address in (("member", email), ("unknown", nobody())):
                        operation = uuid4()
                        refusal, prepare, every = limited.refused(
                            getattr(entry, method), operation, address, flow(),
                            error=AccountMailUnavailable)
                        assert_refused_before_any_account_read(prepare, every)
                        assert nothing_written(connect, entry, kind, operation)
                        answers.setdefault(method, {})[who] = (
                            refusal.message_key, refusal.retry_after_seconds)
                for address in (email, nobody()):
                    free_addresses.append(address)
                    operation = uuid4()
                    refusal, prepare, every = limited.refused(
                        entry.register, operation, address, fresh_password(), "연구자",
                        flow(), error=AccountMailUnavailable)
                    assert_refused_before_any_account_read(prepare, every)
                    assert nothing_written(connect, entry, "registration", operation)
                    if address != email:  # checked before any clean-up (Step 54(m))
                        assert not account_exists(connect, address)
                if name == "outage":
                    for pair in answers.values():
                        assert pair["member"] == pair["unknown"] == (
                            "account-mail.unavailable", None)
                    assert not factory.called
                # The replay keeps its first answer, under the gate's hold and the outage,
                # with no new row.
                if name in ("held", "outage"):
                    assert entry.request_password_reset(sent, email, sent_flow) == answered
                    assert outbox(connect) == []
            assert len(limited.mailbox.names) == files
            assert len(operations_ledger.records(KIND)) == records
        # Only an observed `unavailable` refuses: stale and unknown give the built answer.
        outage = holds(limited.local, allowance)[-1][1]
        entry.account_mail = outage
        for state in ("stale", "unknown"):
            outage._observed_state.state = state
            operation = uuid4()
            assert entry.request_password_reset(operation, nobody(), flow()) == (
                entry._ack(operation))
        # The hold is read first: with 90 places taken it is never the limit's refusal.
        take(allowance, 90 - allowance.counts()["daily"])
        assert allowance.counts()["daily"] == 90
        entry.account_mail = holds(limited.local, allowance)[0][1]
        limited.refused(entry.request_password_reset, uuid4(), email, flow(),
                        error=AccountMailUnavailable)

        class DeliverOnly:
            def deliver(self, item):
                return "held"

        entry.account_mail = DeliverOnly()
        acknowledgements = []
        for address in (email, nobody()):
            operation = uuid4()
            acknowledgements.append(entry.request_password_reset(operation, address, flow()))
            assert acknowledgements[-1] == entry._ack(operation)
    finally:
        entry.account_mail = limited.local
        # Any account a refused registration wrote goes, its outbox rows first.
        for address in free_addresses[1::2]:
            delete_account(connect, address)
    for address in free_addresses[1::2]:
        assert not account_exists(connect, address)


def account_exists(connect, email: str) -> bool:
    with connect("accounts") as conn:
        return conn.execute("SELECT 1 FROM accounts.account WHERE email=%s",
                            (email,)).fetchone() is not None


def test_a_signed_in_email_change_fails_plainly_while_held_and_at_delivery(
    transactions, connect, sign_in_account, own_address, operations_ledger, clock,
    empty_outbox,
):
    _, email = sign_in_account("sign-in-member")
    _, other = sign_in_account("sign-in-migrated")
    limited = mail_entry(transactions, operations_ledger, clock)
    entry, allowance = limited.entry, limited.allowance
    authority = signed_in(entry, email)
    records = len(operations_ledger.records(KIND))
    outage = holds(limited.local, allowance)[-1][1]
    try:
        for hold in (LocalAccountMail(limited.mailbox, allowance=allowance, gate=Gate("held")),
                     outage):
            entry.account_mail = hold
            for new_email in (nobody(), other):
                operation = uuid4()
                refusal, prepare, _ = email_change_refused(
                    limited, authority, operation, new_email, flow(),
                    error=AccountMailUnavailable)
                assert refusal.retry_after_seconds is None
                assert_change_prepare(prepare)
                written = change_written(connect, entry, authority, operation)
                assert not written["proof"] and not written["receipt"]
        assert len(operations_ledger.records(KIND)) == records
        # The rehearsal bound holds the caller's message at delivery.
        entry.account_mail = LocalAccountMail(limited.mailbox, allowance=allowance,
                                              gate=Gate("active", "rehearsal"),
                                              recipients=Recipients())
        operation, new_email, change_flow = uuid4(), nobody(), flow()
        with pytest.raises(AccountMailUnavailable) as held:
            entry.request_email_change(authority, operation, SIGN_IN_PASSWORD, new_email,
                                       change_flow)
        assert held.value.retry_after_seconds is None
        written = change_written(connect, entry, authority, operation)
        assert written["proof"] and not written["receipt"]
        # Under the same rehearsal gate the signed-out reset keeps its acknowledgement.
        first, second = uuid4(), uuid4()
        member_answer = entry.request_password_reset(first, email, flow())
        unknown_answer = entry.request_password_reset(second, nobody(), flow())
        assert {**member_answer, "requestId": None} == {**unknown_answer, "requestId": None}
        # One sender pass under that gate keeps the member's row, held, and no file
        # reaches the mailbox (Step 53(h), L1-69).
        files = len(limited.mailbox.names)
        one_pass(entry)
        _, _, member_key = entry._mail_identity("password-reset", first)
        kept = outbox(connect, member_key)
        assert len(kept) == 1 and kept[0]["attempted_at"] is not None
        assert len(limited.mailbox.names) == files
        # A retry of the same change under an active gate mails once and answers.
        entry.account_mail = LocalAccountMail(limited.mailbox, allowance=allowance,
                                              gate=Gate("active"))
        files = len(limited.mailbox.names)
        assert entry.request_email_change(authority, operation, SIGN_IN_PASSWORD, new_email,
                                          change_flow) == entry._ack(operation)
        assert len(limited.mailbox.names) == files + 1
    finally:
        entry.account_mail = limited.local


# Step 54(n): L1-69, "Send from an outbox" ---------------------------------------------------


class RaiseDeliver:
    """An account mail whose `deliver` raises and that defines nothing else, so Step
    53(d)'s and (g)'s defaults let every request through; it records each call."""

    def __init__(self):
        self.calls = 0

    def deliver(self, item):
        self.calls += 1
        raise AssertionError("deliver may not be called")


class NoDeliver:
    """One of (m)'s holds, wrapped so that its `deliver` raises and is counted."""

    def __init__(self, inner):
        self.inner, self.calls = inner, 0

    def deliver(self, item):
        self.calls += 1
        raise AssertionError("deliver may not be called while held")

    def held_for_all(self):
        return self.inner.held_for_all()

    def limit_reached(self, key):
        return self.inner.limit_reached(key)


class Forwarding:
    """A recorder that forwards each message, and `artifact_of`, to the realm's mail."""

    def __init__(self, inner, *, hold_after_first=False, raise_hold_once=False):
        self.inner, self.messages = inner, []
        self.hold_after_first, self.raise_hold_once = hold_after_first, raise_hold_once
        self.held = False
        self.handed: dict[str, object] = {}
        self.on_deliver = None

    def deliver(self, item):
        if self.on_deliver is not None:
            self.on_deliver(item)
        self.messages.append(item)
        answer = self.inner.deliver(item)
        if self.hold_after_first:
            self.held = True
        event = self.handed.get(item.message_key)
        if event is not None:
            event.set()
        return answer

    def held_for_all(self):
        # Only the sender's thread meets the fault; the request's own up-front read
        # (Step 53(g)) passes.
        if self.raise_hold_once and threading.current_thread() is not threading.main_thread():
            self.raise_hold_once = False
            raise RuntimeError("the hold could not be read")
        return self.held

    def artifact_of(self, key):
        return self.inner.artifact_of(key)


@dataclasses.dataclass
class Mailed:
    """(n)'s setup: the entry, its clock and the reused and free addresses."""

    limited: MailEntry
    clock: Clock
    member: str
    unverified: str
    withdrawn: str
    free: str


def set_account(connect, email: str, assignments: str) -> None:
    with connect("accounts") as conn:
        conn.execute(f"UPDATE accounts.account SET {assignments} WHERE email=%s", (email,))


def withdraw(connect, email: str) -> None:
    """As the withdrawal writes it: inactive, withdrawn, both revisions new."""
    set_account(connect, email, "active=false,lifecycle_state='withdrawn',"
                                "authority_revision=gen_random_uuid(),"
                                "lifecycle_revision=gen_random_uuid()")


def delete_account(connect, email: str) -> None:
    """A test's own registered account, its outbox rows first; its counts go with it by
    the cascade."""
    with connect("accounts") as conn:
        row = conn.execute("SELECT id FROM accounts.account WHERE email=%s",
                           (email,)).fetchone()
        if row is None:
            return
        account = row["id"]
        conn.execute("DELETE FROM accounts.mail_outbox WHERE challenge_id IN (SELECT id FROM "
                     "accounts.challenge WHERE account_id=%s)", (account,))
        conn.execute("DELETE FROM accounts.delivery WHERE challenge_id IN (SELECT id FROM "
                     "accounts.challenge WHERE account_id=%s)", (account,))
        conn.execute("DELETE FROM accounts.challenge WHERE account_id=%s", (account,))
        conn.execute("DELETE FROM accounts.consent WHERE account_id=%s", (account,))
        conn.execute("DELETE FROM accounts.account WHERE id=%s", (account,))


@pytest.fixture
def mailed(transactions, connect, sign_in_account, own_address, operations_ledger,
           empty_outbox):
    """Step 54(n)'s setup: `sign-in-member`, a reused account made unverified and another
    set to withdrawn through the accounts owner's login, and a free address, on (k)'s
    entry and private ledger at a minute of the test's own. Each reused account is
    restored by `sign_in_account` afterwards, and the free address's account deleted."""
    _, member = sign_in_account("sign-in-member")
    _, unverified = sign_in_account("sign-in-migrated")
    _, withdrawn = sign_in_account("sign-in-admin")
    set_account(connect, unverified, "verified=false")
    withdraw(connect, withdrawn)
    moment = Clock(unused_minute())
    free = nobody()
    try:
        yield Mailed(mail_entry(transactions, operations_ledger, moment), moment, member,
                     unverified, withdrawn, free)
    finally:
        delete_account(connect, free)
        for suffix in ("sign-in-member", "sign-in-migrated", "sign-in-admin"):
            sign_in_account(suffix)


MAILED_KINDS = (
    # method, `_mail_identity` kind, proof table, the address attribute
    ("request_password_reset", "password-reset", "control_proof", "member"),
    ("request_verification", "verification", "challenge", "unverified"),
    ("request_reactivation", "reactivation", "control_proof", "withdrawn"),
)


REGISTER_PASSWORD = fresh_password()  # generated per run (L1-36)


def request(setup: Mailed, method: str, address: str, operation=None, binding=None):
    operation, binding = operation or uuid4(), binding or flow()
    entry = setup.limited.entry
    if method == "register":
        return operation, binding, entry.register(operation, address, REGISTER_PASSWORD,
                                                  "연구자", binding)
    return operation, binding, getattr(entry, method)(operation, address, binding)


def without_request(answer: dict) -> dict:
    return {key: value for key, value in answer.items() if key != "requestId"}


def xmin(conn, table: str, column: str, value) -> str:
    return conn.execute(f"SELECT xmin::text AS x FROM accounts.{table} WHERE {column}=%s",
                        (value,)).fetchone()["x"]


def built_payload(kind: str, identifier, proof: str, binding: str) -> dict:
    payload = {"challengeId": str(identifier), "proof": proof, "flowBinding": binding}
    if kind == "password-reset":
        payload["purpose"] = "password-reset"
    if kind == "reactivation":
        payload["purpose"] = "reactivate"
    return payload


def test_the_four_requests_write_their_row_in_the_proofs_transaction_and_never_call_deliver(
    mailed, connect,
):
    entry = mailed.limited.entry
    raising = RaiseDeliver()
    entry.account_mail = raising
    rows = {}
    for method, kind, table, who in MAILED_KINDS + (
        ("register", "registration", "challenge", "free"),
    ):
        address = getattr(mailed, who)
        operation, binding, answer = request(mailed, method, address)
        other_address = mailed.member if method == "register" else nobody()
        other, _, other_answer = request(mailed, method, other_address)
        assert answer == entry._ack(operation) and other_answer == entry._ack(other)
        assert without_request(answer) == without_request(other_answer)
        identifier, proof, key = entry._mail_identity(kind, operation)
        _, _, other_key = entry._mail_identity(kind, other)
        assert len(outbox(connect, key)) == 1 and outbox(connect, other_key) == []
        rows[key] = (kind, table, identifier, proof, binding, address, operation, method)
    assert raising.calls == 0
    assert len(outbox(connect)) == 4
    keys = list(rows)
    with connect("accounts") as conn:
        for index, (key, (kind, table, identifier, proof, binding, address, operation,
                          _method)) in enumerate(rows.items()):
            row = conn.execute("SELECT * FROM accounts.mail_outbox WHERE message_key=%s",
                               (key,)).fetchone()
            # One transaction: the row, its proof or challenge and its receipt.
            assert xmin(conn, "mail_outbox", "message_key", key) == xmin(
                conn, table, "id", identifier) == xmin(
                conn, "entry_receipt", "operation_id", operation)
            text = conn.execute("SELECT o::text AS t FROM accounts.mail_outbox o WHERE "
                                "message_key=%s", (key,)).fetchone()["t"]
            assert proof not in text and binding not in text
            value = bytes(row["protected_payload"])
            assert value.startswith(b"DSC2")
            assert row["key_version"] == entry.protection_version(value)
            for secret in (proof, binding, address):
                for form in (secret, secret.lower(), secret.upper()):
                    assert form.encode() not in value
                    assert form.lower().encode() not in value.lower()
            assert entry.reveal("account-mail:" + key, value) == built_payload(
                kind, identifier, proof, binding)
            with pytest.raises(InvalidTag):
                entry.reveal("account-mail:" + keys[(index + 1) % len(keys)], value)
    # A replay of each mailed operation answers its first answer and leaves no second row.
    for key, (_kind, _, _, _, binding, address, operation, method) in rows.items():
        _, _, replayed = request(mailed, method, address, operation, binding)
        assert replayed == entry._ack(operation)
        assert len(outbox(connect, key)) == 1
    assert len(outbox(connect)) == 4
    # A fault right after the outbox insert leaves nothing of that operation.
    statements = mailed.limited.statements
    statements.fail_after = "INSERT INTO accounts.mail_outbox"
    operation, binding = uuid4(), flow()
    with pytest.raises(InjectedFault):
        entry.request_password_reset(operation, mailed.member, binding)
    identifier, _, key = entry._mail_identity("password-reset", operation)
    assert nothing_written(connect, entry, "password-reset", operation)
    assert entry.request_password_reset(operation, mailed.member, binding) == entry._ack(
        operation)
    assert len(outbox(connect, key)) == 1


def delivered_file(entry, mailbox_names, email: str, purpose: str) -> dict:
    """A message's mailbox file, found as U2's `proof_for` finds it: an `accounts.delivery`
    row for a challenge, the proof's protected payload for a proof."""
    import json

    from backend.artifacts import Artifact
    from backend.local_profile import private_bytes

    def read(conn):
        if purpose == "verify":
            row = conn.execute(
                "SELECT d.* FROM accounts.delivery d JOIN accounts.challenge c ON "
                "c.id=d.challenge_id JOIN accounts.account a ON a.id=c.account_id WHERE "
                "a.email=%s AND NOT c.consumed AND c.expires_at>clock_timestamp() ORDER BY "
                "c.expires_at DESC,c.id DESC LIMIT 1", (email,)).fetchone()
            assert row is not None and row["private_path"] in mailbox_names
            return json.loads(entry.mail.read(Artifact(
                row["private_path"], row["content_hash"], row["byte_length"])))
        # Read as `proof_for` reads it (Step 54(n)): no live forced-reset proof is left on
        # these accounts, since unused_minute() stamps it in the past and the Step 54(q)
        # tests end theirs (end_forced_proofs).
        row = conn.execute(
            "SELECT p.* FROM accounts.control_proof p JOIN accounts.account a ON "
            "a.id=p.account_id WHERE a.email=%s AND p.purpose=%s AND p.consumed_at IS NULL "
            "AND p.expires_at>clock_timestamp() ORDER BY "
            "p.expires_at DESC,p.id DESC LIMIT 1", (email, purpose)).fetchone()
        assert row is not None
        name =entry.reveal("proof:" + str(row["id"]), row["protected_payload"])["delivery"]
        assert name in mailbox_names
        value = json.loads(private_bytes(entry.mail.root / name))
        assert value["challengeId"] == str(row["id"]) and value["purpose"] == purpose
        return value

    return entry.transactions.run("accounts", read)


ENDING_ORDER = (
    re.compile(r"FROM accounts\.account WHERE id=%s FOR NO KEY UPDATE"),
    re.compile(r"FROM accounts\.(challenge|control_proof) WHERE id=%s FOR (SHARE|NO KEY UPDATE)"),
    re.compile(r"DELETE FROM accounts\.mail_outbox WHERE message_key=%s"),
    re.compile(r"INSERT INTO accounts\.delivery|UPDATE accounts\.control_proof SET"),
)


def test_one_pass_sends_each_due_row_once_oldest_first_and_names_its_delivery(
    mailed, connect, operations_ledger,
):
    entry, limited = mailed.limited.entry, mailed.limited
    recorder = Forwarding(limited.local)
    entry.account_mail = recorder
    order = []
    for method, kind, _, who in MAILED_KINDS + (("register", "registration", None, "free"),):
        address = getattr(mailed, who)
        operation, _, _ = request(mailed, method, address)
        _, _, key = entry._mail_identity(kind, operation)
        order.append((key, address))
        mailed.clock.advance(1)
    before = len(limited.statements.runs)
    one_pass(entry)
    assert [(item.message_key, item.payload["email"]) for item in recorder.messages] == order
    assert len(limited.mailbox.names) == 4
    # Each ending transaction locks in SD2-01's order, as a take does: the account, then
    # its proof or challenge, then the row, and only then names the delivery.
    endings = [seen for seen in limited.statements.runs[before:] if any(
        "INSERT INTO accounts.delivery" in item
        or "UPDATE accounts.control_proof SET protected_payload" in item for item in seen)]
    assert len(endings) == 4
    for seen in endings:
        steps = [next(index for index, item in enumerate(seen) if pattern.search(item))
                 for pattern in ENDING_ORDER]
        assert steps == sorted(steps) and len(set(steps)) == 4, seen
    for key, _ in order:
        assert operations_ledger.get(KIND, reservation_id("account", key))["state"] == "settled"
    names = limited.mailbox.names
    assert delivered_file(entry, names, mailed.member, "password-reset")["email"] == (
        mailed.member)
    assert delivered_file(entry, names, mailed.withdrawn, "reactivate")["email"] == (
        mailed.withdrawn)
    assert delivered_file(entry, names, mailed.unverified, "verify")["email"] == (
        mailed.unverified)
    assert delivered_file(entry, names, mailed.free, "verify")["email"] == mailed.free
    assert outbox(connect) == []
    one_pass(entry)
    assert len(recorder.messages) == 4


def test_a_held_or_unknown_send_keeps_its_row_and_place_and_the_retry_reuses_its_key(
    mailed, connect, operations_ledger,
):
    entry, allowance = mailed.limited.entry, mailed.limited.allowance
    operation, _, _ = request(mailed, "request_password_reset", mailed.member)
    _, _, key = entry._mail_identity("password-reset", operation)
    # Unknown: three 503s, then the retry a minute later.
    resend = Resend(503, 503, 503, 200)
    entry.account_mail = resend_mail(allowance, gate=Gate("active"), client_factory=resend)
    one_pass(entry)
    assert [post["headers"]["Idempotency-Key"] for post in resend.posts] == [key] * 3
    assert len(outbox(connect, key)) == 1
    assert operations_ledger.get(KIND, reservation_id("account", key))["state"] == "reserved"
    one_pass(entry)
    assert len(resend.posts) == 3  # not yet RETRY_SECONDS later
    mailed.clock.advance(u8_mail_outbox.RETRY_SECONDS)
    one_pass(entry)
    assert [post["headers"]["Idempotency-Key"] for post in resend.posts] == [key] * 4
    assert operations_ledger.get(KIND, reservation_id("account", key))["state"] == "settled"
    assert len([record for record in operations_ledger.records(KIND)
                if record["messageKey"] == key]) == 1
    assert outbox(connect, key) == []
    # Held: the rehearsal bound holds the member's message.
    operation, _, _ = request(mailed, "request_password_reset", mailed.member)
    _, _, key = entry._mail_identity("password-reset", operation)
    answerless = Resend()
    entry.account_mail = resend_mail(allowance, gate=Gate("active", "rehearsal"),
                                     client_factory=answerless)
    one_pass(entry)
    assert len(outbox(connect, key)) == 1 and answerless.posts == []
    assert operations_ledger.get(KIND, reservation_id("account", key)) is None
    accepting = Resend(200)
    entry.account_mail = resend_mail(allowance, gate=Gate("active"), client_factory=accepting)
    mailed.clock.advance(u8_mail_outbox.RETRY_SECONDS)
    one_pass(entry)
    assert [post["headers"]["Idempotency-Key"] for post in accepting.posts] == [key]
    assert outbox(connect, key) == []


def age(connect, table: str, identifier) -> None:
    """A proof or challenge past its `expires_at`, as `ProviderStarts.retire` ages flows."""
    with connect("accounts") as conn:
        conn.execute(f"UPDATE accounts.{table} SET expires_at=clock_timestamp()-"
                     "interval '2 minutes' WHERE id=%s", (identifier,))


def test_a_row_whose_proof_has_expired_ends_unsent(mailed, connect, operations_ledger):
    entry, local = mailed.limited.entry, mailed.limited.local
    records = len(operations_ledger.records(KIND))

    def queue_aged() -> None:
        entry.account_mail = RaiseDeliver()
        reset, _, _ = request(mailed, "request_password_reset", mailed.member)
        verification, _, _ = request(mailed, "request_verification", mailed.unverified)
        age(connect, "control_proof", entry._mail_identity("password-reset", reset)[0])
        age(connect, "challenge", entry._mail_identity("verification", verification)[0])
        assert len(outbox(connect)) == 2

    queue_aged()
    raising = entry.account_mail
    one_pass(entry)
    assert outbox(connect) == [] and raising.calls == 0
    # Step 1 comes before the hold: held mail never keeps an aged row.
    for hold in (LocalAccountMail(local.mailbox, allowance=mailed.limited.allowance,
                                  gate=Gate("held")), HeldAccountMail()):
        queue_aged()
        wrapped = NoDeliver(hold)
        entry.account_mail = wrapped
        one_pass(entry)
        assert outbox(connect) == [] and wrapped.calls == 0
    assert len(operations_ledger.records(KIND)) == records


def test_a_row_whose_account_changed_ends_unsent(
    mailed, connect, operations_ledger, sign_in_account,
):
    entry = mailed.limited.entry
    raising = RaiseDeliver()
    entry.account_mail = raising
    records = len(operations_ledger.records(KIND))
    # (i) an email change's new authority revision.
    request(mailed, "request_password_reset", mailed.member)
    set_account(connect, mailed.member, "authority_revision=gen_random_uuid()")
    one_pass(entry)
    assert outbox(connect) == [] and raising.calls == 0
    # (ii) a withdrawal, as it writes the account.
    sign_in_account("sign-in-member")
    request(mailed, "request_password_reset", mailed.member)
    withdraw(connect, mailed.member)
    one_pass(entry)
    assert outbox(connect) == [] and raising.calls == 0
    assert len(operations_ledger.records(KIND)) == records


def test_a_new_sender_resumes_the_due_rows(mailed, connect, realm):
    from backend.transactions import OwnerTransactions

    entry, limited = mailed.limited.entry, mailed.limited
    keys = []
    for method, kind, _, who in MAILED_KINDS:
        operation, _, _ = request(mailed, method, getattr(mailed, who))
        keys.append(entry._mail_identity(kind, operation)[2])
        mailed.clock.advance(1)
    assert len(outbox(connect)) == 3
    other = OwnerTransactions(realm)
    try:
        restarted = CompleteControlEntryService(other, U8_SYNTHETIC_POLICY, clock=mailed.clock)
        recorder = Forwarding(limited.local)
        restarted.account_mail = recorder
        one_pass(restarted)
    finally:
        other.close()
    assert [item.message_key for item in recorder.messages] == keys
    assert outbox(connect) == []


# Step 54(o): the sender's hold, its failures and its thread (L1-69, L1-70) -------------------


def counts_folder(tmp_path, clock):
    from backend.u8_counts import ProcessCounts
    from backend.u8_policy import PRODUCTION_OPERATIONS

    folder = tmp_path / "evidence"
    counts = ProcessCounts(folder, "host", policy=PRODUCTION_OPERATIONS, clock=clock)
    return folder, counts, (lambda: counts.record("mail.sender", failed=True))


def sender_lines(folder) -> list[dict]:
    import json

    lines = []
    for path in sorted(folder.glob("*.jsonl")):
        lines += [json.loads(raw) for raw in path.read_text().splitlines() if raw.strip()]
    return [line for line in lines if line["kind"] == "mail.sender"]


def events(caplog, event: str) -> list[dict]:
    import json

    from backend.log_events import EVENTS_LOGGER

    found = [json.loads(record.getMessage()) for record in caplog.records
             if record.name == EVENTS_LOGGER]
    return [line for line in found if line.get("event") == event]


def test_a_pass_sends_nothing_while_all_mail_is_held(mailed, connect, operations_ledger):
    entry, limited = mailed.limited.entry, mailed.limited
    operation, _, _ = request(mailed, "request_password_reset", mailed.member)
    _, _, key = entry._mail_identity("password-reset", operation)
    before = outbox(connect, key)
    records = len(operations_ledger.records(KIND))
    for _, hold, factory in holds(limited.local, limited.allowance):
        wrapped = NoDeliver(hold)
        entry.account_mail = wrapped
        one_pass(entry)
        assert wrapped.calls == 0 and outbox(connect, key) == before
        assert before[0]["attempted_at"] is None
        assert factory is None or not factory.called
    assert len(operations_ledger.records(KIND)) == records
    entry.account_mail = limited.local
    one_pass(entry)
    assert len(limited.mailbox.names) == 1 and outbox(connect) == []


def test_the_hold_is_read_again_before_each_row(mailed, connect):
    entry, limited = mailed.limited.entry, mailed.limited
    keys = []
    for _ in range(2):
        operation, _, _ = request(mailed, "request_password_reset", mailed.member)
        keys.append(entry._mail_identity("password-reset", operation)[2])
        mailed.clock.advance(1)
    entry.account_mail = Forwarding(limited.local, hold_after_first=True)
    one_pass(entry)
    assert outbox(connect, keys[0]) == []
    second = outbox(connect, keys[1])
    assert len(second) == 1 and second[0]["attempted_at"] is None


def test_a_delivery_that_raises_is_logged_by_type_and_keeps_its_row(
    mailed, connect, caplog, tmp_path,
):
    import logging

    from backend.log_events import EVENTS_LOGGER

    entry, limited = mailed.limited.entry, mailed.limited
    caplog.set_level(logging.DEBUG, logger=EVENTS_LOGGER)
    operation, _, _ = request(mailed, "request_password_reset", mailed.member)
    _, proof, key = entry._mail_identity("password-reset", operation)
    secret = "secret-" + uuid4().hex  # generated per run (L1-36)

    class Raising:
        def deliver(self, item):
            raise RuntimeError(f"{item.payload['proof']} {item.payload['email']} {secret}")

    folder, counts, record = counts_folder(tmp_path, mailed.clock)
    entry.account_mail = Raising()
    one_pass(entry, record_failure=record)
    failed = events(caplog, "mail.failed")
    assert len(failed) == 1
    assert failed[0]["component"] == "accounts" and failed[0]["errorType"] == "RuntimeError"
    assert set(failed[0]) == {"ts", "level", "component", "event", "errorType", "location"}
    logged = "\n".join(record.getMessage() for record in caplog.records)
    for value in (proof, mailed.member, secret):
        assert value not in logged
    assert len(outbox(connect, key)) == 1
    # Once the test's clock has passed RETRY_SECONDS, the next pass tries it again.
    entry.account_mail = limited.local
    mailed.clock.advance(u8_mail_outbox.RETRY_SECONDS)
    one_pass(entry, record_failure=record)
    assert outbox(connect, key) == [] and len(limited.mailbox.names) == 1
    # A row the rehearsal bound holds records nothing.
    request(mailed, "request_password_reset", mailed.member)
    entry.account_mail = LocalAccountMail(limited.mailbox, allowance=limited.allowance,
                                          gate=Gate("active", "rehearsal"),
                                          recipients=Recipients())
    one_pass(entry, record_failure=record)
    assert len(outbox(connect)) == 1
    counts.close()
    lines = sender_lines(folder)
    assert sum(line["failed"] for line in lines) == 1
    assert sum(line["total"] for line in lines) == 1
    assert all(set(line) == {"failed", "kind", "total", "window"} for line in lines)


class IdleEvent(threading.Event):
    """The entry's `mail_waiting`, which sets `idle` each time the thread waits on it."""

    def __init__(self):
        super().__init__()
        self.idle = threading.Event()

    def wait(self, timeout=None):
        self.idle.set()
        return super().wait(timeout)


def test_the_thread_wakes_on_mail_waiting_and_stop_ends_it(
    mailed, connect, caplog, tmp_path,
):
    import asyncio
    import logging

    from backend.log_events import EVENTS_LOGGER

    assert u8_mail_outbox.WAKE_SECONDS == 10.0
    entry, limited = mailed.limited.entry, mailed.limited
    caplog.set_level(logging.DEBUG, logger=EVENTS_LOGGER)
    waiting = IdleEvent()
    entry.mail_waiting = waiting
    recorder = Forwarding(limited.local)
    beats = []

    def read_beat(item):
        with connect("accounts") as conn:
            beats.append(conn.execute(
                "SELECT beat_at FROM accounts.mail_sender_beat").fetchone())

    recorder.on_deliver = read_beat
    entry.account_mail = recorder
    folder, counts, record = counts_folder(tmp_path, mailed.clock)
    sender = AccountMailSender(entry, record_failure=record)
    u8_mail_outbox.WAKE_SECONDS = 3600
    release = threading.Event()

    def wake_with_reset() -> threading.Event:
        assert waiting.idle.wait(10)
        waiting.idle.clear()
        operation = uuid4()
        _, _, key = entry._mail_identity("password-reset", operation)
        handed = threading.Event()
        recorder.handed[key] = handed
        entry.request_password_reset(operation, mailed.member, flow())
        return handed

    try:
        sender.start()
        assert wake_with_reset().wait(10)
        assert beats and beats[0] is not None and beats[0]["beat_at"] is not None
        # A pass whose hold read raises: one `mail.pass-failed` line; the next request's
        # pass delivers its message.
        recorder.raise_hold_once = True
        missed = wake_with_reset()
        assert waiting.idle.wait(10)
        assert not missed.is_set()
        assert len(events(caplog, "mail.pass-failed")) == 1
        assert wake_with_reset().wait(10)
        assert missed.wait(10)
        # `stop()` joins the thread before it deletes the beat (Step 54(o); re-review of
        # 2026-11-09): the last delivery is held in flight while `stop()` runs on a helper
        # thread, so without the join the beat's delete would run before the row's.
        in_flight = threading.Event()

        def hold_delivery(item):
            in_flight.set()
            release.wait(10)

        recorder.on_deliver = hold_delivery
        last = wake_with_reset()
        assert in_flight.wait(10)
        thread = sender._thread
        before = len(limited.statements.runs)
        stopper = threading.Thread(target=lambda: asyncio.run(sender.stop()))
        stopper.start()
        assert sender._stopping.wait(10)
        release.set()
        stopper.join(10)
        assert not stopper.is_alive()
        assert last.is_set()
        runs = limited.statements.runs[before:]
        row_deletes = [index for index, seen in enumerate(runs) if any(
            text.startswith("DELETE FROM accounts.mail_outbox WHERE message_key") for text in seen)]
        beat_deletes = [index for index, seen in enumerate(runs) if any(
            text.startswith("DELETE FROM accounts.mail_sender_beat") for text in seen)]
        assert len(row_deletes) == 1 and len(beat_deletes) == 1, runs
        assert row_deletes[0] < beat_deletes[0], runs
        assert outbox(connect) == []
        assert thread is not None and not thread.is_alive()
        with connect("accounts") as conn:
            assert conn.execute("SELECT 1 FROM accounts.mail_sender_beat").fetchone() is None
        sender.run_once()
        with connect("accounts") as conn:
            assert conn.execute("SELECT 1 FROM accounts.mail_sender_beat").fetchone() is None
    finally:
        release.set()  # a failure never leaves a delivery held
        u8_mail_outbox.WAKE_SECONDS = 10.0
        asyncio.run(sender.stop())
    counts.close()
    lines = sender_lines(folder)
    assert sum(line["failed"] for line in lines) == 1
    assert sum(line["total"] for line in lines) == 1


# Step 54(q): L1-71, "Check first and cap daily" ---------------------------------------------


def reset_required_identity(entry, operation):
    """The forced reset's proof id and message key for one operation (first_sign_in)."""
    from uuid import NAMESPACE_URL, uuid5

    seed = entry.verifier("reset-required", str(operation))
    return (uuid5(NAMESPACE_URL, "docsuri-reset-required-proof:" + seed),
            str(uuid5(NAMESPACE_URL, "docsuri-reset-required-message:" + seed)))


def day_count(connect, email: str, day: int | None = None) -> int:
    with connect("accounts") as conn:
        rows = conn.execute(
            "SELECT l.day, l.messages FROM accounts.mail_account_limit l JOIN "
            "accounts.account a ON a.id=l.account_id WHERE a.email=%s", (email,)).fetchall()
    if day is None:
        return sum(row["messages"] for row in rows)
    return sum(row["messages"] for row in rows if row["day"] == day)


def forced_written(connect, entry, operation) -> dict:
    identifier, _ = reset_required_identity(entry, operation)
    with connect("accounts") as conn:
        return {
            "proof": conn.execute("SELECT 1 FROM accounts.control_proof WHERE id=%s",
                                  (identifier,)).fetchone() is not None,
            "receipt": conn.execute("SELECT 1 FROM accounts.entry_receipt WHERE "
                                    "operation_id=%s", (operation,)).fetchone() is not None,
        }


def forced(entry, email: str, operation) -> dict:
    return entry.login(email, "any-" + uuid4().hex, operation=operation,
                       flow_binding="d1").public


class CountingMail:
    def __init__(self, inner):
        self.inner, self.calls = inner, 0

    def deliver(self, item):
        self.calls += 1
        return self.inner.deliver(item)

    def __getattr__(self, name):
        return getattr(self.inner, name)


def test_a_forced_reset_while_mail_is_held_or_at_its_limit_answers_at_once(
    transactions, connect, sign_in_account, own_address, operations_ledger, empty_outbox,
    tmp_path, clock, forget_waits,
):
    _, email = sign_in_account("sign-in-member", reset_required=True)
    _, unverified = sign_in_account("sign-in-migrated", reset_required=True)
    # Its two refused sign-ins now each count a failure (Step 53(l)): removed afterwards,
    # so failures never add up across tests to a wait (Step 54(t)).
    forget_waits.append(unverified)
    set_account(connect, unverified, "verified=false")
    limited = mail_entry(transactions, operations_ledger, Clock(unused_minute()))
    entry, allowance = limited.entry, limited.allowance
    records = len(operations_ledger.records(KIND))
    try:
        for _, hold, factory in holds(limited.local, allowance):
            wrapped = NoDeliver(hold)
            entry.account_mail = wrapped
            with client_address(address_of_its_own()):
                operation = uuid4()
                answer = forced(entry, email, operation)
            _, key = reset_required_identity(entry, operation)
            assert answer == {"state": "reset_required", "delivery": "held", "messageKey": key}
            assert wrapped.calls == 0 and (factory is None or not factory.called)
            assert forced_written(connect, entry, operation) == {"proof": False,
                                                                 "receipt": False}
        assert day_count(connect, email) == 0
        assert len(operations_ledger.records(KIND)) == records
        # At the limit, with no hold: over_allowance, nothing written.
        take(allowance, 90)
        entry.account_mail = CountingMail(limited.local)
        operation = uuid4()
        _, key = reset_required_identity(entry, operation)
        assert forced(entry, email, operation) == {
            "state": "reset_required", "delivery": "over_allowance", "messageKey": key}
        assert entry.account_mail.calls == 0
        assert forced_written(connect, entry, operation) == {"proof": False, "receipt": False}
        assert day_count(connect, email) == 0
        # The same operation, retried over a fresh private ledger, mails once.
        folder = tmp_path / "fresh-ledger"
        folder.mkdir(mode=0o700)
        fresh = Ledger.open(folder, clock=clock)
        try:
            entry.account_mail = LocalAccountMail(
                limited.mailbox, allowance=LedgerAllowance(fresh, SYNTHETIC_OPERATIONS))
            assert forced(entry, email, operation)["delivery"] == "accepted"
            assert len(limited.mailbox.names) == 1
            assert forced_written(connect, entry, operation) == {"proof": True,
                                                                 "receipt": True}
            assert day_count(connect, email) == 1
        finally:
            fresh.close()
        # An account the forced reset's own checks refuse gets the unknown answer,
        # whatever the hold or the limit.
        for mail_now in (LocalAccountMail(limited.mailbox, allowance=allowance,
                                          gate=Gate("held")), limited.local):
            entry.account_mail = mail_now
            operation = uuid4()
            with pytest.raises(PermissionError, match="credentials unavailable"):
                forced(entry, unverified, operation)
            assert forced_written(connect, entry, operation) == {"proof": False,
                                                                 "receipt": False}
    finally:
        end_forced_proofs(connect, email, unverified)
        sign_in_account("sign-in-member")
        sign_in_account("sign-in-migrated")


def end_forced_proofs(connect, *emails: str) -> None:
    """Ends every forced-reset proof these reused accounts still hold. The forced reset
    stamps its proof's expiry from the entry's own clock, so a proof left behind could stay
    live on the realm and be taken for a later test's message."""
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.control_proof p SET expires_at=clock_timestamp() FROM "
            "accounts.account a WHERE a.id=p.account_id AND a.email=ANY(%s) AND "
            "p.purpose='password-reset' AND p.protected_payload IS NULL AND "
            "p.consumed_at IS NULL AND p.expires_at>clock_timestamp()", (list(emails),))


FIVE = dataclasses.replace(U8_SYNTHETIC_POLICY, account_mail_per_day=5)


def stored(connect, entry, kind: str, operation) -> bool:
    _, _, key = entry._mail_identity(kind, operation)
    return len(outbox(connect, key)) == 1


def test_each_signed_out_kind_and_the_forced_reset_stop_at_five_a_utc_day(
    transactions, connect, sign_in_account, own_address, operations_ledger, empty_outbox,
):
    from backend.modules.accounts.entry_limits import EntryLimits, day_of

    _, member = sign_in_account("sign-in-member")
    _, migrated = sign_in_account("sign-in-migrated")
    _, admin = sign_in_account("sign-in-admin")
    moment = Clock(unused_minute())
    limited = mail_entry(transactions, operations_ledger, moment, policy=FIVE)
    entry = limited.entry
    entry.account_mail = RaiseDeliver()
    free = nobody()
    days = []
    try:
        for method, kind, address, prepare in (
            ("request_password_reset", "password-reset", member, None),
            ("request_verification", "verification", migrated, "verified=false"),
            ("request_reactivation", "reactivation", admin, None),
        ):
            if prepare:
                set_account(connect, address, prepare)
            if method == "request_reactivation":
                withdraw(connect, address)
            days.append(day_of(moment()))
            with client_address(address_of_its_own()):
                operations = []
                for number in range(5):
                    if method == "request_password_reset" and number == 2:
                        # A fault right after the count's upsert: the count stays.
                        limited.statements.fail_after = "INSERT INTO accounts.mail_account_limit"
                        faulted, binding = uuid4(), flow()
                        with pytest.raises(InjectedFault):
                            entry.request_password_reset(faulted, address, binding)
                        assert day_count(connect, address, days[-1]) == 2
                        entry.request_password_reset(faulted, address, binding)
                        operations.append((faulted, binding))
                    else:
                        operation, binding, _ = request_for(entry, method, address)
                        operations.append((operation, binding))
                    assert stored(connect, entry, kind, operations[-1][0])
                    assert day_count(connect, address, days[-1]) == number + 1
                sixth, _, answer = request_for(entry, method, address)
                unknown, _, unknown_answer = request_for(entry, method, nobody())
                assert without_request(answer) == without_request(unknown_answer)
                assert nothing_written_but_receipt(connect, entry, kind, sixth)
                assert day_count(connect, address, days[-1]) == 5
                # A replay of a stored request answers its first answer.
                operation, binding = operations[0]
                assert getattr(entry, method)(operation, address, binding) == entry._ack(
                    operation)
                assert day_count(connect, address, days[-1]) == 5
                if method == "request_verification":
                    fifth = entry._mail_identity("verification", operations[-1][0])[0]
                    with connect("accounts") as conn:
                        assert conn.execute("SELECT consumed FROM accounts.challenge WHERE "
                                            "id=%s", (fifth,)).fetchone()["consumed"] is False
            moment.advance(86400)
        # A free address's registration counts 1 for the account it creates.
        with client_address(address_of_its_own()):
            entry.register(uuid4(), free, fresh_password(), "연구자", flow())
            assert day_count(connect, free) == 1
            results = [request_for(entry, "request_verification", free)[0] for _ in range(5)]
            assert [stored(connect, entry, "verification", op) for op in results] == [
                True] * 4 + [False]
        delete_account(connect, free)
        with connect("accounts") as conn:
            assert conn.execute("SELECT count(*) AS n FROM accounts.mail_account_limit l "
                                "LEFT JOIN accounts.account a ON a.id=l.account_id WHERE "
                                "a.id IS NULL").fetchone()["n"] == 0
        moment.advance(86400)
        # The forced reset's sixth sign-in of a day answers over_allowance.
        sign_in_account("sign-in-member", reset_required=True)
        counting = CountingMail(limited.local)
        entry.account_mail = counting
        with client_address(address_of_its_own()):
            for _ in range(5):
                assert forced(entry, member, uuid4())["delivery"] == "accepted"
            calls, records = counting.calls, len(operations_ledger.records(KIND))
            operation = uuid4()
            assert forced(entry, member, operation)["delivery"] == "over_allowance"
        assert counting.calls == calls and len(operations_ledger.records(KIND)) == records
        assert forced_written(connect, entry, operation) == {"proof": False, "receipt": False}
        # Finished days and an erased account's rows go at the next expiry pass.
        last = moment().date() + dt.timedelta(days=1)
        moment.now = dt.datetime.combine(last, dt.time(0, 0, 5), tzinfo=dt.UTC)
        sign_in_account("sign-in-member")
        sign_in_account("sign-in-migrated")
        entry.account_mail = RaiseDeliver()
        with client_address(address_of_its_own()):
            for address in (member, migrated):
                operation, _, _ = request_for(entry, "request_password_reset", address)
                assert stored(connect, entry, "password-reset", operation)
        today = day_of(moment())
        assert day_count(connect, member, today) == day_count(connect, migrated, today) == 1
        set_account(connect, migrated, "lifecycle_state='erased'")
        EntryLimits(transactions, FIVE.entry_limits).expire(now=moment())
        with connect("accounts") as conn:
            left = conn.execute(
                "SELECT a.email, l.day FROM accounts.mail_account_limit l JOIN "
                "accounts.account a ON a.id=l.account_id WHERE a.email=ANY(%s)",
                ([member, migrated, admin],)).fetchall()
        assert [(row["email"], row["day"]) for row in left] == [(member, today)]
    finally:
        end_forced_proofs(connect, member, migrated, admin)
        delete_account(connect, free)
        for suffix in ("sign-in-member", "sign-in-migrated", "sign-in-admin"):
            sign_in_account(suffix)


def request_for(entry, method: str, address: str):
    operation, binding = uuid4(), flow()
    return operation, binding, getattr(entry, method)(operation, address, binding)


def nothing_written_but_receipt(connect, entry, kind: str, operation) -> bool:
    """No proof, challenge or outbox row, with the receipt an unknown address gets."""
    identifier, _, key = entry._mail_identity(kind, operation)
    with connect("accounts") as conn:
        return conn.execute("SELECT 1 FROM accounts.entry_receipt WHERE operation_id=%s",
                            (operation,)).fetchone() is not None and not any((
            conn.execute("SELECT 1 FROM accounts.mail_outbox WHERE message_key=%s",
                         (key,)).fetchone(),
            conn.execute("SELECT 1 FROM accounts.control_proof WHERE id=%s",
                         (identifier,)).fetchone(),
            conn.execute("SELECT 1 FROM accounts.challenge WHERE id=%s",
                         (identifier,)).fetchone(),
        ))


def test_the_email_change_shares_the_count_and_is_refused_with_its_wait(
    transactions, connect, sign_in_account, own_address, operations_ledger, empty_outbox,
    clock,
):
    _, member = sign_in_account("sign-in-member")
    _, migrated = sign_in_account("sign-in-migrated")
    _, admin = sign_in_account("sign-in-admin")
    limited = mail_entry(transactions, operations_ledger, clock, policy=FIVE)
    entry, allowance = limited.entry, limited.allowance
    try:
        # The kinds share one count: three resets and two email changes, then no more.
        authority = signed_in(entry, member)
        for _ in range(3):
            assert stored(connect, entry, "password-reset",
                          request_for(entry, "request_password_reset", member)[0])
        for _ in range(2):
            operation = uuid4()
            assert entry.request_email_change(authority, operation, SIGN_IN_PASSWORD,
                                              nobody(), flow()) == entry._ack(operation)
        assert not stored(connect, entry, "password-reset",
                          request_for(entry, "request_password_reset", member)[0])
        # Five email changes mailed; the sixth waits to the next 00:00 UTC.
        authority = signed_in(entry, migrated)
        for _ in range(5):
            operation = uuid4()
            assert entry.request_email_change(authority, operation, SIGN_IN_PASSWORD,
                                              nobody(), flow()) == entry._ack(operation)
        holder = {}
        token = REFUSAL.set(holder)
        operation = uuid4()
        try:
            with pytest.raises(AccountMailLimitReached) as refusal:
                entry.request_email_change(authority, operation, SIGN_IN_PASSWORD, nobody(),
                                           flow())
        finally:
            REFUSAL.reset(token)
        wait = AccountMailLimitReached("daily", now=clock()).retry_after_seconds
        assert refusal.value.retry_after_seconds == wait
        assert holder == {"retryAfterSeconds": wait}
        written = change_written(connect, entry, authority, operation)
        assert not written["proof"] and not written["receipt"]
        # A late refusal's retry counts once, because its proof already exists.
        authority = signed_in(entry, admin)
        take(allowance, 89 - allowance.counts()["daily"])
        late = TakesLastPlace(limited.local, allowance)
        entry.account_mail = late
        operation, new_email, binding = uuid4(), nobody(), flow()
        with pytest.raises(AccountMailLimitReached):
            entry.request_email_change(authority, operation, SIGN_IN_PASSWORD, new_email,
                                       binding)
        assert day_count(connect, admin) == 1
        allowance.release(late.taken[-1])
        entry.account_mail = limited.local
        assert entry.request_email_change(authority, operation, SIGN_IN_PASSWORD, new_email,
                                          binding) == entry._ack(operation)
        assert day_count(connect, admin) == 1
    finally:
        entry.account_mail = limited.local
        for suffix in ("sign-in-member", "sign-in-migrated", "sign-in-admin"):
            sign_in_account(suffix)


def test_each_policy_holds_its_account_mail_limit():
    from backend.modules.accounts.u8_control_policy import PRODUCTION_POLICY

    assert PRODUCTION_POLICY.account_mail_per_day == 5
    assert U8_SYNTHETIC_POLICY.account_mail_per_day == 90
    with pytest.raises(ValueError):
        dataclasses.replace(PRODUCTION_POLICY, account_mail_per_day=6)
    with pytest.raises(ValueError):
        dataclasses.replace(U8_SYNTHETIC_POLICY, account_mail_per_day=91)


# Step 54(r): L1-73, "End refusals after one try" --------------------------------------------


def queued_reset(mailed, connect) -> str:
    entry = mailed.limited.entry
    held = entry.account_mail
    entry.account_mail = RaiseDeliver()
    operation, _, _ = request(mailed, "request_password_reset", mailed.member)
    entry.account_mail = held
    _, _, key = entry._mail_identity("password-reset", operation)
    assert len(outbox(connect, key)) == 1
    return key


def test_a_definite_refusal_ends_after_its_one_delivery(mailed, connect, operations_ledger):
    allowance = mailed.limited.allowance
    adapter = resend_mail(allowance, gate=Gate("active"), client_factory=Resend(422))
    item = message()
    assert adapter.deliver(item) == "held"
    assert state_of(operations_ledger, item) == "released"
    assert adapter.refused(item.message_key) is True
    assert adapter.refused(str(uuid4())) is False
    entry = mailed.limited.entry
    # 400 joins (r)'s 422 and 401 (Step 54(s), L1-84): only 408 and 409 became unknown.
    for status in (422, 401, 400):
        key = queued_reset(mailed, connect)
        resend = Resend(status)
        entry.account_mail = resend_mail(allowance, gate=Gate("active"), client_factory=resend)
        one_pass(entry)
        assert len(resend.posts) == 1 and outbox(connect, key) == []
        assert operations_ledger.get(KIND, reservation_id("account", key))["state"] == (
            "released")
        mailed.clock.advance(u8_mail_outbox.RETRY_SECONDS)
        one_pass(entry)
        assert len(resend.posts) == 1
    # A definite refusal stays final after an uncertain attempt too (Step 54(s)).
    key = queued_reset(mailed, connect)
    resend = Resend(httpx.ReadTimeout("slow"), 400)
    adapter = resend_mail(allowance, gate=Gate("active"), client_factory=resend)
    entry.account_mail = adapter
    one_pass(entry)
    assert len(resend.posts) == 2 and outbox(connect, key) == []
    assert operations_ledger.get(KIND, reservation_id("account", key))["state"] == "released"
    assert adapter.refused(key) is True


def test_a_throttled_or_unknown_send_keeps_its_retry(mailed, connect, operations_ledger):
    entry, allowance = mailed.limited.entry, mailed.limited.allowance
    key = queued_reset(mailed, connect)
    resend = Resend(429, 429, 429, 200)
    adapter = resend_mail(allowance, gate=Gate("active"), client_factory=resend)
    entry.account_mail = adapter
    one_pass(entry)
    assert len(resend.posts) == 3 and len(outbox(connect, key)) == 1
    assert operations_ledger.get(KIND, reservation_id("account", key))["state"] == "released"
    assert adapter.refused(key) is False
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.mail_outbox SET attempted_at=attempted_at-%s WHERE "
                     "message_key=%s",
                     (dt.timedelta(seconds=u8_mail_outbox.RETRY_SECONDS), key))
    one_pass(entry)
    assert [post["headers"]["Idempotency-Key"] for post in resend.posts] == [key] * 4
    assert operations_ledger.get(KIND, reservation_id("account", key))["state"] == "settled"
    assert outbox(connect, key) == []
    # An unknown outcome keeps its place even when 429s follow it under the same key
    # (D12): Resend may already hold the first send (review of 2026-11-09).
    # A 408 or a 409 leaves the send uncertain, as a 5xx does, at every attempt (Step
    # 54(s), L1-84): the later 429s cannot release its place.
    for answers in ((503, 503, 503), tuple(httpx.ReadTimeout("slow") for _ in range(3)),
                    (httpx.ReadTimeout("slow"), 429, 429), (503, 429, 429),
                    (httpx.ReadTimeout("slow"), 409, 409), (408, 429, 429), (409, 429, 429)):
        key = queued_reset(mailed, connect)
        resend = Resend(*answers)
        adapter = resend_mail(allowance, gate=Gate("active"), client_factory=resend)
        entry.account_mail = adapter
        one_pass(entry)
        assert [post["headers"]["Idempotency-Key"] for post in resend.posts] == [key] * 3
        assert len(outbox(connect, key)) == 1
        assert operations_ledger.get(KIND, reservation_id("account", key))["state"] == (
            "reserved")
        assert adapter.refused(key) is False
        assert adapter.reachable() is False


def test_the_remembered_outcomes_are_bounded(operations_ledger):
    assert account_mail.MAX_REMEMBERED == 256
    allowance = LedgerAllowance(operations_ledger, SYNTHETIC_OPERATIONS)
    account_mail.MAX_REMEMBERED = 2
    try:
        adapter = resend_mail(allowance, gate=Gate("active"),
                              client_factory=Resend(422, 422, 422))
        items = [message() for _ in range(3)]
        for item in items:
            assert adapter.deliver(item) == "held"
        assert [adapter.refused(item.message_key) for item in items] == [False, True, True]
    finally:
        account_mail.MAX_REMEMBERED = 256


def test_a_local_mailbox_row_held_by_the_rehearsal_bound_keeps_its_retry(
    mailed, connect, operations_ledger,
):
    entry, limited = mailed.limited.entry, mailed.limited
    key = queued_reset(mailed, connect)
    entry.account_mail = LocalAccountMail(limited.mailbox, allowance=limited.allowance,
                                          gate=Gate("active", "rehearsal"),
                                          recipients=Recipients())
    one_pass(entry)
    assert len(outbox(connect, key)) == 1 and limited.mailbox.names == []
    assert operations_ledger.get(KIND, reservation_id("account", key)) is None


def test_resend_reachability_stays_a_same_process_input(operations_ledger, clock):
    """No probe clears the adapter's flag (Step 56(a), L1-11): the probe is read first,
    and the passive check stays the second input."""
    from backend.modules.operations.producers import ProviderProducer
    from backend.u8_provider_probes import ProviderProbe

    adapter = mail(operations_ledger, Resend(httpx.ConnectError("refused"), 200))
    assert adapter.deliver(message()) == "held"
    assert adapter.reachable() is False
    passive = ProviderProducer("provider.resend", operations_ledger, reachable=adapter.reachable)
    observed = passive.observe(clock())
    assert (observed.outcome, observed.reason) == ("unavailable", "provider-unreachable")
    answered = []

    def resend_api(request):
        answered.append(request)
        return httpx.Response(401, json={"name": "missing_api_key"})

    probe = ProviderProbe("provider.resend", lambda **options: httpx.AsyncClient(
        transport=httpx.MockTransport(resend_api), **options))
    assert probe() is True  # the probe passes on its 401
    both = ProviderProducer("provider.resend", operations_ledger, reachable=adapter.reachable,
                            probe=probe)
    observed = both.observe(clock())
    assert (observed.outcome, observed.reason) == ("unavailable", "provider-unreachable")
    assert len(answered) == 2
    # An accepted send clears the flag; the next observation, with the probe, is available.
    assert adapter.deliver(message()) == "accepted"
    assert adapter.reachable() is True
    observed = both.observe(clock())
    assert (observed.outcome, observed.reason) == ("available", None)
    assert len(answered) == 3
