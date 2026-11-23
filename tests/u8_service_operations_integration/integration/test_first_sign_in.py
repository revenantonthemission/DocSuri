"""A migrated account's first sign-in (U8 plan Step 20; BR8.5, BR8.6, NFR2.1, BR6.2, A3).

- **Consent-pending.** An account without a recorded decision for each of v2's consent
  purposes signs in to a 15-minute session that every guard denies; it serves only
  listing and giving consents, and a full session follows once they are recorded.
- **Reset-required.** No session: a reset proof and its mail, and an answer saying whether
  the mail was accepted, held or over the allowance.
- **Administrators.** One with a second factor meets it before any administrator action;
  one without gets a 15-minute setup-only session (decision of 2026-10-22) that serves
  only U2's enrolment, after which the full administrator session follows.
- **The verifier-key replacement** ends every session and every outstanding proof.
- **The sign-in answer** is C02 4.0.0's `AccessSignInResult`, and the consent routes serve
  a consent-pending session for giving consents only (decisions of 2026-10-22).
- **A provider-only first sign-in** (decision of 2026-10-22) goes through the identity
  stand-in (`scripts/u8_identity_standin.py`, Step 43's, built early) and the real ORCID
  adapter, and opens the same consent-pending session, answered as
  `AccessIdentityConsentPending`.
- **The stand-in's answers** (Step 109, R-09): a Google sign-in's redirect back carries
  Google's own `scope`, `authuser` and `prompt` beside `code` and `state`; ORCID's carries
  `code` and `state` only, and a refusal `error` and `state` only.

Everything runs through AccountAccess's services and routers in the composed realm. The
three accounts are the shared sign-in accounts, reset by the fixture before each test.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
import pytest
from docsuri_shared.workspace import wire

from backend.local_browser import ENTRY_COOKIE, SESSION_COOKIE
from backend.local_profile import verifier_key_path
from backend.modules.accounts.control_policy import PolicyUnavailable
from backend.modules.accounts.control_repository import ControlRepository
from backend.modules.accounts.integrations.account_mail import LocalAccountMail
from backend.modules.accounts.local_http import ENTRY_POLICY
from backend.modules.accounts.services.control_mfa import totp
from backend.modules.accounts.services.first_sign_in import REQUIRED_CONSENTS, FirstSignIn
from backend.modules.accounts.u8_mail_outbox import AccountMailSender
from backend.modules.accounts.u8_mfa import CompleteMfaService
from backend.modules.accounts.u8_verifier_key import (
    VERIFIER_KEY_ABSENT,
    replace_verifier_key,
    verifier_key_revision,
)
from backend.modules.operations.allowance import LedgerAllowance
from backend.transactions import Authority, guard
from backend.u8_host import LIFECYCLE_MANIFEST, configure_lifecycle
from backend.u8_policy import SYNTHETIC_OPERATIONS
from tests.u8_service_operations_integration.conftest import (
    SIGN_IN_PASSWORD,
    account_client,
    activate_factor,
    database_step,
    post,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

# Step 85(j): no outbox row outlives its test (Step 54(n)'s `empty_outbox`).
pytestmark = pytest.mark.usefixtures("own_address", "empty_outbox")
PURPOSES =("local-research", "personalization", "account-control", "administration")
NEW_PASSWORD = f"Synthetic-Reset-{uuid4().hex[:12]}-1!"  # per run (L1-36)


class Recording(LocalAccountMail):
    """The built local mailbox, keeping each message it was handed."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages = []

    def deliver(self, message):
        answer = super().deliver(message)
        self.messages.append((message, answer))
        return answer


class FixedGate:
    """The provider gate's port, answering one state (Step 21's activation answers it in
    the assembly)."""

    def __init__(self, state: str, mode: str = "live"):
        self._state, self.mode = state, mode

    def state(self, provider: str) -> str:
        return self._state


def authority_of(public: dict) -> Authority:
    session = public["session"]
    return Authority(UUID(session["accountId"]), UUID(session["sessionId"]))


def denied_everywhere(connect, authority) -> bool:
    for purpose in PURPOSES:
        try:
            with connect("library") as conn:
                guard(conn, authority, purpose=purpose)
        except Exception:  # noqa: BLE001 - the guard's denial is the answer under test
            continue
        return False
    return True


def session_row(connect, session_id) -> dict:
    with connect("accounts") as conn:
        return conn.execute("SELECT * FROM accounts.session WHERE id=%s",
                            (session_id,)).fetchone()


# 1 and 2. Consent-pending, then a full session -------------------------------------------


def test_a_consent_pending_session_is_denied_everything_but_giving_consents(
    connect, d1_entry, sign_in_account,
):
    _, email = sign_in_account("sign-in-migrated", consents=False)
    result = d1_entry.login(email, SIGN_IN_PASSWORD, flow_binding="first")
    public = result.public
    assert public["state"] == "consent_pending"
    assert public["consentPurposeIds"] == list(REQUIRED_CONSENTS)
    assert dt.datetime.fromisoformat(public["expiresAt"]) == d1_entry.clock() + dt.timedelta(
        seconds=d1_entry.control_policy.limited_session_seconds)
    authority = authority_of(public)
    assert session_row(connect, authority.session_id)["purpose"] == "consent_pending"
    assert denied_everywhere(connect, authority)
    for call in (
        lambda: d1_entry.inspect_session(result.token),
        lambda: ControlRepository(d1_entry.transactions, d1_entry.control_policy).profile(
            authority),
        lambda: CompleteMfaService(d1_entry).begin(authority, SIGN_IN_PASSWORD, uuid4()),
        lambda: d1_entry.first_sign_in.setup_authority(result.token, result.csrf),
    ):
        with pytest.raises(Exception) as refused:
            call()
        assert isinstance(refused.value, PermissionError) or "denied" in str(refused.value)
    # What it may do: list v2's purposes, none decided yet.
    account_id, items = d1_entry.first_sign_in.consents(result.token, result.csrf)
    assert account_id == authority.account_id
    assert [(item["purpose"], item["granted"]) for item in items] == [
        (purpose, False) for purpose in REQUIRED_CONSENTS]
    assert [item["revision"] for item in items] == [
        FirstSignIn.pending_revision(account_id, purpose) for purpose in REQUIRED_CONSENTS]
    with pytest.raises(PermissionError):
        d1_entry.first_sign_in.consents(result.token, "f" * 64)  # a foreign CSRF token


