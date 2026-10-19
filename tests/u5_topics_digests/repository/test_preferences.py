"""Actual owner transactions fence preparation against preference changes."""

import datetime as dt
from uuid import uuid4

import pytest
from backend.modules.personalization.guarded_service import (
    ASSISTANCE_DEFAULTS,
    GuardedSettingsService,
)
from backend.modules.topics.repository import TopicsRepository


def change(transactions, authority, **changes):
    settings = GuardedSettingsService(transactions)
    before = settings.read(authority)
    return settings.update(authority, uuid4(), before["revision"], changes)


def prepare(transactions, authority):
    repository = TopicsRepository(transactions)
    topic = repository.follow(authority, str(uuid4()), "Research")["topic"]["id"]
    run, _ = repository.prepare_run(
        topic,
        dt.date(2026, 1, 1),
        dt.date(2026, 1, 7),
        1,
        [{"title": "Original title", "publishedOn": "2026-01-03"}],
    )
    return repository, run


def test_two_owners_inherit_distinct_languages(transactions, authority, authority_b):
    change(transactions, authority, assistanceDefaults=dict(ASSISTANCE_DEFAULTS, languageId="en"))
    change(transactions, authority_b, assistanceDefaults=dict(ASSISTANCE_DEFAULTS, languageId="ko"))
    _, english = prepare(transactions, authority)
    _, korean = prepare(transactions, authority_b)
    assert "recent papers" in english["presentation"]["text"]
    assert "최신 논문" in korean["presentation"]["text"]
    assert (
        english["preference_snapshot"]["sourceRevision"]
        != korean["preference_snapshot"]["sourceRevision"]
    )


def test_language_change_discards_unsent_work(transactions, authority):
    change(transactions, authority, assistanceDefaults=dict(ASSISTANCE_DEFAULTS, languageId="en"))
    repository, run = prepare(transactions, authority)
    change(transactions, authority, assistanceDefaults=dict(ASSISTANCE_DEFAULTS, languageId="ko"))
    assert repository.begin_send(run["id"], "local-sink") is None
    replacement, adopted = repository.prepare_run(
        run["topic_id"], run["window_start"], run["window_end"], 1, run["digest_content"]
    )
    assert not adopted and replacement["id"] != run["id"]
    assert replacement["preference_snapshot"]["languageId"] == "ko"


def test_appearance_only_change_keeps_preparation(transactions, authority):
    repository, run = prepare(transactions, authority)
    change(transactions, authority, appearance="dark")
    assert repository.begin_send(run["id"], "local-sink")["id"] == run["id"]
    repository.finish_send(run["id"], "failed")


def test_zone_change_discards_preparation(transactions, authority):
    repository, run = prepare(transactions, authority)
    change(transactions, authority, timeZone="America/New_York")
    assert repository.begin_send(run["id"], "local-sink") is None


def test_started_attempt_retains_original_evidence(transactions, authority):
    repository, run = prepare(transactions, authority)
    sending = repository.begin_send(run["id"], "local-sink")
    change(transactions, authority, timeZone="Asia/Seoul")
    unknown = repository.finish_send(run["id"], "unknown")
    assert unknown["preference_snapshot"] == sending["preference_snapshot"]
    assert repository.begin_send(run["id"], "local-sink") is None


def test_settings_remain_available_after_research_consent_stop(transactions, authority, connect):
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.consent SET granted=false WHERE account_id=%s", (authority.account_id,)
        )
    assert change(transactions, authority, timeZone="UTC")["timeZone"] == "UTC"


def test_invalid_timezone_and_level_refuse(transactions, authority):
    with pytest.raises(ValueError):
        change(transactions, authority, timeZone="Mars/Olympus")
    with pytest.raises(ValueError):
        change(
            transactions,
            authority,
            assistanceDefaults=dict(ASSISTANCE_DEFAULTS, presentationLevelId="invented"),
        )


def test_cross_owner_run_read_is_denied(transactions, authority, authority_b):
    from backend.modules.topics.errors import TopicsError

    repository, run = prepare(transactions, authority)
    with pytest.raises(TopicsError):
        repository.read_run(authority_b, run["topic_id"], run["id"])


def test_changed_calendar_snapshot_cannot_stamp_old_selection(transactions, authority):
    from backend.modules.topics.errors import TopicsError

    repository, run = prepare(transactions, authority)
    old = run["preference_snapshot"]
    change(transactions, authority, timeZone="Europe/London")
    with pytest.raises(TopicsError) as refused:
        repository.prepare_run(
            run["topic_id"],
            dt.date(2026, 1, 8),
            dt.date(2026, 1, 14),
            1,
            [],
            expected_preferences=old,
        )
    assert refused.value.code == "CONFLICT"


def test_real_send_admission_spends_durable_total_budget(transactions, authority):
    # Simulated admission only: this check never binds or calls a real adapter.
    repository, first = prepare(transactions, authority)
    spent = repository.system(
        lambda conn: conn.execute(
            "SELECT count(*) AS n FROM topics.send_log_entry WHERE path_kind='real'"
        ).fetchone()["n"]
    )
    assert spent < 99
    budget = {"real_send_limit": spent + 1, "evidence_retention_days": 30}
    admitted = repository.begin_send(first["id"], "real", **budget)
    assert admitted is not None
    repository.finish_send(first["id"], "failed")
    _, second = prepare(transactions, authority)
    assert repository.begin_send(second["id"], "real", **budget) is None
    assert repository.begin_send(first["id"], "real", **budget) is None
