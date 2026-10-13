from uuid import UUID, uuid4

import pytest

from backend.modules.accounts.services.control_identity import (
    ControlIdentityService, FixtureIdentityProvider, IdentityClaims,
)

pytestmark = pytest.mark.u2_component


@pytest.fixture
def identity(entry, connect, identities):
    with connect('accounts') as conn:
        conn.execute("DELETE FROM accounts.identity_link WHERE account_id IN (%s,%s)", (identities['a'], identities['b']))
        conn.execute("UPDATE accounts.identity_flow SET disposition='expired' WHERE disposition IN ('pending','exchanging')")
    return ControlIdentityService(entry, {name: FixtureIdentityProvider(name) for name in ('google','orcid')})


def callback(identity, authority, connect, provider='google', *, subject=None, invalid_nonce=False):
    flow = str(uuid4())
    started = identity.begin(authority, provider, 'link', flow, 'settings')
    identifier = UUID(started['flowId'])
    with connect('accounts') as conn:
        row = conn.execute("SELECT secret_ciphertext FROM accounts.identity_flow WHERE id=%s", (identifier,)).fetchone()
    protected = identity.entry.reveal('identity:'+str(identifier), row['secret_ciphertext'])
    adapter = identity.providers[provider]
    claims = IdentityClaims(provider, subject or uuid4().hex, adapter.issuer, adapter.audience,
        'bad' if invalid_nonce else protected['nonce'], None, {'label': 'synthetic profile'})
    code = adapter.issue(claims, protected['verifier'])
    return (identifier, started['state'], flow, code, adapter.callback, authority)


def test_google_links_current_owner(identity, authority, connect):
    result = identity.complete(*callback(identity, authority, connect))
    assert result['provider'] == 'google'
    assert identity.list_links(authority)[0]['linkId'] == result['linkId']


def test_orcid_uses_separate_provider_and_attributed_profile(identity, authority, connect):
    identity.complete(*callback(identity, authority, connect, 'orcid'))
    profile = identity.orcid_profile(authority)
    assert profile['source'] == 'orcid' and profile['coverage'] == 'partial'


def test_wrong_state_does_not_call_provider(identity, authority, connect):
    args = list(callback(identity, authority, connect))
    args[1] = 'wrong-state'
    with pytest.raises(PermissionError):
        identity.complete(*args)
    assert len(identity.providers['google']._codes) == 1


def test_wrong_nonce_keeps_unknown_exchange_not_authenticated(identity, authority, connect):
    args = callback(identity, authority, connect, invalid_nonce=True)
    with pytest.raises(PermissionError):
        identity.complete(*args)
    with connect('accounts') as conn:
        assert conn.execute("SELECT disposition FROM accounts.identity_flow WHERE id=%s", (args[0],)).fetchone()['disposition'] == 'unknown'
    assert identity.list_links(authority) == []


def test_callback_replay_returns_original_link_without_exchange(identity, authority, connect):
    args = callback(identity, authority, connect)
    original = identity.complete(*args)
    assert identity.complete(*args) == original
    assert identity.providers['google']._codes == {}


def test_provider_subject_collision_cannot_merge_accounts(identity, authority, connect, identities):
    subject = uuid4().hex
    with connect('accounts') as conn:
        conn.execute("INSERT INTO accounts.identity_link(id,account_id,provider,subject) VALUES(%s,%s,'google',%s)", (uuid4(), identities['b'], subject))
    with pytest.raises(PermissionError):
        identity.complete(*callback(identity, authority, connect, subject=subject))
    assert identity.list_links(authority) == []


def test_unlink_requires_exact_revision(identity, authority, connect):
    linked = identity.complete(*callback(identity, authority, connect))
    with pytest.raises(ValueError):
        identity.unlink(authority, UUID(linked['linkId']), uuid4())
    identity.unlink(authority, UUID(linked['linkId']), UUID(linked['revision']))
    assert identity.list_links(authority) == []


def test_no_orcid_link_preserves_manual_fallback(identity, authority):
    assert identity.orcid_profile(authority)['coverage'] == 'unavailable'
