"""AccountAccess's personal-control routes as the composed realm serves them (U8 plan
Steps 9 and 20; C02, BR6.2, NFR2.1).

The composed host mounts AccountAccess's C02 routers behind D7's boundary under the
D1-shaped policy (`U8_SYNTHETIC_POLICY`), with the full-session paths a signed-in person
takes after the first sign-in: reading and changing the profile, paging consents,
changing the password, the password-reset and email-change proofs, enrolling and meeting
a second factor, linking and unlinking an identity, and preparing and requesting a
withdrawal with its limited status cookie. Each test drives the built routes over HTTP
with a shared `sign-in-member` account the fixture resets first; mail proofs are read
from the realm's local mailbox, the only mail the composed realm sends.
"""

from __future__ import annotations

import contextlib
import json
from urllib.parse import urlsplit
from uuid import uuid4

import psycopg
import pytest
from docsuri_shared.workspace import wire

from backend.local_browser import SESSION_COOKIE
from backend.modules.accounts.local_http import ENTRY_POLICY
from backend.modules.accounts.services.control_mfa import totp
from backend.modules.accounts.u8_mail_outbox import AccountMailSender
from backend.transactions import Authority, guard
from backend.u8_host import LIFECYCLE_MANIFEST, configure_lifecycle
from tests.u8_service_operations_integration.conftest import (
    SIGN_IN_PASSWORD,
    account_client,
    activate_factor,
    database_step,
    post,
)

# Step 85(j): no outbox row outlives its test (Step 54(n)'s `empty_outbox`).
pytestmark = pytest.mark.usefixtures("own_address", "empty_outbox")
NEW_PASSWORD = f"Synthetic-Changed-{uuid4().hex[:12]}-2!"  # per run (L1-36)


def sign_in(client, email: str, password: str = SIGN_IN_PASSWORD):
    csrf = client.get("/api/v2/session").json()["csrfToken"]
    return post(client, "/api/v2/c02/access-login",
                {"email": email, "password": password, "policyRef": ENTRY_POLICY}, csrf)


def csrf_of(client) -> str:
    return client.get("/api/v2/session").json()["csrfToken"]


def sender_pass(entry) -> None:
    """One pass of the outbox's sender over `entry` (U8 plan Steps 53(h) and 85(j), L1-69):
    the four signed-out requests answer before their message leaves."""
    AccountMailSender(entry).run_once()


def mailed(entry, purpose: str, email: str) -> dict:
    """The newest proof the realm's local mailbox holds for `email` and `purpose`, read
    after one sender pass over `entry` (Step 85(j))."""
    sender_pass(entry)
    found = []
    for path in entry.mail.root.glob("*.blob"):
        value = json.loads(path.read_text())
        if value.get("purpose") == purpose and value.get("email") == email:
            found.append((path.stat().st_mtime_ns, value))
    assert found, f"no {purpose} mail for the account"
    return max(found, key=lambda item: item[0])[1]


@pytest.fixture
def member(realm, d1_entry, sign_in_account, own_address, forget_waits, connect):
    """A signed-in member's client on the composed routers, and its account's email. The
    sign-in failures a test provokes on purpose are forgotten before and after (D2), so
    an interrupted earlier run never leaves this one a wait."""
    lifecycle = configure_lifecycle(d1_entry, LIFECYCLE_MANIFEST)
    authority, email = sign_in_account("sign-in-member")
    forget_waits.append(email)
    with connect("accounts") as conn:
        conn.execute("DELETE FROM accounts.entry_email_failure WHERE email_digest=%s",
                     (d1_entry.verifier("entry-email", email),))
    with account_client(realm, d1_entry, lifecycle, address=own_address) as client:
        answer = sign_in(client, email)
        assert answer.status_code == 200, answer.text
        assert answer.json()["state"] == "authenticated"
        yield client, authority, email


def read_profile(client) -> dict:
    answer = post(client, "/api/v2/c02/access-read-profile", {}, csrf_of(client))
    assert answer.status_code == 200, answer.text
    return wire.AccessProfile.model_validate(answer.json()).model_dump(mode="json")


# Profile ------------------------------------------------------------------------------


def test_a_profile_change_is_kept_replayed_and_refused_when_stale_or_ambiguous(
    member, d1_entry,
):
    client, authority, email = member
    before = read_profile(client)
    assert before["accountId"] == str(authority.account_id) and before["email"] == email
    body = {
        "expectedRevision": before["revision"],
        "fieldVocabularyRevision": before["fieldVocabularyRevision"],
        "changes": [{"fieldId": "displayName", "value": "U8 연구자"},
                    {"fieldId": "affiliation", "value": "Synthetic Lab"}],
        "policyRef": d1_entry.control_policy.reference,
    }
    operation = uuid4()
    changed = post(client, "/api/v2/c02/access-update-profile", body, csrf_of(client),
                   operation=operation)
    assert changed.status_code == 200, changed.text
    fields = {item["fieldId"]: item["value"] for item in changed.json()["fields"]}
    assert (fields["displayName"], fields["affiliation"]) == ("U8 연구자", "Synthetic Lab")
    assert changed.json()["revision"] != before["revision"]
    # The same operation answers the same snapshot; a stale revision is a conflict.
    again = post(client, "/api/v2/c02/access-update-profile", body, csrf_of(client),
                 operation=operation)
    assert again.json() == changed.json()
    assert post(client, "/api/v2/c02/access-update-profile", body,
                csrf_of(client)).status_code == 409
    current = read_profile(client)
    for changes, vocabulary in (
        ([{"fieldId": "displayName", "value": "a"}, {"fieldId": "displayName", "value": "b"}],
         current["fieldVocabularyRevision"]),
        ([{"fieldId": "displayName", "value": "a"}], "another-vocabulary"),
    ):
        refused = post(client, "/api/v2/c02/access-update-profile", {
            **body, "expectedRevision": current["revision"], "changes": changes,
            "fieldVocabularyRevision": vocabulary,
        }, csrf_of(client))
        assert refused.status_code in (409, 422)
    assert read_profile(client) == current


