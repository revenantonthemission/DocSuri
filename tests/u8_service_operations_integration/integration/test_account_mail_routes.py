"""Every account email through the realm's account mail (U8 plan Step 21; A7, D12; the
person's decision of 2026-10-23): a password reset, an email verification and an email
change each send exactly one message of their own purpose through the realm's account
mail, under one allowance reservation; a retry of the same request reuses it and sends
nothing more. The account mail is the realm's local mailbox behind ServiceOperations'
allowance on a ledger of the test's own, as the composition wires it (`u8_host`).
"""

from __future__ import annotations

import datetime as dt
import threading
from uuid import uuid4

import httpx
import pytest

from backend.modules.accounts.integrations.account_mail import (
    AccountMessage,
    HeldAccountMail,
    LocalAccountMail,
    ResendAccountMail,
)
from backend.modules.accounts.local_http import ENTRY_POLICY
from backend.modules.operations.allowance import KIND, LedgerAllowance, reservation_id
from backend.u8_host import LIFECYCLE_MANIFEST, configure_lifecycle
from backend.u8_policy import SYNTHETIC_OPERATIONS
from tests.u8_service_operations_integration.conftest import (
    ORIGIN,
    SIGN_IN_PASSWORD,
    account_client,
    post,
)
from tests.u8_service_operations_integration.integration.test_account_routes import (
    csrf_of,
    mailed,
    member,  # noqa: F401 - the signed-in member fixture
    sender_pass,
)
from tests.u8_service_operations_integration.integration.test_first_sign_in import FixedGate
from tests.u8_service_operations_integration.integration.test_reactivation import (
    allowance_ledger,  # noqa: F401 - the entry's account mail behind an allowance
    mailbox_files,
)

# Step 85(j): no outbox row outlives its test (Step 54(n)'s `empty_outbox`).
pytestmark = pytest.mark.usefixtures("own_address", "empty_outbox")


class Recording:
    """The realm's account mail, recording each message it is handed. It forwards the
    up-front reads (Step 85(f), (h)): `limit_reached` (None when the mail it wraps has
    none), `held_for_all` (false when it has none), and `artifact_of` (None when it has
    none, as a Resend message names no file, Step 85(i))."""

    def __init__(self, inner):
        self.inner, self.messages = inner, []

    def deliver(self, message: AccountMessage) -> str:
        self.messages.append(message)
        return self.inner.deliver(message)

    def limit_reached(self, key):
        method = getattr(self.inner, "limit_reached", None)
        return method(key) if callable(method) else None

    def held_for_all(self) -> bool:
        method = getattr(self.inner, "held_for_all", None)
        return bool(callable(method) and method())

    def artifact_of(self, key):
        method = getattr(self.inner, "artifact_of", None)
        return method(key) if callable(method) else None


@pytest.fixture
def recorded(d1_entry, allowance_ledger):  # noqa: F811
    recording = Recording(d1_entry.account_mail)
    d1_entry.account_mail = recording
    return recording


def places(ledger, recording) -> list[str]:
    keys = {message.message_key for message in recording.messages}
    return [record["state"] for record in ledger.records(KIND) if record["messageKey"] in keys]


def test_a_password_reset_sends_one_message_and_a_retry_reuses_its_place(
    member, d1_entry, allowance_ledger, recorded,  # noqa: F811
):
    client, _, email = member
    before = mailbox_files(d1_entry)
    operation = uuid4()
    body = {"email": email, "policyRef": d1_entry.control_policy.reference}
    first = post(client, "/api/v2/c02/access-request-password-reset", body, csrf_of(client),
                 operation=operation)
    assert first.status_code == 200, first.text
    again = post(client, "/api/v2/c02/access-request-password-reset", body, csrf_of(client),
                 operation=operation)
    assert again.json() == first.json()
    sender_pass(d1_entry)  # the request answers before its message leaves (Step 85(j))
    assert [message.purpose for message in recorded.messages] == ["password-reset"]
    assert len(mailbox_files(d1_entry) - before) == 1
    assert places(allowance_ledger, recorded) == ["settled"]
    link = mailed(d1_entry, "password-reset", email)
    assert link["challengeId"] == recorded.messages[0].payload["challengeId"]
    # An unknown address gets the same answer and no message.
    unknown = post(client, "/api/v2/c02/access-request-password-reset", {
        "email": f"nobody-{uuid4().hex[:12]}@fixture.example.com",
        "policyRef": d1_entry.control_policy.reference}, csrf_of(client))
    assert {k: v for k, v in unknown.json().items() if k != "requestId"} == {
        k: v for k, v in first.json().items() if k != "requestId"}
    sender_pass(d1_entry)
    assert len(recorded.messages) == 1


