"""Mounted U2 owner controls with real PostgreSQL and cookie/CSRF transport."""

import time
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from backend.local_host import assemble_journey
from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.accounts.services.control_entry import ControlEntryService
from backend.modules.personalization.guarded_service import POLICY

pytestmark = pytest.mark.u2_integration
ORIGIN = "https://127.0.0.1:18049"
PASSWORD = "Synthetic!Research2026"
CONTROL_POLICY = SYNTHETIC_POLICY.reference
ENTRY_POLICY = {"policyId": "synthetic-local-entry", "revision": "1"}
QUERY = {
    "query": "Transformer",
    "modeId": "lexical",
    "orderId": "relevance",
    "filters": [],
    "vocabularyRevision": "synthetic-paper-options-1",
    "policyRef": {"policyId": "synthetic-local-search", "revision": "1"},
}


@pytest.fixture
def browser(realm, transactions, identities, connect, clear_resets):
    entry = ControlEntryService(transactions, SYNTHETIC_POLICY)
    encoded = entry._hash_password(PASSWORD)
    with connect("accounts") as conn:
        conn.execute("DELETE FROM accounts.entry_budget")
        conn.execute(
            "UPDATE accounts.account SET password_hash=%s,email=%s WHERE id=%s",
            (encoded, "u2-a@fixture.example.com", identities["a"]),
        )
        conn.execute(
            "UPDATE accounts.mfa_enrollment SET state='invalidated' WHERE account_id=ANY(%s)",
            ([identities["a"], identities["b"]],),
        )
    with connect("library") as conn:
        for table in ("saved_query", "saved_paper", "history"):
            conn.execute(f"DELETE FROM library.{table} WHERE account_id=%s", (identities["a"],))
    with connect("personalization") as conn:
        conn.execute(
            "INSERT INTO personalization.settings(account_id,revision,input_boundary) "
            "SELECT %s,%s,coalesce(max(input_boundary),0)+1 FROM personalization.reset_responsibility "
            "WHERE account_id=%s ON CONFLICT(account_id) DO UPDATE SET revision=excluded.revision,"
            "defaults='{}',appearance='system',input_boundary=greatest(personalization.settings.input_boundary,excluded.input_boundary)",
            (identities["a"], uuid4(), identities["a"]),
        )
    app = assemble_journey(realm[0])
    with TestClient(app, base_url=ORIGIN) as client:
        await_admission(client)
        bootstrap = client.get("/api/v2/session")
        assert bootstrap.status_code == 200
        client.headers.update({"Origin": ORIGIN, "X-CSRF-Token": bootstrap.json()["csrfToken"]})
        response = client.post(
            "/api/v2/c02/access-login",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "email": "u2-a@fixture.example.com",
                "password": PASSWORD,
                "policyRef": ENTRY_POLICY,
            },
        )
        assert response.status_code == 200, response.text
        client.headers["X-CSRF-Token"] = client.get("/api/v2/session").json()["csrfToken"]
        yield client
        clear_resets(identities["a"])


def post(client, name, value, *, key=None):
    return client.post(
        "/api/v2/c03/" + name, json=value, headers={"Idempotency-Key": str(key or uuid4())}
    )


def await_admission(client, *, seconds: float = 15.0):
    """Bounded wait for the first capacity observation; normal routes fail closed."""
    deadline = time.monotonic() + seconds
    while True:
        probe = client.get("/health/ready")
        if probe.status_code == 200:
            return
        if time.monotonic() >= deadline:
            raise AssertionError(f"control host never admitted requests: {probe.text}")
        time.sleep(0.05)


def read_settings(client):
    response = post(client, "settings-read", {})
    assert response.status_code == 200, response.text
    return response.json()


def prepare(client, before, *, action="delete_behavior", proof=PASSWORD, key=None):
    return post(
        client,
        "settings-prepare-reset",
        {
            "action": action,
            "currentProof": proof,
            "expectedRevision": before["revision"],
            "policyRef": CONTROL_POLICY,
        },
        key=key,
    )


def reset(client, before, confirmation, *, key=None, action="delete_behavior"):
    return post(
        client,
        "settings-reset",
        {
            "action": action,
            "confirmationRef": confirmation,
            "expectedRevision": before["revision"],
            "policyRef": CONTROL_POLICY,
        },
        key=key,
    )


