"""C02/C03 mounted contract and current-authority checks over the real store."""

import json
from uuid import uuid4
from urllib.parse import urlsplit
import time

import pytest
from test_library_personal_http import PASSWORD, CONTROL_POLICY, ENTRY_POLICY
from test_library_personal_http import browser as browser
from backend.local_browser import ENTRY_COOKIE, SESSION_COOKIE
from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.accounts.services.control_entry import ControlEntryService
from backend.modules.accounts.services.control_mfa import totp

pytestmark = pytest.mark.u2_integration


def post(client, name, value, *, key=None, contract="c02"):
    return client.post(
        "/api/v2/" + contract + "/" + name,
        json=value,
        headers={"Idempotency-Key": str(key or uuid4())},
    )


def read_profile(client):
    response = post(client, "access-read-profile", {})
    assert response.status_code == 200, response.text
    return response.json()


def test_profile_updates_return_original_typed_snapshot(browser):
    before = read_profile(browser)
    value = {
        "expectedRevision": before["revision"],
        "fieldVocabularyRevision": before["fieldVocabularyRevision"],
        "changes": [{"fieldId": "displayName", "value": "새 연구자"}],
        "policyRef": CONTROL_POLICY,
    }
    key = uuid4()
    result = post(browser, "access-update-profile", value, key=key)
    assert result.status_code == 200, result.text
    assert result.json()["revision"] != before["revision"]
    assert post(browser, "access-update-profile", value, key=key).json() == result.json()
    assert post(browser, "access-update-profile", value).status_code == 409


@pytest.mark.parametrize(
    "change",
    [
        [{"fieldId": "role", "value": "administrator"}],
        [
            {"fieldId": "displayName", "value": "first"},
            {"fieldId": "displayName", "value": "second"},
        ],
        [{"fieldId": "displayName", "value": True}],
    ],
)
def test_profile_rejects_unapproved_fields_and_ambiguity(browser, change):
    before = read_profile(browser)
    result = post(
        browser,
        "access-update-profile",
        {
            "expectedRevision": before["revision"],
            "fieldVocabularyRevision": before["fieldVocabularyRevision"],
            "changes": change,
            "policyRef": CONTROL_POLICY,
        },
    )
    assert result.status_code in (409, 422)
    assert read_profile(browser) == before


def test_consent_revocation_keeps_manual_controls_and_replays(browser):
    value = post(browser, "access-list-consents", {"page": {"limit": 10}})
    assert value.status_code == 200, value.text
    consent = next(v for v in value.json()["items"] if v["purposeId"] == "personalization")
    body = {
        "purposeId": "personalization",
        "decision": "revoked",
        "expectedRevision": consent["revision"],
        "policyRef": CONTROL_POLICY,
    }
    key = uuid4()
    result = post(browser, "access-update-consent", body, key=key)
    assert result.status_code == 200, result.text
    assert result.json()["decision"] == "revoked"
    browser.headers["X-CSRF-Token"] = browser.get("/api/v2/session").json()["csrfToken"]
    assert post(browser, "access-update-consent", body, key=key).json() == result.json()
    assert read_profile(browser)["accountId"] == consent["accountId"]


def test_password_change_revokes_cookie_and_requires_fresh_login(browser):
    response = post(
        browser,
        "access-change-password",
        {"currentPassword": PASSWORD, "newPassword": "Different!Research2026"},
    )
    assert response.status_code == 200, response.text
    assert not browser.get("/api/v2/session").json()["signedIn"]
    assert post(browser, "access-read-profile", {}).status_code in (401, 403)


