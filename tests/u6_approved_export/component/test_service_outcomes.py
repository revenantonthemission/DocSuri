"""Export service, outcomes: execute (press, continue, bind refusals), cancel, settle,
the effect and history reads, the error-code matrix and the zero-writes check."""

from uuid import UUID, uuid4

import pytest
from backend.modules.export.lane_store import WriteOutcome
from docsuri_shared.workspace import wire

from tests.u6_approved_export import notion_flows as nf
from tests.u6_approved_export import service_flows as sf
from tests.u6_approved_export import store_flows as flows

# A short check schedule, so a later check can end the scan budget (BR4.4).
SHORT_SCHEDULE = {
    "write_deadline_seconds": 1,
    "settling_wait_seconds": 1,
    "check_offsets_seconds": (1,),
    "check_hourly_seconds": 1,
    "check_hourly_until_seconds": 2,
    "check_late_interval_seconds": 1,
    "check_total_seconds": 3,
}


def page_reads(rig) -> int:
    return sum(1 for entry in rig.fake.requests if entry.path.startswith("/v1/pages/"))


def settle_value(effect: dict, disposition: str = "delivered", **extra) -> dict:
    return {
        "effectId": effect["effectId"],
        "expectedRevision": effect["revision"],
        "disposition": disposition,
        "assumptionAccepted": True,
        **extra,
    }


# -- execute -----------------------------------------------------------------------------


