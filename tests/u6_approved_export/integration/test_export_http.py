"""Mounted C09 routes over the realm: every operation through the shared browser boundary,
with session cookie, Origin, CSRF and Idempotency-Key, real session verification and
the real service over the fake Notion."""

import logging
from uuid import UUID, uuid4

import pytest
from backend.modules.export.fake_notion import Answer
from docsuri_shared.workspace import wire

from tests.u6_approved_export import http_flows as hf
from tests.u6_approved_export import notion_flows as nf
from tests.u6_approved_export import store_flows as flows

# A short check schedule, so settlement is offered within the test (BR4.5).
SHORT_SCHEDULE = {
    "write_deadline_seconds": 1,
    "settling_wait_seconds": 1,
    "check_offsets_seconds": (1,),
    "check_hourly_seconds": 1,
    "check_hourly_until_seconds": 2,
    "check_late_interval_seconds": 1,
    "check_total_seconds": 3,
}


@pytest.fixture
def mount(realm, transactions, connect, authority, authority_b, tmp_path):
    opened = []

    def build(**options):
        mounted = hf.mount(realm, transactions, connect, authority, authority_b, tmp_path, **options)
        opened.append(mounted)
        return mounted

    yield build
    for mounted in opened:
        mounted.close()


def stored_records(connect, account) -> str:
    """Every stored export record of the owner the runtime role may read, as text."""
    with connect("export") as conn:
        rows = [
            conn.execute(
                "SELECT id,revision,state,workspace_name,workspace_id,connection_user_id,"
                "limitations FROM export.connection WHERE account_id=%s",
                (account,),
            ).fetchall(),
            conn.execute(
                "SELECT operation,operation_key,input_hash,response FROM export.replay_record "
                "WHERE account_id=%s",
                (account,),
            ).fetchall(),
        ]
    return repr(rows)


def test_every_operation_answers_through_its_route(mount):
    m = mount(policy=nf.policy(**SHORT_SCHEDULE))
    page = m.rig.page()

    connection = m.connect_owner()
    assert m.ok("read_connection", {}) == connection
    listing = m.ok("list_destinations", {})
    pressed = hf.press(m, page)
    effect = pressed["effect"]
    read = m.ok("read_effect", {"effectId": effect["effectId"]})
    history = m.ok("history", {"limit": 5})
    kept = m.ok(
        "cancel", {"approvalId": pressed["approval"]["approvalId"], "expectedRevision": "1"}
    )
    second = hf.press(m, m.rig.page())["effect"]
    m.rig.uncertain(second)
    m.rig.clock.advance(2)
    m.rig.check(m.rig.row(m.rig.read_effect(second)), "listing-incomplete")
    offered = m.ok("read_effect", {"effectId": second["effectId"]})
    settled = m.ok(
        "settle",
        {
            "effectId": second["effectId"],
            "expectedRevision": offered["revision"],
            "disposition": "not-delivered",
            "assumptionAccepted": True,
        },
    )
    disconnected = m.ok("disconnect", {})

    wire.ExportConnection.model_validate(connection)
    wire.ExportDestinations.model_validate(listing)
    wire.ExportPreview.model_validate(pressed["preview"])
    wire.ExportApproval.model_validate(pressed["approval"])
    wire.ExportEffect.model_validate(read)
    wire.ExportHistoryPage.model_validate(history)
    assert (connection["state"], connection["revision"]) == ("connected", "1")
    assert page in [entry["destinationId"] for entry in listing["destinations"]]
    assert (effect["state"], read["effectId"]) == ("accepted", effect["effectId"])
    assert pressed["approval"]["approvalId"] in [e["approvalId"] for e in history["entries"]]
    assert kept["state"] == "consumed"
    assert m.ok("read_effect", {"effectId": effect["effectId"]})["state"] == "cancelled"
    assert offered["settlementOffered"] is True
    assert (settled["state"], settled["settledBy"]) == ("failed", "owner")
    assert (disconnected["state"], disconnected["revision"]) == ("disconnected", "2")
    assert m.rig.fake.writes == []  # no route writes to Notion (BR2.2)