# Consents -----------------------------------------------------------------------------


def test_a_full_session_pages_its_consents_and_revokes_one(member, d1_entry):
    client, authority, _ = member
    first = post(client, "/api/v2/c02/access-list-consents", {"page": {"limit": 1}},
                 csrf_of(client))
    assert first.status_code == 200, first.text
    page = first.json()
    assert page["appliedLimit"] == 1 and len(page["items"]) == 1
    cursor = page["page"]["nextCursor"]
    assert cursor
    rest = post(client, "/api/v2/c02/access-list-consents",
                {"page": {"limit": 1, "cursor": cursor}}, csrf_of(client))
    assert rest.status_code == 200, rest.text
    items = page["items"] + rest.json()["items"]
    assert {item["purposeId"] for item in items} == {"local-research", "personalization"}
    assert {item["accountId"] for item in items} == {str(authority.account_id)}
    for limit in (0, d1_entry.control_policy.max_page_size + 1):
        assert post(client, "/api/v2/c02/access-list-consents", {"page": {"limit": limit}},
                    csrf_of(client)).status_code in (409, 422)
    research = next(item for item in items if item["purposeId"] == "local-research")
    revoked = post(client, "/api/v2/c02/access-update-consent", {
        "purposeId": "local-research", "decision": "revoked",
        "expectedRevision": research["revision"],
        "policyRef": d1_entry.control_policy.reference,
    }, csrf_of(client))
    assert revoked.status_code == 200, revoked.text
    assert wire.AccessConsentRecord.model_validate(revoked.json()).decision == "revoked"


# Credentials ---------------------------------------------------------------------------


def test_a_password_change_ends_the_session_and_a_wrong_one_changes_nothing(
    member, d1_entry,
):
    client, _, email = member
    wrong_password = f"Wrong-Synthetic-{uuid4().hex[:12]}-9!"  # generated per run (L1-36)
    wrong = post(client, "/api/v2/c02/access-change-password", {
        "currentPassword": wrong_password, "newPassword": NEW_PASSWORD,
    }, csrf_of(client))
    assert wrong.status_code == 403
    assert wrong_password not in wrong.text
    assert client.get("/api/v2/session").json()["signedIn"] is True
    changed = post(client, "/api/v2/c02/access-change-password", {
        "currentPassword": SIGN_IN_PASSWORD, "newPassword": NEW_PASSWORD,
    }, csrf_of(client))
    assert changed.status_code == 200, changed.text
    assert client.get("/api/v2/session").json()["signedIn"] is False
    assert sign_in(client, email, SIGN_IN_PASSWORD).status_code in (401, 403)
    assert sign_in(client, email, NEW_PASSWORD).json()["state"] == "authenticated"


def test_a_lost_password_change_answer_is_reconciled_only_for_the_exact_change(
    member, d1_entry,
):
    client, _, _ = member
    cookie, csrf = client.cookies[SESSION_COOKIE], csrf_of(client)
    operation = uuid4()
    body = {"currentPassword": SIGN_IN_PASSWORD, "newPassword": NEW_PASSWORD}
    changed = post(client, "/api/v2/c02/access-change-password", body, csrf,
                   operation=operation)
    assert changed.status_code == 200, changed.text
    # The answer was lost: the ended session's cookie and the same operation replay it.
    client.cookies.set(SESSION_COOKIE, cookie)
    replay = post(client, "/api/v2/c02/access-change-password", body, csrf,
                  operation=operation)
    assert replay.status_code == 200, replay.text
    assert replay.json() == changed.json()
    client.cookies.set(SESSION_COOKIE, cookie)
    other = post(client, "/api/v2/c02/access-change-password",
                 {**body, "newPassword": f"Synthetic-Another-{uuid4().hex[:12]}-3!"}, csrf,
                 operation=operation)
    assert other.status_code == 403
    assert client.get("/api/v2/session").json()["signedIn"] is False


def test_a_lost_email_change_answer_is_reconciled_from_the_ended_session(
    member, d1_entry,
):
    client, authority, _ = member
    new_email = f"lost-{authority.account_id}@fixture.example.com"
    assert post(client, "/api/v2/c02/access-request-email-change", {
        "currentProof": SIGN_IN_PASSWORD, "newEmail": new_email,
        "policyRef": d1_entry.control_policy.reference,
    }, csrf_of(client)).status_code == 200
    proof = mailed(d1_entry, "email-change", new_email)
    body = {"verification": {key: proof[key] for key in ("challengeId", "proof",
                                                          "flowBinding")}}
    cookie, csrf, operation = client.cookies[SESSION_COOKIE], csrf_of(client), uuid4()
    completed = post(client, "/api/v2/c02/access-complete-email-change", body, csrf,
                     operation=operation)
    assert completed.status_code == 200, completed.text
    client.cookies.set(SESSION_COOKIE, cookie)
    replay = post(client, "/api/v2/c02/access-complete-email-change", body, csrf,
                  operation=operation)
    assert (replay.status_code, replay.json()) == (200, completed.json())


