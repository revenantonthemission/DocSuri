from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from backend.modules.accounts.control_policy import SYNTHETIC_POLICY, PolicyUnavailable
from backend.modules.accounts.services.control_entry import ControlEntryService

PASSWORD = 'Synthetic!Research2026'
NEW_PASSWORD = 'Changed!Research2026'
# Passes the password rules but is longer than the policy's 1,024 bytes.
OVERSIZED_PASSWORD = 'Aa1!' * 257
pytestmark = pytest.mark.u2_component


def reset_proof(entry, mailbox):
    flow = str(uuid4())
    entry.request_password_reset(uuid4(), 'u2-a@fixture.invalid', flow)
    return next(item for item in mailbox('password-reset') if item['flowBinding'] == flow)


def test_normal_login_recovers_current_session(entry):
    session = entry.login('u2-a@fixture.invalid', PASSWORD)
    assert session.public['state'] == 'authenticated'
    assert entry.inspect_session(session.token).public == session.public


def test_wrong_password_does_not_issue_session(entry):
    with pytest.raises(PermissionError):
        entry.login('u2-a@fixture.invalid', 'Wrong!Password')


def test_neutral_reset_request_has_same_shape_for_absence(entry):
    known = entry.request_password_reset(uuid4(), 'u2-a@fixture.invalid', 'known')
    missing = entry.request_password_reset(uuid4(), 'missing@fixture.invalid', 'missing')
    assert {k: v for k, v in known.items() if k != 'requestId'} == {k: v for k, v in missing.items() if k != 'requestId'}


def test_reset_replaces_password_revokes_sessions_and_reconciles(entry, mailbox):
    session = entry.login('u2-a@fixture.invalid', PASSWORD)
    proof = reset_proof(entry, mailbox)
    operation = uuid4()
    args = (operation, UUID(proof['challengeId']), proof['proof'], proof['flowBinding'], NEW_PASSWORD)
    result = entry.complete_password_reset(*args)
    assert entry.complete_password_reset(*args) == result
    with pytest.raises(PermissionError):
        entry.inspect_session(session.token)
    assert entry.login('u2-a@fixture.invalid', NEW_PASSWORD).public['state'] == 'authenticated'


def test_wrong_flow_cannot_consume_reset(entry, mailbox):
    proof = reset_proof(entry, mailbox)
    with pytest.raises(PermissionError):
        entry.complete_password_reset(uuid4(), UUID(proof['challengeId']), proof['proof'], 'other-flow', NEW_PASSWORD)


def test_consumed_reset_cannot_apply_new_operation(entry, mailbox):
    proof = reset_proof(entry, mailbox)
    args = (UUID(proof['challengeId']), proof['proof'], proof['flowBinding'], NEW_PASSWORD)
    entry.complete_password_reset(uuid4(), *args)
    with pytest.raises(PermissionError):
        entry.complete_password_reset(uuid4(), *args)


def test_expired_reset_rejected(entry, mailbox, connect):
    proof = reset_proof(entry, mailbox)
    with connect('accounts') as conn:
        conn.execute("UPDATE accounts.control_proof SET expires_at=clock_timestamp()-interval '1 second' WHERE id=%s", (UUID(proof['challengeId']),))
    with pytest.raises(PermissionError):
        entry.complete_password_reset(uuid4(), UUID(proof['challengeId']), proof['proof'], proof['flowBinding'], NEW_PASSWORD)


def test_email_changes_only_after_verified_replacement(entry, authority, mailbox):
    flow = str(uuid4())
    email = 'new-'+uuid4().hex+'@fixture.invalid'
    entry.request_email_change(authority, uuid4(), PASSWORD, email, flow)
    assert entry.login('u2-a@fixture.invalid', PASSWORD).public['state'] == 'authenticated'
    proof = next(item for item in mailbox('email-change') if item['flowBinding'] == flow)
    entry.complete_email_change(authority, uuid4(), UUID(proof['challengeId']), proof['proof'], flow)
    assert entry.login(email, PASSWORD).public['state'] == 'authenticated'


