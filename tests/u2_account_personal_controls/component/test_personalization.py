"""Real owner transactions for explicit settings and consent/reset boundaries."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from psycopg.errors import InsufficientPrivilege

from backend.modules.accounts.control_cursor import ControlCursor
from backend.modules.accounts.control_policy import SYNTHETIC_POLICY, PolicyUnavailable
from backend.modules.personalization.control_service import (
    PersonalizationControlService,
    ProducerBinding,
)
from backend.modules.personalization.guarded_service import GuardedSettingsService
from backend.modules.personalization.activity import ActivityRelay
from backend.transactions import Authority, Busy


@pytest.fixture
def personal(connect, authority, transactions):
    with connect("personalization") as conn:
        conn.execute(
            "DELETE FROM personalization.behavior WHERE account_id=%s", (authority.account_id,)
        )
        conn.execute(
            "DELETE FROM personalization.projection WHERE account_id=%s", (authority.account_id,)
        )
        # Other isolated component cases exercise erasure of this fixture owner.
        # When rebuilding the fixture, preserve the monotonic reset high-water.
        conn.execute(
            "INSERT INTO personalization.settings(account_id,revision,input_boundary) "
            "SELECT %s,%s,COALESCE(max(input_boundary),0)+1 "
            "FROM personalization.reset_responsibility WHERE account_id=%s "
            "ON CONFLICT(account_id) DO UPDATE SET defaults='{}',appearance='system',"
            "revision=excluded.revision,input_boundary=greatest(personalization.settings.input_boundary,"
            "excluded.input_boundary)",
            (authority.account_id, uuid4(), authority.account_id),
        )
    producer = ProducerBinding("CorpusContent")
    service = PersonalizationControlService(
        transactions, SYNTHETIC_POLICY, ControlCursor(b"p" * 32), producers=(producer,)
    )
    settings = GuardedSettingsService(transactions)
    return service, settings, producer


@pytest.fixture
def paper(connect):
    revision = uuid4()
    with connect("corpus") as conn:
        conn.execute(
            "INSERT INTO corpus.paper(id,title,authors,metadata) VALUES('1706.03762','Synthetic fixture','[]','{}') "
            "ON CONFLICT(id) DO UPDATE SET withdrawn=false"
        )
        conn.execute(
            "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,private_path,eligible,purpose,eligibility_revision,provenance,content) "
            "VALUES('u2-personal-fixture','1706.03762','https://fixture.invalid/paper',%s,'u2-personal','fixture',true,'local-research',%s,'{}','{}') "
            "ON CONFLICT(id) DO UPDATE SET eligible=true,eligibility_revision=excluded.eligibility_revision",
            ("a" * 64, revision),
        )
    return {
        "paperId": "1706.03762",
        "versionId": "u2-personal-fixture",
        "eligibilityRevision": str(revision),
    }


@pytest.fixture
def event(personal, authority, connect, paper):
    with connect("personalization") as conn:
        revision, consent, boundary = personal[0]._state(conn, authority)
    return {
        "eventId": str(uuid4()),
        "accountId": str(authority.account_id),
        "paper": paper,
        "activityId": "paper-view",
        "occurredAt": datetime.now(UTC).isoformat(),
        "consentRevision": str(consent["revision"]),
        "authorityRevision": str(revision),
        "inputBoundary": str(boundary),
    }


def test_optional_activity_declined_consent_has_no_record(personal, authority, connect, paper):
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.consent SET granted=false WHERE account_id=%s "
                     "AND purpose='personalization'", (authority.account_id,))
    relay = ActivityRelay(personal[0], personal[2])
    captured = relay.capture(authority, uuid4(), paper, "paper-view")
    assert captured is None and relay.deliver(authority, captured) == {"disposition": "not-captured"}
    with connect("personalization") as conn:
        assert conn.execute("SELECT count(*) AS n FROM personalization.behavior WHERE account_id=%s",
                            (authority.account_id,)).fetchone()["n"] == 0


def test_optional_activity_capacity_outage_does_not_claim_acceptance(personal, authority, paper, monkeypatch):
    relay = ActivityRelay(personal[0], personal[2])
    captured = relay.capture(authority, uuid4(), paper, "paper-view")
    def busy(*args, **kwargs):
        raise Busy("synthetic capacity fault")
    monkeypatch.setattr(personal[0].transactions, "run", busy)
    assert relay.capture(authority, uuid4(), paper, "paper-view") is None
    assert relay.deliver(authority, captured) == {"disposition": "unavailable"}


def test_optional_activity_late_source_withdrawal_suppresses_tracking(personal, authority, connect, paper):
    relay = ActivityRelay(personal[0], personal[2])
    captured = relay.capture(authority, uuid4(), paper, "paper-view")
    with connect("corpus") as conn:
        conn.execute("UPDATE corpus.version SET eligible=false WHERE id=%s", (paper["versionId"],))
    assert relay.deliver(authority, captured) == {"disposition": "source-unavailable"}
    with connect("personalization") as conn:
        assert conn.execute("SELECT count(*) AS n FROM personalization.behavior WHERE account_id=%s",
                            (authority.account_id,)).fetchone()["n"] == 0


def test_optional_activity_replay_keeps_first_fact(personal, authority, connect, paper):
    relay = ActivityRelay(personal[0], personal[2])
    operation = uuid4()
    first = relay.capture(authority, operation, paper, "paper-view")
    assert relay.deliver(authority, first)["disposition"] == "recorded"
    with connect("personalization") as conn:
        original = conn.execute("SELECT fact FROM personalization.behavior WHERE account_id=%s",
                                (authority.account_id,)).fetchall()
    assert relay.deliver(authority, first)["disposition"] == "duplicate"
    later = relay.capture(authority, operation, paper, "paper-view")
    assert later["eventId"] == first["eventId"] and later["occurredAt"] != first["occurredAt"]
    assert relay.deliver(authority, later) == {"disposition": "conflict"}
    with connect("personalization") as conn:
        rows = conn.execute("SELECT fact FROM personalization.behavior WHERE account_id=%s",
                            (authority.account_id,)).fetchall()
    assert rows == original and len(rows) == 1


def test_optional_activity_revoked_session_cannot_publish(personal, authority, connect, paper):
    relay = ActivityRelay(personal[0], personal[2])
    captured = relay.capture(authority, uuid4(), paper, "paper-view")
    with connect("accounts") as conn:
        conn.execute("UPDATE accounts.session SET revoked=true WHERE id=%s", (authority.session_id,))
    assert relay.deliver(authority, captured)["disposition"] == "suppressed_by_lifecycle"


def test_optional_activity_rejects_unregistered_producer(personal):
    with pytest.raises(PermissionError):
        ActivityRelay(personal[0], ProducerBinding("uninstalled-component"))


def test_defaults_do_not_erase_acknowledged_onboarding(personal, authority):
    _, settings, _ = personal
    before = settings.read(authority)
    chosen = settings.update_onboarding(
        authority, uuid4(), before["revision"], "complete", ["1706.03762"]
    )
    result = settings.update(authority, uuid4(), chosen["revision"], {"appearance": "dark"})
    assert result["onboarding"] == "completed" and result["interestIds"] == ["1706.03762"]
    assert settings.read(authority) == result


def test_skip_preserves_saved_interests(personal, authority):
    settings = personal[1]
    before = settings.read(authority)
    chosen = settings.update_onboarding(
        authority, uuid4(), before["revision"], "save_interests", ["2005.11401"]
    )
    result = settings.update_onboarding(authority, uuid4(), chosen["revision"], "skip", [])
    assert result["onboarding"] == "skipped" and result["interestIds"] == ["2005.11401"]


def test_manual_settings_without_research_or_behavior_consent(personal, authority, connect):
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.consent SET granted=false WHERE account_id=%s", (authority.account_id,)
        )
    settings = personal[1]
    before = settings.read(authority)
    assert (
        settings.update(authority, uuid4(), before["revision"], {"appearance": "light"})[
            "appearance"
        ]
        == "light"
    )


def test_replay_uses_same_effect_after_revision_changes(personal, authority):
    settings = personal[1]
    before = settings.read(authority)
    key = uuid4()
    first = settings.update(authority, key, before["revision"], {"appearance": "dark"})
    settings.update(authority, uuid4(), first["revision"], {"appearance": "light"})
    assert settings.update(authority, key, before["revision"], {"appearance": "dark"}) == first
    assert settings.read(authority)["appearance"] == "light"


def test_replay_cannot_change_intent(personal, authority):
    settings = personal[1]
    before = settings.read(authority)
    key = uuid4()
    settings.update(authority, key, before["revision"], {"appearance": "dark"})
    with pytest.raises(ValueError, match="operation conflict"):
        settings.update(authority, key, before["revision"], {"appearance": "light"})


def test_stale_settings_preserve_acknowledged_value(personal, authority):
    settings = personal[1]
    before = settings.read(authority)
    settings.update(authority, uuid4(), before["revision"], {"appearance": "dark"})
    with pytest.raises(ValueError, match="stale settings"):
        settings.update_onboarding(
            authority, uuid4(), before["revision"], "complete", ["2005.11401"]
        )
    assert settings.read(authority)["appearance"] == "dark"


def test_concurrent_writes_have_one_revision_winner(personal, authority):
    settings = personal[1]
    before = settings.read(authority)

    def attempt(appearance):
        try:
            return settings.update(
                authority, uuid4(), before["revision"], {"appearance": appearance}
            )
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["light", "dark"]))
    assert sum(result is not None for result in results) == 1
    assert settings.read(authority) in results


def test_invalid_interest_rejected_without_write(personal, authority):
    settings = personal[1]
    before = settings.read(authority)
    with pytest.raises(ValueError):
        settings.update_onboarding(
            authority, uuid4(), before["revision"], "complete", ["not-supported"]
        )
    assert settings.read(authority) == before


def test_manual_suggestions_paginate_without_allocating_settings(personal, authority):
    service, settings, _ = personal
    before = settings.read(authority)
    first = service.suggestions(authority, limit=1)
    second = service.suggestions(authority, limit=1, cursor=first["page"]["nextCursor"])
    assert first["items"][0]["interestId"] != second["items"][0]["interestId"]
    assert second["page"]["nextCursor"] is None
    assert settings.read(authority) == before


def test_unavailable_orcid_keeps_manual_path(personal, authority):
    service = personal[0]
    with pytest.raises(PolicyUnavailable):
        service.suggestions(authority, limit=2, identity_link_id=str(uuid4()))
    assert len(service.suggestions(authority, limit=2)["items"]) == 2


def test_duplicate_behavior_is_one_row(personal, authority, event, connect):
    service, _, producer = personal
    assert service.record_behavior(producer, authority, event)["disposition"] == "recorded"
    assert service.record_behavior(producer, authority, event)["disposition"] == "duplicate"
    with connect("personalization") as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM personalization.behavior WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()["n"]
            == 1
        )


def test_changed_event_identity_conflicts(personal, authority, event):
    service, _, producer = personal
    service.record_behavior(producer, authority, event)
    with pytest.raises(ValueError, match="identity conflict"):
        service.record_behavior(producer, authority, dict(event, activityId="save"))


def test_unregistered_producer_cannot_submit(personal, authority, event):
    with pytest.raises(PermissionError, match="unregistered"):
        personal[0].record_behavior(ProducerBinding("CorpusContent"), authority, event)


def test_consent_revocation_suppresses_delayed_event(personal, authority, event, connect):
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.consent SET granted=false,revision=%s WHERE account_id=%s AND purpose='personalization'",
            (uuid4(), authority.account_id),
        )
    assert (
        personal[0].record_behavior(personal[2], authority, event)["disposition"]
        == "suppressed_by_consent"
    )
    projection = personal[0].read_projection(personal[2], authority, purpose="personalization")
    assert projection["disposition"] == "disabled" and projection["interestIds"] == []


def test_reset_suppresses_delayed_event(personal, authority, event):
    service, settings, producer = personal
    before = settings.read(authority)
    service.resets.accept(
        authority,
        uuid4(),
        UUID(before["revision"]),
        "delete_behavior",
        manifest=(("Personalization", "behavior"), ("ServiceOperations", "restore")),
        manifest_revision="u2-personal-test",
    )
    assert (
        service.record_behavior(producer, authority, event)["disposition"] == "suppressed_by_reset"
    )


def test_revoked_session_suppresses_internal_fact_and_denies_read(
    personal, authority, event, connect
):
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.session SET revoked=true WHERE id=%s", (authority.session_id,)
        )
    assert (
        personal[0].record_behavior(personal[2], authority, event)["disposition"]
        == "suppressed_by_lifecycle"
    )
    with pytest.raises(InsufficientPrivilege):
        personal[1].read(authority)


def test_recent_and_projection_reads_do_not_record_activity(personal, authority, event, connect):
    service, _, producer = personal
    assert (
        service.read_projection(producer, authority, purpose="personalization")["disposition"]
        == "cold_start"
    )
    service.record_behavior(producer, authority, event)
    for _ in range(2):
        assert len(service.recent(authority, limit=5)["items"]) == 1
        assert service.read_projection(producer, authority, purpose="personalization")[
            "interestIds"
        ] == ["1706.03762"]
    with connect("personalization") as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM personalization.behavior WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()["n"]
            == 1
        )


def test_withdrawn_source_is_labelled_and_excluded_from_profile(
    personal, authority, event, connect
):
    service, _, producer = personal
    service.record_behavior(producer, authority, event)
    with connect("corpus") as conn:
        conn.execute("UPDATE corpus.paper SET withdrawn=true WHERE id='1706.03762'")
    assert service.recent(authority, limit=5)["items"][0]["sourceDisposition"] == "withdrawn"
    assert (
        service.read_projection(producer, authority, purpose="personalization")["interestIds"] == []
    )


def test_owner_mismatch_and_future_events_denied(personal, authority, event, identities):
    with pytest.raises(ValueError):
        personal[0].record_behavior(
            personal[2], authority, dict(event, accountId=str(identities["b"]))
        )
    with pytest.raises(ValueError, match="future"):
        personal[0].record_behavior(
            personal[2],
            authority,
            dict(event, occurredAt=(datetime.now(UTC) + timedelta(hours=1)).isoformat()),
        )
    with pytest.raises(InsufficientPrivilege):
        personal[0].recent(Authority(identities["b"], authority.session_id), limit=5)


def test_cleanup_keeps_new_generation_and_waits_for_restore(personal, authority, event):
    service, settings, producer = personal
    service.record_behavior(producer, authority, event)
    reset = service.resets.accept(
        authority,
        uuid4(),
        UUID(settings.read(authority)["revision"]),
        "delete_behavior",
        manifest=(("Personalization", "behavior"), ("ServiceOperations", "restore")),
        manifest_revision="u2-personal-test",
    )
    new = dict(event, eventId=str(uuid4()), inputBoundary=reset["inputBoundary"])
    service.record_behavior(producer, authority, new)
    outcome = service.clean_reset(UUID(reset["resetId"]))
    assert outcome["disposition"] == "pending"
    assert [item["activityReference"] for item in service.recent(authority, limit=5)["items"]] == [
        new["eventId"]
    ]
    status = service.resets.inspect(authority, UUID(reset["resetId"]))
    assert [scope["disposition"] for scope in status["scopes"]] == ["complete", "pending"]


def test_consent_obligation_replay_advances_boundary_only_once(personal, authority, event, connect):
    service, _, producer = personal
    service.record_behavior(producer, authority, event)
    consent = uuid4()
    with connect("accounts") as conn:
        conn.execute(
            "UPDATE accounts.consent SET granted=false,revision=%s WHERE account_id=%s AND purpose='personalization'",
            (consent, authority.account_id),
        )
    fact = {
        "id": uuid4(),
        "account_id": authority.account_id,
        "purpose": "personalization",
        "consent_revision": consent,
        "authority_revision": UUID(event["authorityRevision"]),
        "granted": False,
    }
    first = service.apply_consent_boundary(fact)
    assert service.apply_consent_boundary(fact) == first
    projection = service.read_projection(producer, authority, purpose="personalization")
    assert int(projection["inputBoundary"]) == int(event["inputBoundary"]) + 1
    assert projection["disposition"] == "disabled"
    with connect("personalization") as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM personalization.behavior WHERE account_id=%s",
                (authority.account_id,),
            ).fetchone()["n"]
            == 0
        )


def test_superseded_consent_fact_does_not_erase_current_activity(personal, authority, event):
    service, _, producer = personal
    service.record_behavior(producer, authority, event)
    fact = {
        "id": uuid4(),
        "account_id": authority.account_id,
        "purpose": "personalization",
        "consent_revision": uuid4(),
        "authority_revision": UUID(event["authorityRevision"]),
        "granted": False,
    }
    assert service.apply_consent_boundary(fact)["disposition"] == "superseded"
    assert len(service.recent(authority, limit=5)["items"]) == 1