def test_a_mailed_reset_proof_sets_a_new_password_over_the_guest_routes(
    member, d1_entry,
):
    client, _, email = member
    client.cookies.delete(SESSION_COOKIE)
    requested = post(client, "/api/v2/c02/access-request-password-reset", {
        "email": email, "policyRef": d1_entry.control_policy.reference,
    }, csrf_of(client))
    assert requested.status_code == 200, requested.text
    assert set(requested.json()) == {"acknowledgement", "messageKey", "requestId"}
    proof = mailed(d1_entry, "password-reset", email)
    verification = {key: proof[key] for key in ("challengeId", "proof", "flowBinding")}
    elsewhere = post(client, "/api/v2/c02/access-complete-password-reset", {
        "verification": {**verification, "flowBinding": str(uuid4())},
        "newPassword": NEW_PASSWORD,
    }, csrf_of(client))
    assert elsewhere.status_code == 403
    completed = post(client, "/api/v2/c02/access-complete-password-reset", {
        "verification": verification, "newPassword": NEW_PASSWORD,
    }, csrf_of(client))
    assert completed.status_code == 200, completed.text
    assert sign_in(client, email, NEW_PASSWORD).json()["state"] == "authenticated"


def test_a_mailed_email_change_proof_moves_the_address_and_ends_the_session(
    member, d1_entry, connect,
):
    client, authority, email = member
    new_email = f"moved-{authority.account_id}@fixture.example.com"
    requested = post(client, "/api/v2/c02/access-request-email-change", {
        "currentProof": SIGN_IN_PASSWORD, "newEmail": new_email,
        "policyRef": d1_entry.control_policy.reference,
    }, csrf_of(client))
    assert requested.status_code == 200, requested.text
    proof = mailed(d1_entry, "email-change", new_email)
    verification = {key: proof[key] for key in ("challengeId", "proof", "flowBinding")}
    assert post(client, "/api/v2/c02/access-complete-email-change", {
        "verification": {**verification, "flowBinding": str(uuid4())},
    }, csrf_of(client)).status_code == 403
    completed = post(client, "/api/v2/c02/access-complete-email-change",
                     {"verification": verification}, csrf_of(client))
    assert completed.status_code == 200, completed.text
    assert client.get("/api/v2/session").json()["signedIn"] is False
    with connect("accounts") as conn:
        assert conn.execute("SELECT email FROM accounts.account WHERE id=%s",
                            (authority.account_id,)).fetchone()["email"] == new_email
    assert sign_in(client, new_email).json()["state"] == "authenticated"
    assert sign_in(client, email).status_code in (401, 403)


def generated_password() -> str:
    """A new password that meets the password policy, generated per run (L1-36)."""
    return f"Synthetic-{uuid4().hex[:16]}-Aa1!"


def unrevoked_sessions(connect, account_id) -> set:
    with connect("accounts") as conn:
        return {row["id"] for row in conn.execute(
            "SELECT id FROM accounts.session WHERE account_id=%s AND NOT revoked",
            (account_id,)).fetchall()}


def authority_revision(connect, account_id):
    with connect("accounts") as conn:
        return conn.execute("SELECT authority_revision FROM accounts.account WHERE id=%s",
                            (account_id,)).fetchone()["authority_revision"]


def library_guard(connect, account_id, session_id):
    """The library login's own guard for one session (`account-control`)."""
    with connect("library") as conn:
        return guard(conn, Authority(account_id, session_id), purpose="account-control")


def signed_in_three_ways(realm, d1_entry, lifecycle, own_address, email, stack):
    """Two member clients over HTTP and one in-process session (Step 85(e))."""
    clients = []
    for _ in range(2):
        client = stack.enter_context(
            account_client(realm, d1_entry, lifecycle, address=own_address))
        answer = sign_in(client, email)
        assert answer.json()["state"] == "authenticated", answer.text
        clients.append(client)
    d1_entry.login(email, SIGN_IN_PASSWORD, flow_binding="first")
    return clients


def assert_all_three_hold(connect, clients, account_id) -> set:
    assert [client.get("/api/v2/session").json()["signedIn"] for client in clients] == [
        True, True]
    sessions = unrevoked_sessions(connect, account_id)
    assert len(sessions) == 3
    revision = authority_revision(connect, account_id)
    for session in sessions:
        assert library_guard(connect, account_id, session) == revision
    return sessions


def assert_all_three_ended(connect, clients, account_id, sessions, saved) -> None:
    # Before any bootstrap, which clears a revoked session's cookie.
    for client, (cookie, csrf) in zip(clients, saved, strict=True):
        client.cookies.set(SESSION_COOKIE, cookie)
        refused = post(client, "/api/v2/c02/access-read-profile", {}, csrf)
        assert (refused.status_code, refused.json()["code"]) == (403, "FORBIDDEN")
    assert [client.get("/api/v2/session").json()["signedIn"] for client in clients] == [
        False, False]
    assert unrevoked_sessions(connect, account_id) == set()
    for session in sessions:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            library_guard(connect, account_id, session)


