"""Real AccountAccess persistence and private local delivery, after implementation."""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

import psycopg
import pytest

from backend.artifacts import Artifact
from backend.modules.accounts.services.guarded_entry import GuardedEntryService
from backend.transactions import Busy, OwnerTransactions, UnknownCommit

pytestmark = pytest.mark.u1_component
PASSWORD = "LocalFixture!28-A"


@pytest.fixture
def entry(realm, connect):
    profile = realm[0]
    diagnostic = [uuid5(NAMESPACE_URL, profile.run_id + name) for name in ("a", "b")]
    with connect("accounts") as conn:
        rows = conn.execute("SELECT id,email FROM accounts.account WHERE active").fetchall()
        assert all(
            row[0] in diagnostic or row[1].endswith("@entry.fixture.invalid") for row in rows
        ), "unknown ordinary account; refuse diagnostic phase transition"
        for row in rows:
            conn.execute("UPDATE accounts.account SET active=false WHERE id=%s", (row[0],))
        conn.execute("DELETE FROM accounts.entry_budget")
    tx = OwnerTransactions(profile)
    service = GuardedEntryService(tx)
    yield service
    tx.close()


def mailbox(entry, connect, email):
    with connect("accounts") as conn:
        row = conn.execute(
            "SELECT c.id,d.private_path,d.content_hash,d.byte_length FROM accounts.challenge c "
            "JOIN accounts.account a ON a.id=c.account_id JOIN accounts.delivery d ON "
            "d.challenge_id=c.id WHERE a.email=%s AND NOT c.consumed",
            (email,),
        ).fetchone()
    return json.loads(entry.mail.read(Artifact(row[1], row[2], row[3])))


def registered(entry, connect):
    email = uuid4().hex + "@entry.fixture.invalid"
    operation = uuid4()
    result = entry.register(operation, email, PASSWORD, "연구자", "fixture-flow")
    return email, operation, result, mailbox(entry, connect, email)


def verified(entry, connect):
    email, operation, result, mail = registered(entry, connect)
    entry.verify_email(
        UUID(mail["challengeId"]), mail["proof"], mail["flowBinding"], operation=uuid4()
    )
    return email


def test_verified_entry_session_csrf_rotation_and_logout(entry, connect):
    email = verified(entry, connect)
    first = entry.login(email, PASSWORD)
    authority = entry.authenticate(first.token, csrf=first.csrf)
    assert str(authority.account_id) == first.public["session"]["accountId"]
    assert first.public["session"]["authenticationLevel"] == "primary"
    with pytest.raises(PermissionError):
        entry.authenticate(first.token, csrf="wrong")
    second = entry.login(email, PASSWORD)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        entry.authenticate(first.token)
    entry.logout(entry.authenticate(second.token))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        entry.authenticate(second.token)


def test_registration_replay_changed_intent_and_existing_email_are_safe(entry, connect):
    email, operation, result, _ = registered(entry, connect)
    assert entry.register(operation, email, PASSWORD, "연구자", "fixture-flow") == result
    with pytest.raises(ValueError, match="conflict"):
        entry.register(operation, email, PASSWORD, "다른 이름", "fixture-flow")
    other = entry.register(uuid4(), email, PASSWORD, "연구자", "fixture-flow")
    assert set(other) == set(result) == {"requestId", "acknowledgement", "messageKey"}
    assert other["messageKey"] == result["messageKey"]