def test_settings_update_and_stale_browser_conflict(browser):
    before = read_settings(browser)
    changed = post(
        browser,
        "settings-update",
        {"expectedRevision": before["revision"], "appearance": "dark", "policyRef": POLICY},
    )
    assert changed.status_code == 200 and changed.json()["appearance"] == "dark"
    assert (
        post(
            browser,
            "settings-update",
            {"expectedRevision": before["revision"], "appearance": "light", "policyRef": POLICY},
        ).status_code
        == 409
    )
    assert read_settings(browser)["appearance"] == "dark"


def test_settings_update_requires_current_policy(browser):
    before = read_settings(browser)
    result = post(
        browser,
        "settings-update",
        {
            "expectedRevision": before["revision"],
            "appearance": "dark",
            "policyRef": {"policyId": "invented", "revision": "1"},
        },
    )
    assert result.status_code == 503 and result.json()["code"] == "POLICY_UNRESOLVED"
    assert read_settings(browser) == before


def test_skip_keeps_saved_manual_interests(browser):
    before = read_settings(browser)
    selected = post(
        browser,
        "settings-update-onboarding",
        {
            "action": "save_interests",
            "interestIds": ["1706.03762"],
            "expectedRevision": before["revision"],
            "policyRef": POLICY,
        },
    )
    assert selected.status_code == 200, selected.text
    skipped = post(
        browser,
        "settings-update-onboarding",
        {
            "action": "skip",
            "interestIds": [],
            "expectedRevision": selected.json()["revision"],
            "policyRef": POLICY,
        },
    )
    assert skipped.status_code == 200 and skipped.json()["interestIds"] == ["1706.03762"]


def test_manual_suggestions_and_unavailable_linked_provider(browser):
    page = post(browser, "settings-list-suggestions", {"page": {"limit": 1}})
    assert page.status_code == 200 and len(page.json()["items"]) == 1
    assert page.json()["page"]["nextCursor"]
    result = post(
        browser, "settings-list-suggestions", {"page": {"limit": 1}, "identityLinkId": str(uuid4())}
    )
    assert result.status_code == 503 and result.json()["code"] == "POLICY_UNRESOLVED"


def test_recent_read_is_bounded(browser):
    response = post(browser, "settings-list-recent-papers", {"page": {"limit": 2}})
    assert response.status_code == 200 and len(response.json()["items"]) <= 2
    assert post(browser, "settings-list-recent-papers", {"page": {"limit": 51}}).status_code == 409


def test_prepare_reauth_and_forged_reference_refused(browser):
    before = read_settings(browser)
    assert prepare(browser, before, proof="Wrong!SyntheticPassword").status_code == 404
    assert reset(browser, before, str(uuid4())).status_code == 404
    assert read_settings(browser) == before


def test_reset_acceptance_replay_and_read_only_rediscovery(browser, connect, identities):
    before = read_settings(browser)
    prepared = prepare(browser, before)
    assert prepared.status_code == 200, prepared.text
    key = uuid4()
    accepted = reset(browser, before, prepared.json()["confirmationRef"], key=key)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["disposition"] == "pending"
    assert (
        reset(browser, before, prepared.json()["confirmationRef"], key=key).json()
        == accepted.json()
    )
    after = read_settings(browser)
    for _ in range(2):
        listed = browser.get("/api/v2/c03/settings-resets?view=outstanding&limit=50")
        assert listed.status_code == 200
        assert accepted.json()["resetId"] in [item["resetId"] for item in listed.json()["items"]]
        status = browser.get("/api/v2/c03/settings-resets/" + accepted.json()["resetId"])
        assert status.status_code == 200 and len(status.json()["scopes"]) == 2
        assert all(item["disposition"] == "pending" for item in status.json()["scopes"])
    assert read_settings(browser) == after
    with connect("personalization") as conn:
        scopes = conn.execute(
            "SELECT attempts FROM personalization.reset_scope WHERE reset_id=%s",
            (UUID(accepted.json()["resetId"]),),
        ).fetchall()
        assert all(row["attempts"] == 0 for row in scopes)