def test_a_password_reset_ends_every_session_of_the_account(
    realm, d1_entry, sign_in_account, own_address, forget_waits, connect,
):
    """D1 (Step 85(e)): a completed reset ends every session the account holds."""
    lifecycle = configure_lifecycle(d1_entry, LIFECYCLE_MANIFEST)
    authority, email = sign_in_account("sign-in-member")
    forget_waits.append(email)
    new_password = generated_password()
    with contextlib.ExitStack() as stack:
        clients = signed_in_three_ways(realm, d1_entry, lifecycle, own_address, email, stack)
        sessions = assert_all_three_hold(connect, clients, authority.account_id)
        saved = [(client.cookies[SESSION_COOKIE], csrf_of(client)) for client in clients]
        # The guest asks and completes in one browser: a link works only where it was asked
        # for (L1-1; U2's flow binding).
        guest = stack.enter_context(
            account_client(realm, d1_entry, lifecycle, address=own_address))
        asked = post(guest, "/api/v2/c02/access-request-password-reset", {
            "email": email, "policyRef": d1_entry.control_policy.reference,
        }, csrf_of(guest))
        assert asked.status_code == 200, asked.text
        proof = mailed(d1_entry, "password-reset", email)
        completed = post(guest, "/api/v2/c02/access-complete-password-reset", {
            "verification": {key: proof[key] for key in ("challengeId", "proof",
                                                          "flowBinding")},
            "newPassword": new_password,
        }, csrf_of(guest))
        assert completed.status_code == 200, completed.text
        assert_all_three_ended(connect, clients, authority.account_id, sessions, saved)
        assert sign_in(guest, email, new_password).json()["state"] == "authenticated"


def test_a_password_change_ends_every_session_of_the_account(
    realm, d1_entry, sign_in_account, own_address, forget_waits, connect,
):
    """D1 (Step 85(e)): a password change ends every session, the changing one too."""
    lifecycle = configure_lifecycle(d1_entry, LIFECYCLE_MANIFEST)
    authority, email = sign_in_account("sign-in-member")
    forget_waits.append(email)
    new_password = generated_password()
    with contextlib.ExitStack() as stack:
        clients = signed_in_three_ways(realm, d1_entry, lifecycle, own_address, email, stack)
        sessions = assert_all_three_hold(connect, clients, authority.account_id)
        saved = [(client.cookies[SESSION_COOKIE], csrf_of(client)) for client in clients]
        changed = post(clients[0], "/api/v2/c02/access-change-password", {
            "currentPassword": SIGN_IN_PASSWORD, "newPassword": new_password,
        }, saved[0][1])
        assert changed.status_code == 200, changed.text
        assert_all_three_ended(connect, clients, authority.account_id, sessions, saved)
        # A browser of its own: the member clients still carry their ended sessions' cookies.
        fresh = stack.enter_context(
            account_client(realm, d1_entry, lifecycle, address=own_address))
        old = sign_in(fresh, email, SIGN_IN_PASSWORD)
        assert (old.status_code, old.json()["code"]) == (403, "FORBIDDEN")
        assert sign_in(fresh, email, new_password).json()["state"] == "authenticated"


# A new password the policy refuses (your answer of 2026-11-11, "Say the password is too
# weak") ---------------------------------------------------------------------------------


def policy_failing_password() -> str:
    """A new password the password policy refuses (no upper-case letter and no symbol),
    generated per run (L1-36)."""
    return "weak" + uuid4().hex


def assert_password_policy_refusal(answer, password: str) -> None:
    """The route's own refusal of a weak password: 422 `INVALID_ARGUMENT` with `messageKey`
    `password.policy`, never a 500, and the password nowhere in the answer."""
    assert answer.status_code == 422, answer.text
    body = answer.json()
    assert (body["code"], body["messageKey"], body["retryable"]) == (
        "INVALID_ARGUMENT", "password.policy", False)
    assert password not in answer.text


def account_with_email(connect, email: str):
    with connect("accounts") as conn:
        return conn.execute("SELECT id FROM accounts.account WHERE email=%s",
                            (email.lower(),)).fetchone()


def test_registration_refuses_a_weak_password_and_an_invalid_address_without_a_500(
    realm, d1_entry, sign_in_account, own_address, connect,
):
    lifecycle = configure_lifecycle(d1_entry, LIFECYCLE_MANIFEST)
    _, taken = sign_in_account("sign-in-member")
    weak = policy_failing_password()
    with account_client(realm, d1_entry, lifecycle, address=own_address) as client:
        def register(email: str, password: str):
            return post(client, "/api/v2/c02/access-register", {
                "email": email, "password": password, "displayName": "합성 가입자",
                "policyRef": ENTRY_POLICY,
            }, csrf_of(client))

        free = f"weak-{uuid4().hex[:12]}@fixture.example.com"
        assert_password_policy_refusal(register(free, weak), weak)
        assert account_with_email(connect, free) is None
        # The same request on a taken address: refused for the password, and accepted
        # (existence-neutral, no account made) once the password meets the policy.
        assert_password_policy_refusal(register(taken, weak), weak)
        assert register(taken, generated_password()).status_code == 200
        # An address the contract's schema accepts but the account model refuses gets the
        # route's built invalid-input refusal, as an invalid display name does.
        invalid = f"u8!{uuid4().hex[:12]}@fixture.example.com"
        refused = register(invalid, generated_password())
        assert refused.status_code == 409, refused.text
        assert (refused.json()["code"], refused.json()["messageKey"]) == (
            "CONFLICT", "request.conflict")
        assert account_with_email(connect, invalid) is None


