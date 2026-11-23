"""Personalization's manual settings in the composed realm (U8 plan Step 12, allowlist
site 8: `guarded_service.py:43`).

In the composed realm, as in production, the settings service reads and writes under
the full-session `account-control` purpose (U2's), not U1's research guard. A first read
is the cold-start defaults without writing anything; every change is bound to the
revision it was made against, replays under its operation, and refuses a changed intent,
a stale revision and any value outside the retained vocabulary.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from backend.modules.personalization.guarded_service import (
    ASSISTANCE_DEFAULTS,
    INTEREST_VOCABULARY,
    SEARCH_DEFAULTS,
    GuardedSettingsService,
)
from backend.transactions import Authority


@pytest.fixture
def settings(transactions):
    return GuardedSettingsService(transactions)


@pytest.fixture
def cleared(authority):
    """The fixture account (a reused one: receipts are append-only to the owner, so its
    settings carry on from earlier runs and every change starts from its current
    revision)."""
    return authority


def test_the_composed_realm_reads_settings_under_the_account_control_purpose(settings):
    assert settings.purpose == "account-control"


def test_a_read_fills_every_missing_default_and_writes_nothing(settings, cleared, connect):
    with connect("personalization") as conn:
        before = conn.execute("SELECT revision FROM personalization.settings WHERE "
                              "account_id=%s", (cleared.account_id,)).fetchone()
    first = settings.read(cleared)
    assert set(first["searchDefaults"]) == set(SEARCH_DEFAULTS)
    assert set(first["assistanceDefaults"]) == set(ASSISTANCE_DEFAULTS)
    assert first["accountId"] == first["settingsId"] == str(cleared.account_id)
    assert settings.read(cleared) == first
    with connect("personalization") as conn:
        assert conn.execute("SELECT revision FROM personalization.settings WHERE "
                            "account_id=%s", (cleared.account_id,)).fetchone() == before


def test_a_settings_change_is_revision_bound_and_replays_under_its_operation(
    settings, cleared,
):
    before = settings.read(cleared)
    changes = {"appearance": "dark", "timeZone": "Asia/Seoul",
               "searchDefaults": dict(SEARCH_DEFAULTS, modeId="semantic", orderId="newest")}
    operation = uuid4()
    changed = settings.update(cleared, operation, before["revision"], changes)
    assert (changed["appearance"], changed["timeZone"]) == ("dark", "Asia/Seoul")
    assert changed["searchDefaults"]["modeId"] == "semantic"
    assert changed["revision"] != before["revision"]
    assert settings.update(cleared, operation, before["revision"], changes) == changed
    with pytest.raises(ValueError, match="conflict"):
        settings.update(cleared, operation, before["revision"], {"appearance": "light"})
    with pytest.raises(ValueError, match="stale"):
        settings.update(cleared, uuid4(), before["revision"], {"appearance": "light"})
    assert settings.read(cleared) == changed


@pytest.mark.parametrize("changes", [
    {},
    {"onboarding": "completed"},
    {"timeZone": "Mars/Olympus_Mons"},
    {"searchDefaults": dict(SEARCH_DEFAULTS, modeId="hybrid")},
    {"searchDefaults": dict(SEARCH_DEFAULTS, vocabularyRevision="another")},
    {"assistanceDefaults": dict(ASSISTANCE_DEFAULTS, languageId="fr")},
    {"assistanceDefaults": dict(ASSISTANCE_DEFAULTS, presentationLevelId="expert")},
])
def test_a_change_outside_the_retained_vocabulary_is_refused(settings, cleared, changes):
    before = settings.read(cleared)
    with pytest.raises(ValueError):
        settings.update(cleared, uuid4(), before["revision"], changes)
    assert settings.read(cleared) == before


def test_onboarding_saves_completes_or_skips_over_the_same_revision(settings, cleared):
    before = settings.read(cleared)
    interests = [INTEREST_VOCABULARY[0]]
    operation = uuid4()
    saved = settings.update_onboarding(cleared, operation, before["revision"],
                                       "save_interests", interests)
    assert (saved["onboarding"], saved["interestIds"]) == ("in_progress", interests)
    assert settings.update_onboarding(cleared, operation, before["revision"],
                                      "save_interests", interests) == saved
    with pytest.raises(ValueError, match="conflict"):
        settings.update_onboarding(cleared, operation, before["revision"], "complete", [])
    with pytest.raises(ValueError, match="stale"):
        settings.update_onboarding(cleared, uuid4(), before["revision"], "complete", [])
    skipped = settings.update_onboarding(cleared, uuid4(), saved["revision"], "skip", [])
    # Skipping keeps the interests already saved.
    assert (skipped["onboarding"], skipped["interestIds"]) == ("skipped", interests)
    done = settings.update_onboarding(cleared, uuid4(), skipped["revision"], "complete",
                                      list(INTEREST_VOCABULARY))
    assert (done["onboarding"], done["interestIds"]) == ("completed",
                                                         list(INTEREST_VOCABULARY))


@pytest.mark.parametrize("action,interests", [
    ("finish", []),
    ("complete", ["not-a-retained-paper"]),
    ("complete", [INTEREST_VOCABULARY[0], INTEREST_VOCABULARY[0]]),
    ("complete", [INTEREST_VOCABULARY[0]] * 9),
])
def test_an_onboarding_outside_its_vocabulary_is_refused(settings, cleared, action, interests):
    before = settings.read(cleared)
    with pytest.raises(ValueError):
        settings.update_onboarding(cleared, uuid4(), before["revision"], action, interests)
    assert settings.read(cleared) == before


def test_a_session_that_is_not_current_reads_nothing(settings, cleared):
    with pytest.raises(Exception) as refused:
        settings.read(Authority(cleared.account_id, uuid4()))
    assert isinstance(refused.value, PermissionError) or "denied" in str(refused.value)
