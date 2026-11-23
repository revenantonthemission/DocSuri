"""Admission (U8 plan Step 20; security-design § 3.5, NFR1.3, C02 4.0.0 AccessAdmission).

Admission is a policy input the host passes from the profile, never a browser input.
Maintainer-only admits only administrators to sign-in, refusing everyone else with the
answer a wrong password gets. Registration stays closed until the public-activation
evidence and the maintainer's decision open it; the policy's account cap then applies,
refused with AccountAccess's existing answer. A synthetic profile states no admission,
so its realm keeps the built entry rules.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.modules.accounts.control_policy import PolicyUnavailable
from backend.modules.accounts.u8_control_policy import U8_SYNTHETIC_POLICY, Admission
from backend.modules.accounts.u8_entry import CompleteControlEntryService
from backend.transactions import Busy
from tests.u8_service_operations_integration.conftest import (
    SIGN_IN_PASSWORD,
    Clock,
    activate_factor,
)

pytestmark = pytest.mark.usefixtures("own_address")
NEW_PASSWORD = f"Synthetic-Admission-{uuid4().hex[:12]}-1!"  # per run (L1-36)


def entry_with(transactions, admission, policy=U8_SYNTHETIC_POLICY):
    return CompleteControlEntryService(
        transactions, policy, clock=Clock(dt.datetime.now(dt.UTC)), admission=admission)


def refusal(entry, email, password) -> type | None:
    try:
        entry.login(email, password, flow_binding="admission")
    except PermissionError as error:
        return type(error), str(error)
    return None


def active_accounts(connect) -> int:
    with connect("accounts") as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM accounts.account WHERE active").fetchone()["n"]


def test_maintainer_only_refuses_a_member_with_the_wrong_password_answer(
    transactions, sign_in_account, forget_waits,
):
    _, member = sign_in_account("sign-in-member")
    forget_waits.append(member)
    entry = entry_with(transactions, Admission("maintainer-only"))
    right = refusal(entry, member, SIGN_IN_PASSWORD)
    wrong = refusal(entry, member, "wrong-" + uuid4().hex[:12])  # per run (L1-36)
    assert right is not None and right == wrong == (PermissionError, "credentials unavailable")


def test_maintainer_only_admits_the_administrator(transactions, connect, sign_in_account):
    administrator, email = sign_in_account("sign-in-admin", role="administrator")
    entry = entry_with(transactions, Admission("maintainer-only"))
    # Without a second factor: the setup-only session; with one: the second factor.
    assert entry.login(email, SIGN_IN_PASSWORD, flow_binding="admission").public[
        "state"] == "authenticated"
    activate_factor(connect, entry, administrator.account_id)
    assert entry.login(email, SIGN_IN_PASSWORD, flow_binding="admission").public[
        "state"] == "mfa_required"


def test_open_admission_admits_the_migrated_member(transactions, sign_in_account):
    _, member = sign_in_account("sign-in-member")
    entry = entry_with(transactions, Admission("open"))
    assert entry.login(member, SIGN_IN_PASSWORD, flow_binding="admission").public[
        "state"] == "authenticated"


@pytest.mark.parametrize("admission", [Admission("maintainer-only"), Admission("open")])
def test_registration_stays_closed_until_public_activation(transactions, connect, admission):
    before = active_accounts(connect)
    with pytest.raises(PolicyUnavailable):
        entry_with(transactions, admission).register(
            uuid4(), f"new-{uuid4().hex[:12]}@fixture.example.com", NEW_PASSWORD, "연구자",
            "admission",
        )
    assert active_accounts(connect) == before


def test_the_cap_applies_once_registration_opens(transactions, connect):
    before = active_accounts(connect)
    capped = dataclasses.replace(U8_SYNTHETIC_POLICY, max_accounts=max(1, before))
    entry = entry_with(transactions, Admission("open", registration_open=True), capped)
    with pytest.raises(Busy):  # AccountAccess's existing answer at the cap
        entry.register(uuid4(), f"new-{uuid4().hex[:12]}@fixture.example.com", NEW_PASSWORD,
                       "연구자", "admission")
    assert active_accounts(connect) == before


def provider_sign_in(entry, starts):
    """One sign-in through the identity-provider stand-in (U2's fixture adapter, at the
    workspace page): begin, the provider's answer, completion, from a browser and an
    address of the test's own (Step 20 item 9)."""
    from urllib.parse import parse_qs, urlsplit
    from uuid import UUID

    from backend.modules.accounts.services.control_identity import FixtureIdentityProvider
    from backend.modules.accounts.u8_identity import ArrivalIdentityService

    service = ArrivalIdentityService(
        entry, {name: FixtureIdentityProvider(name) for name in ("google", "orcid")})
    binding = starts.binding()
    with starts.at():
        accepted = starts.track(service.begin(None, "google", "sign_in", binding, "account"))
    query = {key: values[0] for key, values in
             parse_qs(urlsplit(service.fixture_authorization(accepted)).query).items()}
    return service.complete(UUID(query["flow"]), query["state"], binding,
                            query["code"], service.providers["google"].callback, None)