def test_reset_completion_refuses_a_weak_password_and_keeps_the_proof(
    member, d1_entry, connect,
):
    client, _, email = member
    client.cookies.delete(SESSION_COOKIE)
    asked = post(client, "/api/v2/c02/access-request-password-reset", {
        "email": email, "policyRef": d1_entry.control_policy.reference,
    }, csrf_of(client))
    assert asked.status_code == 200, asked.text
    proof = mailed(d1_entry, "password-reset", email)
    verification = {key: proof[key] for key in ("challengeId", "proof", "flowBinding")}
    weak = policy_failing_password()
    refused = post(client, "/api/v2/c02/access-complete-password-reset", {
        "verification": verification, "newPassword": weak,
    }, csrf_of(client))
    assert_password_policy_refusal(refused, weak)
    with connect("accounts") as conn:
        assert conn.execute("SELECT consumed_at FROM accounts.control_proof WHERE id=%s",
                            (verification["challengeId"],)).fetchone()["consumed_at"] is None
    assert sign_in(client, email, weak).status_code in (401, 403)
    # The same proof, flow and browser complete the reset with a password that meets it.
    completed = post(client, "/api/v2/c02/access-complete-password-reset", {
        "verification": verification, "newPassword": NEW_PASSWORD,
    }, csrf_of(client))
    assert completed.status_code == 200, completed.text
    assert sign_in(client, email, NEW_PASSWORD).json()["state"] == "authenticated"


def test_a_password_change_refuses_a_weak_password_and_keeps_the_session(
    member, d1_entry, connect,
):
    client, authority, email = member
    revision = authority_revision(connect, authority.account_id)
    weak = policy_failing_password()
    refused = post(client, "/api/v2/c02/access-change-password", {
        "currentPassword": SIGN_IN_PASSWORD, "newPassword": weak,
    }, csrf_of(client))
    assert_password_policy_refusal(refused, weak)
    assert client.get("/api/v2/session").json()["signedIn"] is True
    assert authority_revision(connect, authority.account_id) == revision
    # The same current password and session change it to a password that meets the policy.
    changed = post(client, "/api/v2/c02/access-change-password", {
        "currentPassword": SIGN_IN_PASSWORD, "newPassword": NEW_PASSWORD,
    }, csrf_of(client))
    assert changed.status_code == 200, changed.text
    assert sign_in(client, email, NEW_PASSWORD).json()["state"] == "authenticated"


# An address the schema accepts but the account model refuses (your answer of 2026-11-11 on
# the follow-up's review, "Extend it to all five") -----------------------------------------


def model_refused_address() -> str:
    """An address the contract's schema accepts but `EmailAddress` refuses (its `!`), as
    package F2's registration test uses, generated per run (L1-36)."""
    return f"u8!{uuid4().hex[:12]}@fixture.example.com"


def unknown_address() -> str:
    """A valid address no account holds, generated per run."""
    return f"unknown-{uuid4().hex[:12]}@fixture.example.com"


def assert_invalid_address_refusal(answer) -> None:
    """The route's built invalid-input refusal, as registration gives (package F2): 409
    `CONFLICT` with `request.conflict`, never a 500."""
    assert answer.status_code != 500, answer.text
    assert answer.status_code == 409, answer.text
    body = answer.json()
    assert (body["code"], body["messageKey"], body["retryable"]) == (
        "CONFLICT", "request.conflict", False)


def outbox_rows(connect) -> int:
    with connect("accounts") as conn:
        return conn.execute("SELECT count(*) AS n FROM accounts.mail_outbox").fetchone()["n"]


def failures_of(connect, entry, email: str):
    with connect("accounts") as conn:
        row = conn.execute(
            "SELECT failures FROM accounts.entry_email_failure WHERE email_digest=%s",
            (entry.verifier("entry-email", email),)).fetchone()
    return row["failures"] if row else None


def test_sign_in_with_a_model_refused_address_answers_as_an_unknown_address(
    realm, d1_entry, own_address, forget_waits, connect,
):
    unknown, invalid = unknown_address(), model_refused_address()
    forget_waits.extend([unknown, invalid])
    password = generated_password()
    with account_client(realm, d1_entry, address=own_address) as client:
        answers = [sign_in(client, email, password) for email in (unknown, invalid)]
    known, refused = answers
    assert refused.status_code != 500, refused.text
    assert known.status_code in (401, 403), known.text
    # Field for field the unknown address's answer: the same status, headers and body,
    # apart from each answer's own request identifier.
    assert refused.status_code == known.status_code
    assert set(refused.headers) == set(known.headers)
    assert refused.headers.get("set-cookie") is None and known.headers.get("set-cookie") is None
    first, second = known.json(), refused.json()
    assert set(first) == set(second)
    assert first["requestId"] and second["requestId"]
    assert ({k: v for k, v in first.items() if k != "requestId"}
            == {k: v for k, v in second.items() if k != "requestId"})
    assert password not in refused.text
    # The same path: each failure is counted against its own address, and no account or
    # session is made.
    assert failures_of(connect, d1_entry, unknown) == 1
    assert failures_of(connect, d1_entry, invalid) == 1
    assert account_with_email(connect, invalid) is None