def give_all(entry, result, account_id):
    first = entry.first_sign_in
    outcomes = []
    for purpose, granted in (("local-research", True), ("personalization", False)):
        outcomes.append(first.give_consent(
            result.token, result.csrf, uuid4(),
            UUID(FirstSignIn.pending_revision(account_id, purpose)), purpose, granted,
        ))
    return outcomes


def test_recording_the_consents_turns_a_members_session_into_a_full_one(
    connect, d1_entry, sign_in_account,
):
    _, email = sign_in_account("sign-in-migrated", consents=False)
    result = d1_entry.login(email, SIGN_IN_PASSWORD, flow_binding="first")
    authority = authority_of(result.public)
    research, personalization = give_all(d1_entry, result, authority.account_id)
    assert research.completion == "pending" and research.record["decision"] == "granted"
    assert personalization.completion == "full_session"
    assert personalization.expires_at == d1_entry.clock() + dt.timedelta(
        seconds=d1_entry.control_policy.full_session_seconds("member"))
    row = session_row(connect, authority.session_id)
    assert (row["purpose"], row["expires_at"]) == ("full_session", personalization.expires_at)
    assert d1_entry.inspect_session(result.token).public["state"] == "authenticated"
    with connect("accounts") as conn:
        stored = {item["purpose"]: item["granted"] for item in conn.execute(
            "SELECT purpose,granted FROM accounts.consent WHERE account_id=%s",
            (authority.account_id,)).fetchall()}
    assert stored == {"local-research": True, "personalization": False}
    with connect("library") as conn:
        guard(conn, authority, purpose="local-research")
    # The next sign-in is an ordinary one.
    assert d1_entry.login(email, SIGN_IN_PASSWORD, flow_binding="first").public[
        "state"] == "authenticated"


def test_a_stale_or_unknown_consent_decision_changes_nothing(connect, d1_entry, sign_in_account):
    _, email = sign_in_account("sign-in-migrated", consents=False)
    result = d1_entry.login(email, SIGN_IN_PASSWORD, flow_binding="first")
    first = d1_entry.first_sign_in
    with pytest.raises(ValueError):
        first.give_consent(result.token, result.csrf, uuid4(), uuid4(), "local-research", True)
    with pytest.raises(ValueError):
        first.give_consent(result.token, result.csrf, uuid4(), uuid4(), "marketing", True)
    with connect("accounts") as conn:
        assert conn.execute("SELECT count(*) AS n FROM accounts.consent WHERE account_id=%s",
                            (authority_of(result.public).account_id,)).fetchone()["n"] == 0


def test_an_administrators_consents_end_the_session_and_the_next_sign_in_meets_mfa_setup(
    connect, d1_entry, sign_in_account,
):
    _, email = sign_in_account("sign-in-admin", role="administrator", consents=False)
    result = d1_entry.login(email, SIGN_IN_PASSWORD, flow_binding="first")
    assert result.public["state"] == "consent_pending"
    authority = authority_of(result.public)
    _, last = give_all(d1_entry, result, authority.account_id)
    assert last.completion == "sign_in_again"
    assert session_row(connect, authority.session_id)["revoked"]
    after = d1_entry.login(email, SIGN_IN_PASSWORD, flow_binding="first")
    assert after.public["state"] == "authenticated"
    assert session_row(connect, authority_of(after.public).session_id)["purpose"] == "mfa"


# 3. Reset-required ------------------------------------------------------------------------


def reset_entry(d1_entry, **adapter):
    d1_entry.account_mail = Recording(d1_entry.mail, **adapter)
    return d1_entry.account_mail


def test_a_reset_required_account_gets_its_mail_and_a_retry_sends_nothing_twice(
    connect, d1_entry, sign_in_account,
):
    account, email = sign_in_account("sign-in-migrated", consents=False, reset_required=True)
    mail = reset_entry(d1_entry)
    operation = uuid4()
    probe = "probe-" + uuid4().hex[:12]  # any value is answered alike; generated (L1-36)
    answer = d1_entry.login(email, probe, operation=operation, flow_binding="first")
    assert (answer.token, answer.public["state"], answer.public["delivery"]) == (
        "", "reset_required", "accepted")
    again = d1_entry.login(email, probe, operation=operation, flow_binding="first")
    assert again.public == answer.public and len(mail.messages) == 1
    message = mail.messages[0][0]
    assert message.message_key == answer.public["messageKey"]
    assert message.account_id == account.account_id
    with connect("accounts") as conn:
        assert not conn.execute("SELECT 1 FROM accounts.session WHERE account_id=%s AND NOT "
                                "revoked", (account.account_id,)).fetchone()
    # The mailed proof completes the reset, which clears the marker; the next sign-in is
    # the first one with v2's consents still to give.
    payload = message.payload
    d1_entry.complete_password_reset(uuid4(), UUID(payload["challengeId"]), payload["proof"],
                                     payload["flowBinding"], NEW_PASSWORD)
    with connect("accounts") as conn:
        assert not conn.execute("SELECT reset_required FROM accounts.account WHERE id=%s",
                                (account.account_id,)).fetchone()["reset_required"]
    assert d1_entry.login(email, NEW_PASSWORD, flow_binding="first").public[
        "state"] == "consent_pending"


@pytest.fixture
def operations_ledger(tmp_path, clock):
    """ServiceOperations' ledger component in a private folder (the allowance's store)."""
    from backend.modules.operations.ledger import Ledger

    folder = tmp_path / "operations-ledger"
    folder.mkdir(mode=0o700)
    value = Ledger.open(folder, clock=clock)
    yield value
    value.close()


def proofs_of(connect, account_id) -> int:
    with connect("accounts") as conn:
        return conn.execute("SELECT count(*) AS n FROM accounts.control_proof WHERE "
                            "account_id=%s", (account_id,)).fetchone()["n"]


