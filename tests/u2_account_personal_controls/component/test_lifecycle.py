from uuid import UUID, uuid4

import pytest

from backend.modules.accounts.control_repository import ControlRepository
from backend.modules.accounts.services.control_lifecycle import ControlLifecycleService
from backend.transactions import Authority

PASSWORD = 'Synthetic!Research2026'
pytestmark = pytest.mark.u2_component


@pytest.fixture
def authority(isolated_authority):
    """Lifecycle requests must not accumulate on the shared fixture owner."""
    return isolated_authority


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


def test_restore_cannot_undo_current_withdrawal(entry, authority):
    service = lifecycle(entry)
    result = request(service, authority)
    # Evaluate the owner this case withdrew (the isolated authority), not the shared fixture owner.
    assert service.evaluate_restore(authority.account_id, UUID(result['revision']))['decision'] == 'deny'


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


def test_withdrawn_owner_reactivates_with_one_time_proof(entry, authority, connect, mailbox):
    """Reactivation needs the verified owner proof; scoped completion revives access."""
    manifest = (('Library', 'references'),)
    withdraw = ControlLifecycleService(entry, manifest, revision='reactivate-test')
    request(withdraw, authority)
    with connect('accounts') as conn:
        row = conn.execute(
            "SELECT email,lifecycle_state,active FROM accounts.account WHERE id=%s",
            (authority.account_id,),
        ).fetchone()
    assert row['lifecycle_state'] == 'withdrawn' and not row['active']

    flow = str(uuid4())
    operation = uuid4()
    entry.request_reactivation(operation, row['email'], flow)
    values = [value for value in mailbox('reactivate') if value.get('flowBinding') == flow]
    assert len(values) == 1
    proof = values[0]
    result = withdraw.reactivate(
        uuid4(), UUID(proof['challengeId']), proof['proof'], proof['flowBinding']
    )
    assert result['disposition'] == 'reactivation_pending'
    # The exact proof is single-use: the same verification cannot reactivate twice.
    with pytest.raises(PermissionError):
        withdraw.reactivate(
            uuid4(), UUID(proof['challengeId']), proof['proof'], proof['flowBinding']
        )

    service = ControlLifecycleService(entry, manifest, revision='reactivate-test')
    ticket = service.claim(UUID(result['requestId']), 'Library', 'references')
    service.acknowledge(ticket, evidence=uuid4(), reason='reactivation-reference-check')
    with connect('accounts') as conn:
        revived = conn.execute(
            "SELECT lifecycle_state,active FROM accounts.account WHERE id=%s",
            (authority.account_id,),
        ).fetchone()
    assert revived == {'lifecycle_state': 'active', 'active': True}


def lifecycle_revision(entry, authority):
    profile = ControlRepository(entry.transactions, entry.control_policy).profile(authority)
    return UUID(profile['lifecycleRevision'])


def account_state(connect, authority):
    with connect('accounts') as conn:
        return conn.execute(
            "SELECT lifecycle_state,active FROM accounts.account WHERE id=%s",
            (authority.account_id,),
        ).fetchone()


def reactivation_proof(entry, authority, connect, mailbox):
    flow = str(uuid4())
    email = str(authority.account_id) + '@fixture.invalid'
    entry.request_reactivation(uuid4(), email, flow)
    return next(value for value in mailbox('reactivate') if value.get('flowBinding') == flow)


@pytest.mark.parametrize(
    'manifest,revision',
    [
        ((), 'empty-manifest'),
        ((('Library', 'references'), ('Library', 'references')), 'duplicate-manifest'),
        ((('Library', 'references'),), ''),
    ],
)
def test_lifecycle_requires_a_complete_unique_manifest(entry, manifest, revision):
    with pytest.raises(ValueError, match='lifecycle manifest required'):
        ControlLifecycleService(entry, manifest, revision=revision)


def test_request_refuses_unknown_actions_and_missing_reauthentication(entry, authority, connect):
    service = lifecycle(entry)
    expected = lifecycle_revision(entry, authority)
    with pytest.raises(ValueError, match='unsupported lifecycle action'):
        service.request(authority, uuid4(), expected, 'suspend', PASSWORD)
    with pytest.raises(PermissionError, match='recent reauthentication required'):
        service.request(authority, uuid4(), expected, 'withdraw', None)
    assert account_state(connect, authority) == {'lifecycle_state': 'active', 'active': True}


def test_request_with_a_stale_revision_keeps_access(entry, authority, connect):
    service = lifecycle(entry)
    with pytest.raises(ValueError, match='stale lifecycle revision'):
        service.request(authority, uuid4(), uuid4(), 'withdraw', PASSWORD)
    assert account_state(connect, authority) == {'lifecycle_state': 'active', 'active': True}