def test_an_email_change_sends_one_message_to_the_new_address(
    member, d1_entry, allowance_ledger, recorded,  # noqa: F811
):
    client, authority, _ = member
    new_email = f"changed-{uuid4().hex[:12]}@fixture.example.com"
    body = {"currentProof": SIGN_IN_PASSWORD, "newEmail": new_email,
            "policyRef": d1_entry.control_policy.reference}
    operation = uuid4()
    first = post(client, "/api/v2/c02/access-request-email-change", body, csrf_of(client),
                 operation=operation)
    assert first.status_code == 200, first.text
    again = post(client, "/api/v2/c02/access-request-email-change", body, csrf_of(client),
                 operation=operation)
    assert again.json() == first.json()
    assert [(message.purpose, message.account_id) for message in recorded.messages] == [
        ("email-change", authority.account_id)]
    assert recorded.messages[0].payload["email"] == new_email
    assert places(allowance_ledger, recorded) == ["settled"]
    assert mailed(d1_entry, "email-change", new_email)["challengeId"] == (
        recorded.messages[0].payload["challengeId"])


def test_an_email_verification_sends_one_message_and_a_retry_reuses_its_place(
    d1_entry, allowance_ledger, recorded, sign_in_account, connect,  # noqa: F811
):
    import json

    authority, email = sign_in_account("sign-in-migrated")
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.account SET verified=false WHERE id=%s",
                     (authority.account_id,))
    try:
        flow, operation = str(uuid4()), uuid4()
        first = d1_entry.request_verification(operation, email, flow)
        assert d1_entry.request_verification(operation, email, flow) == first
        sender_pass(d1_entry)  # the request answers before its message leaves (Step 85(j))
        assert [message.purpose for message in recorded.messages] == ["verification"]
        assert places(allowance_ledger, recorded) == ["settled"]
        # The built mailbox row names the message's file for the realm's readers.
        with connect("accounts") as conn:
            row = conn.execute(
                "SELECT d.private_path FROM accounts.delivery d JOIN accounts.challenge c ON "
                "c.id=d.challenge_id WHERE c.account_id=%s AND NOT c.consumed",
                (authority.account_id,)).fetchone()
        sent = json.loads((d1_entry.mail.root / row["private_path"]).read_text())
        assert sent["challengeId"] == recorded.messages[0].payload["challengeId"]
        # A verified account gets the same answer and no message.
        with connect("accounts") as conn:
            conn.execute("UPDATE accounts.account SET verified=true WHERE id=%s",
                         (authority.account_id,))
        other = d1_entry.request_verification(uuid4(), email, flow)
        assert {k: v for k, v in other.items() if k != "requestId"} == {
            k: v for k, v in first.items() if k != "requestId"}
        sender_pass(d1_entry)
        assert len(recorded.messages) == 1
    finally:
        with connect("accounts") as conn:
            conn.execute("UPDATE accounts.account SET verified=true WHERE id=%s",
                         (authority.account_id,))


REGISTER_PASSWORD = f"Synthetic-Register-{uuid4().hex[:12]}-1!"  # per run (L1-36)


def test_a_registration_sends_its_verification_through_the_account_mail_once(
    d1_entry, allowance_ledger, recorded, connect, sign_in_account,  # noqa: F811
):
    """Registration's verification link (Step 21's `verification` purpose), whenever
    registration is open: one message under one place, a retry the same answer and no
    more mail, and an address already taken the same answer with no message at all."""
    _, taken = sign_in_account("sign-in-member")
    email = f"register-{uuid4().hex[:12]}@fixture.example.com"
    flow, operation = str(uuid4()), uuid4()
    created = None
    try:
        first = d1_entry.register(operation, email, REGISTER_PASSWORD, "합성 가입자", flow)
        assert d1_entry.register(operation, email, REGISTER_PASSWORD, "합성 가입자",
                                 flow) == first
        sender_pass(d1_entry)  # the request answers before its message leaves (Step 85(j))
        assert [message.purpose for message in recorded.messages] == ["verification"]
        assert recorded.messages[0].payload["email"] == email
        created = recorded.messages[0].account_id
        assert places(allowance_ledger, recorded) == ["settled"]
        with connect("accounts") as conn:
            row = conn.execute(
                "SELECT d.private_path FROM accounts.delivery d JOIN accounts.challenge c ON "
                "c.id=d.challenge_id WHERE c.account_id=%s", (created,)).fetchone()
        assert row is not None  # the realm's mailbox readers find it
        other = d1_entry.register(uuid4(), taken, REGISTER_PASSWORD, "합성 가입자", str(uuid4()))
        assert {k: v for k, v in other.items() if k != "requestId"} == {
            k: v for k, v in first.items() if k != "requestId"}
        sender_pass(d1_entry)
        assert len(recorded.messages) == 1
    finally:
        if created is None:
            # A failure before the message was read: the account is found by its address.
            with connect("accounts") as conn:
                row = conn.execute("SELECT id FROM accounts.account WHERE email=%s",
                                   (email,)).fetchone()
            created = None if row is None else row["id"]
        if created is not None:
            # The realm's account allocation is finite: the account goes again, its outbox
            # rows first (Step 85(j)).
            with connect("accounts") as conn:
                conn.execute("DELETE FROM accounts.mail_outbox WHERE challenge_id IN (SELECT id "
                             "FROM accounts.challenge WHERE account_id=%s)", (created,))
                conn.execute("DELETE FROM accounts.delivery WHERE challenge_id IN (SELECT id "
                             "FROM accounts.challenge WHERE account_id=%s)", (created,))
                conn.execute("DELETE FROM accounts.challenge WHERE account_id=%s", (created,))
                conn.execute("DELETE FROM accounts.consent WHERE account_id=%s", (created,))
                conn.execute("DELETE FROM accounts.account WHERE id=%s", (created,))