def test_reset_mail_that_is_held_or_over_the_allowance_is_said_so(
    connect, d1_entry, sign_in_account, operations_ledger,
):
    ledger = operations_ledger
    account, email = sign_in_account("sign-in-migrated", consents=False, reset_required=True)
    proofs = proofs_of(connect, account.account_id)
    held = reset_entry(d1_entry, gate=FixedGate("held"))
    short = uuid4().hex[:1]  # a one-character value, generated per run (L1-36)
    assert d1_entry.login(email, short, flow_binding="first").public["delivery"] == "held"
    # Step 53(i)'s check answers before `deliver()` (Step 85(l), L1-71).
    assert held.messages == []
    tight = dataclasses.replace(SYNTHETIC_OPERATIONS, digest_daily_limit=1,
                                account_mail_daily_limit=1)
    allowance = LedgerAllowance(ledger, tight)
    allowance.reserve("account", str(uuid4()))  # the day's one place is taken
    spent = reset_entry(d1_entry, allowance=allowance)
    assert d1_entry.login(email, short, flow_binding="first").public["delivery"] == (
        "over_allowance")
    assert spent.messages == []
    assert proofs_of(connect, account.account_id) == proofs
    # An active gate and a free place: accepted, and the place is settled.
    roomy = LedgerAllowance(ledger, SYNTHETIC_OPERATIONS)
    reset_entry(d1_entry, allowance=roomy, gate=FixedGate("active"))
    accepted = d1_entry.login(email, short, flow_binding="first").public
    assert accepted["delivery"] == "accepted"
    assert ledger.get("email-allowance", _reservation(accepted["messageKey"]))["state"] == (
        "settled")


def _reservation(message_key: str) -> str:
    from backend.modules.operations.allowance import reservation_id

    return reservation_id("account", message_key)


# 4. An administrator with a second factor meets it first ---------------------------------


def test_an_administrator_meets_the_second_factor_before_any_administrator_action(
    connect, d1_entry, sign_in_account,
):
    administrator, email = sign_in_account("sign-in-admin", role="administrator")
    seed = activate_factor(connect, d1_entry, administrator.account_id)
    continuation = d1_entry.login(email, SIGN_IN_PASSWORD, flow_binding="first")
    assert continuation.public["state"] == "mfa_required"
    pending = Authority(administrator.account_id, UUID(continuation.public["challengeId"]))
    assert denied_everywhere(connect, pending)
    session = CompleteMfaService(d1_entry).verify(
        continuation.token, continuation.csrf, UUID(continuation.public["challengeId"]),
        UUID(continuation.public["flowBinding"]), totp(seed, database_step(connect)),
    ).public["session"]
    assert session["authenticationLevel"] == "mfa"
    with connect("library") as conn:
        guard(conn, authority_of({"session": session}), purpose="administration")


# 5. The verifier-key replacement ---------------------------------------------------------


def outstanding(connect) -> dict:
    with connect("accounts") as conn:
        return conn.execute(
            "SELECT (SELECT count(*) FROM accounts.session WHERE NOT revoked) AS sessions,"
            "(SELECT count(*) FROM accounts.control_proof WHERE consumed_at IS NULL AND "
            "expires_at>clock_timestamp()) AS proofs").fetchone()


def test_the_verifier_key_replacement_ends_every_session_and_outstanding_proof(
    realm, connect, d1_entry, sign_in_account, tmp_path,
):
    administrator, admin_email = sign_in_account("sign-in-admin", role="administrator")
    _, member = sign_in_account("sign-in-member")
    full = d1_entry.login(member, SIGN_IN_PASSWORD, flow_binding="first")
    reset_operation = uuid4()
    d1_entry.request_password_reset(reset_operation, member, "first")
    reset_key = d1_entry._mail_identity("password-reset", reset_operation)[2]
    _, migrated = sign_in_account("sign-in-migrated", consents=False)
    pending = d1_entry.login(migrated, SIGN_IN_PASSWORD, flow_binding="first")
    realm_key = verifier_key_path(realm).read_bytes()
    now = d1_entry.clock()
    copy = tmp_path / "account-verifier.key"
    copy.write_bytes(realm_key)
    copy.chmod(0o600)
    before = outstanding(connect)
    assert before["sessions"] >= 2 and before["proofs"] >= 1
    # A stale revision and an unknown reason change nothing.
    with pytest.raises(ValueError):
        replace_verifier_key(d1_entry.transactions, expected_key_revision="0" * 32,
                             reason_key="verifier-key-exposed", now=now, key_path=copy)
    with pytest.raises(ValueError):
        replace_verifier_key(d1_entry.transactions,
                             expected_key_revision=verifier_key_revision(copy),
                             reason_key="because", now=now, key_path=copy)
    # While the key is present, a factor still protected under its legacy version would be
    # lost: refused until the keyring re-protects it.
    activate_factor(connect, d1_entry, administrator.account_id)
    with pytest.raises(PolicyUnavailable):
        replace_verifier_key(d1_entry.transactions,
                             expected_key_revision=verifier_key_revision(copy),
                             reason_key="verifier-key-rotation", now=now, key_path=copy)
    assert outstanding(connect) == before and copy.read_bytes() == realm_key
    # The lost key: replaced, and nothing signed under it verifies again.
    lost = tmp_path / "lost" / "account-verifier.key"
    lost.parent.mkdir(mode=0o700)
    result = replace_verifier_key(d1_entry.transactions,
                                  expected_key_revision=VERIFIER_KEY_ABSENT,
                                  reason_key="verifier-key-lost", now=now, key_path=lost)
    assert result["sessionsEnded"] >= before["sessions"]
    assert result["proofsEnded"] >= before["proofs"]
    assert result["keyRevision"] not in (VERIFIER_KEY_ABSENT, verifier_key_revision(copy))
    assert result["replacedAt"] == now.isoformat()
    assert outstanding(connect) == {"sessions": 0, "proofs": 0}
    for session in (full.public["session"]["sessionId"], pending.public["session"]["sessionId"]):
        assert session_row(connect, UUID(session))["revoked"]
    assert lost.stat().st_mode & 0o777 == 0o600 and len(lost.read_bytes()) == 32
    assert verifier_key_path(realm).read_bytes() == realm_key  # the realm's key untouched
    assert admin_email  # the administrator's factor stays recorded, its sessions ended
    # The reset request's message waits in the outbox (Step 53(h)); the replacement ended
    # its proof, so one pass with a raise-only account mail ends the row unsent (Step
    # 85(j)): nothing is delivered, no file reaches the mailbox and no row is left.
    files = {path.name for path in d1_entry.mail.root.glob("*.blob")}
    with connect("accounts") as conn:
        assert [str(row["message_key"]) for row in conn.execute(
            "SELECT message_key FROM accounts.mail_outbox WHERE message_key=%s",
            (reset_key,)).fetchall()] == [reset_key]
    previous, raise_only = d1_entry.account_mail, RaiseOnlyMail()
    d1_entry.account_mail = raise_only
    try:
        AccountMailSender(d1_entry).run_once()
    finally:
        d1_entry.account_mail = previous
    assert raise_only.calls == 0
    assert {path.name for path in d1_entry.mail.root.glob("*.blob")} == files
    with connect("accounts") as conn:
        assert conn.execute("SELECT 1 FROM accounts.mail_outbox WHERE message_key=%s",
                            (reset_key,)).fetchone() is None
        assert conn.execute("SELECT 1 FROM accounts.mail_outbox").fetchone() is None


