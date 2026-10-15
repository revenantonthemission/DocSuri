from uuid import UUID, uuid4

import pytest

PASSWORD = 'Synthetic!Research2026'
NEW_PASSWORD = 'Changed!Research2026'
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