# Steps 85(f), (h) and (i): every mail request at the limit, while held, and before the
# send (L1-10, L1-53, L1-69) ------------------------------------------------------------

DAYS_EPOCH = dt.datetime(2020, 1, 1, 15, 0, tzinfo=dt.UTC)
SIGNED_OUT = {
    "password-reset": "/api/v2/c02/access-request-password-reset",
    "verification": "/api/v2/c02/access-request-verification",
    "reactivation": "/api/v2/c02/access-request-reactivation",
}
REFUSAL_KEYS = {"code", "requestId", "retryable", "messageKey"}


def own_day() -> dt.datetime:
    """15:00:00 UTC on a day of the test's own between 2020 and 2025, drawn as
    test_sign_in_limits.py draws its minutes: the next 00:00 UTC is 32400 s away."""
    return DAYS_EPOCH + dt.timedelta(days=uuid4().int % (6 * 365))


def generated_password() -> str:
    """A password that meets the password policy, generated per run (L1-36)."""
    return f"Synthetic-{uuid4().hex[:16]}-Aa1!"


def unknown() -> str:
    return f"nobody-{uuid4().hex[:12]}@fixture.example.com"


def free_address() -> str:
    return f"register-{uuid4().hex[:12]}@fixture.example.com"


def answer_shape(answer) -> dict:
    return {key: value for key, value in answer.json().items() if key != "requestId"}


def ask(client, entry, kind: str, email: str, operation):
    policy = ENTRY_POLICY if kind == "verification" else entry.control_policy.reference
    return post(client, SIGNED_OUT[kind], {"email": email, "policyRef": policy},
                csrf_of(client), operation=operation)


def register(client, email: str, operation):
    return post(client, "/api/v2/c02/access-register", {
        "email": email, "password": generated_password(), "displayName": "합성 가입자",
        "policyRef": ENTRY_POLICY}, csrf_of(client), operation=operation)


def change_email(client, entry, new_email: str, operation):
    return post(client, "/api/v2/c02/access-request-email-change", {
        "currentProof": SIGN_IN_PASSWORD, "newEmail": new_email,
        "policyRef": entry.control_policy.reference}, csrf_of(client), operation=operation)


def signed_out_requests(client, entry, mailed_to: dict, free: str) -> list[tuple]:
    """The reset, verification and reactivation requests, each for an address that would
    be mailed and for an unknown one, then the registration of a taken and a free address:
    `(kind, email, operation, answer)` each, the would-be-mailed address first."""
    made = []
    for kind in SIGNED_OUT:
        for email in (mailed_to[kind], unknown()):
            operation = uuid4()
            made.append((kind, email, operation, ask(client, entry, kind, email, operation)))
    for email in (mailed_to["registration"], free):
        operation = uuid4()
        made.append(("registration", email, operation, register(client, email, operation)))
    return made


def email_changes(client, entry, taken: str) -> list[tuple]:
    """The signed-in member's email change to a free and to a taken address."""
    made = []
    for email in (free_address(), taken):
        operation = uuid4()
        made.append(("email-change", email, operation,
                     change_email(client, entry, email, operation)))
    return made


def assert_pairs_equal(made: list[tuple]) -> None:
    """For each kind, the answers are equal apart from `requestId`."""
    kinds: dict[str, list] = {}
    for kind, _, _, answer in made:
        kinds.setdefault(kind, []).append(answer_shape(answer))
    for kind, shapes in kinds.items():
        assert len(shapes) == 2 and shapes[0] == shapes[1], (kind, shapes)


