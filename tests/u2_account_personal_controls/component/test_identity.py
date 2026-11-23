from uuid import UUID, uuid4

import pytest

from backend.modules.accounts.services.control_identity import (
    ControlIdentityService, FixtureIdentityProvider, IdentityClaims,
)
from backend.transactions import Authority

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


@pytest.fixture
def forget_links(connect, identities):
    """These cases leave links behind; other layers expect the owners unlinked."""
    yield
    with connect('accounts') as conn:
        conn.execute("DELETE FROM accounts.identity_link WHERE account_id IN (%s,%s)", (identities['a'], identities['b']))


def sign_in_callback(identity, connect, subject, provider='google'):
    """A provider sign-in flow (no owner) answered by the synthetic adapter."""
    flow = str(uuid4())
    started = identity.begin(None, provider, 'sign_in', flow, 'search')
    identifier = UUID(started['flowId'])
    with connect('accounts') as conn:
        row = conn.execute("SELECT secret_ciphertext FROM accounts.identity_flow WHERE id=%s", (identifier,)).fetchone()
    protected = identity.entry.reveal('identity:' + str(identifier), row['secret_ciphertext'])
    adapter = identity.providers[provider]
    claims = IdentityClaims(provider, subject, adapter.issuer, adapter.audience, protected['nonce'], None, {})
    code = adapter.issue(claims, protected['verifier'])
    return (identifier, started['state'], flow, code, adapter.callback, None)


def test_fixture_adapters_refuse_unknown_providers_codes_and_capacity():
    with pytest.raises(ValueError, match='unsupported provider'):
        FixtureIdentityProvider('github')
    adapter = FixtureIdentityProvider('google')
    claims = IdentityClaims('google', 'subject', adapter.issuer, adapter.audience, 'nonce', None, {})
    with pytest.raises(PermissionError, match='provider code unavailable'):
        adapter.exchange('never-issued', verifier='v', nonce='nonce')
    for _ in range(20):
        adapter.issue(claims, 'verifier')
    with pytest.raises(ValueError, match='finite fixture code capacity'):
        adapter.issue(claims, 'verifier')


def test_service_requires_distinct_google_and_orcid_adapters(entry):
    with pytest.raises(ValueError, match='distinct Google and ORCID'):
        ControlIdentityService(entry, {'google': FixtureIdentityProvider('google')})
    with pytest.raises(ValueError, match='distinct Google and ORCID'):
        ControlIdentityService(entry, {'google': FixtureIdentityProvider('orcid'),
                                       'orcid': FixtureIdentityProvider('orcid')})


def test_begin_refuses_unknown_input_and_an_ownerless_link(identity, authority):
    for provider, intent, route in (('github', 'link', 'settings'), ('google', 'merge', 'settings'),
                                    ('google', 'link', 'admin')):
        with pytest.raises(ValueError, match='identity flow input unavailable'):
            identity.begin(authority, provider, intent, 'flow', route)
    with pytest.raises(PermissionError, match='link owner required'):
        identity.begin(None, 'google', 'link', 'flow', 'settings')


def test_begin_holds_at_most_twenty_open_flows(identity, authority, connect):
    for _ in range(20):
        identity.begin(authority, 'google', 'link', str(uuid4()), 'settings')
    with pytest.raises(ValueError, match='finite identity flow capacity'):
        identity.begin(authority, 'google', 'link', str(uuid4()), 'settings')
    with connect('accounts') as conn:
        conn.execute("UPDATE accounts.identity_flow SET disposition='expired' WHERE disposition='pending'")


def test_only_the_synthetic_adapter_issues_a_fixture_authorization(identity, authority, entry):
    started = identity.begin(authority, 'google', 'link', str(uuid4()), 'settings')
    assert identity.fixture_authorization(started).startswith(identity.providers['google'].callback)
    real = type('RealAdapter', (), {'name': 'google', 'issuer': 'https://accounts.google.com',
                                    'audience': 'docsuri', 'callback': 'https://example.invalid/cb'})()
    other = ControlIdentityService(entry, {'google': real, 'orcid': FixtureIdentityProvider('orcid')})
    with pytest.raises(PermissionError, match='fixture provider required'):
        other.fixture_authorization(started)