def test_entry_without_verifier_custody_refuses_while_accounts_exist(entry, transactions, tmp_path):
    detached = SimpleNamespace(
        profile=SimpleNamespace(realm=transactions.profile.realm, root=tmp_path),
        run=transactions.run,
    )
    with pytest.raises(PolicyUnavailable, match='retained verifier custody'):
        ControlEntryService(detached, SYNTHETIC_POLICY)
    assert not any(tmp_path.iterdir())


def test_login_replay_returns_its_session_and_refuses_a_changed_intent(entry):
    operation = uuid4()
    first = entry.login('u2-a@fixture.invalid', PASSWORD, operation=operation)
    again = entry.login('u2-a@fixture.invalid', PASSWORD, operation=operation)
    assert again.token == first.token and again.public == first.public
    with pytest.raises(ValueError, match='login operation conflict'):
        entry.login('u2-a@fixture.invalid', PASSWORD, operation=operation, flow_binding='other')
    assert entry.inspect_session(first.token).public == first.public


def test_login_replay_after_its_session_was_revoked_issues_nothing(entry, connect):
    operation = uuid4()
    first = entry.login('u2-a@fixture.invalid', PASSWORD, operation=operation)
    with connect('accounts') as conn:
        conn.execute("UPDATE accounts.session SET revoked=true WHERE token_hash=%s",
                     (entry.verifier('session', first.token),))
    with pytest.raises(PermissionError, match='session unavailable'):
        entry.login('u2-a@fixture.invalid', PASSWORD, operation=operation)
    with pytest.raises(PermissionError):
        entry.inspect_session(first.token)


def test_administrator_without_a_factor_gets_no_session(entry, connect, identities):
    with connect('accounts') as conn:
        conn.execute("UPDATE accounts.account SET role='administrator' WHERE id=%s", (identities['a'],))
        before = conn.execute(
            "SELECT count(*) AS n FROM accounts.session WHERE account_id=%s", (identities['a'],)
        ).fetchone()['n']
    try:
        with pytest.raises(PermissionError, match='factor enrollment required'):
            entry.login('u2-a@fixture.invalid', PASSWORD)
        with connect('accounts') as conn:
            after = conn.execute(
                "SELECT count(*) AS n FROM accounts.session WHERE account_id=%s", (identities['a'],)
            ).fetchone()['n']
        assert after == before
    finally:
        with connect('accounts') as conn:
            conn.execute("UPDATE accounts.account SET role='member' WHERE id=%s", (identities['a'],))


def test_reset_request_replays_its_acknowledgement_and_refuses_another_flow(entry):
    operation = uuid4()
    first = entry.request_password_reset(operation, 'u2-a@fixture.invalid', 'replay-flow')
    assert entry.request_password_reset(operation, 'u2-a@fixture.invalid', 'replay-flow') == first
    with pytest.raises(ValueError, match='reset request conflict'):
        entry.request_password_reset(operation, 'u2-a@fixture.invalid', 'another-flow')


def test_reset_refuses_a_password_beyond_the_policy_bytes(entry, mailbox):
    proof = reset_proof(entry, mailbox)
    with pytest.raises(ValueError, match='outside policy'):
        entry.complete_password_reset(
            uuid4(), UUID(proof['challengeId']), proof['proof'], proof['flowBinding'],
            OVERSIZED_PASSWORD,
        )
    assert entry.login('u2-a@fixture.invalid', PASSWORD).public['state'] == 'authenticated'


def test_reset_with_a_never_issued_challenge_is_refused(entry):
    with pytest.raises(PermissionError, match='proof unavailable'):
        entry.complete_password_reset(uuid4(), uuid4(), 'never-issued', 'flow', NEW_PASSWORD)
    assert entry.login('u2-a@fixture.invalid', PASSWORD).public['state'] == 'authenticated'