def assert_refused(answer, message_key: str, retry_after: str | None) -> None:
    assert answer.status_code == 429, answer.text
    body = answer.json()
    assert set(body) == REFUSAL_KEYS, body
    assert (body["code"], body["retryable"], body["messageKey"]) == (
        "RATE_LIMITED", True, message_key)
    assert answer.headers.get("retry-after") == retry_after


def message_key(entry, kind: str, operation) -> str:
    return entry._mail_identity(kind, operation)[2]


def rows_written(connect, entry, made: list[tuple]) -> list[tuple]:
    """Every outbox, proof, challenge, delivery and receipt row these operations wrote."""
    found = []
    with connect("accounts") as conn:
        for kind, _, operation, _ in made:
            identity, _, key = entry._mail_identity(kind, operation)
            checks = (
                ("mail_outbox", "SELECT 1 FROM accounts.mail_outbox WHERE message_key=%s",
                 key),
                ("control_proof", "SELECT 1 FROM accounts.control_proof WHERE id=%s",
                 identity),
                ("challenge", "SELECT 1 FROM accounts.challenge WHERE id=%s", identity),
                ("delivery", "SELECT 1 FROM accounts.delivery WHERE challenge_id=%s",
                 identity),
                ("entry_receipt", "SELECT 1 FROM accounts.entry_receipt WHERE "
                 "operation_id=%s", operation),
                ("control_receipt", "SELECT 1 FROM accounts.control_receipt WHERE key=%s",
                 operation),
            )
            for table, statement, value in checks:
                if conn.execute(statement, (value,)).fetchone():
                    found.append((table, kind, str(operation)))
    return found


def outbox_rows(connect) -> int:
    with connect("accounts") as conn:
        return conn.execute("SELECT count(*) AS n FROM accounts.mail_outbox").fetchone()["n"]


def accounts_with(connect, emails) -> list:
    with connect("accounts") as conn:
        return conn.execute("SELECT id FROM accounts.account WHERE email=ANY(%s)",
                            (list(emails),)).fetchall()


def delete_registered(connect, emails) -> None:
    """Accounts a registration wrote, deleted again, their outbox rows first (Step 85(j)):
    the realm's account allocation is finite."""
    for row in accounts_with(connect, emails):
        created = row["id"]
        with connect("accounts") as conn:
            conn.execute("DELETE FROM accounts.mail_outbox WHERE challenge_id IN (SELECT id "
                         "FROM accounts.challenge WHERE account_id=%s)", (created,))
            conn.execute("DELETE FROM accounts.delivery WHERE challenge_id IN (SELECT id "
                         "FROM accounts.challenge WHERE account_id=%s)", (created,))
            conn.execute("DELETE FROM accounts.challenge WHERE account_id=%s", (created,))
            conn.execute("DELETE FROM accounts.consent WHERE account_id=%s", (created,))
            conn.execute("DELETE FROM accounts.mail_account_limit WHERE account_id=%s",
                         (created,))
            conn.execute("DELETE FROM accounts.account WHERE id=%s", (created,))


def retire_proofs(connect, account_ids) -> None:
    """No outstanding proof or challenge outlives the test on a shared account."""
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.control_proof SET expires_at=clock_timestamp()-"
                     "interval '1 second' WHERE account_id=ANY(%s) AND consumed_at IS NULL "
                     "AND expires_at>clock_timestamp()", (list(account_ids),))
        conn.execute("UPDATE accounts.challenge SET expires_at=clock_timestamp()-"
                     "interval '1 second' WHERE account_id=ANY(%s) AND NOT consumed "
                     "AND expires_at>clock_timestamp()", (list(account_ids),))


def age_proofs(connect, entry, made: list[tuple]) -> None:
    """These operations' proofs aged past their `expires_at` through the accounts owner's
    login, as `ProviderStarts.retire` ages flows."""
    identities = [entry._mail_identity(kind, operation)[0] for kind, _, operation, _ in made]
    with connect("accounts") as conn:
        for table in ("control_proof", "challenge"):
            conn.execute(f"UPDATE accounts.{table} SET expires_at=clock_timestamp()-"
                         "interval '2 minutes' WHERE id=ANY(%s)", (identities,))


@pytest.fixture
def people(sign_in_account, connect):
    """Two reused accounts a request would mail: one made unverified (verification) and
    one set to withdrawn (reactivation), each restored afterwards. `retire` collects
    further accounts whose outstanding proofs end with the test."""
    unverified, unverified_email = sign_in_account("sign-in-migrated")
    withdrawn, withdrawn_email = sign_in_account("sign-in-admin")
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.account SET verified=false WHERE id=%s",
                     (unverified.account_id,))
        conn.execute("UPDATE accounts.account SET lifecycle_state='withdrawn',active=false "
                     "WHERE id=%s", (withdrawn.account_id,))
    retire = [unverified.account_id, withdrawn.account_id]
    try:
        yield {"verification": unverified_email, "reactivation": withdrawn_email,
               "retire": retire}
    finally:
        retire_proofs(connect, retire)
        sign_in_account("sign-in-migrated")
        sign_in_account("sign-in-admin")


