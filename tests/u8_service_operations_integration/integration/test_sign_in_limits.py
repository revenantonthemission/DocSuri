"""D2's sign-in limits and the provider sign-in starts' own limits (U8 plan Step 20 items
1-10; security-design § 3.2 and § 15 "Sign-in limits").

Three limits are checked and counted in one transaction before any password is checked:
20 attempts a minute per client address, a 15-minute wait for an email after 5 failed
sign-ins within 15 minutes (sign-in only), and 120 attempts a minute for everyone. A
refusal rolls back, so it moves no count.

Each test counts on a minute of its own: the entry service's injected clock is set to a
past minute no other test uses, so the realm's persistent counts never mix. The header
tests run a real Uvicorn host behind D7's boundary on 18109 and the public stand-in on
18110, which replaces any `CF-Connecting-IP` with the socket's peer, as Cloudflare does.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import ssl
import sys
import threading
import time
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest
import uvicorn
from docsuri_shared.workspace import wire
from fastapi import APIRouter
from fastapi.testclient import TestClient

from backend.local_browser import COMPLETE_ORIGIN, ENTRY_COOKIE, boundary_route
from backend.local_host import assemble
from backend.modules.accounts.entry_limits import (
    REFUSAL,
    UNKNOWN_ADDRESS,
    EntryLimited,
    address_key,
    client_address,
    minute_of,
)
from backend.modules.accounts.local_http import ENTRY_POLICY
from backend.modules.accounts.services.control_entry import ControlEntryService
from backend.modules.accounts.services.control_identity import (
    ControlIdentityService,
    FixtureIdentityProvider,
)
from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY
from backend.modules.accounts.u8_entry import CompleteControlEntryService
from backend.modules.accounts.u8_identity import (
    ArrivalIdentityService,
    IdentityStartLimited,
    expire_flows,
    start_bucket,
)
from backend.modules.accounts.u8_local_http import d1_account_router
from backend.production_boundary import (
    BoundaryHosts,
    BuildManifest,
    ProductionBoundary,
    server_config,
)
from backend.transactions import Busy, OwnerTransactions
from backend.u8_host import LIFECYCLE_MANIFEST, configure_lifecycle
from backend.u8_profile import listen_port
from docsuri_ops.local_transport import inspect_transport
from tests.u8_service_operations_integration.conftest import (
    ORIGIN,
    SIGN_IN_PASSWORD,
    Clock,
    account_client,
    post,
    provider_answer,
)
from tests.u8_service_operations_integration.integration.test_boundary import wait_port

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from u8_tunnel_standin import ACTIVE_FILE, TunnelStandin, set_route  # noqa: E402

EPOCH = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)
DIGEST = re.compile(r"[0-9a-f]{64}")


def unused_minute() -> dt.datetime:
    """A past minute of the test's own (2020 to 2028), at its first second."""
    return EPOCH + dt.timedelta(minutes=uuid4().int % (8 * 365 * 24 * 60))


def nobody() -> str:
    return f"nobody-{uuid4().hex[:16]}@fixture.example.com"


def fresh_address() -> str:
    """An IPv4 address of the test's own in 100.64.0.0/10, so no bucket is shared."""
    value = uuid4().int
    return f"100.{64 + value % 64}.{(value >> 8) % 256}.{(value >> 16) % 254 + 1}"


def generated_password() -> str:
    """A password that meets the password policy, generated per run (L1-36)."""
    return f"Synthetic-{uuid4().hex[:16]}-Aa1!"


@pytest.fixture
def entry(transactions):
    return CompleteControlEntryService(transactions, U8_SYNTHETIC_POLICY,
                                       clock=Clock(unused_minute()))


@pytest.fixture
def password_checks(entry, monkeypatch):
    """How many passwords the entry service checked."""
    calls = []
    checked = entry._matches_password

    def counted(encoded, password):
        calls.append(1)
        return checked(encoded, password)

    monkeypatch.setattr(entry, "_matches_password", counted)
    return calls


def counts(connect, entry, *, addresses=(), email=None) -> dict:
    """The stored counts at the entry clock's minute, read by keyed digest."""
    minute = minute_of(entry.clock())
    with connect("accounts") as conn:
        shared = conn.execute("SELECT attempts FROM accounts.entry_shared_limit WHERE "
                              "minute=%s", (minute,)).fetchone()
        result = {"shared": shared["attempts"] if shared else 0}
        for address in addresses:
            row = conn.execute(
                "SELECT attempts FROM accounts.entry_address_limit WHERE address_digest=%s "
                "AND minute=%s", (entry.verifier("entry-address", address), minute),
            ).fetchone()
            result[address] = row["attempts"] if row else 0
        if email is not None:
            row = conn.execute(
                "SELECT failures,wait_until FROM accounts.entry_email_failure WHERE "
                "email_digest=%s", (entry.verifier("entry-email", email),),
            ).fetchone()
            result["email"] = dict(row) if row else None
    return result


# A wrong password, generated per run (L1-36).
WRONG_PASSWORD = "wrong-" + uuid4().hex[:12]


def attempt(entry, email: str, password: str = WRONG_PASSWORD):
    """One sign-in attempt; the limit refusal, or None for any other outcome."""
    try:
        entry.login(email, password, flow_binding="limits")
    except EntryLimited as refused:
        return refused
    except PermissionError:
        return None
    return None


# 1. The 21st attempt from one address, before any password -------------------------------


def test_the_21st_attempt_from_one_address_is_refused_before_any_password(
    connect, entry, password_checks,
):
    address = "198.51.100.21"
    with client_address(address):
        assert all(attempt(entry, nobody()) is None for _ in range(20))
        assert len(password_checks) == 20
        refused = attempt(entry, nobody())
    assert refused is not None and refused.reason == "address-limit"
    assert 1 <= refused.retry_after_seconds <= 60
    assert len(password_checks) == 20  # the 21st reached no password check
    assert counts(connect, entry, addresses=[address]) == {"shared": 20, address: 20}


# 2. Five failures make an email wait, account or not --------------------------------------


def test_after_five_failures_an_email_waits_fifteen_minutes_with_or_without_an_account(
    connect, entry, sign_in_account, password_checks, forget_waits,
):
    _, member = sign_in_account("sign-in-member")
    absent = nobody()
    forget_waits.append(member)
    with client_address("198.51.100.22"):
        for email in (member, absent):
            assert all(attempt(entry, email) is None for _ in range(5))
        checked = len(password_checks)
        waits = [attempt(entry, member, SIGN_IN_PASSWORD), attempt(entry, absent)]
        assert len(password_checks) == checked  # refused before the password
        assert [type(item) for item in waits] == [EntryLimited, EntryLimited]
        assert {item.reason for item in waits} == {"email-wait"}
        assert waits[0].retry_after_seconds == waits[1].retry_after_seconds == 900
        for email in (member, absent):
            stored = counts(connect, entry, email=email)["email"]
            assert stored["failures"] == 5
            assert stored["wait_until"] == entry.clock() + dt.timedelta(minutes=15)
        entry.clock.advance(15 * 60 + 1)
        result = entry.login(member, SIGN_IN_PASSWORD, flow_binding="limits")
    assert result.public["state"] == "authenticated"