def email_wait_of(connect, entry, email: str):
    with connect("accounts") as conn:
        row = conn.execute(
            "SELECT wait_until FROM accounts.entry_email_failure WHERE email_digest=%s",
            (entry.verifier("entry-email", email),)).fetchone()
    return row["wait_until"] if row else None


def test_a_mixed_case_refused_address_meets_the_email_wait_as_an_unknown_address_does(
    realm, d1_entry, own_address, forget_waits, connect,
):
    # The schema keeps the local part's case (it trims and lower-cases only the domain), so
    # the text the sign-in limit receives differs from its normalized form: the attempt and
    # its counted failure must still key on one digest (package G2's `_limit_email`).
    tag = uuid4().hex[:12].upper()
    invalid = f"  U8!{tag}@Fixture.Example.COM  "
    unknown = f"  Unknown-{tag}@Fixture.Example.COM  "
    invalid_key, unknown_key = invalid.strip().lower(), unknown.strip().lower()
    # The case-kept text a key on the raw input would have used.
    invalid_raw = f"U8!{tag}@fixture.example.com"
    forget_waits.extend([invalid_key, unknown_key, invalid_raw])
    password = generated_password()
    limit = 5
    with account_client(realm, d1_entry, address=own_address) as client:
        for email in (unknown, invalid):
            for _ in range(limit):
                failed = sign_in(client, email, password)
                assert failed.status_code in (401, 403), failed.text
        # Each failure is counted under the normalized address's digest, never the raw one.
        assert failures_of(connect, d1_entry, invalid_key) == limit
        assert failures_of(connect, d1_entry, unknown_key) == limit
        assert failures_of(connect, d1_entry, invalid_raw) is None
        assert email_wait_of(connect, d1_entry, invalid_key) is not None
        # Past the limit both meet the email wait with the same answer.
        known, refused = (sign_in(client, email, password) for email in (unknown, invalid))
    assert refused.status_code != 500, refused.text
    assert known.status_code not in (401, 403), known.text
    assert refused.status_code == known.status_code
    assert set(refused.headers) == set(known.headers)
    first, second = known.json(), refused.json()
    assert set(first) == set(second)
    varying = {"requestId", "retryAfterSeconds"}
    assert ({k: v for k, v in first.items() if k not in varying}
            == {k: v for k, v in second.items() if k not in varying})
    if "retryAfterSeconds" in first:
        assert abs(first["retryAfterSeconds"] - second["retryAfterSeconds"]) <= 1
    # Refused before any password: no further failure is counted for either address.
    assert failures_of(connect, d1_entry, invalid_key) == limit
    assert failures_of(connect, d1_entry, unknown_key) == limit
    assert account_with_email(connect, invalid_key) is None


def test_a_reset_request_refuses_a_model_refused_address_without_a_500(
    realm, d1_entry, own_address, connect,
):
    lifecycle = configure_lifecycle(d1_entry, LIFECYCLE_MANIFEST)
    with account_client(realm, d1_entry, lifecycle, address=own_address) as client:
        def ask(email: str):
            return post(client, "/api/v2/c02/access-request-password-reset", {
                "email": email, "policyRef": d1_entry.control_policy.reference,
            }, csrf_of(client))

        assert_invalid_address_refusal(ask(model_refused_address()))
        assert outbox_rows(connect) == 0
        # The same request on a valid address no account holds is acknowledged.
        assert ask(unknown_address()).status_code == 200


def test_a_verification_request_refuses_a_model_refused_address_without_a_500(
    realm, d1_entry, own_address, connect,
):
    with account_client(realm, d1_entry, address=own_address) as client:
        def ask(email: str):
            return post(client, "/api/v2/c02/access-request-verification", {
                "email": email, "policyRef": ENTRY_POLICY,
            }, csrf_of(client))

        assert_invalid_address_refusal(ask(model_refused_address()))
        assert outbox_rows(connect) == 0
        assert ask(unknown_address()).status_code == 200


def test_an_email_change_refuses_a_model_refused_address_and_keeps_the_session(
    member, d1_entry, connect,
):
    client, authority, email = member

    def proofs() -> set:
        with connect("accounts") as conn:
            return {row["id"] for row in conn.execute(
                "SELECT id FROM accounts.control_proof WHERE account_id=%s "
                "AND purpose='email-change'", (authority.account_id,)).fetchall()}

    def ask(new_email: str):
        return post(client, "/api/v2/c02/access-request-email-change", {
            "currentProof": SIGN_IN_PASSWORD, "newEmail": new_email,
            "policyRef": d1_entry.control_policy.reference,
        }, csrf_of(client))

    # Read after the fixture's sign-in: earlier tests on this shared account leave proofs.
    before, revision = proofs(), authority_revision(connect, authority.account_id)
    try:
        assert_invalid_address_refusal(ask(model_refused_address()))
        assert proofs() == before
        with connect("accounts") as conn:
            assert conn.execute("SELECT email FROM accounts.account WHERE id=%s",
                                (authority.account_id,)).fetchone()["email"] == email
        assert client.get("/api/v2/session").json()["signedIn"] is True
        assert authority_revision(connect, authority.account_id) == revision
        # The same session, password and request with a valid new address are accepted.
        assert ask(f"valid-{authority.account_id}@fixture.example.com").status_code == 200
        assert len(proofs() - before) == 1
    finally:
        # The accepted request's proof ends with the test: expired, never left usable.
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.control_proof SET expires_at=clock_timestamp() "
                "WHERE account_id=%s AND purpose='email-change' AND NOT (id = ANY(%s))",
                (authority.account_id, list(before)))