def test_each_refusal_lies_in_its_operations_list(mount):
    m = mount()
    # A well-formed CSRF header without a session: the route itself answers 401.
    anonymous = m.browser(None)
    anonymous.headers.update({"X-CSRF-Token": "0" * 64})
    m.connect_owner()
    pressed = hf.press(m, m.rig.page())
    approval = pressed["approval"]
    unconsumed = m.ok("prepare_preview", m.rig.preview_value(m.rig.page()))
    cancelled = m.ok("approve", m.rig.approval_value(unconsumed))
    m.ok("cancel", {"approvalId": cancelled["approvalId"], "expectedRevision": "1"})

    codes = {
        "configure": {
            m.refused("configure", m.configure_body(token=" ")),
            m.refused("configure", m.configure_body(token="unknown-token", expected=1)),
            m.refused("configure", m.configure_body(expected=7)),
        },
        "read_connection": {m.refused("read_connection", {"connectionId": "x"})},
        "list_destinations": {m.refused("list_destinations", {}, client=m.other)},
        "prepare_preview": {
            m.refused("prepare_preview", m.rig.preview_value(m.rig.page()), client=m.other)
        },
        "approve": {
            m.refused("approve", {**m.rig.approval_value(pressed["preview"]), "previewId": str(uuid4())})
        },
        "execute": {
            m.refused(
                "execute",
                {"approvalId": cancelled["approvalId"], "bindingHash": cancelled["bindingHash"]},
            )
        },
        "read_effect": {m.refused("read_effect", {"effectId": str(uuid4())})},
        "cancel": {
            m.refused("cancel", {"approvalId": approval["approvalId"], "expectedRevision": "9"})
        },
        "history": {m.refused("history", {"limit": 0})},
        "settle": {
            m.refused(
                "settle",
                {
                    "effectId": pressed["effect"]["effectId"],
                    "expectedRevision": pressed["effect"]["revision"],
                    "disposition": "delivered",
                    "assumptionAccepted": True,
                },
            )
        },
        "disconnect": {m.refused("disconnect", {}, client=anonymous)},
    }

    assert codes["configure"] == {"INVALID_ARGUMENT", "INVALID_TOKEN", "CONFLICT"}
    assert codes["read_connection"] == {"INVALID_ARGUMENT"}
    assert codes["execute"] == {"APPROVAL_REQUIRED"}
    assert codes["cancel"] == {"CONFLICT"}
    assert codes["settle"] == {"CONFLICT"}
    assert codes["disconnect"] == {"UNAUTHENTICATED"}
    anonymous.close()


def test_another_owners_records_answer_not_found(mount):
    m = mount()
    connection = m.connect_owner()
    pressed = hf.press(m, m.rig.page())
    approval, effect = pressed["approval"], pressed["effect"]
    foreign = {"connectionId": connection["connectionId"]}

    refusals = [
        m.refused("read_connection", foreign, client=m.other),
        m.refused("list_destinations", foreign, client=m.other),
        m.refused("disconnect", foreign, client=m.other),
        m.refused("read_effect", {"effectId": effect["effectId"]}, client=m.other),
        m.refused(
            "cancel",
            {"approvalId": approval["approvalId"], "expectedRevision": effect["revision"]},
            client=m.other,
        ),
        m.refused(
            "execute",
            {"approvalId": approval["approvalId"], "bindingHash": approval["bindingHash"]},
            client=m.other,
        ),
        m.refused("approve", m.rig.approval_value(pressed["preview"]), client=m.other),
    ]

    assert set(refusals) == {"NOT_FOUND"}
    assert m.ok("read_connection", {}) == connection
    assert m.ok("read_effect", {"effectId": effect["effectId"]})["state"] == "accepted"
    assert m.ok("history", {}, client=m.other)["entries"] == []


def test_replays_return_the_original(mount):
    m = mount()
    key = uuid4()
    first = m.ok("configure", m.configure_body(), key=key)
    again = m.ok("configure", m.configure_body(), key=key)
    other_token, _ = m.rig.new_token()
    with_other_token = m.ok("configure", m.configure_body(token=other_token), key=key)
    preview = m.ok("prepare_preview", m.rig.preview_value(m.rig.page()))
    press_key = uuid4()
    approval = m.ok("approve", m.rig.approval_value(preview), key=press_key)
    approval_again = m.ok("approve", m.rig.approval_value(preview), key=press_key)
    body = {"approvalId": approval["approvalId"], "bindingHash": approval["bindingHash"]}
    effect = m.ok("execute", body, key=press_key)
    effect_again = m.ok("execute", body, key=press_key)
    # The approval's replay after the press reads it as it now is: consumed.
    consumed = m.ok("approve", m.rig.approval_value(preview), key=press_key)

    assert again == first == with_other_token
    assert m.refused("configure", m.configure_body(expected=1), key=key) == "IDEMPOTENCY_CONFLICT"
    assert approval_again == approval
    assert {**consumed, "state": "approved"} == approval and consumed["state"] == "consumed"
    assert effect_again == effect
    assert m.ok("read_connection", {})["revision"] == "1"


