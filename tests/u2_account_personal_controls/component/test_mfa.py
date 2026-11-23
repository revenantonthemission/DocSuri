import time
from uuid import UUID, uuid4

import pytest

from backend.modules.accounts.control_policy import PolicyUnavailable
from backend.modules.accounts.services.control_mfa import ControlMfaService, totp

PASSWORD = 'Synthetic!Research2026'
pytestmark = pytest.mark.u2_component


def enroll(entry, authority):
    service = ControlMfaService(entry)
    started = service.begin(authority, PASSWORD, uuid4())
    material = service.material(authority, UUID(started['enrollmentId']), started['deliveryReference'])
    return service, started, material


def test_totp_matches_rfc6238_six_digit_projection():
    assert totp('GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ', 1) == '287082'


def test_mfa_begin_returns_no_seed_or_codes(entry, authority):
    value = ControlMfaService(entry).begin(authority, PASSWORD, uuid4())
    assert set(value) == {'enrollmentId', 'deliveryReference', 'expiresAt', 'nextAction'}


def test_material_is_single_delivery(entry, authority):
    service, started, material = enroll(entry, authority)
    assert len(material['recoveryCodes']) == 8
    with pytest.raises(PermissionError):
        service.material(authority, UUID(started['enrollmentId']), started['deliveryReference'])


def test_material_missing_delivery_denied(entry, authority):
    service = ControlMfaService(entry)
    started = service.begin(authority, PASSWORD, uuid4())
    with pytest.raises(PermissionError):
        service.material(authority, UUID(started['enrollmentId']), str(uuid4()))


def test_mfa_new_enrollment_invalidates_lost_material(entry, authority):
    service = ControlMfaService(entry)
    first = service.begin(authority, PASSWORD, uuid4())
    service.begin(authority, PASSWORD, uuid4())
    with pytest.raises(PermissionError):
        service.material(authority, UUID(first['enrollmentId']), first['deliveryReference'])


def test_primary_mfa_continuation_cannot_access_private_owner(entry, authority):
    service, started, material = enroll(entry, authority)
    service.confirm(authority, UUID(started['enrollmentId']), totp(material['seed'], int(time.time())//30-1), uuid4())
    session = entry.login('u2-a@fixture.invalid', PASSWORD)
    assert session.public['state'] == 'mfa_required'
    with pytest.raises(PermissionError):
        entry.authenticate(session.token)
    completed = service.verify(session.token, session.csrf, UUID(session.public['challengeId']), UUID(session.public['flowBinding']), totp(material['seed'], int(time.time())//30))
    assert completed.public['session']['authenticationLevel'] == 'mfa'


def test_bad_confirmation_factor_keeps_inactive(entry, authority):
    service, started, _ = enroll(entry, authority)
    with pytest.raises(PermissionError):
        service.confirm(authority, UUID(started['enrollmentId']), 'not-a-factor', uuid4())


def test_recovery_policy_never_bypasses_admin(entry):
    service = ControlMfaService(entry)
    for _ in range(3):
        with pytest.raises(PolicyUnavailable):
            service.recover()
    with pytest.raises(PolicyUnavailable):
        service.recover(entry, uuid4(), "administrator")


def current_step():
    return int(time.time()) // 30


def test_begin_replays_its_enrollment(entry, authority):
    service, operation = ControlMfaService(entry), uuid4()
    first = service.begin(authority, PASSWORD, operation)
    assert service.begin(authority, PASSWORD, operation) == first


def test_active_factor_requires_controlled_replacement(entry, authority):
    service, started, material = enroll(entry, authority)
    service.confirm(authority, UUID(started['enrollmentId']), totp(material['seed'], current_step()), uuid4())
    with pytest.raises(ValueError, match='controlled replacement'):
        service.begin(authority, PASSWORD, uuid4())


def test_code_outside_the_drift_window_keeps_the_factor_inactive(entry, authority, connect):
    service, started, material = enroll(entry, authority)
    with pytest.raises(PermissionError, match='factor unavailable'):
        service.confirm(authority, UUID(started['enrollmentId']), totp(material['seed'], current_step() + 10), uuid4())
    with connect('accounts') as conn:
        assert conn.execute("SELECT state FROM accounts.mfa_enrollment WHERE id=%s",
                            (UUID(started['enrollmentId']),)).fetchone()['state'] == 'inactive'


def test_confirmation_replays_and_refuses_unknown_enrollments(entry, authority):
    service, started, material = enroll(entry, authority)
    operation, code = uuid4(), totp(material['seed'], current_step())
    first = service.confirm(authority, UUID(started['enrollmentId']), code, operation)
    assert service.confirm(authority, UUID(started['enrollmentId']), code, operation) == first
    with pytest.raises(PermissionError, match='enrollment unavailable'):
        service.confirm(authority, uuid4(), code, uuid4())


def test_full_session_cannot_be_used_as_a_second_factor_continuation(entry):
    session = entry.login('u2-a@fixture.invalid', PASSWORD)
    assert session.public['state'] == 'authenticated'
    with pytest.raises(PermissionError, match='primary continuation required'):
        ControlMfaService(entry).verify(session.token, session.csrf, uuid4(), uuid4(), '000000')


def test_continuation_without_an_active_factor_issues_no_session(entry, authority, connect):
    service, started, material = enroll(entry, authority)
    service.confirm(authority, UUID(started['enrollmentId']), totp(material['seed'], current_step() - 1), uuid4())
    session = entry.login('u2-a@fixture.invalid', PASSWORD)
    assert session.public['state'] == 'mfa_required'
    with connect('accounts') as conn:
        conn.execute("UPDATE accounts.mfa_enrollment SET state='invalidated' WHERE id=%s",
                     (UUID(started['enrollmentId']),))
    with pytest.raises(PermissionError, match='factor unavailable'):
        service.verify(session.token, session.csrf, UUID(session.public['challengeId']),
                       UUID(session.public['flowBinding']), totp(material['seed'], current_step()))
    assert entry.inspect_session(session.token).public['state'] == 'mfa_required'