def test_fixture_authorization_needs_a_pending_flow(identity, authority, connect, forget_links):
    args = callback(identity, authority, connect)
    identity.complete(*args)
    accepted = {'flowId': str(args[0]), 'provider': 'google', 'state': args[1]}
    with pytest.raises(PermissionError, match='fixture flow unavailable'):
        identity.fixture_authorization(accepted)


def test_linked_provider_sign_in_issues_a_session_and_replays_it(identity, authority, connect, forget_links):
    subject = 'sign-in-' + uuid4().hex
    identity.complete(*callback(identity, authority, connect, subject=subject))
    args = sign_in_callback(identity, connect, subject)
    signed_in = identity.complete(*args)
    assert signed_in.public['state'] == 'authenticated'
    assert signed_in.public['session']['accountId'] == str(authority.account_id)
    assert identity.entry.inspect_session(signed_in.token).public == signed_in.public
    replay = identity.complete(*args)
    assert replay.token == signed_in.token and replay.public == signed_in.public


def test_provider_sign_in_without_a_link_is_refused(identity, connect):
    args = sign_in_callback(identity, connect, 'unlinked-' + uuid4().hex)
    with pytest.raises(PermissionError, match='verified identity link required'):
        identity.complete(*args)
    with connect('accounts') as conn:
        assert conn.execute("SELECT disposition FROM accounts.identity_flow WHERE id=%s",
                            (args[0],)).fetchone()['disposition'] == 'exchanging'


def test_provider_sign_in_for_an_administrator_needs_a_factor(
    identity, authority, connect, identities, forget_links
):
    subject = 'admin-' + uuid4().hex
    identity.complete(*callback(identity, authority, connect, subject=subject))
    with connect('accounts') as conn:
        conn.execute("UPDATE accounts.account SET role='administrator' WHERE id=%s", (identities['a'],))
    try:
        with pytest.raises(PermissionError, match='administrator factor unavailable'):
            identity.complete(*sign_in_callback(identity, connect, subject))
    finally:
        with connect('accounts') as conn:
            conn.execute("UPDATE accounts.account SET role='member' WHERE id=%s", (identities['a'],))


def test_provider_sign_in_to_an_inactive_account_is_refused(
    identity, authority, connect, identities, forget_links
):
    subject = 'inactive-' + uuid4().hex
    identity.complete(*callback(identity, authority, connect, subject=subject))
    with connect('accounts') as conn:
        conn.execute("UPDATE accounts.account SET active=false WHERE id=%s", (identities['a'],))
    try:
        with pytest.raises(PermissionError, match='linked account unavailable'):
            identity.complete(*sign_in_callback(identity, connect, subject))
    finally:
        with connect('accounts') as conn:
            conn.execute("UPDATE accounts.account SET active=true WHERE id=%s", (identities['a'],))


def test_completion_refuses_unknown_flows_and_other_owners(identity, authority, connect, identities):
    with pytest.raises(PermissionError, match='identity flow unavailable'):
        identity.complete(uuid4(), 'state', 'flow', 'code', 'callback', authority)
    args = list(callback(identity, authority, connect))
    args[5] = Authority(identities['b'], uuid4())
    with pytest.raises(PermissionError, match='identity owner unavailable'):
        identity.complete(*args)
    assert identity.list_links(authority) == []


def test_abandoned_flow_cannot_be_exchanged(identity, authority, connect):
    args = callback(identity, authority, connect)
    with connect('accounts') as conn:
        conn.execute("UPDATE accounts.identity_flow SET disposition='unknown' WHERE id=%s", (args[0],))
    with pytest.raises(PermissionError, match='not replayable'):
        identity.complete(*args)
    assert len(identity.providers['google']._codes) == 1


def test_unlink_requires_a_surviving_password(identity, authority, connect, identities, forget_links):
    linked = identity.complete(*callback(identity, authority, connect))
    with connect('accounts') as conn:
        conn.execute("UPDATE accounts.account SET password_hash='!no-local-password' WHERE id=%s",
                     (identities['a'],))
    with pytest.raises(PermissionError, match='verified surviving credential required'):
        identity.unlink(authority, UUID(linked['linkId']), UUID(linked['revision']))
    assert identity.list_links(authority)[0]['linkId'] == linked['linkId']
