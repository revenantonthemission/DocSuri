"""Actual owner stores through mounted canonical ASGI account bindings.

TestClient's HTTPS URL is transport simulation; actual pinned TLS has a separate
component probe and browser/network journey proof is still required.
"""

from dataclasses import replace
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend.local_host import assemble
from backend.modules.accounts.local_http import ENTRY_POLICY, account_router
from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from tests.u1_integrated_paper_journey.component.test_account_entry import (
    PASSWORD,
    entry as entry_fixture,
    mailbox,
)

pytestmark = pytest.mark.u1_integration
ORIGIN = "https://127.0.0.1:18039"
entry = entry_fixture


@pytest.fixture
def browser(entry):
    entry.transactions.profile = replace(entry.transactions.profile, origin=ORIGIN)
    app = assemble(entry.transactions.profile, routers=(account_router(entry),))
    with TestClient(app, base_url=ORIGIN) as client:
        yield client


def headers(browser, *, operation=None):
    response = browser.get("/api/v2/session")
    assert response.status_code == 200
    return {
        "Origin": ORIGIN,
        "X-CSRF-Token": response.json()["csrfToken"],
        "Idempotency-Key": str(operation or uuid4()),
    }


def register_verify(browser, entry, connect):
    email = uuid4().hex + "@entry.fixture.example.com"
    response = browser.post(
        "/api/v2/c02/access-register",
        headers=headers(browser),
        json={
            "email": email,
            "password": PASSWORD,
            "displayName": "연구자",
            "policyRef": ENTRY_POLICY,
        },
    )
    assert response.status_code == 200
    proof = mailbox(entry, connect, email)
    response = browser.post(
        "/api/v2/c02/access-verify-email",
        headers=headers(browser),
        json={
            "verification": {key: proof[key] for key in ("challengeId", "proof", "flowBinding")},
        },
    )
    assert response.status_code == 200
    return email


def credentials(email):
    return {"email": email, "password": PASSWORD, "policyRef": ENTRY_POLICY}


def test_registered_verified_login_fresh_bootstrap_and_logout(browser, entry, connect):
    email = register_verify(browser, entry, connect)
    response = browser.post(
        "/api/v2/c02/access-login", headers=headers(browser), json=credentials(email)
    )
    assert response.status_code == 200
    cookie = browser.cookies.get("session_id")
    assert cookie and cookie not in response.text
    assert all(
        value in response.headers["set-cookie"]
        for value in ("Secure", "HttpOnly", "SameSite=strict")
    )
    signed = browser.get("/api/v2/session").json()
    assert signed["signedIn"] and cookie not in str(signed)
    fresh_entry = GuardedEntryService(entry.transactions)
    fresh_app = assemble(entry.transactions.profile, routers=(account_router(fresh_entry),))
    with TestClient(fresh_app, base_url=ORIGIN) as fresh:
        fresh.cookies.update(browser.cookies)
        assert fresh.get("/api/v2/session").json() == signed
        reply = fresh.post("/api/v2/c02/access-inspect-session", headers=headers(fresh), json={})
        assert reply.json()["session"]["accountId"] == signed["accountId"]
        assert (
            fresh.post("/api/v2/c02/access-logout", headers=headers(fresh), json={}).status_code
            == 200
        )
        assert not fresh.get("/api/v2/session").json()["signedIn"]
    assert not browser.get("/api/v2/session").json()["signedIn"]


@pytest.mark.parametrize(
    "route",
    [
        "access-register",
        "access-login",
        "access-verify-email",
        "access-request-verification",
        "access-logout",
        "access-inspect-session",
    ],
)
def test_every_post_rejects_missing_origin_before_credentials(browser, route):
    request_headers = headers(browser)
    request_headers.pop("Origin")
    assert browser.post("/api/v2/c02/" + route, headers=request_headers, json={}).status_code == 403


def test_anonymous_context_substitution_and_bad_csrf_are_denied(browser, entry):
    good = headers(browser)
    with TestClient(browser.app, base_url=ORIGIN) as other:
        wrong = headers(other)
    good["X-CSRF-Token"] = wrong["X-CSRF-Token"]
    assert (
        browser.post("/api/v2/c02/access-inspect-session", headers=good, json={}).status_code == 403
    )
    good["X-CSRF-Token"] = "x" * 65
    assert (
        browser.post("/api/v2/c02/access-inspect-session", headers=good, json={}).status_code == 403
    )


def test_body_identity_injection_oversize_and_policy_refuse(browser):
    response = browser.post(
        "/api/v2/c02/access-inspect-session",
        headers=headers(browser),
        json={"accountId": str(uuid4())},
    )
    assert response.status_code == 422
    response = browser.post(
        "/api/v2/c02/access-login", headers=headers(browser), json={"password": "x" * 9000}
    )
    assert response.status_code == 422 and "x" * 100 not in response.text
    value = credentials("unregistered@entry.fixture.example.com")
    value["policyRef"] = {"policyId": "paid", "revision": "1"}
    assert (
        browser.post("/api/v2/c02/access-login", headers=headers(browser), json=value).status_code
        == 503
    )


def test_lost_login_reply_recovers_same_operation_and_partial_cookie_delivery(
    browser, entry, connect, monkeypatch
):
    email = register_verify(browser, entry, connect)
    operation = uuid4()
    original_headers = headers(browser, operation=operation)
    original, commits = psycopg.Connection.commit, [0]

    def lost(conn):
        active = conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE
        original(conn)
        commits[0] += int(active)
        if active and commits[0] == 3:
            raise psycopg.OperationalError("injected lost login reply")

    with monkeypatch.context() as patch:
        patch.setattr(psycopg.Connection, "commit", lost)
        response = browser.post(
            "/api/v2/c02/access-login", headers=original_headers, json=credentials(email)
        )
    assert response.status_code == 409 and response.json()["code"] == "UNKNOWN_OUTCOME"
    recovered = browser.post(
        "/api/v2/c02/access-login", headers=original_headers, json=credentials(email)
    )
    assert recovered.status_code == 200
    token = browser.cookies.get("session_id")
    # A reply body may be lost after cookie delivery; rebootstrap obtains the
    # new session CSRF while retaining the original signed entry flow.
    replay = browser.post(
        "/api/v2/c02/access-login",
        headers=headers(browser, operation=operation),
        json=credentials(email),
    )
    assert replay.status_code == 200 and replay.json() == recovered.json()
    assert browser.cookies.get("session_id") == token


def test_session_csrf_substitution_does_not_change_current_identity(browser, entry, connect):
    first_email = register_verify(browser, entry, connect)
    first = browser.post(
        "/api/v2/c02/access-login", headers=headers(browser), json=credentials(first_email)
    )
    first_identity = first.json()["session"]["accountId"]
    first_csrf = headers(browser)["X-CSRF-Token"]
    with TestClient(browser.app, base_url=ORIGIN) as other:
        second_email = register_verify(other, entry, connect)
        other.post(
            "/api/v2/c02/access-login", headers=headers(other), json=credentials(second_email)
        )
        wrong = headers(other)
        wrong["X-CSRF-Token"] = first_csrf
        assert (
            other.post("/api/v2/c02/access-inspect-session", headers=wrong, json={}).status_code
            == 403
        )
        assert other.get("/api/v2/session").json()["accountId"] != first_identity
    assert browser.get("/api/v2/session").json()["accountId"] == first_identity
