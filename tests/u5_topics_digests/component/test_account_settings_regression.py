"""Inherited account/personalization paths on the owned U5 store, without reset quotas."""

import json
from uuid import UUID, uuid4

import psycopg
import pytest
from backend.artifacts import Artifact
from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.modules.personalization.guarded_service import (
    INTEREST_VOCABULARY,
    GuardedSettingsService,
)
from scripts.u5_browser_fixtures import fixture_record


@pytest.fixture
def entry(transactions):
    return GuardedEntryService(transactions)


def login(entry, realm, **kwargs):
    record = fixture_record(realm)["accounts"]["memberA"]
    return entry.login(record["email"], record["password"], **kwargs)


def test_inherited_login_bootstrap_rotation_logout(entry, realm):
    first = login(entry, realm)
    authority = entry.authenticate(first.token, csrf=first.csrf)
    assert str(authority.account_id) == first.public["session"]["accountId"]
    assert entry.inspect_session(first.token).csrf == first.csrf
    with pytest.raises(PermissionError):
        entry.authenticate(first.token, csrf="wrong")
    second = login(entry, realm)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        entry.authenticate(first.token)
    entry.logout(entry.authenticate(second.token), operation=uuid4())
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        entry.inspect_session(second.token)


def test_inherited_login_replay_is_flow_bound(entry, realm):
    operation = uuid4()
    first = login(entry, realm, operation=operation, flow_binding="u5-regression")
    replay = login(entry, realm, operation=operation, flow_binding="u5-regression")
    assert replay == first
    with pytest.raises(ValueError):
        login(entry, realm, operation=operation, flow_binding="other")


def test_wrong_password_unknown_session_and_input_bound(entry, realm):
    record = fixture_record(realm)["accounts"]["memberA"]
    with pytest.raises(PermissionError):
        entry.login(record["email"], "incorrect-password")
    with pytest.raises(PermissionError):
        entry.inspect_session("not-a-session")
    with pytest.raises(ValueError):
        entry.verifier("session", "x" * 2049)


def test_verification_recovery_uses_private_local_mail(entry, realm, connect):
    record = fixture_record(realm)["accounts"]["memberB"]
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.account SET verified=false WHERE id=%s", (UUID(record["accountId"]),)
        )
    operation = uuid4()
    ack = entry.request_verification(operation, record["email"], "u5-flow")
    assert entry.request_verification(operation, record["email"], "u5-flow") == ack
    with connect("accounts") as conn:
        row = conn.execute(
            "SELECT c.id,d.private_path,d.content_hash,d.byte_length FROM accounts.challenge c JOIN accounts.delivery d ON d.challenge_id=c.id WHERE c.account_id=%s AND NOT c.consumed",
            (UUID(record["accountId"]),),
        ).fetchone()
    mail = json.loads(
        entry.mail.read(Artifact(row["private_path"], row["content_hash"], row["byte_length"]))
    )
    challenge = UUID(mail["challengeId"])
    with pytest.raises(PermissionError):
        entry.verify_email(challenge, "wrong", "u5-flow", operation=uuid4())
    operation = uuid4()
    verified = entry.verify_email(challenge, mail["proof"], "u5-flow", operation=operation)
    assert entry.verify_email(challenge, mail["proof"], "u5-flow", operation=operation) == verified


def test_onboarding_preserves_confirmed_zone_and_owner_revision(transactions, authority):
    settings = GuardedSettingsService(transactions)
    before = settings.read(authority)
    selected = [next(iter(INTEREST_VOCABULARY))]
    operation = uuid4()
    saved = settings.update_onboarding(
        authority, operation, before["revision"], "save_interests", selected
    )
    assert saved["timeZone"] == before["timeZone"] == "UTC"
    assert saved["onboarding"] == "in_progress"
    assert (
        settings.update_onboarding(
            authority, operation, before["revision"], "save_interests", selected
        )
        == saved
    )
    completed = settings.update_onboarding(
        authority, uuid4(), saved["revision"], "complete", selected
    )
    assert completed["onboarding"] == "completed"


def test_onboarding_conflict_and_vocabulary_refuse(transactions, authority):
    settings = GuardedSettingsService(transactions)
    before = settings.read(authority)
    for action, interests in (
        ("invented", []),
        ("complete", ["invalid"]),
        ("complete", ["x", "x"]),
    ):
        with pytest.raises(ValueError):
            settings.update_onboarding(authority, uuid4(), before["revision"], action, interests)
    with pytest.raises(ValueError):
        settings.update_onboarding(authority, uuid4(), str(uuid4()), "skip", [])


def test_account_session_survives_consent_stop_but_not_revocation(entry, realm, connect):
    issued = login(entry, realm)
    owner = UUID(issued.public["session"]["accountId"])
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.consent SET granted=false WHERE account_id=%s", (owner,))
    try:
        assert entry.inspect_session(issued.token).public["state"] == "authenticated"
        entry.logout(entry.authenticate(issued.token))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            entry.inspect_session(issued.token)
    finally:
        with connect("accounts") as conn:
            conn.execute(
                "UPDATE accounts.consent SET granted=true WHERE account_id=%s AND purpose='local-research'",
                (owner,),
            )