class RaiseOnlyMail:
    """An account mail whose only method is a `deliver` that raises."""

    def __init__(self) -> None:
        self.calls = 0

    def deliver(self, message):
        self.calls += 1
        raise RuntimeError("no account mail may be delivered here")


# 6. A migrated administrator without a second factor -------------------------------------


def test_a_migrated_administrator_without_a_factor_gets_a_setup_only_session(
    connect, d1_entry, sign_in_account,
):
    administrator, email = sign_in_account("sign-in-admin", role="administrator")
    result = d1_entry.login(email, SIGN_IN_PASSWORD, flow_binding="first")
    public = result.public
    assert public["state"] == "authenticated"
    assert public["session"]["authenticationLevel"] == "primary"
    authority = authority_of(public)
    row = session_row(connect, authority.session_id)
    assert row["purpose"] == "mfa"
    assert row["expires_at"] == d1_entry.clock() + dt.timedelta(
        seconds=d1_entry.control_policy.limited_session_seconds)
    assert denied_everywhere(connect, authority)
    with pytest.raises(PermissionError):
        d1_entry.inspect_session(result.token)
    with pytest.raises(PermissionError):
        d1_entry.first_sign_in.consents(result.token, result.csrf)
    mfa = CompleteMfaService(d1_entry)
    # The full-session path refuses it: the database's session guard denies the authority.
    with pytest.raises(psycopg.errors.InsufficientPrivilege, match="authority denied"):
        mfa.begin(authority, SIGN_IN_PASSWORD, uuid4())
    setup = d1_entry.first_sign_in.setup_authority(result.token, result.csrf)
    assert setup == authority
    enrolment = mfa.begin(setup, SIGN_IN_PASSWORD, uuid4(), setup=True)
    material = mfa.material(setup, UUID(enrolment["enrollmentId"]),
                            enrolment["deliveryReference"], setup=True)
    step = database_step(connect)
    mfa.confirm(setup, UUID(enrolment["enrollmentId"]), totp(material["seed"], step), uuid4(),
                setup=True)
    assert session_row(connect, authority.session_id)["revoked"]  # ended with the enrolment
    # The full administrator session follows: the password, then the new factor.
    continuation = d1_entry.login(email, SIGN_IN_PASSWORD, flow_binding="first")
    assert continuation.public["state"] == "mfa_required"
    session = mfa.verify(
        continuation.token, continuation.csrf, UUID(continuation.public["challengeId"]),
        UUID(continuation.public["flowBinding"]), totp(material["seed"], step + 1),
    ).public["session"]
    assert session["authenticationLevel"] == "mfa"
    with connect("library") as conn:
        guard(conn, authority_of({"session": session}), purpose="administration")


def test_the_setup_path_refuses_a_members_full_session(connect, d1_entry, sign_in_account):
    _, member = sign_in_account("sign-in-member")
    full = d1_entry.login(member, SIGN_IN_PASSWORD, flow_binding="first")
    with pytest.raises(PermissionError):
        d1_entry.first_sign_in.setup_authority(full.token, full.csrf)
    with pytest.raises(PermissionError):
        CompleteMfaService(d1_entry).begin(authority_of(full.public), SIGN_IN_PASSWORD,
                                           uuid4(), setup=True)


def identities(entry):
    from backend.modules.accounts.services.control_identity import FixtureIdentityProvider
    from backend.modules.accounts.u8_identity import ArrivalIdentityService

    return ArrivalIdentityService(
        entry, {name: FixtureIdentityProvider(name) for name in ("google", "orcid")})


def test_each_identity_adapter_registers_the_workspace_page(d1_entry):
    """D3: under a D1-shaped policy each adapter's callback is the workspace page, which
    the shell serves; an adapter registered anywhere else is refused."""
    service = identities(d1_entry)
    assert {name: adapter.callback for name, adapter in service.providers.items()} == {
        name: realm_origin(d1_entry) + "/sign-in/callback/" + name
        for name in ("google", "orcid")}
    d1_entry.identity_providers = {"orcid": SimpleNamespace(
        name="orcid", callback="https://127.0.0.1:18110/api/v2/identity/callback/orcid")}
    with pytest.raises(ValueError):
        identities(d1_entry)


def realm_origin(entry) -> str:
    return entry.transactions.profile.origin


def provider_only(connect, transactions, account, subject: str) -> UUID:
    """The account as the migration leaves an ORCID-only v1 account: no password verifier
    and one ORCID link, each written through AccountAccess's own import operation (A4).
    Returns the link's identity."""
    from backend.modules.accounts.repository.imports import AccountImports

    with connect("accounts") as conn:
        row = conn.execute("SELECT * FROM accounts.account WHERE id=%s",
                           (account.account_id,)).fetchone()
    imports, link = AccountImports(transactions), uuid4()
    assert imports.import_account(
        account.account_id, email=row["email"], email_verified=True, role="member",
        display_name=row["display_name"], password_verifier=None, reset_required=False,
        created_at=row["created_at"],
    )["disposition"] == "updated"
    assert imports.import_identity_link(
        link, account_id=account.account_id, provider="orcid", subject=subject,
        linked_at=dt.datetime(2026, 9, 1, tzinfo=dt.UTC),
    )["disposition"] == "imported"
    return link


