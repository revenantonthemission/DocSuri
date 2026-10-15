"""Synthetic credential setup; each test owns its proof/factor operations."""
import json
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.accounts.services.control_entry import ControlEntryService
from backend.transactions import Authority

PASSWORD = 'Synthetic!Research2026'


@pytest.fixture
def entry(transactions, identities, connect):
    service = ControlEntryService(transactions, SYNTHETIC_POLICY)
    encoded = service._hash_password(PASSWORD)
    with connect('accounts') as conn:
        conn.execute("DELETE FROM accounts.entry_budget")
        conn.execute("UPDATE accounts.account SET password_hash=%s,email=%s WHERE id=%s", (encoded, 'u2-a@fixture.invalid', identities['a']))
        conn.execute("UPDATE accounts.mfa_enrollment SET state='invalidated' WHERE account_id=%s", (identities['a'],))
    return service


@pytest.fixture
def isolated_authority(entry, connect, realm, request, fixture_discard):
    """Dedicated run-scoped owner for cases whose requests/cleanup history would
    otherwise accumulate against the finite lifecycle and reset bounds."""
    identity = realm[0].run_id + ":component:" + request.node.name
    account, session = uuid5(NAMESPACE_URL, identity), uuid5(NAMESPACE_URL, identity + ":session")
    revision = uuid4()
    with connect('accounts') as conn:
        conn.execute(
            "INSERT INTO accounts.account(id,email,password_hash,verified,active,authority_revision,display_name) "
            "VALUES(%s,%s,%s,true,true,%s,'Synthetic component owner') ON CONFLICT(id) DO UPDATE "
            "SET active=true,verified=true,lifecycle_state='active',password_hash=excluded.password_hash,"
            "authority_revision=excluded.authority_revision",
            (account, str(account) + '@fixture.invalid', entry._hash_password(PASSWORD), revision),
        )
        conn.execute(
            "INSERT INTO accounts.session(id,account_id,token_hash,csrf_hash,authority_revision,expires_at,purpose) "
            "VALUES(%s,%s,%s,%s,%s,clock_timestamp()+interval '15 minutes','full_session') ON CONFLICT(id) DO UPDATE "
            "SET revoked=false,expires_at=excluded.expires_at,authority_revision=excluded.authority_revision",
            (session, account, str(uuid4()), str(uuid4()), revision),
        )
        for purpose in ('local-research', 'personalization'):
            conn.execute(
                "INSERT INTO accounts.consent(account_id,purpose,granted) VALUES(%s,%s,true) "
                "ON CONFLICT(account_id,purpose) DO UPDATE SET granted=true",
                (account, purpose),
            )
    yield Authority(account, session)
    fixture_discard(account)


@pytest.fixture
def mailbox(entry):
    def latest(purpose):
        values = [json.loads(path.read_text()) for path in entry.mail.root.glob('*.blob')]
        matches = [value for value in values if value.get('purpose') == purpose]
        # Test callers use a unique flow; never inspect or expose real mail.
        return matches
    return latest