def test_wrong_expired_and_replayed_verification_fail_closed(entry, connect):
    email, _, _, mail = registered(entry, connect)
    challenge = UUID(mail["challengeId"])
    with pytest.raises(PermissionError):
        entry.verify_email(challenge, mail["proof"], "wrong-flow", operation=uuid4())
    with pytest.raises(PermissionError):
        entry.verify_email(challenge, "wrong-proof", "fixture-flow", operation=uuid4())
    operation = uuid4()
    entry.verify_email(challenge, mail["proof"], "fixture-flow", operation=operation)
    entry.verify_email(challenge, mail["proof"], "fixture-flow", operation=operation)
    with pytest.raises(PermissionError):
        entry.verify_email(challenge, mail["proof"], "fixture-flow", operation=uuid4())
    email, _, _, mail = registered(entry, connect)
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.challenge SET expires_at=clock_timestamp()-interval '1 second' "
            "WHERE id=%s",
            (UUID(mail["challengeId"]),),
        )
    with pytest.raises(PermissionError):
        entry.verify_email(
            UUID(mail["challengeId"]), mail["proof"], "fixture-flow", operation=uuid4()
        )


def test_resend_replaces_proof_without_enumerating_unknown_email(entry, connect):
    email, _, _, old = registered(entry, connect)
    operation = uuid4()
    result = entry.request_verification(operation, email, "new-flow")
    assert entry.request_verification(operation, email, "new-flow") == result
    unknown = entry.request_verification(uuid4(), "absent@entry.fixture.invalid", "new-flow")
    assert result["messageKey"] == unknown["messageKey"]
    with pytest.raises(PermissionError):
        entry.verify_email(
            UUID(old["challengeId"]), old["proof"], old["flowBinding"], operation=uuid4()
        )
    new = mailbox(entry, connect, email)
    entry.verify_email(
        UUID(new["challengeId"]), new["proof"], new["flowBinding"], operation=uuid4()
    )


def test_unknown_registration_commit_recovers_original_delivery(entry, connect, monkeypatch):
    email, operation = uuid4().hex + "@entry.fixture.invalid", uuid4()
    original, commits = psycopg.Connection.commit, [0]

    def lost(conn):
        active = conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE
        original(conn)
        commits[0] += int(active)
        if active and commits[0] == 2:
            raise psycopg.OperationalError("injected lost registration reply")

    with monkeypatch.context() as patch:
        patch.setattr(psycopg.Connection, "commit", lost)
        with pytest.raises(UnknownCommit):
            entry.register(operation, email, PASSWORD, "연구자", "fixture-flow")
    before = mailbox(entry, connect, email)
    entry.register(operation, email, PASSWORD, "연구자", "fixture-flow")
    assert mailbox(entry, connect, email) == before


def test_concurrent_proof_consumption_has_one_winner(entry, connect):
    _, _, _, mail = registered(entry, connect)

    def consume():
        try:
            entry.verify_email(
                UUID(mail["challengeId"]), mail["proof"], mail["flowBinding"], operation=uuid4()
            )
            return "accepted"
        except PermissionError:
            return "denied"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: consume(), range(2)))
    assert sorted(outcomes) == ["accepted", "denied"]


def test_unverified_wrong_password_and_absent_session_cannot_authenticate(entry, connect):
    email, _, _, _ = registered(entry, connect)
    for candidate, password in (
        (email, PASSWORD),
        (email, "Wrong!Password2"),
        ("absent@entry.fixture.invalid", PASSWORD),
    ):
        with pytest.raises(PermissionError, match="credentials unavailable"):
            entry.login(candidate, password)
    with pytest.raises(PermissionError, match="session unavailable"):
        entry.authenticate("unknown")


def test_entry_allocation_is_finite_before_expensive_work(entry):
    for _ in range(20):
        entry._admit()
    with pytest.raises(Busy, match="attempt allocation"):
        entry.login("absent@entry.fixture.invalid", PASSWORD)


def test_full_account_allocation_has_same_existing_and_new_disposition(entry, connect):
    email, operation, original, _ = registered(entry, connect)
    registered(entry, connect)
    for candidate in (email, "new@entry.fixture.invalid"):
        with pytest.raises(Busy, match="local account allocation exhausted"):
            entry.register(uuid4(), candidate, PASSWORD, "연구자", "fixture-flow")
    assert entry.register(operation, email, PASSWORD, "연구자", "fixture-flow") == original