# 3. The 121st attempt within a minute is refused for everyone ----------------------------


def test_the_121st_attempt_within_a_minute_is_refused_for_everyone(
    connect, entry, password_checks,
):
    senders = [f"198.51.100.{30 + index}" for index in range(6)]
    for sender in senders:
        with client_address(sender):
            for _ in range(20):
                entry._admit()
    assert counts(connect, entry)["shared"] == 120
    with client_address("198.51.100.99"):
        refused = attempt(entry, nobody())
    assert refused is not None and refused.reason == "shared-limit"
    # Step 85(d): the entry's minute starts at its first second, so the wait is 60 s.
    assert refused.retry_after_seconds == 60
    assert password_checks == []
    assert counts(connect, entry, addresses=["198.51.100.99"]) == {
        "shared": 120, "198.51.100.99": 0}
    # In the same minute a reset request from a fresh address is refused for everyone too.
    fresh = fresh_address()
    with client_address(fresh), pytest.raises(EntryLimited) as shared:
        entry.request_password_reset(uuid4(), nobody(), "limits")
    assert shared.value.reason == "shared-limit"
    assert counts(connect, entry, addresses=[fresh]) == {"shared": 120, fresh: 0}
    # The next minute admits a fresh address again.
    entry.clock.advance(60)
    later = fresh_address()
    with client_address(later):
        entry._admit()
    assert counts(connect, entry, addresses=[later]) == {"shared": 1, later: 1}


# 4. A flood from one address leaves everyone else able to sign in -------------------------


def test_one_address_flooding_leaves_a_second_able_to_sign_in_and_refusals_count_nothing(
    connect, entry, sign_in_account,
):
    _, member = sign_in_account("sign-in-member")
    flooding, second = "198.51.100.40", "198.51.100.41"
    with client_address(flooding):
        refused = [attempt(entry, nobody()) for _ in range(200)]
    assert sum(item is None for item in refused) == 20
    assert {item.reason for item in refused if item is not None} == {"address-limit"}
    assert counts(connect, entry, addresses=[flooding]) == {"shared": 20, flooding: 20}
    with client_address(second):
        result = entry.login(member, SIGN_IN_PASSWORD, flow_binding="limits")
    assert result.public["state"] == "authenticated"
    assert counts(connect, entry, addresses=[flooding, second]) == {
        "shared": 21, flooding: 20, second: 1}


# Step 85(b). The 21st attempt from one address, for each entry operation ------------------


ENTRY_OPERATIONS = (
    "sign-in", "registration", "verification-request", "email-verification",
    "reset-request", "reset-completion", "reactivation-request",
)
# How each of the first 20 is answered right after admission, with no password hashed and
# no mail sent: an unknown address is acknowledged or refused, a blank display name and an
# unknown proof are refused.
FIRST_STATUS = {
    "sign-in": 403, "registration": 409, "verification-request": 200,
    "email-verification": 403, "reset-request": 200, "reset-completion": 422,
    "reactivation-request": 200,
}
PATHS = {
    "sign-in": "/api/v2/c02/access-login",
    "registration": "/api/v2/c02/access-register",
    "verification-request": "/api/v2/c02/access-request-verification",
    "email-verification": "/api/v2/c02/access-verify-email",
    "reset-request": "/api/v2/c02/access-request-password-reset",
    "reset-completion": "/api/v2/c02/access-complete-password-reset",
    "reactivation-request": "/api/v2/c02/access-request-reactivation",
}


def policy_failing_password() -> str:
    """A password the password policy refuses before any hashing (no upper-case letter
    and no symbol), generated per run (L1-36). Since your answer of 2026-11-11 the route
    answers it 422 `password.policy`."""
    return uuid4().hex


def entry_flow_of(client) -> str:
    """The client's own entry flow, the fourth field of its `docsuri_entry` cookie."""
    return client.cookies[ENTRY_COOKIE].split(".")[3]


def operation_body(case: str, entry, client, *, email: str | None, proof: dict) -> dict:
    """One attempt's body: `email` is None for the first 20 (an unknown address or a
    harmless refusal) and the address that would be checked, hashed or mailed for the
    21st."""
    last = email is not None
    address = email if last else nobody()
    if case in ("sign-in", "registration", "verification-request"):
        body = {"email": address, "policyRef": ENTRY_POLICY}
        if case == "sign-in":
            body["password"] = generated_password()
        if case == "registration":
            body |= {"password": generated_password(),
                     "displayName": "합성 가입자" if last else "   "}
        return body
    if case in ("reset-request", "reactivation-request"):
        return {"email": address, "policyRef": entry.control_policy.reference}
    verification = {**proof, "flowBinding": entry_flow_of(client)}
    if case == "email-verification":
        return {"verification": verification}
    return {"verification": verification,
            "newPassword": generated_password() if last else policy_failing_password()}


@pytest.fixture
def entry_calls(entry, monkeypatch):
    """What the entry did: each admission's refusal (or None), and how many passwords it
    checked, hashed and mailed."""
    calls = {"admit": [], "checked": 0, "hashed": 0, "mailed": 0}
    admit, checked, hashed = entry._admit, entry._matches_password, entry._hash_password
    deliver = entry.account_mail.deliver

    def recorded_admit(*args, **options):
        try:
            admit(*args, **options)
        except EntryLimited as refused:
            calls["admit"].append(refused)
            raise
        calls["admit"].append(None)

    def counted(name, inner):
        def call(*args):
            calls[name] += 1
            return inner(*args)
        return call

    monkeypatch.setattr(entry, "_admit", recorded_admit)
    monkeypatch.setattr(entry, "_matches_password", counted("checked", checked))
    monkeypatch.setattr(entry, "_hash_password", counted("hashed", hashed))
    monkeypatch.setattr(entry.account_mail, "deliver", counted("mailed", deliver))
    return calls


def outbox_rows(connect) -> int:
    with connect("accounts") as conn:
        return conn.execute("SELECT count(*) AS n FROM accounts.mail_outbox").fetchone()["n"]


def accounts_count(connect) -> int:
    with connect("accounts") as conn:
        return conn.execute("SELECT count(*) AS n FROM accounts.account").fetchone()["n"]


