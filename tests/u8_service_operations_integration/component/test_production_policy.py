"""AccountAccess's D1-shaped policies (U8 plan Step 20; security-design § 15 "Policy (D1)").

Production's `docsuri-production-v1` runs only in the production realm, so its own lengths
are checked on the policy itself. The service's behaviour runs in the composed realm under
a D1-shaped policy whose three lengths differ (member 15 minutes, administrator 10,
purpose-limited 8), so each session shows which length it took. Issue times come from the
injected clock and expiry from the database's guard, so "ends at" is shown by issuing a
session just inside and just outside its length before now.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from uuid import UUID, uuid4

import pytest

from backend.local_browser import SESSION_COOKIE
from backend.modules.accounts.control_policy import SYNTHETIC_POLICY, PolicyUnavailable
from backend.modules.accounts.local_http import ENTRY_POLICY
from backend.modules.accounts.services.control_mfa import totp
from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.modules.accounts.u8_control_policy import (
    PRODUCTION_POLICY,
    U8_SYNTHETIC_POLICY,
    Admission,
    CompletePolicy,
    remaining_seconds,
)
from backend.modules.accounts.u8_entry import CompleteControlEntryService
from backend.modules.accounts.u8_mfa import CompleteMfaService
from backend.transactions import Authority, Busy, guard
from tests.u8_service_operations_integration.conftest import (
    SIGN_IN_PASSWORD,
    Clock,
    account_client,
    activate_factor,
    database_step,
    post,
)

MEMBER, ADMINISTRATOR, LIMITED = 900, 600, 480
BY_ROLE = dataclasses.replace(
    U8_SYNTHETIC_POLICY, member_session_seconds=MEMBER,
    administrator_session_seconds=ADMINISTRATOR, session_seconds=LIMITED,
)

pytestmark = pytest.mark.usefixtures("own_address")


def entry_at(transactions, moment: dt.datetime, policy=BY_ROLE) -> CompleteControlEntryService:
    return CompleteControlEntryService(transactions, policy, clock=Clock(moment))


def session_row(connect, session_id) -> dict:
    with connect("accounts") as conn:
        return conn.execute("SELECT * FROM accounts.session WHERE id=%s",
                            (UUID(session_id),)).fetchone()


def guarded(connect, session) -> bool:
    authority = Authority(UUID(session["accountId"]), UUID(session["sessionId"]))
    try:
        with connect("library") as conn:
            guard(conn, authority, purpose="account-control")
    except Exception:  # noqa: BLE001 - the guard's denial is the answer under test
        return False
    return True


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(microsecond=0)


def verified(connect, transactions, entry, email, seed) -> dict:
    """Password, then the second factor, through U2's flow."""
    continuation = entry.login(email, SIGN_IN_PASSWORD, flow_binding="d1")
    assert continuation.public["state"] == "mfa_required"
    step = database_step(connect)
    result = CompleteMfaService(entry).verify(
        continuation.token, continuation.csrf, UUID(continuation.public["challengeId"]),
        UUID(continuation.public["flowBinding"]), totp(seed, step),
    )
    return result.public["session"]


# 1. Each length, from the injected clock ------------------------------------------------


def test_each_session_takes_its_policys_length_from_the_injected_clock(
    transactions, connect, sign_in_account,
):
    moment = now()
    member, member_email = sign_in_account("sign-in-member")
    entry = entry_at(transactions, moment)
    full = entry.login(member_email, SIGN_IN_PASSWORD, flow_binding="d1").public
    assert full["state"] == "authenticated"
    assert session_row(connect, full["session"]["sessionId"])["expires_at"] == (
        moment + dt.timedelta(seconds=MEMBER))
    administrator, admin_email = sign_in_account("sign-in-admin", role="administrator")
    seed = activate_factor(connect, entry, administrator.account_id)
    session = verified(connect, transactions, entry, admin_email, seed)
    assert session_row(connect, session["sessionId"])["expires_at"] == (
        moment + dt.timedelta(seconds=ADMINISTRATOR))
    migrated, migrated_email = sign_in_account("sign-in-migrated", consents=False)
    pending = entry.login(migrated_email, SIGN_IN_PASSWORD, flow_binding="d1").public
    assert pending["state"] == "consent_pending"
    assert dt.datetime.fromisoformat(pending["expiresAt"]) == moment + dt.timedelta(
        seconds=LIMITED)