def test_reset_confirmation_bound_to_action(browser):
    before = read_settings(browser)
    confirmation = prepare(browser, before).json()["confirmationRef"]
    assert reset(browser, before, confirmation, action="reset_profile").status_code == 404
    assert read_settings(browser) == before


def test_confirmation_replay_does_not_extend_expiry(browser):
    before = read_settings(browser)
    key = uuid4()
    first = prepare(browser, before, key=key)
    assert first.status_code == 200
    assert prepare(browser, before, key=key).json() == first.json()


def test_reset_confirmation_not_valid_after_expiry(browser, transactions):
    from dataclasses import replace
    from time import sleep
    from backend.modules.accounts.control_confirmation import ResetConfirmationService
    from backend.transactions import Authority

    before = read_settings(browser)
    session = browser.post(
        "/api/v2/c02/access-inspect-session", json={}, headers={"Idempotency-Key": str(uuid4())}
    ).json()["session"]
    authority = Authority(UUID(session["accountId"]), UUID(session["sessionId"]))
    policy = replace(SYNTHETIC_POLICY, proof_seconds=1, material_seconds=1)
    entry = ControlEntryService(transactions, SYNTHETIC_POLICY)
    service = ResetConfirmationService(transactions, policy, entry)
    value = service.prepare(
        authority,
        uuid4(),
        action="delete_behavior",
        expected=UUID(before["revision"]),
        proof=PASSWORD,
    )
    sleep(1.05)
    assert reset(browser, before, value["confirmationRef"]).status_code == 404
    assert read_settings(browser) == before


def test_reset_unknown_and_foreign_ids_have_same_disposition(browser):
    result = browser.get("/api/v2/c03/settings-resets/" + str(uuid4()))
    assert result.status_code == 404
    assert (
        browser.get("/api/v2/c03/settings-resets?view=history&limit=1&limit=2").status_code == 422
    )


def test_saved_query_pagination_and_history_are_separate(browser):
    for word in ("alpha", "beta", "gamma"):
        result = post(browser, "library-save-search", {"queryContext": dict(QUERY, query=word)})
        assert result.status_code == 200, result.text
    page = post(browser, "library-list-saved-searches", {"page": {"limit": 2}})
    assert page.status_code == 200 and len(page.json()["items"]) == 2
    second = post(
        browser,
        "library-list-saved-searches",
        {"page": {"limit": 2, "cursor": page.json()["page"]["nextCursor"]}},
    )
    assert second.status_code == 200 and len(second.json()["items"]) == 1
    history = post(browser, "library-list-history", {"page": {"limit": 2}})
    assert history.status_code == 200 and history.json()["items"] == []


def test_clear_history_is_durable_and_preserves_saved_queries(browser):
    saved = post(browser, "library-save-search", {"queryContext": QUERY})
    assert saved.status_code == 200
    before = post(browser, "library-list-history", {"page": {"limit": 2}}).json()
    key = uuid4()
    body = {"expectedRevision": before["clearBoundary"], "policyRef": CONTROL_POLICY}
    result = post(browser, "library-clear-history", body, key=key)
    assert result.status_code == 200, result.text
    assert post(browser, "library-clear-history", body, key=key).json() == result.json()
    assert (
        len(post(browser, "library-list-saved-searches", {"page": {"limit": 2}}).json()["items"])
        == 1
    )


def test_library_remove_checks_observed_revision(browser):
    saved = post(browser, "library-save-search", {"queryContext": QUERY}).json()
    body = {"savedSearchId": saved["savedSearchId"], "expectedRevision": str(uuid4())}
    assert post(browser, "library-remove-saved-search", body).status_code == 409
    body["expectedRevision"] = saved["revision"]
    assert post(browser, "library-remove-saved-search", body).status_code == 200


def test_ambiguous_json_and_foreign_origin_refused(browser):
    result = browser.post(
        "/api/v2/c03/settings-read",
        content='{"x":1,"x":2}',
        headers={"Content-Type": "application/json", "Idempotency-Key": str(uuid4())},
    )
    assert result.status_code == 422
    result = browser.post(
        "/api/v2/c03/settings-read",
        json={},
        headers={"Origin": "https://foreign.invalid", "Idempotency-Key": str(uuid4())},
    )
    assert result.status_code == 403