def test_a_provider_only_first_sign_in_through_the_identity_standin_is_consent_pending(
    realm, connect, transactions, d1_entry, sign_in_account, own_address, provider_starts,
):
    """A migrated ORCID-only account's first sign-in (decision of 2026-10-22): through the
    identity stand-in's page, the real ORCID adapter and the callback route, it opens the
    password path's 15-minute consent-pending session, which every guard denies but the
    consent routes serve; recording the consents makes it a full session."""
    from urllib.parse import parse_qs, urlsplit

    import httpx
    from docsuri_shared.workspace import execution

    from backend.modules.accounts.integrations.identity_providers import OrcidIdentityProvider
    from u8_identity_standin import (
        CLIENTS,
        Identity,
        IdentityStandin,
        RecordedAnswers,
        client_context,
        page_target,
    )

    account, _ = sign_in_account("sign-in-migrated", consents=False)
    subject = f"0000-0002-{uuid4().int % 10_000:04d}-{uuid4().int % 10_000:04d}"
    link = provider_only(connect, transactions, account, subject)
    standin = IdentityStandin(realm)
    answers = RecordedAnswers(standin)
    standin.sign_in_as("orcid", Identity(subject))
    d1_entry.identity_providers = {"orcid": OrcidIdentityProvider(
        client_id=CLIENTS["orcid"], client_secret=orcid_client_secret(),
        origin=realm.origin, client_factory=answers.client_factory)}
    lifecycle = configure_lifecycle(d1_entry, LIFECYCLE_MANIFEST)
    policy = d1_entry.control_policy
    try:
        with (standin.running(),
              httpx.Client(verify=client_context(realm), timeout=10) as browser,
              account_client(realm, d1_entry, lifecycle, address=own_address) as client):
            boot = client.get("/api/v2/session")
            # Step 85(a): the bootstrap's entry cookie is a private cookie of the realm.
            [entry_cookie] = entry_cookies(boot)
            assert_private_cookie(entry_cookie)
            csrf = boot.json()["csrfToken"]
            begun = post(client, "/api/v2/c02/access-begin-identity-flow", {
                "provider": "orcid", "intent": "sign_in", "returnRouteId": "account",
                "policyRef": policy.reference,
            }, csrf)
            assert begun.status_code == 200, begun.text
            wire.AccessProviderRedirect.model_validate(begun.json())
            # Counted under the test's own address and entry cookie, then aged and deleted
            # (Step 20 item 9).
            redirect = provider_starts.track(begun.json())
            # The browser at the provider's page, a different site, and back (D3).
            page = browser.get(page_target(redirect["authorizationUrl"]))
            assert page.status_code == 302, page.text
            back = urlsplit(page.headers["location"])
            assert f"{back.scheme}://{back.netloc}{back.path}" == (
                realm.origin + "/sign-in/callback/orcid")
            query = {key: values[0] for key, values in parse_qs(back.query).items()}
            arrived = client.get("/api/v2/identity/callback/orcid", params={
                "flow": redirect["flowId"], "state": query["state"], "code": query["code"]})
            assert arrived.status_code == 200, arrived.text
            body = arrived.json()
            execution.AccessIdentityResult.model_validate(body)
            assert body["state"] == "consent_pending"
            assert body["consentPurposeIds"] == list(REQUIRED_CONSENTS)
            assert (body["identityLink"]["provider"], body["identityLink"]["providerSubject"],
                    body["identityLink"]["identityLinkId"]) == ("orcid", subject, str(link))
            assert dt.datetime.fromisoformat(body["expiresAt"]) == d1_entry.clock() + (
                dt.timedelta(seconds=policy.limited_session_seconds))
            [cookie] = session_cookies(arrived)
            assert f"Max-Age={policy.limited_session_seconds}" in cookie
            assert_private_cookie(cookie)
            # Step 44's gap: the completed first sign-in read again answers the same,
            # while its consent-pending session is current.
            again = client.get("/api/v2/identity/callback/orcid", params={
                "flow": redirect["flowId"], "state": query["state"], "code": query["code"]})
            assert again.status_code == 200, again.text
            assert again.json() == body
            authority = authority_of(body)
            assert authority.account_id == account.account_id
            assert session_row(connect, authority.session_id)["purpose"] == "consent_pending"
            # Every guard denies it; nothing but the consent routes serves it.
            assert denied_everywhere(connect, authority)
            token = client.cookies[SESSION_COOKIE]
            csrf = d1_entry.verifier("session-csrf", token)
            for path, value in (("/api/v2/c02/access-read-profile", {}),
                                ("/api/v2/c02/access-list-identity-links",
                                 {"page": {"limit": 10}})):
                assert post(client, path, value, csrf).status_code in (401, 403), path
            assert client.get("/api/v2/session").json()["signedIn"] is False
            listed = post(client, "/api/v2/c02/access-list-consents", {"page": {"limit": 10}},
                          csrf)
            assert listed.status_code == 200, listed.text
            given = None
            for item, decision in zip(listed.json()["items"], ("granted", "revoked"),
                                      strict=True):
                given = post(client, "/api/v2/c02/access-update-consent", {
                    "purposeId": item["purposeId"], "decision": decision,
                    "policyRef": policy.reference, "expectedRevision": item["revision"],
                }, csrf)
                assert given.status_code == 200, given.text
            # A full session of the member's length follows.
            [cookie] = session_cookies(given)
            assert f"Max-Age={policy.full_session_seconds('member')}" in cookie
            assert_private_cookie(cookie)
            assert client.get("/api/v2/session").json()["signedIn"] is True
            assert session_row(connect, authority.session_id)["purpose"] == "full_session"
            with connect("library") as conn:
                guard(conn, authority, purpose="local-research")
            # The stand-in's code was redeemed once, for this flow's PKCE verifier.
            assert [item.used for item in standin.issued.values()] == [True]
    finally:
        with connect("accounts") as conn:
            conn.execute("DELETE FROM accounts.identity_link WHERE id=%s", (link,))


def orcid_client_secret() -> str:
    """The ORCID adapter's client secret, generated per run (L1-36)."""
    return "realm-orcid-client-secret-" + uuid4().hex


