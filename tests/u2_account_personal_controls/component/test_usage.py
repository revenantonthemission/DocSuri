from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest

from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.plans.control_service import ControlUsageService
from backend.modules.plans.guarded_repository import UsageQuotaExceeded
from backend.transactions import Authority

pytestmark = pytest.mark.u2_component


@pytest.fixture
def authority(connect, realm, request, fixture_discard):
    """Dedicated run-scoped administrator; U1 rejection proofs are append-only."""
    identity = realm[0].run_id + ":usage:" + request.node.name
    account, session = uuid5(NAMESPACE_URL, identity), uuid5(NAMESPACE_URL, identity + ":session")
    revision = uuid4()
    with connect('accounts') as conn:
        conn.execute(
            "INSERT INTO accounts.account(id,email,password_hash,verified,active,role,authority_revision,display_name) "
            "VALUES(%s,%s,'database-fixture-not-a-login-hash',true,true,'administrator',%s,'Synthetic usage administrator') "
            "ON CONFLICT(id) DO UPDATE SET active=true,verified=true,lifecycle_state='active',"
            "role='administrator',authority_revision=excluded.authority_revision",
            (account, str(account) + "@fixture.invalid", revision),
        )
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,expires_at,purpose,mfa_at) "
            "VALUES(%s,%s,%s,%s,%s,clock_timestamp()+interval '15 minutes','full_session',clock_timestamp()) "
            "ON CONFLICT(id) DO UPDATE SET revoked=false,purpose='full_session',mfa_at=clock_timestamp(),"
            "expires_at=excluded.expires_at,authority_revision=excluded.authority_revision",
            (session, account, str(uuid4()), str(uuid4()), revision),
        )
        for purpose in ("local-research", "personalization"):
            conn.execute(
                "INSERT INTO accounts.consent(account_id,purpose,granted) VALUES(%s,%s,true) "
                "ON CONFLICT(account_id,purpose) DO UPDATE SET granted=true",
                (account, purpose),
            )
    yield Authority(account, session)
    fixture_discard(account)


@pytest.fixture
def usage(transactions, authority, connect):
    with connect('usage') as conn:
        conn.execute("DELETE FROM usage.reservation WHERE account_id=%s", (authority.account_id,))
        conn.execute("DELETE FROM usage.entitlement WHERE account_id=%s", (authority.account_id,))
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