def test_production_holds_d1s_lengths_and_the_second_factor_within_five_minutes():
    assert PRODUCTION_POLICY.full_session_seconds("member") == 12 * 3600
    assert PRODUCTION_POLICY.full_session_seconds("administrator") == 3600
    assert PRODUCTION_POLICY.limited_session_seconds == 15 * 60
    assert PRODUCTION_POLICY.proof_seconds == 5 * 60
    assert PRODUCTION_POLICY.d1_shaped and U8_SYNTHETIC_POLICY.d1_shaped
    # U2's policy has no D1 shape at all: its cookie and every session's length are the
    # built `session_seconds`.
    assert not hasattr(SYNTHETIC_POLICY, "d1_shaped")
    assert not hasattr(SYNTHETIC_POLICY, "full_session_seconds")
    assert SYNTHETIC_POLICY.session_seconds == 900
    with pytest.raises(ValueError):
        PRODUCTION_POLICY.full_session_seconds("owner")


def test_a_session_ends_at_its_length_and_not_a_second_later(
    transactions, connect, sign_in_account,
):
    _, email = sign_in_account("sign-in-member")
    inside = entry_at(transactions, now() - dt.timedelta(seconds=MEMBER - 60))
    session = inside.login(email, SIGN_IN_PASSWORD, flow_binding="d1").public["session"]
    assert guarded(connect, session)
    outside = entry_at(transactions, now() - dt.timedelta(seconds=MEMBER + 1))
    ended = outside.login(email, SIGN_IN_PASSWORD, flow_binding="d1").public["session"]
    assert not guarded(connect, ended)


# 2. Activity extends none --------------------------------------------------------------


def test_activity_extends_no_session(transactions, connect, sign_in_account):
    _, email = sign_in_account("sign-in-member")
    entry = entry_at(transactions, now())
    result = entry.login(email, SIGN_IN_PASSWORD, flow_binding="d1")
    session = result.public["session"]
    before = session_row(connect, session["sessionId"])["expires_at"]
    for _ in range(3):
        entry.inspect_session(result.token)
        assert guarded(connect, session)
    entry.clock.advance(300)
    entry.inspect_session(result.token)
    assert session_row(connect, session["sessionId"])["expires_at"] == before


# 3. A member with a second factor gets the member's length -----------------------------


def test_a_member_with_a_second_factor_gets_the_members_length(
    transactions, connect, sign_in_account,
):
    moment = now()
    member, email = sign_in_account("sign-in-member")
    entry = entry_at(transactions, moment)
    seed = activate_factor(connect, entry, member.account_id)
    session = verified(connect, transactions, entry, email, seed)
    assert session["authenticationLevel"] == "mfa"
    assert session_row(connect, session["sessionId"])["expires_at"] == (
        moment + dt.timedelta(seconds=MEMBER))


# 4. Each policy refuses the other's realm ----------------------------------------------


def test_each_policy_refuses_the_other_realm(transactions):
    with pytest.raises(PolicyUnavailable):
        U8_SYNTHETIC_POLICY.require_realm("production")
    with pytest.raises(PolicyUnavailable):
        PRODUCTION_POLICY.require_realm("service-operations")
    # Production's policy, with its admission, refuses the composed realm; U2's policy is
    # not a complete realm's at all.
    with pytest.raises(PolicyUnavailable):
        CompleteControlEntryService(transactions, PRODUCTION_POLICY,
                                    admission=Admission("maintainer-only"))
    with pytest.raises(PolicyUnavailable):
        CompleteControlEntryService(transactions, SYNTHETIC_POLICY)
    fields = {field.name: getattr(PRODUCTION_POLICY, field.name)
              for field in dataclasses.fields(CompletePolicy)}
    with pytest.raises(PolicyUnavailable):
        CompletePolicy(**{**fields, "realm": "service-operations"})
    with pytest.raises(PolicyUnavailable):
        CompletePolicy(**{**fields, "policy_id": "u8-synthetic-v1", "realm": "production"})
    with pytest.raises(PolicyUnavailable):
        CompletePolicy(**{**fields, "policy_id": "u2-synthetic-v1",
                          "realm": "account-controls"})


# 5. The account cap, with the existing answer -------------------------------------------


def cap_password() -> str:
    """A registration password that meets the policy, generated per run (L1-36)."""
    return f"synthetic-cap-{uuid4().hex[:12]}-A1!"


def test_the_cap_refuses_the_next_account_with_the_existing_answer(transactions, connect):
    assert PRODUCTION_POLICY.max_accounts == 500
    with pytest.raises(ValueError):
        dataclasses.replace(PRODUCTION_POLICY, max_accounts=501)
    with connect("accounts") as conn:
        active = conn.execute(
            "SELECT count(*) AS n FROM accounts.account WHERE active").fetchone()["n"]
    full = CompleteControlEntryService(
        transactions, dataclasses.replace(U8_SYNTHETIC_POLICY, max_accounts=max(1, active)),
        clock=Clock(now()),
    )
    assert full.account_limit == max(1, active)
    with pytest.raises(Busy):
        full.register(uuid4(), f"cap-{uuid4().hex[:12]}@fixture.invalid",
                      cap_password(), "연구자", "d1")
    with connect("accounts") as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM accounts.account WHERE active").fetchone()["n"] == active


