"""Account entry and settings in the U6 realm run under the `account-control` purpose:
sign-in, the session read, logout and the settings read and save work through the
mounted routes even while research consent is withdrawn, and the export routes, which
send a research result, stay under the research purpose."""

from uuid import uuid4

import pytest
from backend.modules.accounts.local_http import ENTRY_POLICY, account_router
from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.modules.export.http import PREFIX, export_router
from backend.modules.personalization.guarded_service import POLICY as SETTINGS_POLICY
from backend.modules.personalization.local_http import settings_router
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.u6_approved_export import service_flows as sf

# A synthetic password that satisfies the local policy; never a real credential.
PASSWORD = "Synthetic-U6-Passw0rd!"


@pytest.fixture
def signed_out(realm, transactions, connect, authority_b, tmp_path):
    """A browser for owner B, who can sign in with a synthetic password, with B's
    research consent withdrawn for the test and restored afterwards."""
    entry = GuardedEntryService(transactions)
    rig = sf.build(transactions, connect, authority_b, tmp_path)
    app = FastAPI()
    app.include_router(account_router(entry))
    app.include_router(settings_router(transactions, entry=entry))
    app.include_router(export_router(transactions, entry=entry, service=rig.service))
    account = authority_b.account_id
    # The conftest's `.invalid` address is not a sign-in address; give the same account
    # a deterministic synthetic one, as U5's browser fixtures use.
    email = f"{account}@u6.fixture.example.com"
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.account SET password_hash=%s,email=%s WHERE id=%s",
            (entry.hasher.hash(PASSWORD), email, account),
        )
        conn.execute(
            "UPDATE accounts.consent SET granted=false WHERE account_id=%s "
            "AND purpose='local-research'",
            (account,),
        )
    client = TestClient(app, base_url=realm.origin)
    try:
        yield client, email
    finally:
        client.close()
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.consent SET granted=true WHERE account_id=%s "
                "AND purpose='local-research'",
                (account,),
            )


def boot(client) -> dict:
    response = client.get("/api/v2/session")
    assert response.status_code == 200
    return response.json()


def headers(client, realm) -> dict:
    return {
        "Origin": realm.origin,
        "X-CSRF-Token": boot(client)["csrfToken"],
        "Idempotency-Key": str(uuid4()),
    }


def post(client, realm, path, body):
    return client.post(path, json=body, headers=headers(client, realm))


def test_entry_and_settings_work_under_account_control_while_research_is_withdrawn(
    signed_out, realm
):
    client, email = signed_out
    assert boot(client)["signedIn"] is False

    login = post(
        client,
        realm,
        "/api/v2/c02/access-login",
        {"email": email, "password": PASSWORD, "policyRef": ENTRY_POLICY},
    )
    session = boot(client)
    inspected = post(client, realm, "/api/v2/c02/access-inspect-session", {})
    settings = post(client, realm, "/api/v2/c03/settings-read", {})
    assert settings.status_code == 200, (login.json(), settings.json())
    saved = post(
        client,
        realm,
        "/api/v2/c03/settings-update",
        {
            "appearance": "dark",
            "policyRef": SETTINGS_POLICY,
            "expectedRevision": settings.json()["revision"],
        },
    )
    export = post(client, realm, PREFIX + "read-notion-connection", {})
    logout = post(client, realm, "/api/v2/c02/access-logout", {})

    assert login.status_code == 200, login.json()
    assert session["signedIn"] is True
    assert inspected.json()["state"] == "authenticated"
    assert settings.status_code == 200
    assert (saved.status_code, saved.json()["appearance"]) == (200, "dark")
    # The export store's guard runs under the research purpose, which is withdrawn.
    assert (export.status_code, export.json()["code"]) == (404, "NOT_FOUND")
    assert logout.status_code == 200
    assert boot(client)["signedIn"] is False
    after = post(client, realm, "/api/v2/c03/settings-read", {})
    assert after.status_code == 401


def test_a_wrong_password_signs_nobody_in(signed_out, realm):
    client, email = signed_out

    refused = post(
        client,
        realm,
        "/api/v2/c02/access-login",
        {"email": email, "password": PASSWORD + "x", "policyRef": ENTRY_POLICY},
    )

    assert refused.status_code == 403, refused.json()
    assert PASSWORD not in refused.text
    assert boot(client)["signedIn"] is False
