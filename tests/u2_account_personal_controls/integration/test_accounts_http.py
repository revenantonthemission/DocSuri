"""C02/C03 mounted contract and current-authority checks over the real store."""

from uuid import uuid4
from urllib.parse import urlsplit
import time

import pytest
from test_library_personal_http import PASSWORD, CONTROL_POLICY
from test_library_personal_http import browser as browser
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