def test_password_lost_ack_reconciles_only_exact_effect(browser):
    original_cookie = browser.cookies.get("session_id")
    original_csrf = browser.headers["X-CSRF-Token"]
    key = uuid4()
    body = {"currentPassword": PASSWORD, "newPassword": "Changed!Research2026"}
    result = post(browser, "access-change-password", body, key=key)
    assert result.status_code == 200, result.text
    headers = {
        "Cookie": "session_id=" + original_cookie,
        "X-CSRF-Token": original_csrf,
        "Idempotency-Key": str(key),
    }
    replay = browser.post("/api/v2/c02/access-change-password", json=body, headers=headers)
    assert replay.status_code == 200, replay.text
    assert replay.json() == result.json()
    changed = browser.post(
        "/api/v2/c02/access-change-password",
        json=dict(body, newPassword="Another!Research2026"),
        headers=headers,
    )
    assert changed.status_code == 403
    assert not browser.get("/api/v2/session").json()["signedIn"]


def test_wrong_password_never_changes_authority(browser):
    before = read_profile(browser)
    response = post(
        browser,
        "access-change-password",
        {"currentPassword": "Wrong!Research2026", "newPassword": "Different!Research2026"},
    )
    assert response.status_code == 403
    assert read_profile(browser) == before


def test_error_envelopes_redact_submitted_secrets(browser):
    marker = "SyntheticLeakCanary!2026"
    response = post(
        browser,
        "access-change-password",
        {"currentPassword": marker, "newPassword": marker},
    )
    assert response.status_code in (403, 409, 422)
    assert marker not in response.text
    assert response.headers.get("cache-control") == "no-store"
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert set(response.json()) >= {"code", "messageKey", "requestId", "retryable"}
    assert "set-cookie" not in {key.lower() for key in response.headers}
    assert browser.get("/api/v2/session").json()["signedIn"]


def test_password_reset_ack_hides_account_existence(browser):
    responses = [
        post(
            browser,
            "access-request-password-reset",
            {"email": address, "policyRef": CONTROL_POLICY},
        )
        for address in ("u2-a@fixture.example.com", "missing@fixture.example.com")
    ]
    assert all(r.status_code == 200 for r in responses)
    assert {tuple(sorted(r.json())) for r in responses} == {
        ("acknowledgement", "messageKey", "requestId")
    }


def test_lifecycle_confirmation_prevents_action_substitution(browser):
    before = read_profile(browser)
    prepared = post(
        browser,
        "access-prepare-lifecycle",
        {
            "action": "withdraw",
            "expectedRevision": before["lifecycleRevision"],
            "currentProof": PASSWORD,
            "policyRef": CONTROL_POLICY,
        },
    )
    assert prepared.status_code == 200, prepared.text
    result = post(
        browser,
        "lifecycle-request",
        {
            "action": "erase",
            "confirmationRef": prepared.json()["confirmationRef"],
            "policyRef": CONTROL_POLICY,
        },
    )
    assert result.status_code == 403
    assert read_profile(browser) == before


def test_withdrawal_limited_cookie_reads_only_its_request(browser):
    before = read_profile(browser)
    prepared = post(
        browser,
        "access-prepare-lifecycle",
        {
            "action": "withdraw",
            "expectedRevision": before["lifecycleRevision"],
            "currentProof": PASSWORD,
            "policyRef": CONTROL_POLICY,
        },
    )
    assert prepared.status_code == 200, prepared.text
    result = post(
        browser,
        "lifecycle-request",
        {
            "action": "withdraw",
            "confirmationRef": prepared.json()["confirmationRef"],
            "policyRef": CONTROL_POLICY,
        },
    )
    assert result.status_code == 200, result.text
    value = result.json()
    assert value["state"] == "accepted" and value["revocation"] == "effective"
    bootstrap = browser.get("/api/v2/session").json()
    assert not bootstrap["signedIn"]
    browser.headers["X-CSRF-Token"] = bootstrap["csrfToken"]
    assert (
        post(
            browser, "lifecycle-inspect", {"lifecycleRequestId": value["lifecycleRequestId"]}
        ).status_code
        == 200
    )
    assert (
        post(browser, "lifecycle-inspect", {"lifecycleRequestId": str(uuid4())}).status_code == 403
    )
    assert post(browser, "access-read-profile", {}).status_code == 401


