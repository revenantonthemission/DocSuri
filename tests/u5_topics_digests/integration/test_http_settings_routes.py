"""Mounted C03 settings routes, as U5 mounts them beside the topics routes: real session
verification over the real realm, revision-checked and acknowledged saves, and
consent-independent manual settings while delivery still stops.

The settings routes' six tests, moved unchanged from `test_http.py` (plan Step 35,
decision L3-1); the mounted app and its request helpers are in `http_mount.py`."""

from uuid import uuid4

import pytest
from backend.modules.personalization.guarded_service import ASSISTANCE_DEFAULTS, POLICY
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from tests.u5_topics_digests.http_mount import follow, mount, post, settings_read, settings_update


@pytest.fixture(scope="module")
def mounted(realm):
    yield from mount(realm)


def test_settings_mounted_and_acknowledged(mounted):
    before = settings_read(mounted.client)
    saved = settings_update(
        mounted.client,
        before["revision"],
        timeZone="Asia/Seoul",
        assistanceDefaults=dict(ASSISTANCE_DEFAULTS, languageId="ko"),
    )
    assert saved.status_code == 200, saved.text
    assert settings_read(mounted.client)["timeZone"] == "Asia/Seoul"
    topic = follow(mounted.client)["topicId"]
    view = mounted.client.get(f"/api/v2/topics/{topic}/settings").json()
    assert view["effectivePreferences"]["languageId"] == "ko"


def test_settings_lost_ack_replay_and_stale_revision(mounted):
    before = settings_read(mounted.client)
    key = uuid4()
    first = settings_update(mounted.client, before["revision"], key, appearance="light")
    replay = settings_update(mounted.client, before["revision"], key, appearance="light")
    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    stale = settings_update(mounted.client, before["revision"], appearance="dark")
    assert stale.status_code == 409


def test_settings_invalid_zone_and_vocabulary(mounted):
    before = settings_read(mounted.client)
    assert (
        settings_update(mounted.client, before["revision"], timeZone="Mars/Olympus").status_code
        == 422
    )
    assert (
        settings_update(
            mounted.client,
            before["revision"],
            assistanceDefaults=dict(ASSISTANCE_DEFAULTS, languageId="invented"),
        ).status_code
        == 422
    )


def test_settings_other_owner_revision_is_not_authority(mounted):
    other = settings_read(mounted.other)
    foreign = settings_update(mounted.client, other["revision"], timeZone="Europe/London")
    assert foreign.status_code == 409
    assert settings_read(mounted.other) == other


def test_settings_consent_independent_delivery_still_stops(mounted):
    before = settings_read(mounted.client)
    mounted.transactions.run(
        "accounts",
        lambda conn: conn.execute(
            "UPDATE accounts.consent SET granted=false WHERE account_id=%s",
            (mounted.authority.account_id,),
        ),
    )
    try:
        assert (
            settings_update(mounted.client, before["revision"], timeZone="UTC").status_code == 200
        )
        assert mounted.repository.digest_recipient(mounted.authority.account_id)["granted"] is False
    finally:
        mounted.transactions.run(
            "accounts",
            lambda conn: conn.execute(
                "UPDATE accounts.consent SET granted=true WHERE account_id=%s",
                (mounted.authority.account_id,),
            ),
        )


def test_settings_require_current_session_and_csrf(mounted):
    anonymous = TestClient(mounted.client.app, base_url=mounted.client.base_url)
    assert post(anonymous, "/api/v2/c03/settings-read", {}).status_code in (401, 403)
    before = settings_read(mounted.client)
    response = mounted.client.post(
        "/api/v2/c03/settings-update",
        json={"expectedRevision": before["revision"], "policyRef": POLICY, "timeZone": "UTC"},
        headers={"Idempotency-Key": str(uuid4()), "X-CSRF-Token": "incorrect"},
    )
    assert response.status_code == 403
    anonymous.close()


# Plan Step 36: the inherited-defaults marker read through the mounted topic settings
# route, not only inside PostgreSQL (database/test_chain_upgrade.py).


def test_topic_settings_route_marks_inherited_defaults_without_a_saved_choice(mounted):
    owner = mounted.other_authority.account_id

    def saved_defaults(conn):
        return conn.execute(
            "SELECT defaults FROM personalization.settings WHERE account_id=%s", (owner,)
        ).fetchone()["defaults"]

    def write_defaults(value):
        mounted.transactions.run(
            "personalization",
            lambda conn: conn.execute(
                "UPDATE personalization.settings SET defaults=%s WHERE account_id=%s",
                (Jsonb(value), owner),
            ),
        )

    # The second owner is the conftest's shared account, which other suites may give a
    # language: arrange "no saved language or level" by removing only that choice, and
    # put the row back exactly as it was afterwards.
    original = mounted.transactions.run("personalization", saved_defaults)
    write_defaults({key: value for key, value in original.items() if key != "assistanceDefaults"})
    try:
        topic = follow(mounted.other)["topicId"]
        view = mounted.other.get(f"/api/v2/topics/{topic}/settings")
        assert view.status_code == 200, view.text
        preferences = view.json()["effectivePreferences"]
        assert preferences["usesDefaults"] is True
        assert (preferences["languageId"], preferences["presentationLevelId"]) == ("en", "standard")
    finally:
        write_defaults(original)
    assert mounted.transactions.run("personalization", saved_defaults) == original


def test_topic_settings_route_clears_the_defaults_marker_once_the_owner_chooses(mounted):
    before = settings_read(mounted.client)
    # The owner chooses the very values the defaults would give: the marker must follow
    # the saved choice, not the values.
    chosen = settings_update(
        mounted.client,
        before["revision"],
        assistanceDefaults=dict(
            ASSISTANCE_DEFAULTS, languageId="en", presentationLevelId="standard"
        ),
    )
    assert chosen.status_code == 200, chosen.text
    topic = follow(mounted.client)["topicId"]
    view = mounted.client.get(f"/api/v2/topics/{topic}/settings")
    assert view.status_code == 200, view.text
    preferences = view.json()["effectivePreferences"]
    assert preferences["usesDefaults"] is False
    assert (preferences["languageId"], preferences["presentationLevelId"]) == ("en", "standard")