def test_changed_confirmation_cannot_replay_accepted_operation(browser):
    before = read_settings(browser)
    preparation_key = uuid4()
    proof = prepare(browser, before, key=preparation_key).json()
    key = uuid4()
    accepted = reset(browser, before, proof["confirmationRef"], key=key)
    assert accepted.status_code == 200
    assert reset(browser, before, str(uuid4()), key=key).status_code == 409
    assert prepare(browser, before, key=preparation_key).json() == proof


def test_reset_record_and_cursor_stay_with_owner(browser, connect, identities):
    before = read_settings(browser)
    proof = prepare(browser, before).json()["confirmationRef"]
    accepted = reset(browser, before, proof).json()
    for _ in range(2):
        assert post(browser, "library-save-search", {"queryContext": QUERY}).status_code == 200
    page = post(browser, "library-list-saved-searches", {"page": {"limit": 1}}).json()
    with connect("accounts") as conn:
        encoded = browser.app.state.entry._hash_password(PASSWORD)
        conn.execute(
            "UPDATE accounts.account SET password_hash=%s,email=%s WHERE id=%s",
            (encoded, "u2-b@fixture.example.com", identities["b"]),
        )
    browser.cookies.clear()
    bootstrap = browser.get("/api/v2/session").json()
    browser.headers["X-CSRF-Token"] = bootstrap["csrfToken"]
    response = browser.post(
        "/api/v2/c02/access-login",
        json={"email": "u2-b@fixture.example.com", "password": PASSWORD, "policyRef": ENTRY_POLICY},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 200, response.text
    browser.headers["X-CSRF-Token"] = browser.get("/api/v2/session").json()["csrfToken"]
    foreign = browser.get("/api/v2/c03/settings-resets/" + accepted["resetId"])
    absent = browser.get("/api/v2/c03/settings-resets/" + str(uuid4()))
    assert foreign.status_code == absent.status_code == 404
    assert foreign.json()["code"] == absent.json()["code"]
    assert (
        post(
            browser,
            "library-list-saved-searches",
            {"page": {"limit": 1, "cursor": page["page"]["nextCursor"]}},
        ).status_code
        == 409
    )


def test_saved_paper_preserves_original_metadata_after_withdrawal(browser, connect):
    revision = uuid4()
    with connect("corpus") as conn:
        conn.execute(
            "INSERT INTO corpus.paper(id,title,authors,metadata) VALUES('u2-http-paper','Original title','[]','{}') "
            "ON CONFLICT(id) DO UPDATE SET withdrawn=false,title='Original title'"
        )
        conn.execute(
            "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,private_path,eligible,purpose,eligibility_revision,provenance,content) "
            "VALUES('u2-http-version','u2-http-paper','https://fixture.example.com/paper',%s,'u2','fixture',true,'local-research',%s,'{}','{}') "
            "ON CONFLICT(id) DO UPDATE SET eligible=true,eligibility_revision=excluded.eligibility_revision",
            ("c" * 64, revision),
        )
    body = {
        "paper": {
            "paperId": "u2-http-paper",
            "versionId": "u2-http-version",
            "eligibilityRevision": str(revision),
        },
        "policyRef": CONTROL_POLICY,
    }
    saved = post(browser, "library-save-paper", body)
    assert saved.status_code == 200, saved.text
    recent = post(browser, "settings-list-recent-papers", {"page": {"limit": 50}})
    assert recent.status_code == 200
    assert "u2-http-version" in [item["paper"]["versionId"] for item in recent.json()["items"]]
    with connect("corpus") as conn:
        conn.execute(
            "UPDATE corpus.paper SET withdrawn=true,title='Changed title' WHERE id='u2-http-paper'"
        )
    read = post(browser, "library-read-saved-paper", {"savedPaperId": saved.json()["savedPaperId"]})
    assert read.status_code == 200, read.text
    assert read.json()["savedTitle"] == "Original title"
    assert read.json()["sourceDisposition"] == "withdrawn"
    assert read.json()["savedPaper"]["eligibilityRevision"] == str(revision)
    assert "resolvedPaper" not in read.json()