def test_identity_local_fixture_link_callback_and_unlink_replay(browser, connect, identities):
    with connect("accounts") as conn:
        conn.execute("DELETE FROM accounts.identity_link WHERE account_id=%s", (identities["a"],))
        conn.execute(
            "UPDATE accounts.identity_flow SET disposition='expired' WHERE disposition IN ('pending','exchanging')"
        )
    begin = post(
        browser,
        "access-begin-identity-flow",
        {
            "provider": "google",
            "intent": "link",
            "returnRouteId": "settings",
            "policyRef": CONTROL_POLICY,
        },
    )
    assert begin.status_code == 200, begin.text
    url = urlsplit(begin.json()["authorizationUrl"])
    assert url.netloc == "127.0.0.1:18049"
    callback = browser.get(url.path + "?" + url.query)
    assert callback.status_code == 200, callback.text
    link = callback.json()["identityLink"]
    assert callback.json()["state"] == "linked" and link["providerSubject"].startswith("synthetic-")
    key = uuid4()
    value = {"identityLinkId": link["identityLinkId"], "expectedRevision": link["revision"]}
    removed = post(browser, "access-unlink-identity", value, key=key)
    assert removed.status_code == 200, removed.text
    assert post(browser, "access-unlink-identity", value, key=key).json() == removed.json()