def test_a_reactivation_request_refuses_a_model_refused_address_without_a_500(
    realm, d1_entry, own_address, connect,
):
    lifecycle = configure_lifecycle(d1_entry, LIFECYCLE_MANIFEST)
    with account_client(realm, d1_entry, lifecycle, address=own_address) as client:
        def ask(email: str):
            return post(client, "/api/v2/c02/access-request-reactivation", {
                "email": email, "policyRef": d1_entry.control_policy.reference,
            }, csrf_of(client))

        assert_invalid_address_refusal(ask(model_refused_address()))
        assert outbox_rows(connect) == 0
        assert ask(unknown_address()).status_code == 200


# Second factor --------------------------------------------------------------------------


def test_a_member_enrols_a_factor_and_the_next_sign_in_meets_it(member, d1_entry, connect):
    client, _, email = member
    begun = post(client, "/api/v2/c02/access-begin-mfa-enrollment", {
        "currentProof": SIGN_IN_PASSWORD, "policyRef": d1_entry.control_policy.reference,
    }, csrf_of(client))
    assert begun.status_code == 200, begun.text
    enrolment = begun.json()
    body = {"enrollmentId": enrolment["enrollmentId"],
            "deliveryReference": enrolment["deliveryReference"],
            "currentProof": SIGN_IN_PASSWORD}
    material = post(client, "/api/v2/c02/access-retrieve-mfa-enrollment-material", body,
                    csrf_of(client))
    assert material.status_code == 200, material.text
    # The material is delivered once.
    assert post(client, "/api/v2/c02/access-retrieve-mfa-enrollment-material", body,
                csrf_of(client)).status_code in (403, 409)
    seed = material.json()["seed"]
    session = post(client, "/api/v2/c02/access-inspect-session", {},
                   csrf_of(client)).json()["session"]
    foreign = post(client, "/api/v2/c02/access-confirm-mfa-enrollment", {
        "enrollmentId": enrolment["enrollmentId"],
        "verification": {"challengeId": enrolment["enrollmentId"],
                         "flowBinding": str(uuid4()), "proof": "000000"},
    }, csrf_of(client))
    assert foreign.status_code == 403
    confirmed = post(client, "/api/v2/c02/access-confirm-mfa-enrollment", {
        "enrollmentId": enrolment["enrollmentId"],
        "verification": {"challengeId": enrolment["enrollmentId"],
                         "flowBinding": session["sessionId"],
                         # An accepted step is never presented again: confirm with the
                         # step before, verify with the current one.
                         "proof": totp(seed, database_step(connect) - 1)},
    }, csrf_of(client))
    assert confirmed.status_code == 200, confirmed.text
    post(client, "/api/v2/c02/access-logout", {}, csrf_of(client))
    challenged = sign_in(client, email)
    assert challenged.status_code == 200, challenged.text
    assert challenged.json()["state"] == "mfa_required"
    challenge = challenged.json().get("mfaChallenge", challenged.json())
    assert post(client, "/api/v2/c02/access-read-profile", {},
                csrf_of(client)).status_code in (401, 403)
    # Recovery stays gated with no administrator bypass: the answer is the unresolved
    # policy, and the challenge stays open.
    recovery = post(client, "/api/v2/c02/access-recover-mfa", {
        "verification": {"challengeId": challenge["challengeId"],
                         "flowBinding": challenge["flowBinding"],
                         "proof": "synthetic-recovery-code"},
        "policyRef": d1_entry.control_policy.reference}, csrf_of(client))
    assert (recovery.status_code, recovery.json()["code"]) == (503, "POLICY_UNRESOLVED")
    verified = post(client, "/api/v2/c02/access-verify-mfa", {
        "factorKind": "totp",
        "verification": {"challengeId": challenge["challengeId"],
                         "flowBinding": challenge["flowBinding"],
                         "proof": totp(seed, database_step(connect))},
    }, csrf_of(client))
    assert verified.status_code == 200, verified.text
    assert verified.json()["state"] == "authenticated"
    assert client.get("/api/v2/session").json()["signedIn"] is True


def test_an_administrator_with_a_factor_meets_it_over_http(
    realm, d1_entry, sign_in_account, connect, own_address,
):
    lifecycle = configure_lifecycle(d1_entry, LIFECYCLE_MANIFEST)
    authority, email = sign_in_account("sign-in-admin", role="administrator")
    seed = activate_factor(connect, d1_entry, authority.account_id)
    with account_client(realm, d1_entry, lifecycle, address=own_address) as client:
        challenged = sign_in(client, email)
        assert challenged.json()["state"] == "mfa_required", challenged.text
        challenge = challenged.json().get("mfaChallenge", challenged.json())
        wrong = post(client, "/api/v2/c02/access-verify-mfa", {
            "factorKind": "totp",
            "verification": {"challengeId": challenge["challengeId"],
                             "flowBinding": challenge["flowBinding"], "proof": "000000"},
        }, csrf_of(client))
        assert wrong.status_code in (401, 403)
        verified = post(client, "/api/v2/c02/access-verify-mfa", {
            "factorKind": "totp",
            "verification": {"challengeId": challenge["challengeId"],
                             "flowBinding": challenge["flowBinding"],
                             "proof": totp(seed, database_step(connect))},
        }, csrf_of(client))
        assert verified.status_code == 200, verified.text
        cookie = next(value for value in verified.headers.get_list("set-cookie")
                      if value.startswith(SESSION_COOKIE + "="))
        assert (f"Max-Age={d1_entry.control_policy.full_session_seconds('administrator')}"
                in cookie)


