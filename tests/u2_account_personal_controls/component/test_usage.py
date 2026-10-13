from uuid import UUID, uuid4

import pytest

from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.plans.control_service import ControlUsageService
from backend.modules.plans.guarded_repository import UsageQuotaExceeded
from backend.transactions import Authority

pytestmark = pytest.mark.u2_component


@pytest.fixture
def usage(transactions, identities, connect):
    with connect('accounts') as conn:
        conn.execute("UPDATE accounts.account SET role='administrator' WHERE id=%s", (identities['a'],))
        conn.execute("UPDATE accounts.session SET mfa_at=clock_timestamp() WHERE id=%s", (identities['session'],))
    with connect('usage') as conn:
        conn.execute("DELETE FROM usage.reservation WHERE account_id=%s", (identities['a'],))
        conn.execute("DELETE FROM usage.entitlement WHERE account_id=%s", (identities['a'],))
    return ControlUsageService(transactions, SYNTHETIC_POLICY)


def grant(usage, authority, allocation=3):
    return usage.assign(authority, authority.account_id, uuid4(), usage.initial_revision(authority.account_id), allocation=allocation, revoked=False, reason='finite synthetic allocation')


def admission(usage, authority):
    period = usage.transactions.run('usage', usage._period)
    return {'operation_id': uuid4(), 'account_id': authority.account_id, 'intent_hash': 'c'*64,
        'generation': 1, 'period_id': period, 'quantity': 1, 'policy_ref': SYNTHETIC_POLICY.reference, 'disposition': 'open'}


def test_initial_assignment_read_does_not_allocate(usage, authority):
    value = usage.assignment(authority, authority.account_id)
    assert value['entitlement'] is None and value['revision']


def test_assignment_lost_ack_replays_original(usage, authority):
    operation = uuid4()
    args = (authority, authority.account_id, operation, usage.initial_revision(authority.account_id))
    options = dict(allocation=3, revoked=False, reason='test')
    result = usage.assign(*args, **options)
    assert usage.assign(*args, **options) == result


def test_stale_assignment_cannot_overwrite(usage, authority):
    grant(usage, authority)
    with pytest.raises(ValueError, match='stale assignment'):
        grant(usage, authority, allocation=1)


def test_assignment_requires_current_mfa(usage, authority, connect):
    with connect('accounts') as conn:
        conn.execute("UPDATE accounts.session SET mfa_at=clock_timestamp()-interval '6 minutes' WHERE id=%s", (authority.session_id,))
    with pytest.raises(Exception):
        grant(usage, authority)


def test_reservation_replay_holds_one_allocation(usage, authority):
    grant(usage, authority)
    intent = admission(usage, authority)
    first = usage.reserve(authority, intent)
    assert usage.reserve(authority, intent)['id'] == first['id']
    assert usage.repository.inspect_assignment(authority)['counts'] == {'reserved': 1}


def test_capacity_exhaustion_never_invents_quota(usage, authority):
    grant(usage, authority, allocation=1)
    usage.reserve(authority, admission(usage, authority))
    with pytest.raises(UsageQuotaExceeded):
        usage.reserve(authority, admission(usage, authority))


def test_forged_quantity_denied(usage, authority):
    grant(usage, authority)
    value = admission(usage, authority)
    value['quantity'] = 0
    with pytest.raises(ValueError, match='bound'):
        usage.reserve(authority, value)


def test_revocation_blocks_new_but_preserves_prior_responsibility(usage, authority):
    assigned = grant(usage, authority)
    value = admission(usage, authority)
    original = usage.reserve(authority, value)
    usage.assign(authority, authority.account_id, uuid4(), UUID(assigned['revision']), allocation=0, revoked=True, reason='stop future acceptance')
    assert usage.reserve(authority, value)['id'] == original['id']
    with pytest.raises(UsageQuotaExceeded):
        usage.reserve(authority, admission(usage, authority))
