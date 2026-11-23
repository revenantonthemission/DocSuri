import base64
import dataclasses
import hmac
from uuid import uuid4

import pytest

from backend.modules.accounts.control_confirmation import ResetConfirmationService
from backend.modules.accounts.control_cursor import ControlCursor
from backend.modules.accounts.control_policy import (
    SYNTHETIC_POLICY,
    PolicyUnavailable,
    for_realm,
    public_evidence,
)

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


def test_policy_refuses_another_identity_and_unbounded_values():
    with pytest.raises(PolicyUnavailable):
        dataclasses.replace(SYNTHETIC_POLICY, policy_id='public-v1')
    with pytest.raises(ValueError, match='max_accounts'):
        dataclasses.replace(SYNTHETIC_POLICY, max_accounts=21)
    with pytest.raises(ValueError, match='max_page_size'):
        dataclasses.replace(SYNTHETIC_POLICY, max_page_size=True)


def test_policy_refuses_inconsistent_deadlines():
    with pytest.raises(ValueError, match='attempt deadline'):
        dataclasses.replace(SYNTHETIC_POLICY, lease_seconds=10, attempt_seconds=10)
    with pytest.raises(ValueError, match='material delivery'):
        dataclasses.replace(SYNTHETIC_POLICY, proof_seconds=30, material_seconds=60)


def test_realm_policy_selection_keeps_u2_policy_only_in_its_realm():
    assert for_realm('account-controls') is SYNTHETIC_POLICY
    assert for_realm('paper-journey') is None
    for realm in ('service-operations', 'production'):
        selected = for_realm(realm)
        assert selected is not None and selected is not SYNTHETIC_POLICY
        assert selected.reference != SYNTHETIC_POLICY.reference


def test_public_evidence_names_only_unresolved_gates():
    evidence = public_evidence()
    assert set(evidence) >= {'credentials', 'google', 'orcid', 'email', 'lifecycle'}
    assert all(value.startswith('G') and value.endswith('-unresolved') for value in evidence.values())


def test_cursor_requires_a_full_key_and_bounded_lifetime():
    with pytest.raises(ValueError, match='finite cursor'):
        ControlCursor(b'k' * 16)
    with pytest.raises(ValueError, match='finite cursor'):
        ControlCursor(b'k' * 32, lifetime=301)


def test_cursor_refuses_oversized_state_and_non_text_tokens():
    codec, owner = ControlCursor(b't' * 32), uuid4()
    with pytest.raises(ValueError, match='exceeds policy'):
        codec.encode(owner, 'history', {'id': 'x' * 3000})
    with pytest.raises(ValueError, match='invalid cursor'):
        codec.decode(owner, 'history', 12345)
    with pytest.raises(ValueError, match='invalid cursor'):
        codec.decode(owner, 'history', 'A' * 4097)


def test_cursor_signed_but_malformed_body_is_invalid():
    key, owner = b't' * 32, uuid4()
    raw = b'not-a-json-cursor'
    token = base64.urlsafe_b64encode(raw + hmac.digest(key, raw, 'sha256')).decode()
    with pytest.raises(ValueError, match='invalid cursor'):
        ControlCursor(key).decode(owner, 'history', token)


def test_protected_envelope_with_invalid_version_length_is_refused(entry):
    with pytest.raises(ValueError, match='envelope'):
        entry.reveal('control', b'DSC2' + bytes([0]) + b'x' * 20)


def test_never_issued_cookie_has_no_session(entry):
    with pytest.raises(PermissionError, match='session unavailable'):
        entry.inspect_session('never-issued-synthetic-cookie')


def test_reset_confirmation_refuses_unknown_action_before_reauthentication(entry, transactions, authority):
    service = ResetConfirmationService(transactions, SYNTHETIC_POLICY, entry)
    with pytest.raises(ValueError, match='invalid reset action'):
        service.prepare(authority, uuid4(), action='erase', expected=uuid4(), proof='wrong')


def test_reset_confirmation_replays_and_refuses_a_changed_intent(entry, transactions, authority):
    service = ResetConfirmationService(transactions, SYNTHETIC_POLICY, entry)
    operation, expected = uuid4(), uuid4()
    first = service.prepare(
        authority, operation, action='delete_behavior', expected=expected, proof=PASSWORD
    )
    assert service.prepare(
        authority, operation, action='delete_behavior', expected=expected, proof=PASSWORD
    ) == first
    with pytest.raises(ValueError, match='confirmation operation conflict'):
        service.prepare(
            authority, operation, action='reset_profile', expected=expected, proof=PASSWORD
        )