def the_21sts_address(case: str, connect, sign_in_account) -> str | None:
    """The reused account a 21st attempt would check, hash or mail; None where any
    address serves (sign-in, email verification and reset completion)."""
    if case in ("registration", "reset-request"):
        return sign_in_account("sign-in-member")[1]
    if case == "verification-request":
        authority, email = sign_in_account("sign-in-migrated")
        change = "verified=false"
    elif case == "reactivation-request":
        authority, email = sign_in_account("sign-in-admin")
        change = "lifecycle_state='withdrawn',active=false"
    else:
        return None
    with connect("accounts") as conn:
        conn.execute(f"UPDATE accounts.account SET {change} WHERE id=%s",
                     (authority.account_id,))
    return email


@pytest.mark.parametrize("case", ENTRY_OPERATIONS)
def test_the_21st_attempt_from_one_address_is_refused_for_each_entry_operation(
    realm, connect, entry, entry_calls, sign_in_account, case,
):
    lifecycle = configure_lifecycle(entry, LIFECYCLE_MANIFEST)
    first_address, second_address = fresh_address(), fresh_address()
    proof = {"challengeId": str(uuid4()), "proof": "unknown-proof-" + uuid4().hex}
    try:
        target = the_21sts_address(case, connect, sign_in_account)
        # Counted after the case's own account exists: `sign_in_account` creates it on
        # first use, which in a shorter file list (the security phase's) is this case.
        accounts_before = accounts_count(connect)
        with account_client(realm, entry, lifecycle, address=first_address) as client:
            csrf = client.get("/api/v2/session").json()["csrfToken"]
            for attempt_number in range(1, 21):
                answer = post(client, PATHS[case], operation_body(
                    case, entry, client, email=None, proof=proof), csrf)
                assert answer.status_code == FIRST_STATUS[case], answer.text
                assert "retry-after" not in answer.headers
                assert counts(connect, entry, addresses=[first_address])[
                    first_address] == attempt_number
            before = dict(entry_calls, admit=len(entry_calls["admit"]))
            outbox = outbox_rows(connect)
            refused = post(client, PATHS[case], operation_body(
                case, entry, client, email=target or nobody(), proof=proof), csrf)
        assert refused.status_code == 429, refused.text
        assert (refused.json()["code"], refused.json()["messageKey"]) == (
            "RATE_LIMITED", "request.rate_limited")
        assert refused.headers["retry-after"] == "60"
        assert len(entry_calls["admit"]) == before["admit"] + 1
        last = entry_calls["admit"][-1]
        assert isinstance(last, EntryLimited) and last.reason == "address-limit"
        for name in ("checked", "hashed", "mailed"):
            assert entry_calls[name] == before[name], name
        assert outbox_rows(connect) == outbox
        assert counts(connect, entry, addresses=[first_address]) == {
            "shared": 20, first_address: 20}
        with account_client(realm, entry, lifecycle, address=second_address) as other:
            other_csrf = other.get("/api/v2/session").json()["csrfToken"]  # bootstrap first
            answer = post(other, PATHS[case], operation_body(
                case, entry, other, email=None, proof=proof), other_csrf)
            assert answer.status_code == FIRST_STATUS[case], answer.text
        assert counts(connect, entry, addresses=[first_address, second_address]) == {
            "shared": 21, first_address: 20, second_address: 1}
        assert accounts_count(connect) == accounts_before
    finally:
        # Each changed account is restored (active, verified, its sessions ended).
        if case == "verification-request":
            sign_in_account("sign-in-migrated")
        elif case == "reactivation-request":
            sign_in_account("sign-in-admin")


# Step 85(c). Passwords are checked one at a time per process ------------------------------


class RecordingHasher:
    """A hasher whose every check and hash takes 0.05 s and records `[start, end]`."""

    def __init__(self):
        self.work, self._lock = [], threading.Lock()

    def _record(self) -> None:
        start = time.monotonic()
        time.sleep(0.05)
        end = time.monotonic()
        with self._lock:
            self.work.append([start, end])

    def verify(self, encoded, password) -> bool:
        self._record()
        return False

    def hash(self, password) -> str:
        self._record()
        return "recorded-hash"


def test_passwords_are_checked_one_at_a_time_per_process(connect, entry, transactions):
    assert "_credential_work" in vars(GuardedEntryService)
    for service in (ControlEntryService, CompleteControlEntryService):
        assert "_credential_work" not in vars(service)
    guarded = GuardedEntryService(transactions)  # both built first: each hashes its dummy
    assert entry._credential_work is guarded._credential_work
    assert guarded._credential_work.acquire(blocking=False)
    try:
        assert not entry._credential_work.acquire(blocking=False)
    finally:
        guarded._credential_work.release()
    hasher = RecordingHasher()
    entry.hasher = guarded.hasher = hasher
    barrier = threading.Barrier(9, timeout=5)
    results: dict[int, tuple] = {}
    addresses = [f"198.51.100.11{index}" for index in range(4)]

    def sign_in(address):
        with client_address(address):
            return entry.login(nobody(), generated_password(), flow_binding="limits")

    work = [lambda address=address: sign_in(address) for address in addresses]
    probe = generated_password()  # the probes are generated per run (L1-36)
    work += [lambda: guarded._matches_password(guarded._dummy, probe)] * 4
    work += [lambda: guarded._hash_password(probe)]

    def run(index, call):
        try:
            barrier.wait()
            results[index] = ("value", call())
        except BaseException as error:  # noqa: BLE001 - every outcome is asserted below
            results[index] = ("error", error)

    threads = [threading.Thread(target=run, args=(index, call))
               for index, call in enumerate(work)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)
    assert not any(thread.is_alive() for thread in threads)
    spans = sorted(hasher.work)
    assert len(spans) == 9
    assert all(earlier[1] <= later[0] for earlier, later in zip(spans, spans[1:], strict=False))
    assert spans[-1][1] - spans[0][0] >= 0.45
    for index in range(4):
        kind, error = results[index]
        assert kind == "error" and type(error) is PermissionError, results[index]
        assert str(error) == "credentials unavailable"
    assert [results[index] for index in range(4, 8)] == [("value", False)] * 4
    assert results[8] == ("value", "recorded-hash")
    assert counts(connect, entry, addresses=addresses) == {
        "shared": 4, **{address: 1 for address in addresses}}


# Step 85(d). A password check that waits over 2 s gets the plain busy answer --------------