# Identity links -------------------------------------------------------------------------


def test_a_fixture_identity_is_linked_listed_and_unlinked(member, d1_entry, connect,
                                                         provider_starts):
    client, authority, _ = member
    with connect("accounts") as conn:
        conn.execute("DELETE FROM accounts.identity_link WHERE account_id=%s",
                     (authority.account_id,))
    # The start counts under the test's own address and the client's own entry cookie, and
    # its flow is aged and deleted afterwards (Step 20 item 9).
    begun = post(client, "/api/v2/c02/access-begin-identity-flow", {
        "provider": "google", "intent": "link", "returnRouteId": "settings",
        "policyRef": d1_entry.control_policy.reference,
    }, csrf_of(client))
    assert begun.status_code == 200, begun.text
    provider_starts.track(begun.json())
    # The fixture provider returns to the web app's callback page, which hands the
    # query to the backend's callback route.
    url = urlsplit(begun.json()["authorizationUrl"])
    assert url.path == "/sign-in/callback/google"
    callback = "/api/v2/identity/callback/"
    assert client.get(callback + "unknown?" + url.query).status_code == 422
    assert client.get(callback + "google?" + url.query + "&extra=1").status_code == 422
    linked = client.get(callback + "google?" + url.query)
    assert linked.status_code == 200, linked.text
    assert linked.json()["state"] == "linked"
    link = linked.json()["identityLink"]
    listed = post(client, "/api/v2/c02/access-list-identity-links", {"page": {"limit": 10}},
                  csrf_of(client))
    assert listed.status_code == 200, listed.text
    assert [item["identityLinkId"] for item in listed.json()["items"]] == [
        link["identityLinkId"]]
    assert post(client, "/api/v2/c02/access-read-orcid-profile", {
        "identityLinkId": link["identityLinkId"]}, csrf_of(client)).status_code == 403
    value = {"identityLinkId": link["identityLinkId"], "expectedRevision": link["revision"]}
    operation = uuid4()
    removed = post(client, "/api/v2/c02/access-unlink-identity", value, csrf_of(client),
                   operation=operation)
    assert removed.status_code == 200, removed.text
    assert post(client, "/api/v2/c02/access-unlink-identity", value, csrf_of(client),
                operation=operation).json() == removed.json()
    assert post(client, "/api/v2/c02/access-list-identity-links", {"page": {"limit": 10}},
                csrf_of(client)).json()["items"] == []


# Lifecycle ------------------------------------------------------------------------------


def test_a_withdrawal_is_confirmed_requested_and_read_through_its_limited_cookie(
    member, d1_entry, connect,
):
    client, authority, email = member
    before = read_profile(client)
    prepare = {"action": "withdraw", "expectedRevision": before["lifecycleRevision"],
               "currentProof": SIGN_IN_PASSWORD,
               "policyRef": d1_entry.control_policy.reference}
    prepared = post(client, "/api/v2/c02/access-prepare-lifecycle", prepare, csrf_of(client))
    assert prepared.status_code == 200, prepared.text
    confirmation = prepared.json()["confirmationRef"]
    # The confirmation binds its action.
    assert post(client, "/api/v2/c02/lifecycle-request", {
        "action": "erase", "confirmationRef": confirmation,
        "policyRef": d1_entry.control_policy.reference,
    }, csrf_of(client)).status_code == 403
    requested = post(client, "/api/v2/c02/lifecycle-request", {
        "action": "withdraw", "confirmationRef": confirmation,
        "policyRef": d1_entry.control_policy.reference,
    }, csrf_of(client))
    assert requested.status_code == 200, requested.text
    value = wire.LifecycleRequest.model_validate(requested.json()).model_dump(mode="json")
    assert value["state"] == "accepted"
    assert client.get("/api/v2/session").json()["signedIn"] is False
    status = post(client, "/api/v2/c02/lifecycle-inspect",
                  {"lifecycleRequestId": value["lifecycleRequestId"]}, csrf_of(client))
    assert status.status_code == 200, status.text
    assert post(client, "/api/v2/c02/lifecycle-inspect",
                {"lifecycleRequestId": str(uuid4())}, csrf_of(client)).status_code == 403
    with connect("accounts") as conn:
        row = conn.execute("SELECT lifecycle_state,active FROM accounts.account WHERE id=%s",
                           (authority.account_id,)).fetchone()
    assert row["lifecycle_state"] == "withdrawn" and not row["active"]
    # A withdrawn account asks for reactivation by mail; the answer hides nothing new.
    asked = post(client, "/api/v2/c02/access-request-reactivation", {
        "email": email, "policyRef": d1_entry.control_policy.reference,
    }, csrf_of(client))
    assert asked.status_code == 200, asked.text
    proof = mailed(d1_entry, "reactivate", email)
    reactivated = post(client, "/api/v2/c02/lifecycle-reactivate", {
        "confirmationRef": proof["challengeId"],
        "verification": {key: proof[key] for key in ("challengeId", "proof", "flowBinding")},
        "policyRef": d1_entry.control_policy.reference,
    }, csrf_of(client))
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["access"] == "reactivation_pending"
