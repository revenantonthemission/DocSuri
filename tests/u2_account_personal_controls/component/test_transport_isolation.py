from uuid import uuid4

import pytest

from backend.modules.accounts.control_cursor import ControlCursor
from backend.modules.accounts.control_policy import SYNTHETIC_POLICY, PolicyUnavailable

PASSWORD = 'Synthetic!Research2026'
pytestmark = pytest.mark.u2_component


def test_wrong_csrf_cannot_authenticate(entry):
    session = entry.login('u2-a@fixture.invalid', PASSWORD)
    with pytest.raises(PermissionError):
        entry.authenticate(session.token, csrf='wrong-csrf')


def test_revoked_cookie_cannot_bootstrap(entry, connect):
    session = entry.login('u2-a@fixture.invalid', PASSWORD)
    with connect('accounts') as conn:
        conn.execute("UPDATE accounts.session SET revoked=true WHERE token_hash=%s", (entry.verifier('session', session.token),))
    with pytest.raises(PermissionError):
        entry.inspect_session(session.token)


def test_secret_ciphertext_bound_to_exact_purpose(entry):
    encrypted = entry.protect('enrollment-one', {'seed': 'private-test-material'})
    assert b'private-test-material' not in encrypted
    with pytest.raises(Exception):
        entry.reveal('different-enrollment', encrypted)


def test_corrupt_protected_value_does_not_decrypt(entry):
    encrypted = entry.protect('control', {'value': 'private'})
    with pytest.raises(Exception):
        entry.reveal('control', encrypted[:-1]+bytes([encrypted[-1]^1]))


def test_cursor_owner_cannot_be_replaced():
    codec = ControlCursor(b't'*32)
    token = codec.encode(uuid4(), 'history', {'id':'one'})
    with pytest.raises(ValueError):
        codec.decode(uuid4(), 'history', token)


def test_cursor_tampering_rejected():
    codec, owner = ControlCursor(b't'*32), uuid4()
    token = codec.encode(owner, 'history', {'id':'one'})
    with pytest.raises(ValueError):
        codec.decode(owner, 'history', ('A' if token[0] != 'A' else 'B')+token[1:])


def test_cursor_expiry_requires_fresh_read(monkeypatch):
    codec, owner = ControlCursor(b't'*32), uuid4()
    monkeypatch.setattr('backend.modules.accounts.control_cursor.time.time', lambda: 1000)
    token = codec.encode(owner, 'history', {'id':'one'})
    monkeypatch.setattr('backend.modules.accounts.control_cursor.time.time', lambda: 1400)
    with pytest.raises(ValueError):
        codec.decode(owner, 'history', token)


def test_synthetic_policy_cannot_activate_public_realm():
    with pytest.raises(PolicyUnavailable):
        SYNTHETIC_POLICY.require_realm('production')