def test_request_with_an_unknown_confirmation_keeps_access(entry, authority, connect):
    service = lifecycle(entry)
    expected = lifecycle_revision(entry, authority)
    with pytest.raises(PermissionError, match='confirmation unavailable'):
        service.request(authority, uuid4(), expected, 'withdraw', None, confirmation=uuid4())
    assert account_state(connect, authority) == {'lifecycle_state': 'active', 'active': True}


def test_prepare_refuses_unknown_actions_and_stale_revisions(entry, authority):
    service = lifecycle(entry)
    with pytest.raises(ValueError, match='unsupported lifecycle action'):
        service.prepare_confirmation(authority, uuid4(), uuid4(), 'suspend', PASSWORD)
    with pytest.raises(ValueError, match='stale lifecycle revision'):
        service.prepare_confirmation(authority, uuid4(), uuid4(), 'withdraw', PASSWORD)


def test_browser_request_recovers_only_its_exact_accepted_operation(entry, authority):
    service = lifecycle(entry)
    session = entry.login(str(authority.account_id) + '@fixture.invalid', PASSWORD)
    current = Authority(authority.account_id, UUID(session.public['session']['sessionId']))
    confirmation = service.prepare_confirmation(
        current, uuid4(), lifecycle_revision(entry, current), 'withdraw', PASSWORD
    )
    reference, operation = UUID(confirmation['confirmationRef']), uuid4()
    accepted = service.request_browser(session.token, session.csrf, operation, reference, 'withdraw')
    assert accepted['accessRevoked'] and accepted['disposition'] == 'pending'
    # The cookie is revoked now; it can only read back the exact accepted operation.
    assert service.request_browser(session.token, session.csrf, operation, reference, 'withdraw') == accepted
    for csrf, attempt, action in (
        ('wrong-csrf', operation, 'withdraw'),
        (session.csrf, uuid4(), 'withdraw'),
        (session.csrf, operation, 'erase'),
    ):
        with pytest.raises(PermissionError, match='lifecycle receipt unavailable'):
            service.request_browser(session.token, csrf, attempt, reference, action)


def test_status_cookie_needs_the_current_accepted_request(entry, authority):
    service = lifecycle(entry)
    with pytest.raises(PermissionError, match='lifecycle request unavailable'):
        service.status_transport({'requestId': str(uuid4()), 'revision': str(uuid4())}, uuid4())
    accepted = request(service, authority)
    with pytest.raises(PermissionError, match='superseded lifecycle request'):
        service.status_transport(dict(accepted, revision=str(uuid4())), uuid4())


def test_limited_status_reports_scope_and_completion_evidence(entry, authority):
    service = ControlLifecycleService(entry, (('Library', 'live_records'),), revision='status-test')
    accepted = request(service, authority)
    limited = service.status_transport(accepted, uuid4())
    identifier = UUID(accepted['requestId'])
    assert service.inspect_limited(limited.token, limited.csrf, identifier)['state'] == 'accepted'
    evidence = uuid4()
    service.acknowledge(service.claim(identifier, 'Library', 'live_records'), evidence=evidence,
                        reason='synthetic-reference-check')
    status = service.inspect_limited(limited.token, limited.csrf, identifier)
    assert status['state'] == 'complete' and status['completionEvidenceRef'] == str(identifier)
    scope = status['participants'][0]['scopes'][0]
    assert scope['evidenceReference'] == str(evidence)
    assert scope['disposition'] == 'retained_by_policy'
    assert status['participants'][0]['state'] == 'acknowledged'


def test_limited_status_is_superseded_by_a_reactivation(entry, authority, connect, mailbox):
    service = ControlLifecycleService(entry, (('Library', 'live_records'),), revision='supersede-test')
    accepted = request(service, authority)
    limited = service.status_transport(accepted, uuid4())
    proof = reactivation_proof(entry, authority, connect, mailbox)
    service.reactivate(uuid4(), UUID(proof['challengeId']), proof['proof'], proof['flowBinding'])
    with pytest.raises(PermissionError, match='superseded lifecycle authority'):
        service.inspect_limited(limited.token, limited.csrf, UUID(accepted['requestId']))


def test_claim_refuses_unknown_superseded_and_leased_scopes(entry, authority):
    service = lifecycle(entry)
    with pytest.raises(PermissionError, match='lifecycle request unavailable'):
        service.claim(uuid4(), 'Library', 'references')
    identifier = UUID(request(service, authority)['requestId'])
    other = ControlLifecycleService(entry, service.manifest, revision='another-manifest-revision')
    with pytest.raises(ValueError, match='superseded lifecycle request'):
        other.claim(identifier, 'Library', 'references')
    service.claim(identifier, 'Library', 'references')
    with pytest.raises(ValueError, match='not claimable'):
        service.claim(identifier, 'Library', 'references')