def mailed_to(people, member_email: str) -> dict:
    return {"password-reset": member_email, "verification": people["verification"],
            "reactivation": people["reactivation"], "registration": member_email}


def test_account_mail_at_its_limit_fails_plainly_for_any_address(
    member, people, d1_entry, allowance_ledger, recorded, clock, connect,  # noqa: F811
):
    """L1-10 (Step 85(f)): at 90 account messages a day, every mail request is refused
    with the same plain notice for any address, naming the next 00:00 UTC."""
    client, authority, email = member
    people["retire"].append(authority.account_id)
    clock.now = own_day()
    allowance = LedgerAllowance(allowance_ledger, SYNTHETIC_OPERATIONS)
    for _ in range(89):
        allowance.reserve("account", str(uuid4()))
    before = mailbox_files(d1_entry)
    operation_k = uuid4()
    first = ask(client, d1_entry, "password-reset", email, operation_k)
    assert first.status_code == 200, first.text
    sender_pass(d1_entry)
    assert [message.purpose for message in recorded.messages] == ["password-reset"]
    assert places(allowance_ledger, recorded) == ["settled"]
    assert allowance.counts()["daily"] == 90
    again = ask(client, d1_entry, "password-reset", email, operation_k)
    assert again.json() == first.json()
    assert outbox_rows(connect) == 0  # no second row
    sender_pass(d1_entry)
    assert len(recorded.messages) == 1
    sent_k = mailbox_files(d1_entry) - before
    assert len(sent_k) == 1
    free = free_address()
    try:
        made = signed_out_requests(client, d1_entry, mailed_to(people, email), free)
        made += email_changes(client, d1_entry, people["verification"])
        for _, _, _, answer in made:
            assert_refused(answer, "account-mail.allowance-exhausted", "32400")
        assert_pairs_equal(made)
        sender_pass(d1_entry)
        assert mailbox_files(d1_entry) - before == sent_k
        assert len(recorded.messages) == 1
        assert rows_written(connect, d1_entry, made) == []
        assert outbox_rows(connect) == 0
        assert accounts_with(connect, [free, made[-2][1]]) == []
        assert allowance.counts()["daily"] == 90
        # The month's window, reached for real: 90 a day from the 1st to the 30th.
        for day in range(1, 31):
            clock.now = dt.datetime(2026, 10, day, 1, 0, tzinfo=dt.UTC)
            for _ in range(90):
                allowance.reserve("account", str(uuid4()))
        clock.now = dt.datetime(2026, 10, 30, 15, 0, tzinfo=dt.UTC)
        assert allowance.counts()["monthly"] == 2700 and allowance.counts()["daily"] == 90
        monthly = [ask(client, d1_entry, "password-reset", address, uuid4())
                   for address in (email, unknown())]
        for answer in monthly:
            # 2026-11-01T00:00:00Z, 09:00 in Seoul: the month's reset answers.
            assert_refused(answer, "account-mail.allowance-exhausted", "118800")
        assert answer_shape(monthly[0]) == answer_shape(monthly[1])
    finally:
        delete_registered(connect, [free])


class PlaceTaker:
    """An account mail whose `deliver` first takes the day's last place under a fresh key,
    as another process would, then hands the message on, then releases that place unless
    `keep`. It forwards `limit_reached` and `artifact_of` to the mail it wraps."""

    def __init__(self, inner, allowance, *, keep: bool = False):
        self.inner, self.allowance, self.keep = inner, allowance, keep
        self.messages, self.answers = [], []

    def deliver(self, message: AccountMessage) -> str:
        self.messages.append(message)
        taken = self.allowance.reserve("account", str(uuid4()))
        try:
            answer = self.inner.deliver(message)
        finally:
            if not self.keep:
                self.allowance.release(taken)
        self.answers.append(answer)
        return answer

    def limit_reached(self, key):
        return self.inner.limit_reached(key)

    def artifact_of(self, key):
        return self.inner.artifact_of(key)


