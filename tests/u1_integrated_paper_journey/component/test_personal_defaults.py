"""Explicit defaults remain usable without behavioral consent or inferred interests."""

from uuid import uuid4

import psycopg
import pytest

from backend.modules.personalization.guarded_service import GuardedSettingsService
from backend.transactions import Authority, OwnerTransactions

pytestmark = pytest.mark.u1_component


@pytest.fixture
def settings(realm, identities, connect):
    tx = OwnerTransactions(realm[0])
    with connect("personalization") as conn:
        conn.execute("DELETE FROM personalization.settings WHERE account_id=%s", (identities["a"],))
    service = GuardedSettingsService(tx)
    yield service, Authority(identities["a"], identities["session"]), identities
    tx.close()


def test_cold_start_is_readonly_and_repeatable(settings, connect):
    service, authority, _ = settings
    first = service.read(authority)
    assert first == service.read(authority)
    assert first["appearance"] == "system"
    assert first["searchDefaults"]["modeId"] == "lexical"
    with connect("personalization") as conn:
        assert (
            conn.execute(
                "SELECT count(*) FROM personalization.settings WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()[0]
            == 0
        )


def test_acknowledged_defaults_survive_fresh_service(settings, realm):
    service, authority, _ = settings
    initial = service.read(authority)
    changed = service.update(authority, uuid4(), initial["revision"], {"appearance": "dark"})
    tx = OwnerTransactions(realm[0])
    try:
        assert GuardedSettingsService(tx).read(authority) == changed
    finally:
        tx.close()


def test_receipt_replay_precedes_stale_cas_and_changed_intent_conflicts(settings):
    service, authority, _ = settings
    original = service.read(authority)
    operation = uuid4()
    saved = service.update(authority, operation, original["revision"], {"appearance": "dark"})
    service.update(authority, uuid4(), saved["revision"], {"appearance": "light"})
    assert (
        service.update(authority, operation, original["revision"], {"appearance": "dark"}) == saved
    )
    with pytest.raises(ValueError, match="operation conflict"):
        service.update(authority, operation, original["revision"], {"appearance": "system"})
    with pytest.raises(ValueError, match="stale"):
        service.update(authority, uuid4(), original["revision"], {"appearance": "system"})


def test_manual_defaults_work_with_behavioral_consent_disabled(settings, connect):
    service, authority, _ = settings
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.consent SET granted=false WHERE account_id=%s "
            "AND purpose='personalization'",
            (authority.account_id,),
        )
    initial = service.read(authority)
    assistance = dict(initial["assistanceDefaults"], actionId="translate", languageId="ko")
    result = service.update(
        authority, uuid4(), initial["revision"], {"assistanceDefaults": assistance}
    )
    assert result["assistanceDefaults"]["languageId"] == "ko"


def test_current_authority_precedes_receipt_and_cross_account_reads(settings, connect):
    service, authority, ids = settings
    original = service.read(authority)
    operation = uuid4()
    service.update(authority, operation, original["revision"], {"appearance": "dark"})
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        service.read(Authority(ids["b"], authority.session_id))
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.session SET revoked=true WHERE id=%s", (authority.session_id,)
        )
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        service.update(authority, operation, original["revision"], {"appearance": "dark"})


def test_invalid_revision_fields_and_vocabulary_do_not_write(settings):
    service, authority, _ = settings
    original = service.read(authority)
    for fields in (
        {},
        {"ownerId": "other"},
        {"appearance": "rainbow"},
        {"searchDefaults": dict(original["searchDefaults"], vocabularyRevision="stale")},
    ):
        with pytest.raises(ValueError):
            service.update(authority, uuid4(), original["revision"], fields)
    with pytest.raises(ValueError):
        service.update(authority, uuid4(), "", {"appearance": "dark"})
    assert service.read(authority) == original