def generated_password() -> str:
    """A new password that meets the password policy, generated per run (L1-36)."""
    return f"Synthetic-{uuid4().hex[:16]}-Aa1!"


def entry_cookies(answer) -> list[str]:
    return [value for value in answer.headers.get_list("set-cookie")
            if value.startswith(ENTRY_COOKIE + "=")]


def assert_private_cookie(cookie: str) -> None:
    """Step 85(a): `Secure`, `HttpOnly`, `SameSite=strict` (compared case-insensitively),
    `Path=/` and no `Domain`."""
    parts = [part.strip().lower() for part in cookie.split(";")[1:]]
    assert "secure" in parts and "httponly" in parts, cookie
    assert "samesite=strict" in parts and "path=/" in parts, cookie
    assert not any(part.startswith("domain") for part in parts), cookie


class StandInClock:
    """A stand-in for the name `time` inside `preauthentication` only (Step 85(a)): it moves
    the entry context's clock and nothing else, so `OwnerTransactions.run`, `fresh_expiry`
    and the client's cookie jar keep reading real time."""

    def __init__(self, now: int):
        self.now = now

    def time(self) -> float:
        return float(self.now)


def issued_of(cookie: str) -> int:
    return int(cookie.split(".")[1])


def flow_of(cookie: str) -> str:
    return cookie.split(".")[3]


def test_an_abandoned_flows_entry_context_simply_expires_after_15_minutes(
    realm, d1_entry, own_address, provider_starts, monkeypatch,
):
    """D3 (Step 85(a)): a sign-in begun and never finished leaves only its entry context,
    which ends 900 s after it was issued; the next bootstrap issues a new flow."""
    from backend.modules.accounts import preauthentication
    from backend.modules.accounts.integrations.identity_providers import OrcidIdentityProvider
    from backend.modules.accounts.preauthentication import Preauthentication
    from u8_identity_standin import CLIENTS, IdentityStandin, RecordedAnswers

    answers = RecordedAnswers(IdentityStandin(realm))
    d1_entry.identity_providers = {"orcid": OrcidIdentityProvider(
        client_id=CLIENTS["orcid"], client_secret=orcid_client_secret(),
        origin=realm.origin, client_factory=answers.client_factory)}
    lifecycle = configure_lifecycle(d1_entry, LIFECYCLE_MANIFEST)
    with account_client(realm, d1_entry, lifecycle, address=own_address) as client:
        boot = client.get("/api/v2/session")
        [cookie_header] = entry_cookies(boot)
        cookie = client.cookies[ENTRY_COOKIE]
        assert cookie_header.startswith(ENTRY_COOKIE + "=" + cookie)
        issued = issued_of(cookie)
        begun = post(client, "/api/v2/c02/access-begin-identity-flow", {
            "provider": "orcid", "intent": "sign_in", "returnRouteId": "account",
            "policyRef": d1_entry.control_policy.reference,
        }, boot.json()["csrfToken"])
        assert begun.status_code == 200, begun.text
        provider_starts.track(begun.json())
        assert entry_cookies(begun) == []  # the flow sets no new entry context
        clock = StandInClock(issued + 899)
        monkeypatch.setattr(preauthentication, "time", clock)
        assert Preauthentication(d1_entry).read(cookie).expires_at == issued + 900
        clock.now = issued + 900
        with pytest.raises(PermissionError, match="entry context unavailable"):
            Preauthentication(d1_entry).read(cookie)
        assert client.cookies[ENTRY_COOKIE] == cookie  # the jar still sends the old one
        again = client.get("/api/v2/session")
        [renewed] = entry_cookies(again)
        fresh = renewed.split(";")[0].split("=", 1)[1]
        assert issued_of(fresh) == issued + 900
        assert flow_of(fresh) != flow_of(cookie)


def test_the_asking_browsers_own_link_is_refused_once_its_entry_context_has_ended(
    realm, connect, d1_entry, sign_in_account, own_address, monkeypatch,
):
    """L1-54 (Step 85(a)): a reset link asked for in the context's last second is refused
    after the context ends, in the asking browser as in any other, and its proof stays
    unused; the proof's own 300 s run on the database's clock, which this test leaves."""
    from backend.modules.accounts import preauthentication

    mail = reset_entry(d1_entry)
    _, email = sign_in_account("sign-in-member")
    lifecycle = configure_lifecycle(d1_entry, LIFECYCLE_MANIFEST)
    proof_id = None
    try:
        with account_client(realm, d1_entry, lifecycle, address=own_address) as client:
            boot = client.get("/api/v2/session")
            cookie = client.cookies[ENTRY_COOKIE]
            issued = issued_of(cookie)
            clock = StandInClock(issued + 899)
            monkeypatch.setattr(preauthentication, "time", clock)
            asked = post(client, "/api/v2/c02/access-request-password-reset", {
                "email": email, "policyRef": d1_entry.control_policy.reference,
            }, boot.json()["csrfToken"])
            assert asked.status_code == 200, asked.text
            AccountMailSender(d1_entry).run_once()  # Step 53(h), L1-69
            [(message, delivery)] = mail.messages
            assert delivery == "accepted"
            payload = message.payload
            proof_id = UUID(payload["challengeId"])
            assert payload["flowBinding"] == flow_of(cookie)
            clock.now = issued + 900
            renewed = client.get("/api/v2/session")
            assert flow_of(client.cookies[ENTRY_COOKIE]) != flow_of(cookie)
            refused = post(client, "/api/v2/c02/access-complete-password-reset", {
                "verification": {key: payload[key] for key in (
                    "challengeId", "proof", "flowBinding")},
                "newPassword": generated_password(),
            }, renewed.json()["csrfToken"])
            assert (refused.status_code, refused.json()["code"]) == (403, "FORBIDDEN")
        with connect("accounts") as conn:
            row = conn.execute("SELECT consumed_at,expires_at>clock_timestamp() AS fresh "
                               "FROM accounts.control_proof WHERE id=%s",
                               (proof_id,)).fetchone()
        assert row["consumed_at"] is None
        assert row["fresh"]  # still inside its 300 s: only the entry context ended
    finally:
        if proof_id is not None:
            # No outstanding proof outlives the test on the shared member.
            with connect("accounts") as conn:
                conn.execute("UPDATE accounts.control_proof SET expires_at=clock_timestamp()"
                             "-interval '1 second' WHERE id=%s", (proof_id,))