def test_a_taken_address_at_the_cap_gets_the_same_busy_answer(
    transactions, connect, sign_in_account,
):
    """Step 44's correction: capacity is checked before the address, as built, so a taken
    address never answers differently from a free one while the cap is reached."""
    _, email = sign_in_account("sign-in-member")
    with connect("accounts") as conn:
        active = conn.execute(
            "SELECT count(*) AS n FROM accounts.account WHERE active").fetchone()["n"]
    full = CompleteControlEntryService(
        transactions, dataclasses.replace(U8_SYNTHETIC_POLICY, max_accounts=max(1, active)),
        clock=Clock(now()),
    )
    for address in (email, f"cap-{uuid4().hex[:12]}@fixture.invalid"):
        with pytest.raises(Busy):
            full.register(uuid4(), address, cap_password(), "연구자", "d1")


def test_production_entry_without_its_admission_is_refused_before_anything(transactions):
    """Step 44's correction: production's policy always carries its admission."""
    with pytest.raises(PolicyUnavailable, match="admission"):
        CompleteControlEntryService(transactions, PRODUCTION_POLICY)


# 6. The cookie's Max-Age is the issued session's remaining length ------------------------


def login(client, email: str):
    csrf = client.get("/api/v2/session").json()["csrfToken"]
    return post(client, "/api/v2/c02/access-login",
                {"email": email, "password": SIGN_IN_PASSWORD, "policyRef": ENTRY_POLICY}, csrf)


def max_age(answer) -> int:
    cookie = next(value for value in answer.headers.get_list("set-cookie")
                  if value.startswith(SESSION_COOKIE + "="))
    return int(next(part.split("=", 1)[1] for part in cookie.split("; ")
                    if part.lower().startswith("max-age=")))


def test_the_session_cookie_lasts_exactly_as_long_as_its_session(
    realm, transactions, sign_in_account, own_address,
):
    _, email = sign_in_account("sign-in-member")
    moment = now()
    entry = entry_at(transactions, moment)
    with account_client(realm, entry, address=own_address) as client:
        answer = login(client, email)
    assert answer.status_code == 200, answer.text
    expires = answer.json()["session"]["expiresAt"]
    assert max_age(answer) == remaining_seconds(expires, moment) == MEMBER
    # Later in the session the cookie carries only what is left of it.
    entry.clock.advance(120)
    with account_client(realm, entry, address=own_address) as client:
        again = login(client, email)
    assert max_age(again) == MEMBER  # a new session, its own full length
    assert remaining_seconds(expires, entry.clock()) == MEMBER - 120


def session_cookie(answer) -> dict:
    """The answer's one `session_id` cookie, its attributes by lower-case name."""
    [cookie] = [value for value in answer.headers.get_list("set-cookie")
                if value.startswith(SESSION_COOKIE + "=")]
    attributes = {}
    for part in cookie.split(";")[1:]:
        name, _, value = part.strip().partition("=")
        attributes[name.lower()] = value
    return attributes


def built_attributes(answer) -> int:
    """Asserts the built attributes of the answer's session cookie; returns its Max-Age."""
    attributes = session_cookie(answer)
    assert "secure" in attributes and "httponly" in attributes
    assert attributes["samesite"].lower() == "strict"
    assert attributes["path"] == "/" and "domain" not in attributes
    return int(attributes["max-age"])


def remaining_of(public: dict, moment: dt.datetime) -> int:
    return remaining_seconds(public.get("expiresAt") or public["session"]["expiresAt"], moment)


def give_consents(client, entry, csrf: str):
    listed = post(client, "/api/v2/c02/access-list-consents", {"page": {"limit": 10}}, csrf)
    assert listed.status_code == 200, listed.text
    given = None
    for item, decision in zip(listed.json()["items"], ("granted", "revoked"), strict=True):
        given = post(client, "/api/v2/c02/access-update-consent", {
            "purposeId": item["purposeId"], "decision": decision,
            "policyRef": entry.control_policy.reference,
            "expectedRevision": item["revision"],
        }, csrf)
        assert given.status_code == 200, given.text
    return given


def verify_over_http(client, connect, answer, seed: str):
    challenge = answer.json().get("mfaChallenge", answer.json())
    csrf = client.get("/api/v2/session").json()["csrfToken"]
    return post(client, "/api/v2/c02/access-verify-mfa", {
        "factorKind": "totp",
        "verification": {"challengeId": challenge["challengeId"],
                         "flowBinding": challenge["flowBinding"],
                         "proof": totp(seed, database_step(connect))},
    }, csrf)


