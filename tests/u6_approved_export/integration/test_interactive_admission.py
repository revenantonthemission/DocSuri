"""D15 through the routes: with the fake Notion hanging, browser-driven Notion operations
are capped at two per process and one per connection, and refused at once beyond either
cap; other routes and the export lane keep working."""

import threading
import time
from uuid import UUID

import pytest
from backend.modules.export.fake_notion import HANG, Answer
from backend.modules.export.lane import ExportLane, LaneItem

from tests.u6_approved_export import http_flows as hf
from tests.u6_approved_export import lane_flows as lf
from tests.u6_approved_export import notion_flows as nf
from tests.u6_approved_export import store_flows as flows

# A hanging answer holds its slot for this long, then its own budget ends it.
HOLD_SECONDS = 3
SHORT_BUDGETS = {
    "listing_budget_seconds": HOLD_SECONDS,
    "page_read_budget_seconds": HOLD_SECONDS,
    "token_check_budget_seconds": HOLD_SECONDS,
    "read_timeout_seconds": HOLD_SECONDS,
}
# A refusal at the gate never waits on Notion.
AT_ONCE_SECONDS = 1.0


@pytest.fixture
def mount(realm, transactions, connect, authority, authority_b, tmp_path):
    opened = []

    def build(**policy):
        mounted = hf.mount(
            realm,
            transactions,
            connect,
            authority,
            authority_b,
            tmp_path,
            policy=nf.policy(**SHORT_BUDGETS, **policy),
        )
        opened.append(mounted)
        return mounted

    yield build
    for mounted in opened:
        mounted.close()


class Background:
    """One request in its own thread and its own browser, whose answer is kept."""

    def __init__(self, m, session, operation: str, body: dict):
        self.client = m.browser(session)
        self.answer = None
        self.thread = threading.Thread(target=self._run, args=(m, operation, body))
        self.thread.start()

    def _run(self, m, operation, body):
        self.answer = m.post(operation, body, client=self.client)

    def join(self):
        self.thread.join(HOLD_SECONDS * 10)
        self.client.close()
        return self.answer


def timed(call):
    started = time.monotonic()
    response = call()
    return response, time.monotonic() - started


def connect_both(m) -> tuple[dict, dict]:
    own = m.connect_owner()
    token, _ = m.rig.new_token()
    other = m.connect_owner(client=m.other, token=token)
    return own, other


def preview_body(m, page: str, connection: dict) -> dict:
    return {
        "source": m.rig.research.ready(),
        "destination": m.rig.destination(page, connection),
        "renderPolicy": m.rig.policy.reference(),
    }


def unavailable_listing(response) -> bool:
    body = response.json()
    return (
        response.status_code == 200
        and body["destinations"] == []
        and body["listingComplete"] is False
    )