def test_acknowledgement_refuses_an_unbounded_reason(entry, authority):
    service = lifecycle(entry)
    ticket = service.claim(UUID(request(service, authority)['requestId']), 'Library', 'references')
    with pytest.raises(ValueError, match='outside manifest'):
        service.acknowledge(ticket, evidence=uuid4(), reason='r' * 129)


def test_completed_scope_replays_its_evidence_and_refuses_other_evidence(entry, authority):
    service = lifecycle(entry)
    ticket = service.claim(UUID(request(service, authority)['requestId']), 'Library', 'references')
    evidence = uuid4()
    first = service.acknowledge(ticket, evidence=evidence, reason='synthetic-reference-check')
    again = service.acknowledge(ticket, evidence=evidence, reason='synthetic-reference-check')
    assert again['id'] == first['id'] and again['revision'] == first['revision']
    with pytest.raises(ValueError, match='lifecycle evidence conflict'):
        service.acknowledge(ticket, evidence=uuid4(), reason='synthetic-reference-check')


def test_expired_claim_cannot_record_evidence(entry, authority, connect):
    service = lifecycle(entry)
    identifier = UUID(request(service, authority)['requestId'])
    ticket = service.claim(identifier, 'Library', 'references')
    with connect('accounts') as conn:
        conn.execute(
            "UPDATE accounts.lifecycle_scope SET lease_until=clock_timestamp()-interval '1 second' "
            "WHERE request_id=%s AND participant='Library'",
            (identifier,),
        )
    with pytest.raises(ValueError, match='expired lifecycle claim'):
        service.acknowledge(ticket, evidence=uuid4(), reason='late-evidence')
    with connect('accounts') as conn:
        assert conn.execute(
            "SELECT disposition FROM accounts.lifecycle_scope WHERE request_id=%s AND participant='Library'",
            (identifier,),
        ).fetchone()['disposition'] == 'pending'


def test_recorded_step_runs_once_with_the_first_evidence(entry, authority):
    service = lifecycle(entry)
    ticket = service.claim(UUID(request(service, authority)['requestId']), 'Library', 'references')
    calls = []
    evidence = uuid4()
    service._acknowledge_in(ticket, evidence, 'synthetic-reference-check', calls.append)
    service._acknowledge_in(ticket, evidence, 'synthetic-reference-check', calls.append)
    assert len(calls) == 1


def test_restore_without_restriction_evidence_requires_reconciliation(entry):
    decision = lifecycle(entry).evaluate_restore(uuid4(), uuid4())
    assert decision == {
        'decision': 'requires_reconciliation',
        'reasonKey': 'current-restriction-evidence-missing',
    }


def test_reactivation_refuses_unknown_and_wrong_proofs(entry, authority, connect, mailbox):
    service = ControlLifecycleService(entry, (('Library', 'references'),), revision='reactivate-refusal')
    with pytest.raises(PermissionError, match='reactivation proof unavailable'):
        service.reactivate(uuid4(), uuid4(), 'never-issued', 'flow')
    request(service, authority)
    proof = reactivation_proof(entry, authority, connect, mailbox)
    with pytest.raises(PermissionError, match='reactivation proof unavailable'):
        service.reactivate(uuid4(), UUID(proof['challengeId']), 'wrong-proof', proof['flowBinding'])
    assert account_state(connect, authority) == {'lifecycle_state': 'withdrawn', 'active': False}


def test_reactivation_operation_cannot_be_reused_for_another_proof(entry, authority, connect, mailbox):
    service = ControlLifecycleService(entry, (('Library', 'references'),), revision='reactivate-reuse')
    request(service, authority)
    first = reactivation_proof(entry, authority, connect, mailbox)
    operation = uuid4()
    accepted = service.reactivate(operation, UUID(first['challengeId']), first['proof'], first['flowBinding'])
    second = reactivation_proof(entry, authority, connect, mailbox)
    with pytest.raises(PermissionError, match='reactivation proof unavailable'):
        service.reactivate(operation, UUID(second['challengeId']), second['proof'], second['flowBinding'])
    with connect('accounts') as conn:
        assert str(conn.execute(
            "SELECT lifecycle_revision FROM accounts.account WHERE id=%s", (authority.account_id,)
        ).fetchone()['lifecycle_revision']) == accepted['revision']


def test_reactivation_replay_returns_the_original_outcome(entry, authority, connect, mailbox):
    service = ControlLifecycleService(entry, (('Library', 'references'),), revision='reactivate-replay')
    request(service, authority)
    proof = reactivation_proof(entry, authority, connect, mailbox)
    operation = uuid4()
    args = (UUID(proof['challengeId']), proof['proof'], proof['flowBinding'])
    first = service.reactivate(operation, *args)
    assert service.reactivate(operation, *args) == first
    assert first['disposition'] == 'reactivation_pending'