def test_execute_replays_and_tells_a_press_from_a_continue(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    key = uuid4()
    approval = rig.approve(rig.preview(rig.page()), key=key)
    reads = page_reads(rig)

    effect = rig.execute(approval, key=key)

    wire.ExportEffect.model_validate(effect)
    assert (effect["state"], effect["approvalId"]) == ("accepted", approval["approvalId"])
    assert page_reads(rig) == reads  # a press does not re-derive the binding
    assert rig.execute(approval, key=key) == effect
    rig.succeed(effect)
    later = rig.approve(rig.preview(rig.page()))
    reads, calls = page_reads(rig), len(rig.research.calls)
    continued = rig.execute(later)
    assert continued["state"] == "accepted"
    assert page_reads(rig) == reads + 1 and len(rig.research.calls) == calls + 1
    # The same key on another approval is CONFLICT.
    assert sf.refuse("execute", lambda: rig.execute(later, key=key)) == "CONFLICT"


def test_a_continue_under_a_stale_session_invalidates_and_requires_approval(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    other = flows.second_session(connect, authority)
    approval = rig.approve(rig.preview(rig.page()), authority=other)
    flows.end_session(connect, other)

    assert sf.refuse("execute", lambda: rig.execute(approval)) == "APPROVAL_REQUIRED"
    row = flows.approval_row(connect, UUID(approval["approvalId"]))
    assert (row["state"], row["invalidation_reason"]) == ("invalidated", "authority-revoked")
    assert sf.refuse("execute", lambda: rig.execute(approval)) == "APPROVAL_REQUIRED"


def test_bind_refusals_leave_the_approval_approved(transactions, connect, authority, tmp_path):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    page = rig.page()
    source = rig.research.ready()
    flight = rig.press(page, source)["effect"]
    waiting = rig.approve(rig.preview(rig.page()))

    assert sf.refuse("execute", lambda: rig.execute(waiting)) == "CAPACITY_EXHAUSTED"
    assert flows.approval_row(connect, UUID(waiting["approvalId"]))["state"] == "approved"
    rig.uncertain(flight)
    rig.clock.advance(1)
    again = rig.approve(rig.preview(page, source))
    assert sf.refuse("execute", lambda: rig.execute(again)) == "OUTCOME_UNKNOWN"
    assert flows.approval_row(connect, UUID(again["approvalId"]))["state"] == "approved"
    assert rig.execute(waiting)["state"] == "accepted"


def test_continuing_an_older_approval_after_a_newer_success_is_conflict(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    page = rig.page()
    source = rig.research.ready()
    older = rig.approve(rig.preview(page, source))
    rig.clock.advance(1)
    newer = rig.press(page, source)
    rig.clock.advance(1)
    rig.succeed(newer["effect"])

    code, error = sf.refusal(lambda: rig.execute(older))

    assert code == "CONFLICT" and error.current == {"field": "newerExport"}
    assert flows.approval_row(connect, UUID(older["approvalId"]))["state"] == "approved"


def test_the_hourly_limit_carries_the_seconds_until_the_oldest_bind_leaves(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path, policy=nf.policy(binds_per_window=2))
    rig.configure()
    rig.succeed(rig.press(rig.page())["effect"])
    rig.clock.advance(10)
    rig.succeed(rig.press(rig.page())["effect"])
    rig.clock.advance(20)
    approval = rig.approve(rig.preview(rig.page()))

    code, error = sf.refusal(lambda: rig.execute(approval))

    assert code == "CAPACITY_EXHAUSTED"
    assert error.retry_after == rig.policy.binds_window_seconds - 30
    assert flows.approval_row(connect, UUID(approval["approvalId"]))["state"] == "approved"


# -- cancel ------------------------------------------------------------------------------


def test_cancel_works_before_the_write_and_refuses_after_it(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()

    def cancel(approval, revision):
        value = {"approvalId": approval["approvalId"], "expectedRevision": str(revision)}
        return rig.service.cancel(authority, value)

    approved = rig.approve(rig.preview(rig.page()))
    assert sf.refuse("cancel", lambda: cancel(approved, 2)) == "CONFLICT"
    assert cancel(approved, 1)["state"] == "cancelled"
    pressed = rig.press(rig.page())
    effect = pressed["effect"]
    kept = cancel(pressed["approval"], effect["revision"])
    assert kept["state"] == "consumed"
    ended = rig.read_effect(effect)
    assert (ended["state"], ended["outcomeReason"]) == ("cancelled", "owner-cancelled")
    started = rig.press(rig.page())
    claimed = rig.claim(started["effect"])
    revision = claimed.effect["revision"]
    assert sf.refuse("cancel", lambda: cancel(started["approval"], revision)) == "CONFLICT"
    unknown = rig.repo.record_write_outcome(
        claimed.effect["id"],
        claimed.attempt["id"],
        revision,
        WriteOutcome("uncertain"),
        now=rig.clock.now,
    )
    assert (
        sf.refuse("cancel", lambda: cancel(started["approval"], unknown["revision"]))
        == "OUTCOME_UNKNOWN"
    )


# -- settle ------------------------------------------------------------------------------


def unknown_effect(rig) -> dict:
    pressed = rig.press(rig.page())
    rig.uncertain(pressed["effect"])
    return rig.read_effect(pressed["effect"])


def test_settlement_is_offered_only_in_its_three_cases_after_the_settling_wait(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path, policy=nf.policy(**SHORT_SCHEDULE))
    rig.configure()
    first = unknown_effect(rig)
    assert first["settlementOffered"] is False and "nextCheckAt" in first
    assert (
        sf.refuse(
            "settle", lambda: rig.service.settle(authority, settle_value(first), operation=uuid4())
        )
        == "CONFLICT"
    )
    rig.clock.advance(2)
    assert rig.read_effect(first)["settlementOffered"] is False
    rig.check(
        {"id": UUID(first["effectId"]), "revision": int(first["revision"])}, "listing-incomplete"
    )
    first = rig.read_effect(first)
    assert first["settlementOffered"] is True
    link = f"https://www.notion.so/workspace/Exported-{uuid4().hex}"
    key = uuid4()
    settled = rig.service.settle(authority, settle_value(first, remoteUrl=link), operation=key)
    assert (settled["state"], settled["settledBy"], settled["remoteUrl"]) == (
        "succeeded",
        "owner",
        link,
    )
    assert settled["outcomeReason"] == "owner-settled-delivered"
    again = settle_value(first, remoteUrl=link)
    assert rig.service.settle(authority, again, operation=key) == settled
    assert (
        sf.refuse("settle", lambda: rig.service.settle(authority, again, operation=uuid4()))
        == "CONFLICT"
    )

    stopped = unknown_effect(rig)
    rig.clock.advance(60)
    rig.check({"id": UUID(stopped["effectId"]), "revision": int(stopped["revision"])}, "not-found")
    stopped = rig.read_effect(stopped)
    assert stopped["settlementOffered"] is True and "nextCheckAt" not in stopped

    unreadable = unknown_effect(rig)
    rig.clock.advance(2)
    assert rig.read_effect(unreadable)["settlementOffered"] is False
    rig.service.disconnect(authority, {})
    unreadable = rig.read_effect(unreadable)
    assert unreadable["settlementOffered"] is True
    settled = rig.service.settle(
        authority, settle_value(unreadable, "not-delivered"), operation=uuid4()
    )
    assert (settled["state"], settled["outcomeReason"]) == (
        "failed",
        "owner-settled-not-delivered",
    )


@pytest.mark.parametrize(
    "link",
    [
        "http://www.notion.so/Page-0123456789abcdef0123456789abcdef",
        "https://example.org/Page-0123456789abcdef0123456789abcdef",
        "https://www.notion.so/page-without-an-id",
        "https://user@www.notion.so/0123456789abcdef0123456789abcdef",
        "https://www.notion.so:8443/0123456789abcdef0123456789abcdef",
        "not a link",
    ],
)
def test_a_settlement_link_must_be_a_notion_page_link(
    transactions, connect, authority, tmp_path, link
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    value = settle_value({"effectId": str(uuid4()), "revision": "1"}, remoteUrl=link)
    assert (
        sf.refuse("settle", lambda: rig.service.settle(authority, value, operation=uuid4()))
        == "INVALID_ARGUMENT"
    )


def test_settle_refuses_a_missing_assumption_and_a_link_on_not_delivered(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    effect = {"effectId": str(uuid4()), "revision": "1"}
    link = f"https://team.notion.site/Page-{uuid4().hex}"
    for value in (
        settle_value(effect, assumptionAccepted=False),
        settle_value(effect, "not-delivered", remoteUrl=link),
        settle_value(effect, "maybe"),
    ):
        assert (
            sf.refuse("settle", lambda v=value: rig.service.settle(authority, v, operation=uuid4()))
            == "INVALID_ARGUMENT"
        )
    # A valid link on a foreign or absent effect answers not-found.
    assert (
        sf.refuse(
            "settle",
            lambda: rig.service.settle(
                authority, settle_value(effect, remoteUrl=link), operation=uuid4()
            ),
        )
        == "NOT_FOUND"
    )


# -- reads -------------------------------------------------------------------------------


def test_history_pages_newest_first_with_continuable_and_possible_duplicates(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path, policy=nf.policy(**SHORT_SCHEDULE))
    rig.configure()
    marked = unknown_effect(rig)
    duplicate = {"remoteReference": uuid4().hex, "remoteUrl": "https://www.notion.so/dup"}
    rig.clock.advance(1)
    rig.check(
        {"id": UUID(marked["effectId"]), "revision": int(marked["revision"])},
        "marker-found",
        remote_reference=uuid4().hex,
        remote_url="https://www.notion.so/found",
        other_marked_pages=[duplicate],
    )
    rig.clock.advance(1)
    open_approval = rig.approve(rig.preview(rig.page()))
    rig.clock.advance(1)
    other = flows.second_session(connect, authority)
    stale = rig.approve(rig.preview(rig.page()), authority=other)
    flows.end_session(connect, other)

    first = rig.service.history(authority, {"limit": 2})
    rest = rig.service.history(authority, {"limit": 2, "cursor": first["nextCursor"]})

    wire.ExportHistoryPage.model_validate(first)
    wire.ExportHistoryPage.model_validate(rest)
    order = [entry["approvalId"] for entry in first["entries"] + rest["entries"]]
    assert order == [stale["approvalId"], open_approval["approvalId"], marked["approvalId"]]
    assert rest["nextCursor"] is None
    by_id = {entry["approvalId"]: entry for entry in first["entries"] + rest["entries"]}
    assert by_id[open_approval["approvalId"]]["continuable"] is True
    assert by_id[stale["approvalId"]]["continuable"] is False
    exported = by_id[marked["approvalId"]]
    assert exported["effect"]["state"] == "succeeded" and "endedAt" in exported
    assert exported["effect"]["possibleDuplicates"] == [duplicate]
    assert exported["destinationTitle"] == "합성 페이지"
    found = rig.read_effect(marked)
    assert (found["settledBy"], found["remoteUrl"]) == (
        "reconciliation",
        "https://www.notion.so/found",
    )
    assert sf.refuse("history", lambda: rig.service.history(authority, {"cursor": "%%"})) == (
        "INVALID_ARGUMENT"
    )


# -- the error-code matrix and the zero-writes check -----------------------------------


def test_every_refusal_lies_in_its_operations_own_list(
    transactions, connect, authority, authority_b, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    service, absent = rig.service, str(uuid4())
    key = uuid4()
    view = rig.configure(key=key)
    pressed = rig.press(rig.page())
    effect, approval = pressed["effect"], pressed["approval"]
    cancelled = rig.approve(rig.preview(rig.page()))
    service.cancel(authority, {"approvalId": cancelled["approvalId"], "expectedRevision": "1"})
    foreign = {"connectionId": view["connectionId"]}
    cases = {
        "configure": [
            lambda: rig.configure(token=" "),
            lambda: rig.configure(token="unknown", expected=1),
            lambda: rig.configure(expected=7),
            lambda: rig.configure(key=key, expected=1),
        ],
        "read_connection": [
            lambda: service.read_connection(authority_b, foreign),
            lambda: service.read_connection(authority, {"connectionId": "x"}),
        ],
        "disconnect": [lambda: service.disconnect(authority_b, foreign)],
        "list_destinations": [lambda: service.list_destinations(authority_b, foreign)],
        "prepare_preview": [
            lambda: service.prepare_preview(authority_b, rig.preview_value(rig.page())),
            lambda: service.prepare_preview(
                authority, {**rig.preview_value(rig.page()), "destination": {"parentPageId": 1}}
            ),
        ],
        "approve": [
            lambda: rig.approve(pressed["preview"], authority=authority_b),
            lambda: rig.approve({**pressed["preview"], "previewId": absent}),
        ],
        "execute": [
            lambda: rig.execute(approval, authority=authority_b),
            lambda: rig.execute({**cancelled, "bindingHash": "0" * 64}),
            lambda: rig.execute(cancelled),
        ],
        "read_effect": [lambda: service.read_effect(authority_b, {"effectId": effect["effectId"]})],
        "cancel": [
            lambda: service.cancel(
                authority_b, {"approvalId": approval["approvalId"], "expectedRevision": "1"}
            ),
            lambda: service.cancel(
                authority, {"approvalId": approval["approvalId"], "expectedRevision": "9"}
            ),
        ],
        "history": [lambda: service.history(authority, {"limit": 0})],
        "settle": [
            lambda: service.settle(authority_b, settle_value(effect), operation=uuid4()),
            lambda: service.settle(authority, settle_value(effect), operation=uuid4()),
        ],
    }
    seen = {name: {sf.refuse(name, call) for call in calls} for name, calls in cases.items()}

    assert set(seen) == set(sf.OPERATION_ERRORS)
    assert seen["configure"] == {
        "INVALID_ARGUMENT",
        "INVALID_TOKEN",
        "CONFLICT",
        "IDEMPOTENCY_CONFLICT",
    }
    assert seen["execute"] == {"NOT_FOUND", "CONFLICT", "APPROVAL_REQUIRED"}
    assert rig.fake.writes == []


def test_no_operation_but_the_lane_writes_to_notion(transactions, connect, authority, tmp_path):
    rig = sf.build(transactions, connect, authority, tmp_path)
    service = rig.service
    rig.configure()
    service.read_connection(authority, {})
    service.list_destinations(authority, {})
    pressed = rig.press(rig.page())
    effect = pressed["effect"]
    rig.read_effect(effect)
    service.history(authority, {})
    service.cancel(
        authority,
        {"approvalId": pressed["approval"]["approvalId"], "expectedRevision": effect["revision"]},
    )
    sf.refusal(lambda: service.settle(authority, settle_value(effect), operation=uuid4()))
    service.disconnect(authority, {})

    assert rig.fake.writes == []
    assert {entry.method for entry in rig.fake.requests if entry.path == "/v1/pages"} == set()