def test_a_place_taken_between_the_check_and_delivery_keeps_the_signed_out_acknowledgements_and_refuses_the_email_change(  # noqa: E501
    member, people, d1_entry, allowance_ledger, clock, connect,  # noqa: F811
):
    """L1-10 (Step 85(f)): every request meets 89 at its check; the place is taken before
    its delivery, so the signed-out requests keep their acknowledgement and their rows end
    unsent, and the signed-in email change is refused."""
    client, authority, email = member
    people["retire"].append(authority.account_id)
    clock.now = own_day()
    allowance = LedgerAllowance(allowance_ledger, SYNTHETIC_OPERATIONS)
    for _ in range(89):
        allowance.reserve("account", str(uuid4()))
    inner = d1_entry.account_mail
    taker = PlaceTaker(inner, allowance)
    d1_entry.account_mail = taker
    before = mailbox_files(d1_entry)
    free = free_address()
    try:
        made = signed_out_requests(client, d1_entry, mailed_to(people, email), free)
        for _, _, _, answer in made:
            assert answer.status_code == 200, answer.text
        assert_pairs_equal(made)
        assert outbox_rows(connect) == 4  # the four mailed addresses' rows
        sender_pass(d1_entry)
        assert taker.answers == ["over_allowance"] * 4
        assert mailbox_files(d1_entry) == before
        for message in taker.messages:
            assert allowance_ledger.get(KIND, reservation_id(
                "account", message.message_key)) is None
        assert outbox_rows(connect) == 0
        changes = []
        for keep, retry_after in ((False, None), (True, "32400")):
            # The second wrapper differs from the first only in keeping the place it took.
            d1_entry.account_mail = PlaceTaker(inner, allowance, keep=keep)
            operation, new_email = uuid4(), free_address()
            answer = change_email(client, d1_entry, new_email, operation)
            assert_refused(answer, "account-mail.allowance-exhausted", retry_after)
            changes.append(("email-change", new_email, operation, answer))
        assert rows_written(connect, d1_entry, changes) == [
            ("control_proof", "email-change", str(operation))
            for _, _, operation, _ in changes]  # the proofs stay for a retry; no receipt
        assert mailbox_files(d1_entry) == before
    finally:
        delete_registered(connect, [free])


def test_while_account_mail_is_held_every_mail_request_fails_plainly_for_any_address(
    member, people, d1_entry, allowance_ledger, recorded, clock, connect,  # noqa: F811
):
    """L1-53 (Step 85(h)): under each of the four holds, every mail request is refused up
    front with the same plain notice and no wait, for any address."""
    client, authority, email = member
    people["retire"].append(authority.account_id)
    clock.now = own_day()
    allowance = LedgerAllowance(allowance_ledger, SYNTHETIC_OPERATIONS)
    before = mailbox_files(d1_entry)
    operation_k = uuid4()
    first = ask(client, d1_entry, "password-reset", email, operation_k)
    assert first.status_code == 200, first.text
    sender_pass(d1_entry)
    assert len(recorded.messages) == 1
    sent_k = mailbox_files(d1_entry) - before
    assert len(sent_k) == 1
    factory_calls = []

    def raise_only(**options):
        factory_calls.append(options)
        raise RuntimeError("no Resend client may be built here")

    outage = ResendAccountMail(
        api_key="re_" + uuid4().hex, sender="account@fixture.example.com", origin=ORIGIN,
        allowance=allowance, gate=FixedGate("active"), client_factory=raise_only,
        observed_state=lambda: "unavailable",
    )
    holds = [
        LocalAccountMail(d1_entry.mail, allowance=allowance, gate=FixedGate("held")),
        LocalAccountMail(d1_entry.mail, allowance=allowance, gate=FixedGate("unavailable")),
        HeldAccountMail(),
        outage,
    ]
    recordings, made_all, frees = [], [], []
    try:
        for hold in holds:
            clock.advance(60)  # a minute of its own: no hold meets D2's 20 per address
            recording = Recording(hold)
            recordings.append(recording)
            d1_entry.account_mail = recording
            frees.append(free_address())
            made = signed_out_requests(client, d1_entry, mailed_to(people, email), frees[-1])
            made += email_changes(client, d1_entry, people["verification"])
            for _, _, _, answer in made:
                assert_refused(answer, "account-mail.unavailable", None)
            assert_pairs_equal(made)
            retry = ask(client, d1_entry, "password-reset", email, operation_k)
            assert retry.json() == first.json()
            made_all += made
    finally:
        d1_entry.account_mail = recorded
        delete_registered(connect, frees)
    sender_pass(d1_entry)
    assert mailbox_files(d1_entry) - before == sent_k
    assert len(recorded.messages) == 1
    assert [recording.messages for recording in recordings] == [[]] * 4
    assert factory_calls == []
    assert rows_written(connect, d1_entry, made_all) == []
    assert outbox_rows(connect) == 0
    assert accounts_with(connect, frees) == []
    assert [record["messageKey"] for record in allowance_ledger.records(KIND)] == [
        message_key(d1_entry, "password-reset", operation_k)]