def test_every_session_cookie_keeps_its_built_attributes(
    realm, transactions, connect, sign_in_account, own_address,
):
    from backend.u8_host import LIFECYCLE_MANIFEST, configure_lifecycle

    moment = now()
    entry = entry_at(transactions, moment)
    lifecycle = configure_lifecycle(entry, LIFECYCLE_MANIFEST)
    member, member_email = sign_in_account("sign-in-member")
    _, migrated_email = sign_in_account("sign-in-migrated", consents=False)
    administrator, admin_email = sign_in_account("sign-in-admin", role="administrator")
    with account_client(realm, entry, lifecycle, address=own_address) as client:
        assert built_attributes(login(client, member_email)) == MEMBER
    with account_client(realm, entry, lifecycle, address=own_address) as client:
        pending = login(client, migrated_email)
        assert pending.json()["state"] == "consent_pending"
        assert built_attributes(pending) == LIMITED
        csrf = entry.verifier("session-csrf", client.cookies[SESSION_COOKIE])
        assert built_attributes(give_consents(client, entry, csrf)) == MEMBER
    with account_client(realm, entry, lifecycle, address=own_address) as client:
        setup = login(client, admin_email)  # no factor yet: a setup-only session
        assert setup.json()["session"]["authenticationLevel"] == "primary"
        assert built_attributes(setup) == remaining_of(setup.json(), moment)
    seed = activate_factor(connect, entry, administrator.account_id)
    with account_client(realm, entry, lifecycle, address=own_address) as client:
        continuation = login(client, admin_email)
        assert continuation.json()["state"] == "mfa_required"
        assert built_attributes(continuation) == remaining_of(continuation.json(), moment)
        verified_answer = verify_over_http(client, connect, continuation, seed)
        assert verified_answer.status_code == 200, verified_answer.text
        assert built_attributes(verified_answer) == ADMINISTRATOR
    member_seed = activate_factor(connect, entry, member.account_id)
    with account_client(realm, entry, lifecycle, address=own_address) as client:
        continuation = login(client, member_email)
        assert continuation.json()["state"] == "mfa_required"
        verified_answer = verify_over_http(client, connect, continuation, member_seed)
        assert verified_answer.status_code == 200, verified_answer.text
        assert built_attributes(verified_answer) == MEMBER


def test_productions_lengths_become_max_age():
    moment = now()
    for length, expected in ((PRODUCTION_POLICY.full_session_seconds("member"), 43200),
                             (PRODUCTION_POLICY.full_session_seconds("administrator"), 3600),
                             (PRODUCTION_POLICY.limited_session_seconds, 900)):
        assert remaining_seconds(moment + dt.timedelta(seconds=length), moment) == expected


UNCHANGED = {
    "max_body_bytes": 65536, "max_password_bytes": 1024, "max_value_bytes": 4096,
    "max_page_size": 50, "max_scopes": 32, "max_outstanding": 100,
    "material_seconds": 60, "cursor_seconds": 300, "lease_seconds": 15,
    "attempt_seconds": 10, "max_attempts": 3, "period_seconds": 900, "quota": 3,
}


def test_every_other_production_field_keeps_u2s_built_value():
    from backend.modules.accounts import control_policy
    from backend.modules.accounts.control_policy import ControlPolicy
    from backend.u8_host import CONTROL_POLICIES

    built = [field.name for field in dataclasses.fields(ControlPolicy)]
    assert len(built) == 18
    # D1's two role lengths and, by your answer of 2026-11-08 (L1-71, Step 53(i)),
    # `account_mail_per_day`, whose values Step 54(q) asserts.
    added = ["member_session_seconds", "administrator_session_seconds",
             "account_mail_per_day"]
    assert [field.name for field in dataclasses.fields(PRODUCTION_POLICY)] == built + added
    assert CONTROL_POLICIES["production"] is control_policy.for_realm("production")
    assert control_policy.for_realm("production") is PRODUCTION_POLICY
    assert (PRODUCTION_POLICY.policy_id, PRODUCTION_POLICY.realm) == (
        "docsuri-production-v1", "production")
    kept = set(built) - {"policy_id", "realm", "max_accounts", "session_seconds",
                         "proof_seconds"}
    assert kept == set(UNCHANGED)
    for name, value in UNCHANGED.items():
        assert getattr(PRODUCTION_POLICY, name) == getattr(SYNTHETIC_POLICY, name) == value


def test_an_earlier_realms_cookie_is_as_built(realm, transactions, sign_in_account, own_address):
    """A policy without D1's shape (here U1's own entry service, which every earlier realm
    builds on) keeps the built cookie: the entry context's bound, at most an hour."""
    _, email = sign_in_account("sign-in-member")
    entry = GuardedEntryService(transactions)
    assert getattr(entry, "first_sign_in", None) is None
    with account_client(realm, entry, address=own_address) as client:
        answer = login(client, email)
    assert answer.status_code == 200, answer.text
    assert "expiresAt" not in answer.json()["session"]
    assert max_age(answer) == 3600