def test_reset_replay_with_another_password_is_refused(entry, mailbox):
    proof = reset_proof(entry, mailbox)
    operation = uuid4()
    args = (UUID(proof['challengeId']), proof['proof'], proof['flowBinding'])
    entry.complete_password_reset(operation, *args, NEW_PASSWORD)
    with pytest.raises(PermissionError, match='proof unavailable'):
        entry.complete_password_reset(operation, *args, 'Another!Research2026')
    assert entry.login('u2-a@fixture.invalid', NEW_PASSWORD).public['state'] == 'authenticated'


def test_password_change_refuses_a_password_beyond_the_policy_bytes(entry, authority):
    with pytest.raises(ValueError, match='outside policy'):
        entry.change_password(authority, uuid4(), PASSWORD, OVERSIZED_PASSWORD)
    assert entry.login('u2-a@fixture.invalid', PASSWORD).public['state'] == 'authenticated'


def test_credential_reconciliation_refuses_unknown_kinds_and_cookies(entry):
    with pytest.raises(PermissionError, match='receipt unavailable'):
        entry.reconcile_credential_change('cookie', 'csrf', uuid4(), 'profile-change', [])
    with pytest.raises(PermissionError, match='receipt unavailable'):
        entry.reconcile_credential_change(
            'never-issued-cookie', 'csrf', uuid4(), 'password-change', [PASSWORD, NEW_PASSWORD]
        )


def test_email_request_replays_and_refuses_another_address(entry, authority):
    operation, flow = uuid4(), str(uuid4())
    email = 'replay-' + uuid4().hex + '@fixture.invalid'
    first = entry.request_email_change(authority, operation, PASSWORD, email, flow)
    assert entry.request_email_change(authority, operation, PASSWORD, email, flow) == first
    with pytest.raises(ValueError, match='email request conflict'):
        entry.request_email_change(
            authority, operation, PASSWORD, 'other-' + uuid4().hex + '@fixture.invalid', flow
        )


def test_email_completion_with_a_wrong_proof_keeps_the_address(entry, authority, mailbox):
    flow, email = str(uuid4()), 'wrong-proof-' + uuid4().hex + '@fixture.invalid'
    entry.request_email_change(authority, uuid4(), PASSWORD, email, flow)
    proof = next(item for item in mailbox('email-change') if item['flowBinding'] == flow)
    with pytest.raises(PermissionError, match='email proof unavailable'):
        entry.complete_email_change(authority, uuid4(), UUID(proof['challengeId']), 'wrong', flow)
    assert entry.login('u2-a@fixture.invalid', PASSWORD).public['state'] == 'authenticated'


def test_email_completion_refuses_an_address_another_account_took(
    entry, authority, mailbox, connect, identities
):
    flow, email = str(uuid4()), 'taken-' + uuid4().hex + '@fixture.invalid'
    entry.request_email_change(authority, uuid4(), PASSWORD, email, flow)
    proof = next(item for item in mailbox('email-change') if item['flowBinding'] == flow)
    with connect('accounts') as conn:
        previous = conn.execute(
            "SELECT email FROM accounts.account WHERE id=%s", (identities['b'],)
        ).fetchone()['email']
        conn.execute("UPDATE accounts.account SET email=%s WHERE id=%s", (email, identities['b']))
    try:
        with pytest.raises(PermissionError, match='replacement unavailable'):
            entry.complete_email_change(
                authority, uuid4(), UUID(proof['challengeId']), proof['proof'], flow
            )
    finally:
        with connect('accounts') as conn:
            conn.execute(
                "UPDATE accounts.account SET email=%s WHERE id=%s", (previous, identities['b'])
            )
    assert entry.login('u2-a@fixture.invalid', PASSWORD).public['state'] == 'authenticated'


def test_reactivation_request_replays_and_refuses_another_flow(entry):
    operation = uuid4()
    first = entry.request_reactivation(operation, 'u2-a@fixture.invalid', 'replay-flow')
    assert entry.request_reactivation(operation, 'u2-a@fixture.invalid', 'replay-flow') == first
    with pytest.raises(ValueError, match='reactivation request conflict'):
        entry.request_reactivation(operation, 'u2-a@fixture.invalid', 'another-flow')