def test_the_identity_standin_answers_only_its_registration(realm):
    """The stand-in's page refuses an unregistered client or redirect and a missing PKCE
    challenge, redirects back with `error` when the person refuses, and serves only the
    composed realm (BR7.1)."""
    from urllib.parse import parse_qs, urlencode, urlsplit

    from u8_identity_standin import CLIENTS, ORIGIN, IdentityStandin

    standin = IdentityStandin(realm)
    request = {"client_id": CLIENTS["orcid"], "redirect_uri": standin.callback("orcid"),
               "response_type": "code", "scope": "openid", "state": "s" * 32,
               "nonce": "n" * 32, "code_challenge": "c" * 43, "code_challenge_method": "S256"}
    standin.refuse("orcid")
    back = urlsplit(standin.redirect("/oauth/authorize?" + urlencode(request)))
    assert parse_qs(back.query) == {"error": ["access_denied"], "state": ["s" * 32]}
    for change in ({"client_id": "APP-SOMEONE-ELSE"},
                   {"redirect_uri": "https://evil.example/sign-in/callback/orcid"},
                   {"redirect_uri": realm.origin + "/api/v2/identity/callback/orcid"},
                   {"code_challenge_method": "plain"}, {"scope": "openid email"}):
        with pytest.raises(ValueError):
            standin.redirect("/oauth/authorize?" + urlencode({**request, **change}))
    assert ORIGIN == "https://localhost:18114"  # a different site from the realm's origin
    production = SimpleNamespace(is_production=True, realm="service-operations")
    with pytest.raises(ValueError):
        IdentityStandin(production)


def test_the_identity_standins_google_return_carries_googles_own_keys(realm):
    """A Google sign-in's redirect back carries the keys Google's own adds (`scope`,
    `authuser`, `prompt`) beside `code` and `state`, and no `flow`; ORCID's carries `code`
    and `state` only; a refusal carries `error` and `state` only (R-09). No server starts
    and no request leaves: `redirect` answers the page's `Location` directly."""
    from urllib.parse import parse_qs, urlencode, urlsplit

    from u8_identity_standin import CLIENTS, Identity, IdentityStandin

    standin = IdentityStandin(realm)
    standin.sign_in_as("google", Identity("google-" + uuid4().hex))
    standin.sign_in_as("orcid", Identity("orcid-" + uuid4().hex))

    # The request the real Google adapter builds (v1's `oidc.py`).
    google = {"client_id": CLIENTS["google"], "redirect_uri": standin.callback("google"),
              "response_type": "code", "scope": "openid email", "state": "g" * 32,
              "nonce": "n" * 32, "code_challenge": "c" * 43, "code_challenge_method": "S256",
              "prompt": "select_account"}
    back = urlsplit(standin.redirect("/o/oauth2/v2/auth?" + urlencode(google)))
    assert f"{back.scheme}://{back.netloc}{back.path}" == realm.origin + "/sign-in/callback/google"
    query = parse_qs(back.query, strict_parsing=True)
    assert sorted(query) == ["authuser", "code", "prompt", "scope", "state"]
    assert all(len(values) == 1 for values in query.values())
    assert query["scope"] == ["email openid https://www.googleapis.com/auth/userinfo.email"]
    assert query["authuser"] == ["0"]
    assert query["prompt"] == ["consent"]
    assert query["state"] == [google["state"]]
    [code] = query["code"]
    assert standin.issued[code].used is False

    # The request ORCID's adapter builds: no `prompt`, and an answer of `code` and `state`.
    orcid = {"client_id": CLIENTS["orcid"], "redirect_uri": standin.callback("orcid"),
             "response_type": "code", "scope": "openid", "state": "o" * 32,
             "nonce": "m" * 32, "code_challenge": "d" * 43, "code_challenge_method": "S256"}
    answered = parse_qs(urlsplit(standin.redirect("/oauth/authorize?" + urlencode(orcid))).query,
                        strict_parsing=True)
    assert sorted(answered) == ["code", "state"]
    assert all(len(values) == 1 for values in answered.values())
    assert answered["state"] == [orcid["state"]]

    # A refusal carries `error` and `state` only, as both providers' refusals do.
    standin.refuse("google")
    refused = parse_qs(urlsplit(standin.redirect("/o/oauth2/v2/auth?" + urlencode(google))).query,
                       strict_parsing=True)
    assert refused == {"error": ["access_denied"], "state": [google["state"]]}


# 7. The sign-in answer and the consent routes, over HTTP ----------------------------------


def sign_in(client, email: str, password: str = SIGN_IN_PASSWORD):
    csrf = client.get("/api/v2/session").json()["csrfToken"]
    return post(client, "/api/v2/c02/access-login",
                {"email": email, "password": password, "policyRef": ENTRY_POLICY}, csrf)


def session_cookies(answer) -> list[str]:
    return [value for value in answer.headers.get_list("set-cookie")
            if value.startswith(SESSION_COOKIE + "=")]