def test_a_password_check_that_waits_over_two_seconds_gets_the_plain_busy_answer(
    realm, entry,
):
    direct, served = fresh_address(), fresh_address()
    login = {"email": nobody(), "password": generated_password(), "policyRef": ENTRY_POLICY}
    work = GuardedEntryService._credential_work
    with account_client(realm, entry, address=served) as client:
        csrf = client.get("/api/v2/session").json()["csrfToken"]  # bootstraps first
        assert work.acquire(blocking=False)
        try:
            outcomes: dict[str, tuple] = {}

            def in_process():
                started = time.monotonic()
                try:
                    with client_address(direct):
                        entry.login(nobody(), generated_password(), flow_binding="limits")
                    outcomes["direct"] = (None, time.monotonic() - started)
                except BaseException as error:  # noqa: BLE001 - asserted below
                    outcomes["direct"] = (error, time.monotonic() - started)

            def over_http():
                started = time.monotonic()
                answer = post(client, "/api/v2/c02/access-login", login, csrf)
                outcomes["http"] = (answer, time.monotonic() - started)

            threads = [threading.Thread(target=in_process), threading.Thread(target=over_http)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(5)
            assert not any(thread.is_alive() for thread in threads)
            error, elapsed = outcomes["direct"]
            assert type(error) is Busy, error
            assert str(error) == "local credential work allocation exhausted"
            assert 2.0 <= elapsed < 2.6, elapsed
            answer, elapsed = outcomes["http"]
            assert answer.status_code == 429, answer.text
            body = answer.json()
            assert (body["code"], body["messageKey"], body["retryable"]) == (
                "RATE_LIMITED", "request.rate_limited", True)
            assert answer.headers.get_list("cache-control") == ["no-store"]
            assert "retry-after" not in answer.headers
            assert 1.9 <= elapsed < 3.0, elapsed
            assert not work.acquire(blocking=False)  # the failed waits released nothing
        finally:
            work.release()
        reached = post(client, "/api/v2/c02/access-login", login, csrf)
    assert (reached.status_code, reached.json()["code"]) == (403, "FORBIDDEN")


# 5 and 6. The address a request counts under, through the public stand-in ------------------


@pytest.fixture(scope="module")
def served(realm):
    transactions = OwnerTransactions(realm)
    entry = CompleteControlEntryService(transactions, U8_SYNTHETIC_POLICY,
                                        clock=Clock(unused_minute()))
    boundary = ProductionBoundary(BoundaryHosts.for_profile(realm),
                                  BuildManifest.empty(realm.root), context=None)
    app = assemble(realm, routers=(d1_account_router(entry),), boundary=boundary)
    server = uvicorn.Server(server_config(app, listen_port(realm), log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    wait_port(listen_port(realm))
    set_route(realm, "v2-host")
    standin = TunnelStandin(realm)
    certificate = inspect_transport(realm).certificate
    try:
        with standin.running():
            yield entry, ssl.create_default_context(cafile=str(certificate))
    finally:
        server.should_exit = True
        thread.join(15)
        (realm.root / ACTIVE_FILE).unlink(missing_ok=True)
        transactions.close()


def sign_in_over(client, headers: dict) -> httpx.Response:
    """Bootstrap, then one wrong sign-in. The entry cookie is carried explicitly: it is
    `Secure`, and the loopback requests run over plain HTTP to the host."""
    bootstrap = client.get("/api/v2/session", headers=headers)
    csrf = bootstrap.json()["csrfToken"]
    cookie = next(value.split(";", 1)[0] for value in bootstrap.headers.get_list("set-cookie")
                  if value.startswith("docsuri_entry="))
    client.cookies.clear()
    return client.post(
        "/api/v2/c02/access-login",
        json={"email": nobody(), "password": WRONG_PASSWORD, "policyRef": ENTRY_POLICY},
        headers={**headers, "origin": ORIGIN, "x-csrf-token": csrf, "cookie": cookie,
                 "idempotency-key": str(uuid4())},
    )


def test_a_forged_connecting_address_through_the_standin_counts_under_its_peer(
    connect, served,
):
    entry, context = served
    forged = "203.0.113.50"
    before = counts(connect, entry, addresses=["127.0.0.1", forged])
    with httpx.Client(base_url="https://127.0.0.1:18110", verify=context, timeout=15) as client:
        for _ in range(2):
            answer = sign_in_over(client, {"cf-connecting-ip": forged})
            assert answer.status_code == 403, answer.text  # credentials unavailable
    after = counts(connect, entry, addresses=["127.0.0.1", forged])
    assert after["127.0.0.1"] == before["127.0.0.1"] + 2
    assert after[forged] == before[forged] == 0


def test_a_missing_or_malformed_header_lands_in_the_unknown_bucket(connect, served):
    entry, _ = served
    before = counts(connect, entry, addresses=[UNKNOWN_ADDRESS])
    public = {"host": "127.0.0.1:18110"}
    with httpx.Client(base_url="http://127.0.0.1:18109", timeout=15) as client:
        for extra in ({}, {"cf-connecting-ip": "not-an-address"},
                      {"cf-connecting-ip": "203.0.113.7, 203.0.113.8"}):
            answer = sign_in_over(client, {**public, **extra})
            assert answer.status_code == 403, answer.text
    after = counts(connect, entry, addresses=[UNKNOWN_ADDRESS])
    assert after[UNKNOWN_ADDRESS] == before[UNKNOWN_ADDRESS] + 3


def test_the_address_key_reads_one_parsed_header_on_the_public_origin_only():
    assert address_key(["203.0.113.9"], public=True, peer="127.0.0.1") == "203.0.113.9"
    for values in ([], ["203.0.113.9", "203.0.113.10"], [""], [" 203.0.113.9"],
                   ["203.0.113.9, 198.51.100.1"], ["x" * 65], ["999.1.1.1"]):
        assert address_key(values, public=True, peer="127.0.0.1") == UNKNOWN_ADDRESS
    # A loopback-origin request counts by its socket peer, whatever it claims.
    assert address_key(["203.0.113.9"], public=False, peer="127.0.0.1") == "127.0.0.1"
    assert address_key([], public=False, peer="testclient") == UNKNOWN_ADDRESS
    assert address_key(["::ffff:203.0.113.9"], public=True, peer=None) == "203.0.113.9"


# 7. Two IPv6 addresses in one /64 share a bucket ------------------------------------------


def test_two_ipv6_addresses_in_one_64_share_a_bucket(connect, entry):
    first = address_key(["2001:db8:1:2::a"], public=True, peer=None)
    second = address_key(["2001:db8:1:2:ffff:ffff:ffff:fffe"], public=True, peer=None)
    other = address_key(["2001:db8:1:3::a"], public=True, peer=None)
    assert first == second == "2001:db8:1:2::/64" and other != first
    for key in (first, second):
        with client_address(key):
            assert attempt(entry, nobody()) is None
    assert counts(connect, entry, addresses=[first, other]) == {
        "shared": 2, first: 2, other: 0}


# 8. Nothing but keyed digests ------------------------------------------------------------


def test_no_address_or_email_appears_outside_its_keyed_digest(connect, entry, caplog):
    address, email = "198.51.100.88", nobody()
    caplog.set_level(logging.DEBUG)
    with client_address(address):
        for _ in range(5):
            attempt(entry, email)
        attempt(entry, email)
    with connect("accounts") as conn:
        rows = {
            "address": conn.execute("SELECT * FROM accounts.entry_address_limit").fetchall(),
            "email": conn.execute("SELECT * FROM accounts.entry_email_failure").fetchall(),
            "shared": conn.execute("SELECT * FROM accounts.entry_shared_limit").fetchall(),
        }
    assert all(DIGEST.fullmatch(row["address_digest"]) for row in rows["address"])
    assert all(DIGEST.fullmatch(row["email_digest"]) for row in rows["email"])
    assert set(rows["shared"][0]) == {"minute", "attempts"} if rows["shared"] else True
    text = " ".join(str(value) for group in rows.values() for row in group
                    for value in row.values())
    logged = " ".join(record.getMessage() for record in caplog.records)
    for secret in (address, email, email.split("@")[0]):
        assert secret not in text and secret not in logged
    assert entry.verifier("entry-address", address) in text
    assert entry.verifier("entry-email", email) in text


# 9. Provider sign-in starts ----------------------------------------------------------------
# (your decisions of 2026-10-24, "Limit starts per address", and of 2026-10-25, "Cap per
# address, raise site cap" and "Count every start, free places at once"). Every start and
# finish is a real `begin()` or `complete()` call; no test writes a flow. Each test draws
# its addresses and browser bindings from a uuid and, afterwards, ages its own flows and
# runs the deletion pass (`provider_starts`), so no later test or rerun meets them.


FIXTURES = ("google", "orcid")


def all_flows(connect) -> int:
    with connect("accounts") as conn:
        return conn.execute("SELECT count(*) AS n FROM accounts.identity_flow").fetchone()["n"]


def open_flows(connect) -> int:
    """The open flows U2's `begin` caps: unexpired and pending or exchanging."""
    with connect("accounts") as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM accounts.identity_flow WHERE expires_at>clock_timestamp() "
            "AND disposition IN ('pending','exchanging')").fetchone()["n"]


def unexpired_flows(connect) -> int:
    """The starts the site counts within 5 minutes: every unexpired flow."""
    with connect("accounts") as conn:
        return conn.execute("SELECT count(*) AS n FROM accounts.identity_flow WHERE "
                            "expires_at>clock_timestamp()").fetchone()["n"]


def arrival(entry) -> ArrivalIdentityService:
    return ArrivalIdentityService(entry, {name: FixtureIdentityProvider(name) for name in FIXTURES})


def route_of(intent: str) -> str:
    return "settings" if intent == "link" else "account"


def start(service, starts, *, address: str, binding: str | None = None, authority=None,
          intent: str = "sign_in", provider: str = "google") -> dict:
    """One admitted start from `address` and a browser; the answer with its binding."""
    binding = binding or starts.binding()
    with client_address(address):
        accepted = service.begin(authority, provider, intent, binding, route_of(intent))
    return dict(starts.track(accepted), binding=binding)


def refused_start(service, *, address: str, binding: str, authority=None,
                  intent: str = "sign_in", provider: str = "google") -> IdentityStartLimited:
    """One start refused by a limit, with its wait left for the boundary's `Retry-After`."""
    holder: dict = {}
    token = REFUSAL.set(holder)
    try:
        with client_address(address), pytest.raises(IdentityStartLimited) as raised:
            service.begin(authority, provider, intent, binding, route_of(intent))
    finally:
        REFUSAL.reset(token)
    assert isinstance(raised.value, Busy)  # the built busy answer
    assert holder == {"retryAfterSeconds": raised.value.retry_after_seconds}
    # The answer carries its fixed reason (the person's decision of 2026-10-25).
    assert raised.value.message_key == "identity-start." + raised.value.reason
    return raised.value


def finish(service, accepted: dict, code: str, *, authority=None, state: str | None = None):
    return service.complete(UUID(accepted["flowId"]), state or accepted["state"],
                            accepted["binding"], code,
                            service.providers[accepted["provider"]].callback, authority)


def finish_unusable(service, accepted: dict) -> None:
    with pytest.raises(PermissionError, match="provider code unavailable"):
        finish(service, accepted, "unusable-code")


def dispositions(connect, started: list[dict]) -> list[str | None]:
    ids = [UUID(item["flowId"]) for item in started]
    with connect("accounts") as conn:
        found = {row["id"]: row["disposition"] for row in conn.execute(
            "SELECT id,disposition FROM accounts.identity_flow WHERE id=ANY(%s)",
            (ids,)).fetchall()}
    return [found.get(identifier) for identifier in ids]


def unlinked() -> str:
    return "unlinked-" + uuid4().hex


@pytest.fixture
def linked_identity(connect, sign_in_account):
    """A fresh provider subject linked to the shared sign-in member, removed afterwards."""
    made = []

    def link(provider: str) -> str:
        account, _ = sign_in_account("sign-in-member")
        subject, identifier = f"{provider}-{uuid4().hex}", uuid4()
        with connect("accounts") as conn:
            conn.execute("DELETE FROM accounts.identity_link WHERE account_id=%s AND "
                         "provider=%s", (account.account_id, provider))
            conn.execute("INSERT INTO accounts.identity_link(id,account_id,provider,subject) "
                         "VALUES(%s,%s,%s,%s)", (identifier, account.account_id, provider,
                                                 subject))
        made.append(identifier)
        return subject

    yield link
    with connect("accounts") as conn:
        for identifier in made:
            conn.execute("DELETE FROM accounts.identity_link WHERE id=%s", (identifier,))


def test_an_addresss_fourth_open_start_is_refused_writing_nothing_while_another_starts(
    connect, entry, d1_entry, provider_starts,
):
    """Three browsers at one address hold its three places: a fourth browser's start is
    refused with the busy answer and a 30-second wait, nothing written, while another
    address still starts. No start or refusal moves a D2 sign-in budget."""
    service = arrival(d1_entry)
    first, second = provider_starts.address(), provider_starts.address()
    budgets = counts(connect, entry, addresses=[first, second])
    started = [start(service, provider_starts, address=first, provider=FIXTURES[index % 2])
               for index in range(3)]
    before = all_flows(connect)
    refusal = refused_start(service, address=first, binding=provider_starts.binding())
    assert (refusal.reason, refusal.retry_after_seconds) == ("places", 30)
    assert all_flows(connect) == before  # the refused start wrote nothing
    started.append(start(service, provider_starts, address=second, provider="orcid"))
    with connect("accounts") as conn:
        digests = {row["id"]: row["client_address_digest"] for row in conn.execute(
            "SELECT id,client_address_digest FROM accounts.identity_flow WHERE id=ANY(%s)",
            ([UUID(item["flowId"]) for item in started],)).fetchall()}
    mine = d1_entry.verifier("identity-flow-address", first)
    assert [digests[UUID(item["flowId"])] for item in started] == [
        mine, mine, mine, d1_entry.verifier("identity-flow-address", second)]
    assert counts(connect, entry, addresses=[first, second]) == budgets


def test_completions_refused_after_the_answer_free_their_places_and_one_before_its_claim_does_not(
    connect, d1_entry, provider_starts,
):
    """Three completions refused after the provider's answer (an identity no link holds)
    leave their flows `denied`, so the address's next start is admitted; a second callback
    for one of them is refused at its claim and changes nothing; a completion refused
    before its claim (a wrong state) leaves its flow pending and counted."""
    service = arrival(d1_entry)
    address = provider_starts.address()
    denied = [start(service, provider_starts, address=address, provider="orcid")
              for _ in range(3)]
    for accepted in denied:
        code = provider_answer(service, accepted, unlinked())
        with pytest.raises(PermissionError, match="verified identity link required"):
            finish(service, accepted, code)
    assert dispositions(connect, denied) == ["denied"] * 3
    with pytest.raises(PermissionError, match="identity exchange not replayable"):
        finish(service, denied[0], "any-code")
    assert dispositions(connect, denied) == ["denied"] * 3
    pending = start(service, provider_starts, address=address)  # the places were freed
    with pytest.raises(PermissionError, match="identity flow unavailable"):
        finish(service, pending, "any-code", state="not-this-flows-state")
    assert dispositions(connect, [pending]) == ["pending"]
    more = [start(service, provider_starts, address=address) for _ in range(2)]
    # The pending flow still holds one of the three places.
    assert refused_start(service, address=address,
                         binding=provider_starts.binding()).reason == "places"
    assert dispositions(connect, [pending, *more]) == ["pending"] * 3


def test_a_completion_with_an_unusable_code_leaves_its_flow_unknown_and_frees_its_place(
    connect, d1_entry, provider_starts,
):
    service = arrival(d1_entry)
    address = provider_starts.address()
    started = [start(service, provider_starts, address=address) for _ in range(3)]
    finish_unusable(service, started[0])
    assert dispositions(connect, started) == ["unknown", "pending", "pending"]
    started.append(start(service, provider_starts, address=address))  # its place is free
    assert refused_start(service, address=address,
                         binding=provider_starts.binding()).reason == "places"


class FailingDenial:
    """The service's transactions, refusing only the denial's own write."""

    def __init__(self, inner):
        self.inner = inner
        self.profile = inner.profile

    def run(self, owner, work):
        if getattr(work, "__name__", "") == "deny":
            raise Busy("process connection allocation exhausted")
        return self.inner.run(owner, work)


def test_when_the_denial_cannot_be_written_the_built_refusal_stands_and_the_flow_stays_exchanging(
    connect, d1_entry, provider_starts, caplog,
):
    service = arrival(d1_entry)
    accepted = start(service, provider_starts, address=provider_starts.address(),
                     provider="orcid")
    code = provider_answer(service, accepted, unlinked())
    service.transactions = FailingDenial(service.transactions)
    caplog.set_level(logging.ERROR, logger="docsuri.events")
    with pytest.raises(PermissionError, match="verified identity link required"):
        finish(service, accepted, code)
    assert dispositions(connect, [accepted]) == ["exchanging"]
    lines = [json.loads(record.getMessage()) for record in caplog.records
             if record.name == "docsuri.events"]
    [unrecorded] = [line for line in lines if line["event"] == "identity.denial_unrecorded"]
    assert (unrecorded["component"], unrecorded["errorType"]) == ("accounts", "Busy")
    assert set(unrecorded) <= {"ts", "level", "component", "event", "errorType", "location"}


def test_one_browser_keeps_its_two_latest_pending_starts_and_two_tabs_both_complete(
    connect, d1_entry, provider_starts, linked_identity,
):
    """Five starts from one browser with no answer are all admitted; its two latest stay
    pending and the older three close as `expired`. Both latest, two tabs, complete."""
    service = arrival(d1_entry)
    address, binding = provider_starts.address(), provider_starts.binding()
    started = [start(service, provider_starts, address=address, binding=binding)
               for _ in range(5)]
    assert dispositions(connect, started) == ["expired"] * 3 + ["pending"] * 2
    subject = linked_identity("google")
    for accepted in started[3:]:
        signed_in = finish(service, accepted, provider_answer(service, accepted, subject))
        assert signed_in.public["state"] == "authenticated"
    assert dispositions(connect, started) == ["expired"] * 3 + ["complete"] * 2


def test_ten_unfinished_starts_refuse_the_eleventh_and_thirty_in_all_refuse_the_thirty_first(
    connect, d1_entry, provider_starts, linked_identity,
):
    """Ten starts from one address, each finished with an unusable code, leave the
    eleventh refused until the oldest leaves its 5 minutes, while another address still
    starts. Completed sign-ins don't count as unfinished: thirty from one address are all
    admitted, the eleventh among them, and the thirty-first is refused."""
    service = arrival(d1_entry)
    failing = provider_starts.address()
    for _ in range(10):
        finish_unusable(service, start(service, provider_starts, address=failing))
    refusal = refused_start(service, address=failing, binding=provider_starts.binding())
    assert refusal.reason == "unfinished-starts" and 1 <= refusal.retry_after_seconds <= 300
    start(service, provider_starts, address=provider_starts.address())
    completing, subject = provider_starts.address(), linked_identity("google")
    for index in range(30):
        accepted = start(service, provider_starts, address=completing)
        signed_in = finish(service, accepted, provider_answer(service, accepted, subject))
        assert signed_in.public["state"] == "authenticated", index
    refusal = refused_start(service, address=completing, binding=provider_starts.binding())
    assert refusal.reason == "starts" and 1 <= refusal.retry_after_seconds <= 300


def test_three_64s_of_one_48_fill_its_places_while_d2_counts_each_64_apart(
    connect, entry, d1_entry, provider_starts,
):
    service = arrival(d1_entry)
    prefix = provider_starts.ipv6_48()
    other = next(value for value in iter(provider_starts.ipv6_48, None) if value != prefix)
    keys = [address_key([f"{prefix}:{index:x}::a"], public=True, peer=None)
            for index in (1, 2, 3, 4)]
    assert len(set(keys)) == 4 and len({start_bucket(key) for key in keys}) == 1
    for key in keys[:3]:
        start(service, provider_starts, address=key)
    assert refused_start(service, address=keys[3],
                         binding=provider_starts.binding()).reason == "places"
    start(service, provider_starts,
          address=address_key([f"{other}:1::a"], public=True, peer=None))
    # D2's own limits still count each /64 apart (item 7).
    for key in keys[:2]:
        with client_address(key):
            assert attempt(entry, nobody()) is None
    found = counts(connect, entry, addresses=keys[:2])
    assert (found[keys[0]], found[keys[1]]) == (1, 1)


def test_a_members_link_starts_count_under_the_account_and_under_the_address(
    connect, d1_entry, authority, provider_starts,
):
    """A member's link start takes one of its address's places, and the member's fourth
    open link start, from a fourth browser at a fourth address, is refused, while a guest
    at another address still starts."""
    service = arrival(d1_entry)
    shared = provider_starts.address()
    start(service, provider_starts, address=shared, authority=authority, intent="link")
    for _ in range(2):
        start(service, provider_starts, address=shared)
    assert refused_start(service, address=shared,
                         binding=provider_starts.binding()).reason == "places"
    for _ in range(2):
        start(service, provider_starts, address=provider_starts.address(),
              authority=authority, intent="link")
    refusal = refused_start(service, address=provider_starts.address(),
                            binding=provider_starts.binding(), authority=authority,
                            intent="link")
    assert (refusal.reason, refusal.retry_after_seconds) == ("places", 30)
    start(service, provider_starts, address=provider_starts.address())


def test_the_complete_realms_admit_the_200th_open_flow_and_refuse_the_201st_and_u2_keeps_20(
    connect, entry, d1_entry, provider_starts,
):
    """Real starts from fresh addresses fill the site. U2's own `begin` keeps its 20 in the
    same database, while the complete realms admit flows up to 200 and refuse the 201st
    with the busy answer, writing nothing."""
    service = arrival(d1_entry)
    built = ControlIdentityService(
        d1_entry, {name: FixtureIdentityProvider(name) for name in FIXTURES})
    assert (built.flow_capacity, service.flow_capacity) == (20, 201)
    budgets = counts(connect, entry)

    def fresh(index: int = 0) -> dict:
        return start(service, provider_starts, address=provider_starts.address(),
                     provider=FIXTURES[index % 2])

    while open_flows(connect) < 20:
        fresh()
    with pytest.raises(ValueError, match="finite identity flow capacity"):
        built.begin(None, "google", "sign_in", provider_starts.binding(), "account")
    while open_flows(connect) < 199:
        fresh(open_flows(connect))
    fresh()  # the 200th open flow is admitted
    assert open_flows(connect) == 200
    before = all_flows(connect)
    refusal = refused_start(service, address=provider_starts.address(),
                            binding=provider_starts.binding())
    assert (refusal.reason, refusal.retry_after_seconds) == ("site-places", 30)
    assert all_flows(connect) == before  # the refusal wrote nothing
    assert counts(connect, entry) == budgets


def test_fresh_addresses_are_refused_once_the_site_counts_600_starts_within_5_minutes(
    connect, d1_entry, provider_starts,
):
    """Starts from fresh addresses and browsers, each finished with an unusable code, are
    admitted until the site counts 600 within 5 minutes; the next is refused with the busy
    answer, writing nothing."""
    service = arrival(d1_entry)
    refusal = None
    while refusal is None:
        address, binding = provider_starts.address(), provider_starts.binding()
        try:
            accepted = start(service, provider_starts, address=address, binding=binding)
        except IdentityStartLimited as refused:
            refusal = refused
        else:
            finish_unusable(service, accepted)
            assert unexpired_flows(connect) <= 600
    assert refusal.reason == "site-starts" and 1 <= refusal.retry_after_seconds <= 300
    assert refusal.message_key == "identity-start.site-starts"
    assert unexpired_flows(connect) == 600  # the refused start wrote nothing


class Conflicting:
    """The service's transactions, where every attempt of a start meets a serialization
    failure, as simultaneous starts do; the real retry loop runs out."""

    def __init__(self, inner):
        self.inner, self.profile, self.attempts = inner, inner.profile, 0

    def run(self, owner, work):
        def conflicting(conn):
            self.attempts += 1
            raise psycopg.errors.SerializationFailure("could not serialize access")

        return self.inner.run(owner, conflicting)


def test_simultaneous_starts_that_run_out_of_retries_get_the_busy_answer_with_one_second(
    connect, d1_entry, provider_starts,
):
    service = arrival(d1_entry)
    service.transactions = Conflicting(service.transactions)
    before = all_flows(connect)
    refusal = refused_start(service, address=provider_starts.address(),
                            binding=provider_starts.binding())
    assert (refusal.reason, refusal.retry_after_seconds) == ("conflict", 1)
    assert service.transactions.attempts == 3  # the built retries, then the busy answer
    assert all_flows(connect) == before


# 9b. The busy answer carries its reason (the person's decision of 2026-10-25, "Different
# text for site-wide"; plan Step 44 test item 6). The answer's `messageKey` is
# `identity-start.<reason>`, which the entry panel's Korean text resolves.


def begin_over(client) -> httpx.Response:
    """One guest provider start over the composed routes, with a fresh entry cookie."""
    client.cookies.clear()
    csrf = client.get("/api/v2/session").json()["csrfToken"]
    return post(client, "/api/v2/c02/access-begin-identity-flow", {
        "provider": "google", "intent": "sign_in", "returnRouteId": "account",
        "policyRef": U8_SYNTHETIC_POLICY.reference,
    }, csrf)


def test_a_full_address_answers_over_http_with_its_reason_retry_after_and_nothing_written(
    connect, realm, d1_entry, provider_starts,
):
    """Three starts fill an address's places; the fourth, a guest's over the composed
    routes behind D7's boundary, is the busy answer: 429 RATE_LIMITED, the message key
    `identity-start.places`, and a 30-second wait that travels only in the `Retry-After`
    header (the busy answer's body carries no wait), and no flow written. A start from
    another address over the same routes is admitted."""
    service = arrival(d1_entry)
    full, other = provider_starts.address(), provider_starts.address()
    for _ in range(3):
        start(service, provider_starts, address=full)
    before = all_flows(connect)
    lifecycle = configure_lifecycle(d1_entry, LIFECYCLE_MANIFEST)
    with account_client(realm, d1_entry, lifecycle, address=full) as client:
        refused = begin_over(client)
    assert refused.status_code == 429, refused.text
    body = wire.Error.model_validate(refused.json()).model_dump(mode="json",
                                                                 exclude_none=True)
    assert (body["code"], body["messageKey"], body["retryable"]) == (
        "RATE_LIMITED", "identity-start.places", True)
    assert refused.headers["retry-after"] == "30"
    # The body itself, as sent, carries no wait anywhere (review finding, Minor, R15).
    raw = refused.json()
    assert "retryAfterSeconds" not in raw, raw
    assert "retryAfterSeconds" not in (raw.get("details") or {}), raw
    assert "retryAfterSeconds" not in refused.text
    assert all_flows(connect) == before
    with account_client(realm, d1_entry, lifecycle, address=other) as client:
        admitted = begin_over(client)
    assert admitted.status_code == 200, admitted.text
    provider_starts.track(admitted.json())


@pytest.fixture(scope="module")
def raising(realm):
    """A route on the complete origin behind D7's boundary that raises one refusal: an
    `IdentityStartLimited` of the given reason, or (`plain`) a built `Busy`."""
    router = APIRouter(route_class=boundary_route(COMPLETE_ORIGIN))

    @router.get("/test-only/refuse/{reason}")
    async def refuse(reason: str):
        if reason == "plain":
            raise Busy("process connection allocation exhausted")
        raise IdentityStartLimited(reason, 7)

    boundary = ProductionBoundary(BoundaryHosts.for_profile(realm),
                                  BuildManifest.empty(realm.root), context=None)
    app = assemble(realm, routers=(router,), boundary=boundary)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        yield client


@pytest.mark.parametrize("reason", IdentityStartLimited.REASONS)
def test_each_start_refusal_answers_with_its_own_reason(raising, reason):
    answer = raising.get(f"/test-only/refuse/{reason}")
    assert answer.status_code == 429, answer.text
    body = wire.Error.model_validate(answer.json()).model_dump(mode="json", exclude_none=True)
    assert (body["code"], body["messageKey"]) == ("RATE_LIMITED", "identity-start." + reason)
    assert answer.headers["retry-after"] == "7"


def test_every_other_busy_keeps_the_built_message_key_and_an_unknown_reason_is_refused(
    raising,
):
    answer = raising.get("/test-only/refuse/plain")
    assert answer.status_code == 429, answer.text
    assert answer.json()["messageKey"] == "request.rate_limited"
    assert "retry-after" not in answer.headers  # a plain Busy names no wait
    for unknown in ("site", "PLACES", "identity start limit"):
        with pytest.raises(ValueError, match="unknown identity start limit reason"):
            IdentityStartLimited(unknown, 1)


# 10. The deletion pass ------------------------------------------------------------------------


def test_the_deletion_pass_deletes_flows_a_minute_past_their_expiry_at_most_limit_at_a_time(
    connect, d1_entry, provider_starts,
):
    """`expire_flows` runs through the runtime login `docsuri_accounts`, which cannot delete
    a flow itself. It deletes at most `limit` flows at a time, each expired more than a
    minute ago, with its address digest, and keeps every other flow. The one arranged
    value is each flow's expiry, set in the past to stand for its age."""
    service = arrival(d1_entry)
    flows = [start(service, provider_starts, address=provider_starts.address())
             for _ in range(5)]
    ids = [UUID(item["flowId"]) for item in flows]
    with connect("accounts") as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM accounts.identity_flow WHERE id=%s", (ids[0],))
        conn.rollback()
        digests = {row["id"]: row["client_address_digest"] for row in conn.execute(
            "SELECT id,client_address_digest FROM accounts.identity_flow WHERE id=ANY(%s)",
            (ids,)).fetchall()}
        for identifier, age in zip(ids, ("3 minutes", "2 minutes", "90 seconds",
                                         "30 seconds"), strict=False):
            conn.execute("UPDATE accounts.identity_flow SET expires_at=clock_timestamp()-"
                         "%s::interval WHERE id=%s", (age, identifier))
    assert expire_flows(d1_entry.transactions, limit=10_000) >= 0  # earlier leftovers
    with connect("accounts") as conn:
        remaining = {row["id"] for row in conn.execute(
            "SELECT id FROM accounts.identity_flow WHERE id=ANY(%s)", (ids,)).fetchall()}
        assert remaining == {ids[3], ids[4]}  # 30 seconds past expiry, and unexpired
        assert not conn.execute(
            "SELECT 1 FROM accounts.identity_flow WHERE client_address_digest=ANY(%s)",
            ([digests[identifier] for identifier in ids[:3]],)).fetchone()
        for identifier in ids[3:]:
            conn.execute("UPDATE accounts.identity_flow SET expires_at=clock_timestamp()-"
                         "interval '5 minutes' WHERE id=%s", (identifier,))
    assert expire_flows(d1_entry.transactions, limit=1) == 1  # at most `limit` at a time
    assert expire_flows(d1_entry.transactions, limit=1) == 1
    for limit in (0, 10_001, 1.5, True):
        with pytest.raises(ValueError):
            expire_flows(d1_entry.transactions, limit=limit)


# 11. D2: no forwarding header but Cloudflare's chooses the bucket (Step 131(d)) -------------


def test_forwarded_and_true_client_addresses_never_choose_the_bucket(connect, served):
    """On the public authority, `X-Forwarded-For`, `True-Client-IP` and `Forwarded` are
    never read: a sign-in carrying only one of them counts as unknown, and one beside
    `CF-Connecting-IP` counts under Cloudflare's value alone."""
    entry, _ = served
    claimed, connecting = fresh_address(), fresh_address()
    addresses = [UNKNOWN_ADDRESS, connecting, claimed, "127.0.0.1"]
    before = counts(connect, entry, addresses=addresses)
    public = {"host": "127.0.0.1:18110"}
    with httpx.Client(base_url="http://127.0.0.1:18109", timeout=15) as client:
        for extra in ({"x-forwarded-for": claimed}, {"true-client-ip": claimed},
                      {"forwarded": "for=" + claimed},
                      {"cf-connecting-ip": connecting, "x-forwarded-for": claimed,
                       "true-client-ip": claimed}):
            answer = sign_in_over(client, {**public, **extra})
            assert answer.status_code == 403, (extra, answer.text)
    after = counts(connect, entry, addresses=addresses)
    moved = {key: after[key] - before[key] for key in before}
    assert moved == {UNKNOWN_ADDRESS: 3, connecting: 1, claimed: 0, "127.0.0.1": 0,
                     "shared": 4}, moved