def test_mfa_one_delivery_and_limited_login_restart(browser):
    enrollment = post(
        browser,
        "access-begin-mfa-enrollment",
        {"currentProof": PASSWORD, "policyRef": CONTROL_POLICY},
    )
    assert enrollment.status_code == 200, enrollment.text
    value = enrollment.json()
    material_body = {
        "enrollmentId": value["enrollmentId"],
        "deliveryReference": value["deliveryReference"],
        "currentProof": PASSWORD,
    }
    material = post(browser, "access-retrieve-mfa-enrollment-material", material_body)
    assert material.status_code == 200, material.text
    assert post(browser, "access-retrieve-mfa-enrollment-material", material_body).status_code in (
        403,
        409,
    )
    session = post(browser, "access-inspect-session", {}).json()["session"]
    seed = material.json()["seed"]
    confirmation = post(
        browser,
        "access-confirm-mfa-enrollment",
        {
            "enrollmentId": value["enrollmentId"],
            "verification": {
                "challengeId": value["enrollmentId"],
                "flowBinding": session["sessionId"],
                "proof": totp(seed, int(time.time()) // 30 - 1),
            },
        },
    )
    assert confirmation.status_code == 200, confirmation.text
    post(browser, "access-logout", {})
    browser.headers["X-CSRF-Token"] = browser.get("/api/v2/session").json()["csrfToken"]
    login = post(
        browser,
        "access-login",
        {
            "email": "u2-a@fixture.example.com",
            "password": PASSWORD,
            "policyRef": {"policyId": "synthetic-local-entry", "revision": "1"},
        },
    )
    assert login.status_code == 200, login.text
    assert login.json()["state"] == "mfa_required"
    bootstrap = browser.get("/api/v2/session").json()
    assert not bootstrap["signedIn"]
    browser.headers["X-CSRF-Token"] = bootstrap["csrfToken"]
    assert post(browser, "access-inspect-session", {}).json()["state"] == "mfa_required"
    assert post(browser, "access-read-profile", {}).status_code == 401
    value = login.json()
    verified = post(
        browser,
        "access-verify-mfa",
        {
            "factorKind": "totp",
            "verification": {
                "challengeId": value["challengeId"],
                "flowBinding": value["flowBinding"],
                "proof": totp(seed, int(time.time()) // 30),
            },
        },
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["state"] == "authenticated"


def test_usage_inspection_does_not_allocate(browser, connect, identities):
    with connect("usage") as conn:
        conn.execute("DELETE FROM usage.reservation WHERE account_id=%s", (identities["a"],))
        before = conn.execute(
            "SELECT allocation,revoked FROM usage.entitlement WHERE account_id=%s",
            (identities["a"],),
        ).fetchone()
    result = post(browser, "usage-inspect", {"page": {"limit": 1}}, contract="c03")
    assert result.status_code == 200, result.text
    expected = int(before["allocation"]) if before and not before["revoked"] else 0
    assert result.json()["items"][0]["allocated"] == expected
    with connect("usage") as conn:
        after = conn.execute(
            "SELECT allocation,revoked FROM usage.entitlement WHERE account_id=%s",
            (identities["a"],),
        ).fetchone()
    assert after == before


def test_usage_records_preserve_period_and_bound_cursor(browser, connect, identities):
    identifiers = [uuid4(), uuid4()]
    with connect("usage") as conn:
        conn.execute(
            "INSERT INTO usage.entitlement(account_id,allocation,policy) "
            "VALUES(%s,3,'u2-synthetic-v1') ON CONFLICT DO NOTHING",
            (identities["a"],),
        )
        for identifier in identifiers:
            conn.execute(
                "INSERT INTO usage.reservation(id,account_id,operation_id,intent_hash,disposition,period_id) "
                "VALUES(%s,%s,%s,%s,'reserved','original-acceptance-period')",
                (identifier, identities["a"], uuid4(), "c" * 64),
            )
    response = post(browser, "usage-list-records", {"page": {"limit": 1}}, contract="c03")
    assert response.status_code == 200, response.text
    first = response.json()
    assert first["items"][0]["periodId"] == "original-acceptance-period"
    assert first["items"][0]["usageRecordId"] in [str(i) for i in identifiers]
    cursor = first["page"]["nextCursor"]
    response = post(
        browser, "usage-list-records", {"page": {"limit": 1, "cursor": cursor}}, contract="c03"
    )
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["usageRecordId"] != first["items"][0]["usageRecordId"]
    assert (
        post(
            browser, "usage-list-records", {"page": {"limit": 2, "cursor": cursor}}, contract="c03"
        ).status_code
        == 409
    )


def test_admin_assignment_requires_role_and_mfa(browser, connect, identities):
    value = {"accountId": str(identities["a"])}
    assert post(browser, "usage-read-assignment", value, contract="c03").status_code == 404
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.account SET role='administrator' WHERE id=%s", (identities["a"],)
        )
        conn.execute(
            "UPDATE accounts.session SET mfa_at=clock_timestamp() WHERE account_id=%s AND NOT revoked",
            (identities["a"],),
        )
    assigned = post(browser, "usage-read-assignment", value, contract="c03")
    assert assigned.status_code == 200, assigned.text
    granted = post(
        browser,
        "usage-grant-entitlement",
        dict(
            value,
            tierId="synthetic-free",
            reasonKey="synthetic-test",
            expectedRevision=assigned.json()["revision"],
            policyRef=CONTROL_POLICY,
        ),
        contract="c03",
    )
    assert granted.status_code == 200, granted.text
    assert granted.json()["disposition"] == "active"


@pytest.mark.parametrize(
    "header,value",
    [
        ("Host", "127.0.0.1:18039"),
        ("Origin", "https://attacker.example.com"),
        ("X-CSRF-Token", "0" * 64),
    ],
)
def test_control_transport_rejects_wrong_authority(browser, header, value):
    result = browser.post(
        "/api/v2/c02/access-read-profile",
        json={},
        headers={header: value, "Idempotency-Key": str(uuid4())},
    )
    assert result.status_code == 403


NEW_PASSWORD = "Reset!Research2026"
EMAIL = "u2-a@fixture.example.com"


@pytest.fixture
def mail(transactions):
    """The realm's synthetic verification mailbox: only mail a case itself caused."""
    root = ControlEntryService(transactions, SYNTHETIC_POLICY).mail.root
    before = set(root.glob("*.blob"))

    def delivered(purpose):
        values = [json.loads(path.read_text()) for path in set(root.glob("*.blob")) - before]
        return [value for value in values if value.get("purpose") == purpose]

    return delivered


def refresh_csrf(client):
    bootstrap = client.get("/api/v2/session").json()
    client.headers["X-CSRF-Token"] = bootstrap["csrfToken"]
    return bootstrap


def sign_in(client, password):
    client.cookies.delete(SESSION_COOKIE)
    refresh_csrf(client)
    response = post(
        client, "access-login", {"email": EMAIL, "password": password, "policyRef": ENTRY_POLICY}
    )
    refresh_csrf(client)
    return response


def withdraw_over_http(client):
    before = read_profile(client)
    prepared = post(
        client,
        "access-prepare-lifecycle",
        {
            "action": "withdraw",
            "expectedRevision": before["lifecycleRevision"],
            "currentProof": PASSWORD,
            "policyRef": CONTROL_POLICY,
        },
    )
    assert prepared.status_code == 200, prepared.text
    result = post(
        client,
        "lifecycle-request",
        {
            "action": "withdraw",
            "confirmationRef": prepared.json()["confirmationRef"],
            "policyRef": CONTROL_POLICY,
        },
    )
    assert result.status_code == 200, result.text
    refresh_csrf(client)


def link_over_http(client, provider):
    begin = post(
        client,
        "access-begin-identity-flow",
        {"provider": provider, "intent": "link", "returnRouteId": "settings", "policyRef": CONTROL_POLICY},
    )
    assert begin.status_code == 200, begin.text
    url = urlsplit(begin.json()["authorizationUrl"])
    callback = client.get(url.path + "?" + url.query)
    assert callback.status_code == 200, callback.text
    return callback.json()["identityLink"]


@pytest.fixture
def unlinked(connect, identities):
    """Start with no links or open flows; leave none behind for the other layers."""
    with connect("accounts") as conn:
        conn.execute("DELETE FROM accounts.identity_link WHERE account_id=%s", (identities["a"],))
        conn.execute(
            "UPDATE accounts.identity_flow SET disposition='expired' WHERE disposition IN ('pending','exchanging')"
        )
    yield
    with connect("accounts") as conn:
        conn.execute("DELETE FROM accounts.identity_link WHERE account_id=%s", (identities["a"],))


def test_profile_update_with_another_field_vocabulary_conflicts(browser):
    before = read_profile(browser)
    result = post(
        browser,
        "access-update-profile",
        {
            "expectedRevision": before["revision"],
            "fieldVocabularyRevision": "another-profile-vocabulary",
            "changes": [{"fieldId": "displayName", "value": "바뀌면 안 됨"}],
            "policyRef": CONTROL_POLICY,
        },
    )
    assert result.status_code == 409 and result.json()["code"] == "CONFLICT"
    assert read_profile(browser) == before


def test_consent_page_beyond_the_policy_limit_is_refused(browser):
    result = post(browser, "access-list-consents", {"page": {"limit": 51}})
    assert result.status_code == 409
    assert post(browser, "access-list-consents", {"page": {"limit": 50}}).status_code == 200


def test_password_reset_completes_only_for_its_entry_flow(browser, mail):
    requested = post(
        browser, "access-request-password-reset", {"email": EMAIL, "policyRef": CONTROL_POLICY}
    )
    assert requested.status_code == 200, requested.text
    (proof,) = mail("password-reset")
    verification = {
        "challengeId": proof["challengeId"],
        "proof": proof["proof"],
        "flowBinding": "another-entry-flow",
    }
    body = {"verification": verification, "newPassword": NEW_PASSWORD}
    assert post(browser, "access-complete-password-reset", body).status_code == 403
    verification["flowBinding"] = proof["flowBinding"]
    done = post(browser, "access-complete-password-reset", body)
    assert done.status_code == 200, done.text
    assert set(done.json()) == {"resourceId", "revision", "requestId"}
    assert not browser.get("/api/v2/session").json()["signedIn"]
    assert sign_in(browser, PASSWORD).status_code in (401, 403)
    login = sign_in(browser, NEW_PASSWORD)
    assert login.status_code == 200, login.text
    assert login.json()["state"] == "authenticated"


def test_email_change_completes_over_http_and_its_lost_ack_reconciles(browser, mail):
    address = "u2-http-" + uuid4().hex + "@fixture.example.com"
    requested = post(
        browser,
        "access-request-email-change",
        {"currentProof": PASSWORD, "newEmail": address, "policyRef": CONTROL_POLICY},
    )
    assert requested.status_code == 200, requested.text
    (proof,) = mail("email-change")
    verification = {
        "challengeId": proof["challengeId"],
        "proof": proof["proof"],
        "flowBinding": proof["flowBinding"],
    }
    forged = post(
        browser,
        "access-complete-email-change",
        {"verification": dict(verification, flowBinding="another-entry-flow")},
    )
    assert forged.status_code == 403
    cookies = "; ".join(
        name + "=" + browser.cookies.get(name) for name in (SESSION_COOKIE, ENTRY_COOKIE)
    )
    csrf, key = browser.headers["X-CSRF-Token"], uuid4()
    done = post(browser, "access-complete-email-change", {"verification": verification}, key=key)
    assert done.status_code == 200, done.text
    assert not browser.get("/api/v2/session").json()["signedIn"]
    replay = browser.post(
        "/api/v2/c02/access-complete-email-change",
        json={"verification": verification},
        headers={"Cookie": cookies, "X-CSRF-Token": csrf, "Idempotency-Key": str(key)},
    )
    assert replay.status_code == 200, replay.text
    assert replay.json() == done.json()


def test_withdrawn_owner_reactivates_over_http_with_a_limited_status_cookie(browser, mail):
    withdraw_over_http(browser)
    requested = post(
        browser, "access-request-reactivation", {"email": EMAIL, "policyRef": CONTROL_POLICY}
    )
    assert requested.status_code == 200, requested.text
    (proof,) = mail("reactivate")
    verification = {
        "challengeId": proof["challengeId"],
        "proof": proof["proof"],
        "flowBinding": proof["flowBinding"],
    }
    mismatched = post(
        browser,
        "lifecycle-reactivate",
        {"verification": verification, "confirmationRef": str(uuid4()), "policyRef": CONTROL_POLICY},
    )
    assert mismatched.status_code == 403
    accepted = post(
        browser,
        "lifecycle-reactivate",
        {"verification": verification, "confirmationRef": proof["challengeId"], "policyRef": CONTROL_POLICY},
    )
    assert accepted.status_code == 200, accepted.text
    value = accepted.json()
    assert value["state"] == "accepted" and value["access"] == "reactivation_pending"
    status = post(browser, "lifecycle-inspect", {"lifecycleRequestId": value["lifecycleRequestId"]})
    assert status.status_code == 200, status.text
    assert status.json()["action"] == "reactivate"
    assert post(browser, "access-read-profile", {}).status_code == 401


def test_mfa_routes_refuse_mismatched_proofs_and_gated_recovery(browser):
    session = post(browser, "access-inspect-session", {}).json()["session"]
    mismatched = post(
        browser,
        "access-confirm-mfa-enrollment",
        {
            "enrollmentId": str(uuid4()),
            "verification": {"challengeId": str(uuid4()), "flowBinding": session["sessionId"], "proof": "123456"},
        },
    )
    assert mismatched.status_code == 403
    proof = {"challengeId": str(uuid4()), "flowBinding": str(uuid4()), "proof": "recovery-code"}
    verified = post(browser, "access-verify-mfa", {"factorKind": "recovery_proof", "verification": proof})
    assert verified.status_code == 503 and verified.json()["code"] == "POLICY_UNRESOLVED"
    recovered = post(browser, "access-recover-mfa", {"verification": proof, "policyRef": CONTROL_POLICY})
    assert recovered.status_code == 503 and recovered.json()["code"] == "POLICY_UNRESOLVED"
    assert read_profile(browser)["accountId"] == session["accountId"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/v2/identity/callback/github?flow=x&state=y&code=z",
        "/api/v2/identity/callback/google?flow=x&state=y",
        "/api/v2/identity/callback/google?flow=x&state=y&code=z&code=w",
    ],
)
def test_identity_callback_refuses_unknown_providers_and_malformed_queries(browser, path):
    result = browser.get(path)
    assert result.status_code == 422 and result.json()["code"] == "INVALID_ARGUMENT"


def test_linked_identity_lists_and_signs_in_through_the_provider(browser, unlinked):
    link = link_over_http(browser, "google")
    listed = post(browser, "access-list-identity-links", {"page": {"limit": 5}})
    assert listed.status_code == 200, listed.text
    assert [item["identityLinkId"] for item in listed.json()["items"]] == [link["identityLinkId"]]
    post(browser, "access-logout", {})
    browser.cookies.delete(SESSION_COOKIE)
    refresh_csrf(browser)
    begin = post(
        browser,
        "access-begin-identity-flow",
        {"provider": "google", "intent": "sign_in", "returnRouteId": "search", "policyRef": CONTROL_POLICY},
    )
    assert begin.status_code == 200, begin.text
    url = urlsplit(begin.json()["authorizationUrl"])
    callback = browser.get(url.path + "?" + url.query)
    assert callback.status_code == 200, callback.text
    value = callback.json()
    assert value["state"] == "signed_in"
    assert value["identityLink"]["identityLinkId"] == link["identityLinkId"]
    assert browser.get("/api/v2/session").json()["signedIn"]


def test_provider_sign_in_with_an_active_factor_asks_for_the_second_factor(browser, unlinked):
    link_over_http(browser, "google")
    enrollment = post(
        browser, "access-begin-mfa-enrollment", {"currentProof": PASSWORD, "policyRef": CONTROL_POLICY}
    ).json()
    material = post(
        browser,
        "access-retrieve-mfa-enrollment-material",
        {
            "enrollmentId": enrollment["enrollmentId"],
            "deliveryReference": enrollment["deliveryReference"],
            "currentProof": PASSWORD,
        },
    ).json()
    session = post(browser, "access-inspect-session", {}).json()["session"]
    confirmed = post(
        browser,
        "access-confirm-mfa-enrollment",
        {
            "enrollmentId": enrollment["enrollmentId"],
            "verification": {
                "challengeId": enrollment["enrollmentId"],
                "flowBinding": session["sessionId"],
                "proof": totp(material["seed"], int(time.time()) // 30),
            },
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    post(browser, "access-logout", {})
    browser.cookies.delete(SESSION_COOKIE)
    refresh_csrf(browser)
    begin = post(
        browser,
        "access-begin-identity-flow",
        {"provider": "google", "intent": "sign_in", "returnRouteId": "search", "policyRef": CONTROL_POLICY},
    )
    assert begin.status_code == 200, begin.text
    url = urlsplit(begin.json()["authorizationUrl"])
    callback = browser.get(url.path + "?" + url.query)
    assert callback.status_code == 200, callback.text
    assert callback.json()["state"] == "mfa_required"
    assert not browser.get("/api/v2/session").json()["signedIn"]


def test_orcid_profile_reads_only_the_owners_orcid_link(browser, unlinked):
    absent = post(browser, "access-read-orcid-profile", {"identityLinkId": str(uuid4())})
    assert absent.status_code == 403
    google = link_over_http(browser, "google")
    assert (
        post(browser, "access-read-orcid-profile", {"identityLinkId": google["identityLinkId"]}).status_code
        == 403
    )
    orcid = link_over_http(browser, "orcid")
    profile = post(browser, "access-read-orcid-profile", {"identityLinkId": orcid["identityLinkId"]})
    assert profile.status_code == 200, profile.text
    value = profile.json()
    assert value["identityLinkId"] == orcid["identityLinkId"]
    assert value["provenance"] == "synthetic-orcid-fixture" and value["coverage"] == "partial"