def test_the_sign_in_answer_and_the_consent_routes_over_http(
    realm, d1_entry, sign_in_account, own_address,
):
    lifecycle = configure_lifecycle(d1_entry, LIFECYCLE_MANIFEST)
    _, email = sign_in_account("sign-in-migrated", consents=False)
    with account_client(realm, d1_entry, lifecycle, address=own_address) as client:
        answer = sign_in(client, email)
        assert answer.status_code == 200, answer.text
        value = wire.AccessSignInResult.model_validate(answer.json())
        assert value.model_dump(mode="json")["state"] == "consent_pending"
        token = client.cookies[SESSION_COOKIE]
        csrf = d1_entry.verifier("session-csrf", token)
        # The bootstrap keeps the limited cookie and hands it its CSRF token.
        boot = client.get("/api/v2/session")
        assert boot.json()["signedIn"] is False and boot.json()["csrfToken"] == csrf
        assert session_cookies(boot) == []
        listed = post(client, "/api/v2/c02/access-list-consents", {"page": {"limit": 10}}, csrf)
        assert listed.status_code == 200, listed.text
        # The page as the built route shapes it: its null members are left out.
        page = listed.json()
        assert page["page"].get("nextCursor") is None and page["appliedLimit"] == 10
        items = page["items"]
        for item in items:
            wire.AccessConsentRecord.model_validate(item)
        assert [item["purposeId"] for item in items] == list(REQUIRED_CONSENTS)
        # Nothing else serves it.
        profile = post(client, "/api/v2/c02/access-read-profile", {}, csrf)
        assert profile.status_code in (401, 403)
        given = None
        for item, decision in zip(items, ("granted", "revoked"), strict=True):
            given = post(client, "/api/v2/c02/access-update-consent", {
                "purposeId": item["purposeId"], "decision": decision,
                "policyRef": d1_entry.control_policy.reference,
                "expectedRevision": item["revision"],
            }, csrf)
            assert given.status_code == 200, given.text
            wire.AccessConsentRecord.model_validate(given.json())
        # The last decision made the session a full one, and its cookie lasts as long.
        [cookie] = session_cookies(given)
        assert f"Max-Age={d1_entry.control_policy.full_session_seconds('member')}" in cookie
        assert client.get("/api/v2/session").json()["signedIn"] is True
    _, reset = sign_in_account("sign-in-migrated", consents=False, reset_required=True)
    with account_client(realm, d1_entry, lifecycle, address=own_address) as client:
        answer = sign_in(client, reset, "probe-" + uuid4().hex[:12])
        assert answer.status_code == 200, answer.text
        value = wire.AccessSignInResult.model_validate(answer.json()).model_dump(mode="json")
        assert value["state"] == "reset_required" and value["delivery"] == "accepted"
        assert session_cookies(answer) == []  # no session


def test_the_enrolment_routes_serve_a_setup_only_session_and_nothing_else_does(
    realm, connect, d1_entry, sign_in_account, own_address,
):
    lifecycle = configure_lifecycle(d1_entry, LIFECYCLE_MANIFEST)
    _, email = sign_in_account("sign-in-admin", role="administrator")
    with account_client(realm, d1_entry, lifecycle, address=own_address) as client:
        answer = sign_in(client, email)
        value = wire.AccessSignInResult.model_validate(answer.json()).model_dump(mode="json")
        assert value["state"] == "authenticated"
        csrf = client.get("/api/v2/session").json()["csrfToken"]
        assert csrf == d1_entry.verifier("session-csrf", client.cookies[SESSION_COOKIE])
        begun = post(client, "/api/v2/c02/access-begin-mfa-enrollment", {
            "currentProof": SIGN_IN_PASSWORD, "policyRef": d1_entry.control_policy.reference,
        }, csrf)
        assert begun.status_code == 200, begun.text
        wire.AccessMfaEnrollment.model_validate(begun.json())
        assert post(client, "/api/v2/c02/access-read-profile", {}, csrf).status_code in (
            401, 403)
        assert post(client, "/api/v2/c02/access-list-consents", {"page": {"limit": 10}},
                    csrf).status_code in (401, 403)
        # Step 44's gap: the setup-only session's material and confirm, over HTTP.
        enrolment = begun.json()
        material = post(client, "/api/v2/c02/access-retrieve-mfa-enrollment-material", {
            "enrollmentId": enrolment["enrollmentId"],
            "deliveryReference": enrolment["deliveryReference"],
            "currentProof": SIGN_IN_PASSWORD}, csrf)
        assert material.status_code == 200, material.text
        wire.AccessMfaMaterial.model_validate(material.json())
        setup = d1_entry.first_sign_in.setup_authority(client.cookies[SESSION_COOKIE], csrf)
        confirmed = post(client, "/api/v2/c02/access-confirm-mfa-enrollment", {
            "enrollmentId": enrolment["enrollmentId"],
            "verification": {"challengeId": enrolment["enrollmentId"],
                             "flowBinding": str(setup.session_id),
                             "proof": totp(material.json()["seed"],
                                           database_step(connect) - 1)},
        }, csrf)
        assert confirmed.status_code == 200, confirmed.text
        # The setup-only session ended with the enrolment: its cookie is cleared.
        [cookie] = session_cookies(confirmed)
        assert "Max-Age=0" in cookie
        assert session_row(connect, setup.session_id)["revoked"]


def test_an_administrators_consents_over_http_clear_the_cookie_to_sign_in_again(
    realm, connect, d1_entry, sign_in_account, own_address,
):
    """Step 44's gap: `sign_in_again` over HTTP. A migrated administrator's last consent
    ends the consent-pending session; the answer clears its cookie, and the next sign-in
    meets the second factor's setup."""
    lifecycle = configure_lifecycle(d1_entry, LIFECYCLE_MANIFEST)
    _, email = sign_in_account("sign-in-admin", role="administrator", consents=False)
    with account_client(realm, d1_entry, lifecycle, address=own_address) as client:
        answer = sign_in(client, email)
        assert answer.json()["state"] == "consent_pending", answer.text
        csrf = d1_entry.verifier("session-csrf", client.cookies[SESSION_COOKIE])
        listed = post(client, "/api/v2/c02/access-list-consents", {"page": {"limit": 10}},
                      csrf).json()["items"]
        given = None
        for item, decision in zip(listed, ("granted", "revoked"), strict=True):
            given = post(client, "/api/v2/c02/access-update-consent", {
                "purposeId": item["purposeId"], "decision": decision,
                "policyRef": d1_entry.control_policy.reference,
                "expectedRevision": item["revision"]}, csrf)
            assert given.status_code == 200, given.text
        [cookie] = session_cookies(given)
        assert "Max-Age=0" in cookie
        assert client.get("/api/v2/session").json()["signedIn"] is False


def test_the_answers_hold_no_secret(d1_entry, sign_in_account):
    _, email = sign_in_account("sign-in-migrated", consents=False)
    result = d1_entry.login(email, SIGN_IN_PASSWORD, flow_binding="first")
    text = json.dumps(result.public)
    for secret in (result.token, result.csrf, SIGN_IN_PASSWORD,
                   hashlib.sha256(result.token.encode()).hexdigest()):
        assert secret not in text
    assert SimpleNamespace(**result.public).state == "consent_pending"
