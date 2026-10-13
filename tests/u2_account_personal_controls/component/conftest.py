"""Synthetic credential setup; each test owns its proof/factor operations."""
import json

import pytest

from backend.modules.accounts.control_policy import SYNTHETIC_POLICY
from backend.modules.accounts.services.control_entry import ControlEntryService

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
def mailbox(entry):
    def latest(purpose):
        values = [json.loads(path.read_text()) for path in entry.mail.root.glob('*.blob')]
        matches = [value for value in values if value.get('purpose') == purpose]
        # Test callers use a unique flow; never inspect or expose real mail.
        return matches
    return latest
