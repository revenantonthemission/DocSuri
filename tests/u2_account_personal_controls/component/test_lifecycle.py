from uuid import UUID, uuid4

import pytest

from backend.modules.accounts.control_repository import ControlRepository
from backend.modules.accounts.services.control_lifecycle import ControlLifecycleService

PASSWORD = 'Synthetic!Research2026'
pytestmark = pytest.mark.u2_component


def lifecycle(entry):
    return ControlLifecycleService(entry, (('Library','references'), ('ServiceOperations','restore')), revision='test-u2-manifest')


def request(service, authority):
    value = ControlRepository(service.transactions, service.entry.control_policy).profile(authority)
    return service.request(authority, uuid4(), UUID(value['lifecycleRevision']), 'withdraw', PASSWORD)


def test_withdraw_revokes_access_before_cleanup(entry, authority):
    service = lifecycle(entry)
    result = request(service, authority)
    assert result['accessRevoked'] and result['disposition'] == 'pending'
    with pytest.raises(Exception):
        ControlRepository(service.transactions, service.entry.control_policy).profile(authority)


def test_one_scope_cannot_complete_manifest(entry, authority):
    service = lifecycle(entry)
    result = request(service, authority)
    ticket = service.claim(UUID(result['requestId']), 'Library', 'references')
    outcome = service.acknowledge(ticket, evidence=uuid4(), reason='test-reference-suppression')
    assert outcome['disposition'] == 'pending'


def test_missing_restore_evidence_is_blocked(entry, authority):
    service = lifecycle(entry)
    result = request(service, authority)
    ticket = service.claim(UUID(result['requestId']), 'ServiceOperations', 'restore')
    assert service.acknowledge(ticket, evidence=None, reason='restore-not-demonstrated')['disposition'] == 'blocked'


def test_stale_ticket_rejected(entry, authority):
    service = lifecycle(entry)
    result = request(service, authority)
    ticket = service.claim(UUID(result['requestId']), 'Library', 'references')
    ticket['generation'] += 1
    with pytest.raises(ValueError, match='stale'):
        service.acknowledge(ticket, evidence=uuid4(), reason='stale')


def test_wrong_participant_cannot_claim(entry, authority):
    service = lifecycle(entry)
    result = request(service, authority)
    with pytest.raises(PermissionError):
        service.claim(UUID(result['requestId']), 'Uninstalled', 'all-data')


def test_restore_cannot_undo_current_withdrawal(entry, authority, identities):
    service = lifecycle(entry)
    result = request(service, authority)
    assert service.evaluate_restore(identities['a'], UUID(result['revision']))['decision'] == 'deny'


def test_all_scope_evidence_required_for_completion(entry, authority):
    service = lifecycle(entry)
    result = request(service, authority)
    for participant, scope in service.manifest:
        ticket = service.claim(UUID(result['requestId']), participant, scope)
        outcome = service.acknowledge(ticket, evidence=uuid4(), reason='synthetic-participant-test')
    assert outcome['disposition'] == 'complete'


def test_erased_identity_gets_no_reactivation_proof(entry, authority, connect, identities):
    with connect('accounts') as conn:
        conn.execute("UPDATE accounts.account SET lifecycle_state='erased',active=false WHERE id=%s", (identities['a'],))
    flow = str(uuid4())
    entry.request_reactivation(uuid4(), 'u2-a@fixture.invalid', flow)
    with connect('accounts') as conn:
        assert conn.execute("SELECT count(*) AS n FROM accounts.control_proof WHERE flow_hash=%s AND purpose='reactivate'", (entry.verifier('flow', flow),)).fetchone()['n'] == 0


def test_confirmation_binds_action_and_preserves_original_expiry(entry, authority):
    service = lifecycle(entry)
    profile = ControlRepository(service.transactions, entry.control_policy).profile(authority)
    revision, operation = UUID(profile['lifecycleRevision']), uuid4()
    confirmation = service.prepare_confirmation(authority, operation, revision, 'withdraw', PASSWORD)
    assert service.prepare_confirmation(authority, operation, revision, 'withdraw', PASSWORD) == confirmation
    with pytest.raises(PermissionError):
        service.request_confirmed(authority, uuid4(), UUID(confirmation['confirmationRef']), 'erase')
    result = service.request_confirmed(authority, uuid4(), UUID(confirmation['confirmationRef']), 'withdraw')
    assert result['accessRevoked']


def test_confirmation_cannot_cross_session(entry, authority, connect, identities):
    service = lifecycle(entry)
    profile = ControlRepository(service.transactions, entry.control_policy).profile(authority)
    confirmation = service.prepare_confirmation(authority, uuid4(), UUID(profile['lifecycleRevision']), 'withdraw', PASSWORD)
    from backend.transactions import Authority
    other = Authority(identities['b'], uuid4())
    with pytest.raises(PermissionError):
        service.request_confirmed(other, uuid4(), UUID(confirmation['confirmationRef']), 'withdraw')