def test_a_message_held_at_delivery_keeps_the_signed_out_acknowledgements_and_refuses_the_email_change(  # noqa: E501
    member, people, d1_entry, allowance_ledger, clock, connect,  # noqa: F811
):
    """L1-53 (Step 85(h)): the up-front check passes, but the rehearsal bound holds every
    message at delivery: the signed-out requests keep their acknowledgement, their rows
    wait and then end unsent, and the email change is refused until mail can go."""
    client, authority, email = member
    people["retire"].append(authority.account_id)
    clock.now = own_day()
    allowance = LedgerAllowance(allowance_ledger, SYNTHETIC_OPERATIONS)
    rehearsal = Recording(LocalAccountMail(d1_entry.mail, allowance=allowance,
                                           gate=FixedGate("active", "rehearsal")))
    d1_entry.account_mail = rehearsal
    before = mailbox_files(d1_entry)
    free = free_address()
    try:
        made = signed_out_requests(client, d1_entry, mailed_to(people, email), free)
        for _, _, _, answer in made:
            assert answer.status_code == 200, answer.text
        assert_pairs_equal(made)
        sender_pass(d1_entry)
        assert len(rehearsal.messages) == 4  # each mailed row handed on once, and held
        assert outbox_rows(connect) == 4
        assert mailbox_files(d1_entry) == before
        assert allowance_ledger.records(KIND) == []
        age_proofs(connect, d1_entry, made)
        sender_pass(d1_entry)
        assert outbox_rows(connect) == 0
        assert mailbox_files(d1_entry) == before
        assert allowance_ledger.records(KIND) == []
        change_operation, new_email = uuid4(), free_address()
        refused = change_email(client, d1_entry, new_email, change_operation)
        assert_refused(refused, "account-mail.unavailable", None)
        change = [("email-change", new_email, change_operation, refused)]
        assert ("control_receipt", "email-change", str(change_operation)) not in (
            rows_written(connect, d1_entry, change))
        active = Recording(LocalAccountMail(d1_entry.mail, allowance=allowance,
                                            gate=FixedGate("active")))
        d1_entry.account_mail = active
        retried = change_email(client, d1_entry, new_email, change_operation)
        assert retried.status_code == 200, retried.text
        assert [message.purpose for message in active.messages] == ["email-change"]
        assert len(mailbox_files(d1_entry) - before) == 1
    finally:
        delete_registered(connect, [free])


class BlockingResend:
    """Resend's `/emails` through the adapter's client seam (shaped as
    component/test_account_mail.py's `Resend`): each post records its `Idempotency-Key`
    and recipient, sets `started`, then holds its thread on `release` (a bounded wait, so
    a fault fails the pass rather than hanging it), answers 200, and only then counts as
    completed. Holding the thread itself, no attempt bound can end a post first."""

    RELEASE_SECONDS = 30

    def __init__(self):
        self.started, self.release = threading.Event(), threading.Event()
        self.posts: list[tuple[str, str]] = []
        self.completed: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def __call__(self, **options):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, endpoint, *, headers, json):
        sent = (headers["Idempotency-Key"], json["to"][0])
        with self._lock:
            self.posts.append(sent)
        self.started.set()
        if not self.release.wait(self.RELEASE_SECONDS):
            raise AssertionError("the held post was never released")
        answer = httpx.Response(200, json={"id": str(uuid4())})
        with self._lock:
            self.completed.append(sent)
        return answer