def test_two_owners_hold_the_process_slots_and_a_third_request_is_refused_at_once(
    mount, transactions, connect
):
    m = mount()
    own, other = connect_both(m)
    own_page, other_page = m.rig.page(), m.rig.page()
    pressed = hf.press(m, own_page)  # done before anything hangs
    m.rig.fake.queue("search", Answer.of(HANG))
    m.rig.fake.queue("pages.retrieve", Answer.of(HANG), target=other_page)

    listing = Background(m, m.own, "list_destinations", {})
    preview = Background(m, m.other_session, "prepare_preview", preview_body(m, other_page, other))
    lf.wait_for(lambda: m.rig.gate.held == 2, seconds=HOLD_SECONDS)

    third_preview, preview_seconds = timed(
        lambda: m.post("prepare_preview", preview_body(m, own_page, own))
    )
    third_listing, listing_seconds = timed(
        lambda: m.post("list_destinations", {}, client=m.other)
    )
    replacement, _ = m.rig.new_token()
    third_configure, configure_seconds = timed(
        lambda: m.post("configure", m.configure_body(replacement, expected=1), client=m.other)
    )
    reads, read_seconds = timed(
        lambda: [
            m.post("read_connection", {}),
            m.post("history", {}),
            m.post("read_effect", {"effectId": pressed["effect"]["effectId"]}),
        ]
    )
    asked = len(m.rig.gate.asked)
    lane = ExportLane(
        m.rig.repo, m.rig.service.adapter, m.rig.service.binding, policy=m.rig.policy,
        clock=m.rig.clock,
    )
    lane.start()
    try:
        effect = pressed["effect"]
        assert lane.offer(LaneItem("execute", UUID(effect["effectId"]), int(effect["revision"])))
        lf.wait_for(
            lambda: flows.effect_row(connect, UUID(effect["effectId"]))["state"] == "succeeded",
            seconds=HOLD_SECONDS,
        )
    finally:
        assert lane.stop()
    held_during_lane = m.rig.gate.held
    first_listing, first_preview = listing.join(), preview.join()

    assert (third_preview.status_code, third_preview.json()["code"]) == (
        503,
        "DEPENDENCY_UNAVAILABLE",
    )
    assert unavailable_listing(third_listing)
    assert (third_configure.status_code, third_configure.json()["code"]) == (
        503,
        "DEPENDENCY_UNAVAILABLE",
    )
    assert max(preview_seconds, listing_seconds, configure_seconds) < AT_ONCE_SECONDS
    assert [response.status_code for response in reads] == [200, 200, 200]
    assert read_seconds < AT_ONCE_SECONDS
    assert len(m.rig.gate.asked) == asked  # the lane never takes a slot
    assert held_during_lane == 2
    assert m.ok("read_connection", {}, client=m.other) == other  # the replace stored nothing
    assert first_listing.status_code == 200 and first_listing.json()["listingComplete"] is False
    assert (first_preview.status_code, first_preview.json()["code"]) == (
        503,
        "DEPENDENCY_UNAVAILABLE",
    )
    assert m.rig.gate.held == 0


def test_a_second_listing_on_one_connection_is_refused_while_a_process_slot_is_free(mount):
    m = mount()
    m.connect_owner()
    m.rig.fake.queue("search", Answer.of(HANG))

    holding = Background(m, m.own, "list_destinations", {})
    lf.wait_for(lambda: m.rig.gate.held == 1, seconds=HOLD_SECONDS)
    second, seconds = timed(lambda: m.post("list_destinations", {}))
    preview, preview_seconds = timed(
        lambda: m.post("prepare_preview", m.rig.preview_value(m.rig.page()))
    )
    held = m.rig.gate.held
    holding.join()

    assert held == 1 < m.rig.policy.interactive_per_process
    assert unavailable_listing(second)
    assert (preview.status_code, preview.json()["code"]) == (503, "DEPENDENCY_UNAVAILABLE")
    assert max(seconds, preview_seconds) < AT_ONCE_SECONDS
    assert m.ok("list_destinations", {})["listingComplete"] is True


def test_a_refused_first_configure_releases_its_pending_row(mount, connect):
    m = mount(interactive_per_process=1)
    m.connect_owner()
    m.rig.fake.queue("search", Answer.of(HANG))

    holding = Background(m, m.own, "list_destinations", {})
    lf.wait_for(lambda: m.rig.gate.held == 1, seconds=HOLD_SECONDS)
    token, _ = m.rig.new_token()
    refused, seconds = timed(
        lambda: m.post("configure", m.configure_body(token), client=m.other)
    )
    rows_during = m.refused("read_connection", {}, client=m.other)
    holding.join()

    assert (refused.status_code, refused.json()["code"]) == (503, "DEPENDENCY_UNAVAILABLE")
    assert seconds < AT_ONCE_SECONDS
    assert rows_during == "NOT_FOUND"
    with connect("export") as conn:
        assert (
            conn.execute(
                "SELECT id FROM export.connection WHERE account_id=%s",
                (m.other_authority.account_id,),
            ).fetchall()
            == []
        )
    assert m.connect_owner(client=m.other, token=token)["state"] == "connected"