def test_fresh_service_bootstrap_recovers_csrf_without_rotating_or_exposing_cookie(entry, connect):
    email = verified(entry, connect)
    issued = entry.login(email, PASSWORD)
    fresh = GuardedEntryService(entry.transactions)
    restored = fresh.inspect_session(issued.token)
    assert restored.csrf == issued.csrf
    assert restored.public["session"]["sessionId"] == issued.public["session"]["sessionId"]
    assert issued.token not in json.dumps(restored.public)
    assert fresh.authenticate(issued.token, csrf=issued.csrf)
    assert fresh.inspect_session(issued.token).csrf == restored.csrf
    fresh.logout(fresh.authenticate(issued.token))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        fresh.inspect_session(issued.token)


def test_bootstrap_rejects_changed_persisted_csrf_and_cross_session_token(entry, connect):
    email = verified(entry, connect)
    first = entry.login(email, PASSWORD)
    second = entry.login(email, PASSWORD)
    with pytest.raises(PermissionError):
        entry.authenticate(second.token, csrf=first.csrf)
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.session SET csrf_hash=%s WHERE id=%s",
            (
                entry.verifier("csrf", "old-random-policy"),
                UUID(second.public["session"]["sessionId"]),
            ),
        )
    with pytest.raises(PermissionError, match="session unavailable"):
        entry.inspect_session(second.token)


def test_login_replay_binds_flow_and_recovers_one_session_after_lost_reply(
    entry, connect, monkeypatch
):
    email = verified(entry, connect)
    operation = uuid4()
    original, commits = psycopg.Connection.commit, [0]

    def lost(conn):
        active = conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE
        original(conn)
        commits[0] += int(active)
        # Admission, observed credential read, then durable session/receipt.
        if active and commits[0] == 3:
            raise psycopg.OperationalError("injected lost login reply")

    with monkeypatch.context() as patch:
        patch.setattr(psycopg.Connection, "commit", lost)
        with pytest.raises(UnknownCommit):
            entry.login(email, PASSWORD, operation=operation, flow_binding="browser-a")
    recovered = entry.login(email, PASSWORD, operation=operation, flow_binding="browser-a")
    repeated = entry.login(email, PASSWORD, operation=operation, flow_binding="browser-a")
    assert repeated == recovered
    assert entry.authenticate(recovered.token, csrf=recovered.csrf)
    with connect("accounts") as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM accounts.session WHERE account_id=%s",
                (UUID(recovered.public["session"]["accountId"]),),
            ).fetchone()[0]
            == 1
        )
        receipt = conn.execute(
            "SELECT outcome::text FROM accounts.entry_receipt WHERE operation_id=%s", (operation,)
        ).fetchone()[0]
    assert PASSWORD not in receipt and recovered.token not in receipt
    with pytest.raises(ValueError, match="conflict"):
        entry.login(email, PASSWORD, operation=operation, flow_binding="browser-b")
    entry.logout(entry.authenticate(recovered.token))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        entry.login(email, PASSWORD, operation=operation, flow_binding="browser-a")


def test_verified_and_logout_acknowledgements_are_owner_bound(entry, connect):
    from docsuri_shared.workspace import wire

    _, _, _, mail = registered(entry, connect)
    operation = uuid4()
    acknowledgement = entry.verify_email(
        UUID(mail["challengeId"]), mail["proof"], mail["flowBinding"], operation=operation
    )
    wire.Ack.model_validate(acknowledgement)
    assert (
        entry.verify_email(
            UUID(mail["challengeId"]), mail["proof"], mail["flowBinding"], operation=operation
        )
        == acknowledgement
    )
    login = entry.login(mail["email"], PASSWORD)
    authority = entry.authenticate(login.token)
    result = entry.logout(authority, operation=uuid4())
    wire.Ack.model_validate(result)
    assert result["resourceId"] == login.public["session"]["sessionId"]
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        entry.logout(authority)