def test_every_signed_out_mail_request_answers_before_any_send_completes(
    realm, d1_entry, allowance_ledger, people, sign_in_account, own_address,  # noqa: F811
    clock, connect,
):
    """L1-69 (Step 85(i)): while a send is held inside Resend, every signed-out mail
    request answers; order is asserted through events, never time."""
    member_authority, member_email = sign_in_account("sign-in-member")
    people["retire"].append(member_authority.account_id)
    clock.now = own_day()
    blocking = BlockingResend()
    allowance = LedgerAllowance(allowance_ledger, SYNTHETIC_OPERATIONS)
    recording = Recording(ResendAccountMail(
        api_key="re_" + uuid4().hex, sender="account@fixture.example.com", origin=ORIGIN,
        allowance=allowance, gate=FixedGate("active"), client_factory=blocking,
    ))
    previous, d1_entry.account_mail = d1_entry.account_mail, recording
    lifecycle = configure_lifecycle(d1_entry, LIFECYCLE_MANIFEST)
    free, held = free_address(), None
    try:
        with account_client(realm, d1_entry, lifecycle, address=own_address) as guest:
            operation_k = uuid4()
            first = ask(guest, d1_entry, "password-reset", member_email, operation_k)
            assert first.status_code == 200, first.text
            held = threading.Thread(target=sender_pass, args=(d1_entry,))
            held.start()
            assert blocking.started.wait(10)  # that pass is inside K's post
            made = signed_out_requests(guest, d1_entry, mailed_to(people, member_email),
                                       free)
            for _, _, _, answer in made:
                assert answer.status_code == 200, answer.text
            assert_pairs_equal(made)
            assert blocking.completed == []  # no answer waited on a send
        blocking.release.set()
        held.join(10)
        assert not held.is_alive()
        sender_pass(d1_entry)
        mailed = [(operation_k, "password-reset", member_email)] + [
            (operation, kind, email) for kind, email, operation, _ in made
            if email in (member_email, people["verification"], people["reactivation"], free)
            and not (kind == "registration" and email == member_email)]
        expected = sorted((message_key(d1_entry, kind, operation), email)
                          for operation, kind, email in mailed)
        assert len(expected) == 5
        assert sorted(blocking.completed) == expected
        assert sorted(blocking.posts) == expected  # nothing for unknown or taken addresses
        assert sorted(message.message_key for message in recording.messages) == [
            key for key, _ in expected]
        for key, _ in expected:
            assert allowance_ledger.get(KIND, reservation_id("account", key))[
                "state"] == "settled"
        assert outbox_rows(connect) == 0
    finally:
        blocking.release.set()  # first, so a failure never leaves the pass held
        if held is not None:
            held.join(10)
        d1_entry.account_mail = previous
        delete_registered(connect, [free])


# Step 85(k): the harness's `proof` waits for the served realm's sender (Step 96(j), L1-69)


def account_outbox_rows(connect, email: str) -> int:
    """The outbox rows of the account at `email`, through its challenges."""
    with connect("accounts") as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM accounts.mail_outbox o JOIN accounts.challenge c ON "
            "c.id=o.challenge_id JOIN accounts.account a ON a.id=c.account_id WHERE a.email=%s",
            (email,)).fetchone()["n"]


def test_the_harness_proof_waits_for_the_senders_delivery(
    d1_entry, allowance_ledger, connect, monkeypatch,  # noqa: F811
):
    """The harness reads only addresses `SYNTHETIC_EMAIL` accepts, so the test registers a
    free `<per-run hex>@example.com` through `d1_entry` under its own client address; the
    account is deleted afterwards, its outbox rows first."""
    from tests.u8_service_operations_integration import browser_harness
    from u2_browser_fixtures import proof_for

    assert browser_harness.PROOF_WAIT_SECONDS == 60  # the bound, as a literal
    email = f"{uuid4().hex[:16]}@example.com"
    flow = str(uuid4())
    try:
        d1_entry.register(uuid4(), email, generated_password(), "합성 가입자", flow)
        assert account_outbox_rows(connect, email) == 1  # the registration's row waits
        monkeypatch.setattr(browser_harness, "PROOF_WAIT_SECONDS", 0.4)
        with pytest.raises(browser_harness.HarnessRefused,
                           match="the account's mail was not sent within 60 s"):
            browser_harness.proof({"email": email, "purpose": "verify"})
        # One sender pass sends it: `proof` then answers at its first read, with no wait.
        sender_pass(d1_entry)
        assert account_outbox_rows(connect, email) == 0
        pauses = []
        original = browser_harness.pause

        def counted() -> None:
            pauses.append(1)
            return original()

        monkeypatch.setattr(browser_harness, "pause", counted)
        answer = browser_harness.proof({"email": email, "purpose": "verify"})
        expected = proof_for(d1_entry, email, "verify")
        assert answer == {key: expected[key] for key in ("challengeId", "flowBinding", "proof")}
        assert pauses == []
        # A verification request writes a second row. Both challenges are aged past their
        # expiry through the accounts owner's login; one pass ends the row unsent, and
        # `proof` answers at its first read with `proof_for`'s own refusal.
        d1_entry.request_verification(uuid4(), email, flow)
        assert account_outbox_rows(connect, email) == 1
        with connect("accounts") as conn:
            aged = conn.execute(
                "UPDATE accounts.challenge SET expires_at=clock_timestamp()-interval '1 second' "
                "WHERE account_id=(SELECT id FROM accounts.account WHERE email=%s)",
                (email,)).rowcount
        assert aged == 2
        sender_pass(d1_entry)
        assert account_outbox_rows(connect, email) == 0
        with pytest.raises(ValueError, match="fresh owned verification unavailable"):
            browser_harness.proof({"email": email, "purpose": "verify"})
        assert pauses == []
    finally:
        delete_registered(connect, [email])