def test_a_configure_body_that_fails_validation_is_not_echoed(mount):
    m = mount()
    secret = "synthetic-notion-token-" + uuid4().hex
    bodies = [
        {**m.configure_body(token=secret), "extra": secret},
        {"token": secret, "credentialPolicy": m.rig.policy.reference()},
        {**m.configure_body(token=secret), "credentialPolicy": secret},
    ]
    responses = [m.post("configure", body) for body in bodies]
    duplicated = m.client.post(
        hf.PREFIX + hf.ROUTE["configure"],
        content=('{"token":"%s","token":"%s"}' % (secret, secret)).encode(),
        headers={"Idempotency-Key": str(uuid4()), "Content-Type": "application/json"},
    )
    responses.append(duplicated)

    for response in responses:
        assert (response.status_code, response.json()["code"]) == (422, "INVALID_ARGUMENT")
        assert secret not in response.text
        assert set(response.json()) <= {"code", "requestId", "retryable", "messageKey"}
    assert m.refused("read_connection", {}) == "NOT_FOUND"


def test_no_token_appears_in_any_response_or_stored_record_after_failures(
    mount, connect, caplog
):
    m = mount()
    caplog.set_level(logging.DEBUG)
    responses = []
    m.rig.fake.queue("users.me", Answer.error(500))
    responses.append(m.post("configure", m.configure_body()))
    responses.append(m.post("configure", m.configure_body(token="synthetic-unknown-" + uuid4().hex)))
    connection = m.connect_owner()
    replacement, _ = m.rig.new_token()
    m.rig.fake.queue("users.me", Answer.error(503))
    responses.append(m.post("configure", m.configure_body(replacement, expected=1)))
    responses.append(m.post("configure", m.configure_body("synthetic-bad-" + uuid4().hex, 1)))
    m.rig.fake.queue("search", Answer.error(401))
    responses.append(m.post("list_destinations", {}))

    texts = [response.text for response in responses]
    assert [response.status_code for response in responses] == [503, 422, 503, 422, 404]
    stored = stored_records(connect, m.authority.account_id)
    for token in (m.rig.token, replacement):
        assert all(token not in text for text in texts)
        assert token not in stored
        assert token not in caplog.text
    revoked = flows.connection_row(connect, UUID(connection["connectionId"]))
    assert (revoked["state"], revoked["revision"]) == ("revoked", 2)


def test_a_bad_candidate_while_connected_leaves_the_connection_unchanged(mount, connect):
    m = mount()
    connection = m.connect_owner()
    before = flows.connection_row(connect, UUID(connection["connectionId"]))

    code = m.refused("configure", m.configure_body("synthetic-bad-" + uuid4().hex, expected=1))

    assert code == "INVALID_TOKEN"
    assert m.ok("read_connection", {}) == connection
    assert flows.connection_row(connect, UUID(connection["connectionId"])) == before
    assert m.ok("list_destinations", {})["listingComplete"] is True  # the stored token works


def test_the_hourly_limit_answers_429_with_the_wait_in_the_body(mount):
    m = mount(policy=nf.policy(binds_per_window=1))
    m.connect_owner()
    first = hf.press(m, m.rig.page())
    m.ok(
        "cancel",
        {
            "approvalId": first["approval"]["approvalId"],
            "expectedRevision": first["effect"]["revision"],
        },
    )
    m.rig.clock.advance(30)
    preview = m.ok("prepare_preview", m.rig.preview_value(m.rig.page()))
    key = uuid4()
    approval = m.ok("approve", m.rig.approval_value(preview), key=key)

    response = m.post(
        "execute",
        {"approvalId": approval["approvalId"], "bindingHash": approval["bindingHash"]},
        key=key,
    )

    assert response.status_code == 429
    body = response.json()
    assert body["code"] == "CAPACITY_EXHAUSTED"
    assert body["retryAfterSeconds"] == m.rig.policy.binds_window_seconds - 30
    assert "retry-after" not in {name.lower() for name in response.headers}
    assert response.headers["cache-control"] == "no-store"
    assert m.ok("history", {})["entries"][0]["state"] == "approved"