@pytest.fixture
def provider_link(connect):
    """Link the stand-in's Google identity to one account, removed afterwards."""
    made = []

    def link(account_id):
        subject = "synthetic-researcher-google"
        with connect("accounts") as conn:
            if conn.execute("SELECT 1 FROM accounts.identity_link WHERE provider='google' "
                            "AND subject=%s", (subject,)).fetchone():
                pytest.fail("the stand-in's Google identity is linked elsewhere in this realm")
            identifier = uuid4()
            conn.execute("INSERT INTO accounts.identity_link(id,account_id,provider,subject) "
                         "VALUES(%s,%s,'google',%s)", (identifier, account_id, subject))
        made.append(identifier)

    yield link
    with connect("accounts") as conn:
        for identifier in made:
            conn.execute("DELETE FROM accounts.identity_link WHERE id=%s", (identifier,))


def live_sessions(connect, account_id) -> int:
    with connect("accounts") as conn:
        return conn.execute("SELECT count(*) AS n FROM accounts.session WHERE account_id=%s "
                            "AND NOT revoked", (account_id,)).fetchone()["n"]


def test_maintainer_only_refuses_a_member_signing_in_through_a_provider(
    transactions, connect, sign_in_account, provider_link, provider_starts,
):
    member, _ = sign_in_account("sign-in-member")
    provider_link(member.account_id)
    with pytest.raises(PermissionError) as refused:
        provider_sign_in(entry_with(transactions, Admission("maintainer-only")), provider_starts)
    assert str(refused.value) == "credentials unavailable"  # the password path's answer
    assert live_sessions(connect, member.account_id) == 0
    # Once admission opens, the same identity signs in.
    signed_in = provider_sign_in(entry_with(transactions, Admission("open")), provider_starts)
    assert signed_in.public["state"] == "authenticated"
    assert live_sessions(connect, member.account_id) == 1


def test_maintainer_only_refuses_a_members_second_factor_and_issues_nothing(
    transactions, connect, sign_in_account,
):
    from uuid import UUID

    from backend.modules.accounts.services.control_mfa import totp
    from backend.modules.accounts.u8_mfa import CompleteMfaService
    from tests.u8_service_operations_integration.conftest import database_step

    member, email = sign_in_account("sign-in-member")
    opened = entry_with(transactions, Admission("open"))
    seed = activate_factor(connect, opened, member.account_id)
    continuation = opened.login(email, SIGN_IN_PASSWORD, flow_binding="admission")
    assert continuation.public["state"] == "mfa_required"
    closed = entry_with(transactions, Admission("maintainer-only"))
    with pytest.raises(PermissionError):
        CompleteMfaService(closed).verify(
            continuation.token, continuation.csrf,
            UUID(continuation.public["challengeId"]),
            UUID(continuation.public["flowBinding"]), totp(seed, database_step(connect)),
        )
    with connect("accounts") as conn:
        row = conn.execute("SELECT purpose FROM accounts.session WHERE id=%s",
                           (UUID(continuation.public["challengeId"]),)).fetchone()
    assert row["purpose"] == "primary_mfa_continuation"  # never upgraded


def test_admission_is_a_profile_input_with_a_closed_vocabulary(realm, transactions):
    assert Admission.from_profile(realm) is None
    production = SimpleNamespace(is_production=True, admission="maintainer-only")
    assert Admission.from_profile(production) == Admission("maintainer-only")
    for bad in ({"state": "everyone"}, {"state": "maintainer-only", "registration_open": True},
                {"state": "open", "registration_open": "yes"}):
        with pytest.raises(ValueError):
            Admission(**bad)
    # The built entry rules hold where no admission is stated: registration is open.
    assert entry_with(transactions, None).admission is None
