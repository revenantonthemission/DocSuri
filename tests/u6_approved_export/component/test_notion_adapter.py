"""The Notion adapter over the real SDK, the fake Notion and the real store: the bound
write, read-back, scans, read retries, listings, revocation and custody (§7–§9)."""

import asyncio
import datetime as dt
import time
from uuid import uuid4

import httpx
import pytest
from backend.modules.export import notion_adapter as adapter_module
from backend.modules.export.classification import (
    COULD_NOT_CHECK,
    CREATED,
    OK,
    PROTECTION_UNAVAILABLE,
    REFUSAL_CONTENT_REJECTED,
    REFUSED,
    TOKEN_INVALID,
    UNCERTAIN,
)
from backend.modules.export.fake_notion import (
    LOST_AFTER_SUCCESS,
    SAVED_BUSY,
    TIMEOUT_AFTER_SUCCESS,
    Answer,
)
from backend.modules.export.notion_adapter import (
    LISTING_INCOMPLETE,
    LISTING_UNAVAILABLE,
    MARKER_FOUND,
    NOT_FOUND,
    BoundContent,
    NotionAdapter,
    ScanRequest,
    StoreContentPort,
)
from backend.modules.export.notion_session import InteractiveGate, NotionSession

from tests.u6_approved_export import notion_flows as nf


@pytest.fixture
def setup(transactions, connect, authority, tmp_path):
    policy = nf.policy()
    repo = nf.repository(transactions, policy)
    opener = nf.vault(tmp_path)
    token, bot = nf.synthetic_token(), nf.bot_id()
    fake = nf.fake_with(token, bot)
    target, connection = nf.stored_connection(repo, connect, authority, opener, token, user=bot)
    destination = fake.add_page(title="내보내기 대상")
    return {
        "policy": policy,
        "repo": repo,
        "vault": opener,
        "token": token,
        "bot": bot,
        "fake": fake,
        "target": target,
        "connection": connection,
        "destination": destination,
        "adapter": nf.adapter(repo, opener, fake, policy),
    }


def connection_state(connect, connection_id):
    with connect("export") as conn:
        return conn.execute(
            "SELECT state,revision FROM export.connection WHERE id=%s", (connection_id,)
        ).fetchone()


def scan_request(setup, marker, *, started=None, writers=None):
    return ScanRequest(
        uuid4(),
        setup["destination"],
        marker,
        frozenset(writers or {setup["bot"]}),
        started or nf.now() - dt.timedelta(minutes=1),
    )


def marked_page(fake, parent, marker, *, creator, created_time=None, extra_last=None):
    page = fake.add_page(
        title="내보낸 페이지", parent_id=parent, created_by=creator, created_time=created_time
    )
    fake.add_block(page, text="요약")
    fake.add_block(page, text=marker)
    if extra_last:
        fake.add_block(page, text=extra_last)
    return page


# -- the write ------------------------------------------------------------------------


async def test_the_written_body_hashes_to_the_bound_value(setup, authority):
    bound = nf.bound_effect(setup["repo"], authority, setup["connection"], setup["destination"])
    request = nf.write_request(bound, setup["connection"], setup["bot"])

    result = await setup["adapter"].create_page(setup["target"], request, deadline_seconds=5)

    fake = setup["fake"]
    assert result.category == CREATED and result.sent is True
    assert [entry.content_hash for entry in fake.writes] == [bound["preview"]["rendered_content_hash"]]
    assert fake.pages_under(setup["destination"]) == [result.outcome.remote_reference]
    assert result.outcome.creator_confirmed is True
    assert result.provider_result().disposition == "committed"
    assert result.provider_outcome().outcome == "succeeded"


class TamperedPort(StoreContentPort):
    def bound_content(self, effect_id):
        content = super().bound_content(effect_id)
        body = {**content.body, "children": [*content.body["children"][:-1]]}
        return BoundContent(body, content.content_hash, content.marker, content.destination_id)


async def test_a_content_mismatch_sends_nothing(setup, authority):
    bound = nf.bound_effect(setup["repo"], authority, setup["connection"], setup["destination"])
    elsewhere = nf.write_request(
        bound, setup["connection"], setup["bot"], destination_id=uuid4().hex
    )
    tampered = NotionAdapter(
        nf.session(setup["repo"], setup["vault"], setup["fake"], setup["policy"]),
        setup["repo"],
        content=TamperedPort(setup["repo"]),
    )

    moved = await setup["adapter"].create_page(setup["target"], elsewhere, deadline_seconds=5)
    altered = await tampered.create_page(
        setup["target"],
        nf.write_request(bound, setup["connection"], setup["bot"]),
        deadline_seconds=5,
    )

    for result in (moved, altered):
        assert result.category == REFUSED and result.refusal == REFUSAL_CONTENT_REJECTED
        assert result.sent is False and result.outcome.reason == REFUSAL_CONTENT_REJECTED
    assert setup["fake"].requests == []


@pytest.mark.parametrize("kind", [LOST_AFTER_SUCCESS, TIMEOUT_AFTER_SUCCESS])
async def test_a_response_lost_after_the_page_was_created_is_unknown(setup, authority, kind):
    bound = nf.bound_effect(setup["repo"], authority, setup["connection"], setup["destination"])
    setup["fake"].queue("pages.create", Answer.of(kind))

    result = await setup["adapter"].create_page(
        setup["target"],
        nf.write_request(bound, setup["connection"], setup["bot"]),
        deadline_seconds=5,
    )

    assert result.category == UNCERTAIN and result.provider_result().disposition == "unknown"
    assert len(setup["fake"].writes) == 1
    assert len(setup["fake"].pages_under(setup["destination"])) == 1


async def test_saved_but_busy_counts_as_created_only_after_its_read_back(setup, authority):
    bound = nf.bound_effect(setup["repo"], authority, setup["connection"], setup["destination"])
    request = nf.write_request(bound, setup["connection"], setup["bot"])
    setup["fake"].queue("pages.create", Answer.of(SAVED_BUSY))

    saved = await setup["adapter"].create_page(setup["target"], request, deadline_seconds=5)

    assert saved.category == CREATED
    assert saved.outcome.remote_reference == setup["fake"].pages_under(setup["destination"])[0]
    setup["fake"].queue("pages.create", Answer.error(503))
    unnamed = await setup["adapter"].create_page(setup["target"], request, deadline_seconds=5)
    assert unnamed.category == UNCERTAIN


async def test_read_back_passes_only_with_all_three_checks(setup):
    fake, adapter, bot = setup["fake"], setup["adapter"], setup["bot"]
    destination, marker = setup["destination"], "docsuri-export:v1:" + "a" * 32 + ":1"
    good = marked_page(fake, destination, marker, creator=bot)
    other_parent = fake.add_page(title="다른 곳")
    misplaced = marked_page(fake, other_parent, marker, creator=bot)
    foreign = marked_page(fake, destination, marker, creator=nf.bot_id())
    buried = marked_page(fake, destination, marker, creator=bot, extra_last="꼬리")

    async def check(page):
        return await adapter.read_back(
            setup["target"], page_id=page, destination_id=destination,
            writer_identity=bot, marker=marker,
        )

    results = [await check(page) for page in (good, misplaced, foreign, buried)]
    assert [result.passed for result in results] == [True, False, False, False]
    assert results[0].remote_url == f"https://www.notion.so/{good}"


async def test_a_refused_write_carries_its_class(setup, authority):
    bound = nf.bound_effect(setup["repo"], authority, setup["connection"], setup["destination"])
    setup["fake"].queue("pages.create", Answer.block_limit())
    result = await setup["adapter"].create_page(
        setup["target"],
        nf.write_request(bound, setup["connection"], setup["bot"]),
        deadline_seconds=5,
    )
    assert result.category == REFUSED and result.refusal == "workspace-block-limit"
    assert result.provider_result().refusalClass == "workspace-block-limit"


async def test_a_rate_limited_write_is_a_c12_retry_later(setup, authority):
    bound = nf.bound_effect(setup["repo"], authority, setup["connection"], setup["destination"])
    setup["fake"].queue("pages.create", Answer.overloaded(wait=7))
    result = await setup["adapter"].create_page(
        setup["target"],
        nf.write_request(bound, setup["connection"], setup["bot"]),
        deadline_seconds=5,
    )
    outcome = result.provider_outcome()
    assert result.outcome.response_class == "rate-limited" and result.retry_after_seconds == 7
    assert outcome.outcome == "retry_later" and outcome.retryAfterSeconds.root == 7
    assert result.provider_result() is None and len(setup["fake"].writes) == 1


# -- scans ----------------------------------------------------------------------------


async def test_a_scan_finds_the_marker_inside_containers_and_reports_duplicates(setup):
    fake, bot, destination = setup["fake"], setup["bot"], setup["destination"]
    marker = "docsuri-export:v1:" + "b" * 32 + ":1"
    toggle = fake.add_block(destination, "toggle", text="접기")
    columns = fake.add_block(destination, "column_list")
    column = fake.add_block(columns, "column")
    earlier = nf.now() - dt.timedelta(minutes=2)  # Notion times are minute-rounded
    first = marked_page(fake, toggle, marker, creator=bot, created_time=earlier)
    second = marked_page(fake, column, marker, creator=bot)
    marked_page(fake, destination, marker, creator=nf.bot_id())
    marked_page(fake, destination, marker, creator=bot, created_time=nf.now() - dt.timedelta(days=1))

    scan = await setup["adapter"].scan(setup["target"], scan_request(setup, marker))

    assert scan.result == MARKER_FOUND and scan.check.remote_reference == first
    assert scan.check.other_marked_pages == [
        {"remoteReference": second, "remoteUrl": f"https://www.notion.so/{second}"}
    ]
    assert scan.evidence.disposition == "committed" and scan.evidence.scanComplete is True


async def test_a_complete_scan_with_no_marker_is_not_found(setup):
    marked_page(setup["fake"], setup["destination"], "another marker", creator=setup["bot"])
    scan = await setup["adapter"].scan(setup["target"], scan_request(setup, "the marker"))
    assert scan.result == NOT_FOUND and scan.evidence.disposition == "unknown"
    assert scan.check.remote_reference is None and len(scan.check.evidence_hash) == 64


async def test_a_partial_scan_is_listing_incomplete(setup):
    toggle = setup["fake"].add_block(setup["destination"], "toggle", text="접기")
    setup["fake"].add_block(toggle, text="안쪽")
    setup["fake"].queue("blocks.children", Answer.error(500), target=toggle)
    scan = await setup["adapter"].scan(setup["target"], scan_request(setup, "m"))
    assert scan.result == LISTING_INCOMPLETE and scan.evidence.scanComplete is False


async def test_an_unreadable_destination_is_listing_unavailable(setup):
    hidden = setup["fake"].add_page(title="비공개", readable=False)
    request = ScanRequest(uuid4(), hidden, "m", frozenset({setup["bot"]}), nf.now())
    scan = await setup["adapter"].scan(setup["target"], request)
    assert scan.result == LISTING_UNAVAILABLE


# -- read retries ---------------------------------------------------------------------


async def test_a_429_that_is_not_blocked_is_retried_and_succeeds(setup):
    setup["fake"].queue("users.me", Answer.rate_limited(wait=0))
    result = await setup["adapter"].identify(setup["target"])
    assert result.category == OK and len(setup["fake"].requests) == 2


async def test_spent_retries_give_could_not_check_and_a_scan_listing_incomplete(setup):
    for _ in range(4):
        setup["fake"].queue("users.me", Answer.overloaded(wait=0))
        setup["fake"].queue("blocks.children", Answer.rate_limited(wait=0))
    identity = await setup["adapter"].identify(setup["target"])
    scan = await setup["adapter"].scan(setup["target"], scan_request(setup, "m"))
    assert identity.category == COULD_NOT_CHECK and scan.result == LISTING_INCOMPLETE
    assert len(setup["fake"].requests) == 8


async def test_a_stated_wait_past_the_budget_stops_at_once(setup):
    adapter = nf.adapter(
        setup["repo"], setup["vault"], setup["fake"],
        nf.policy(read_timeout_seconds=2, token_check_budget_seconds=2),
    )
    setup["fake"].queue("users.me", Answer.rate_limited(wait=30))
    started = time.monotonic()
    result = await adapter.identify(setup["target"])
    assert result.category == COULD_NOT_CHECK and time.monotonic() - started < 1.5
    assert len(setup["fake"].requests) == 1


async def test_a_blocked_429_is_never_retried(setup):
    setup["fake"].queue("users.me", Answer.rate_limited(wait=0, blocked=True))
    result = await setup["adapter"].identify(setup["target"])
    assert result.category == COULD_NOT_CHECK and len(setup["fake"].requests) == 1


@pytest.mark.parametrize(("pace_ms", "stated", "least"), [(400, 0, 0.35), (1, 1, 0.95)])
async def test_each_retry_waits_for_the_later_of_the_stated_wait_and_the_pace(
    setup, transactions, pace_ms, stated, least
):
    # The pace interval is the store's policy value: both sides use the same policy.
    paced = nf.policy(pace_interval_ms=pace_ms)
    adapter = nf.adapter(nf.repository(transactions, paced), setup["vault"], setup["fake"], paced)
    setup["fake"].queue("users.me", Answer.rate_limited(wait=stated))
    await asyncio.sleep(pace_ms / 1000)  # start from a free slot
    result = await adapter.identify(setup["target"])
    first, second = setup["fake"].requests
    assert result.category == OK and second.at - first.at >= least


# -- listings -------------------------------------------------------------------------


async def test_search_pages_are_joined_with_entries_as_derived(setup):
    fake = setup["fake"]
    parent = fake.add_page(title="상위")
    titled = fake.add_page(title="같은 제목", parent_id=parent)
    same = fake.add_page(title="같은 제목")
    untitled = fake.add_page()
    fake.set_search("complete", page_size=2)

    listing = await setup["adapter"].list_destinations(setup["target"])

    entries = {entry.destination_id: entry for entry in listing.destinations}
    assert listing.category == OK and listing.complete is True
    assert set(entries) == {setup["destination"], parent, titled, same, untitled}
    assert entries[untitled].title is None
    assert entries[titled].context == "상위 페이지: 상위"
    assert entries[same].context == "워크스페이스 최상위"
    assert all(e.readable is None and e.writable and e.creation_capability == "unknown"
               for e in entries.values())


async def test_a_page_cap_or_spent_retries_leave_the_listing_incomplete(setup, monkeypatch):
    fake = setup["fake"]
    for index in range(3):
        fake.add_page(title=f"페이지 {index}")
    fake.set_search("complete", page_size=2)
    monkeypatch.setattr(adapter_module, "MAX_SEARCH_PAGES", 1)
    capped = await setup["adapter"].list_destinations(setup["target"])
    monkeypatch.setattr(adapter_module, "MAX_SEARCH_PAGES", 10)
    fake.set_search("partial", page_size=2)
    partial = await setup["adapter"].list_destinations(setup["target"])
    for _ in range(4):
        fake.queue("search", Answer.rate_limited(wait=0))
    spent = await setup["adapter"].list_destinations(setup["target"])

    assert capped.complete is False and len(capped.destinations) == 2
    assert partial.complete is False and len(partial.destinations) == 2
    assert spent.complete is False and spent.destinations == ()


async def test_the_last_destination_is_read_directly_and_capability_drives_writable(setup):
    fake, destination = setup["fake"], setup["destination"]
    hidden = fake.add_page(title="읽을 수 없음", readable=False)

    readable = await setup["adapter"].list_destinations(
        setup["target"], last_destination_id=destination, creation_capability="confirmed"
    )
    unreadable = await setup["adapter"].list_destinations(
        setup["target"], last_destination_id=hidden, creation_capability="refused"
    )

    entry = {e.destination_id: e for e in readable.destinations}[destination]
    assert readable.last_destination_readable is True and entry.readable is True
    assert entry.writable is True and entry.creation_capability == "confirmed"
    hidden_entry = {e.destination_id: e for e in unreadable.destinations}[hidden]
    assert unreadable.last_destination_readable is False
    assert hidden_entry.readable is False and hidden_entry.writable is False
    assert all(e.writable is False for e in unreadable.destinations)
    reads = [e.path for e in fake.requests if e.method == "GET" and e.path.startswith("/v1/pages/")]
    assert reads == [f"/v1/pages/{destination}", f"/v1/pages/{hidden}"]


# -- revocation and custody ---------------------------------------------------------------


class ReplacingTransport(httpx.AsyncBaseTransport):
    """Replaces the owner's token after the scan opened the old one, then answers."""

    def __init__(self, fake, replace):
        self._fake, self._replace, self.replaced = fake, replace, False

    async def handle_async_request(self, request):
        if not self.replaced:
            self.replaced = True
            await asyncio.to_thread(self._replace)
        return await self._fake.handle_async_request(request)

    async def aclose(self):
        return None


async def test_a_401_from_an_old_token_after_a_replace_does_not_revoke(setup, connect, authority):
    repo, fake = setup["repo"], setup["fake"]
    new_token = nf.synthetic_token()
    transport = ReplacingTransport(
        fake,
        lambda: nf.replace_token(repo, authority, setup["vault"], new_token, user=setup["bot"]),
    )
    session = NotionSession(
        store=repo, vault=setup["vault"], policy=setup["policy"],
        gate=InteractiveGate.for_policy(setup["policy"]), transport_factory=lambda: transport,
    )
    fake.queue("blocks.children", Answer.error(401))

    scan = await NotionAdapter(session, repo).scan(setup["target"], scan_request(setup, "m"))

    assert scan.result == LISTING_UNAVAILABLE and scan.revoked is False
    row = connection_state(connect, setup["connection"]["id"])
    assert row["state"] == "connected" and row["revision"] == setup["connection"]["revision"] + 1


async def test_a_401_on_the_stored_token_revokes_by_its_opened_revision(setup, connect):
    setup["fake"].queue("users.me", Answer.error(401))
    result = await setup["adapter"].identify(setup["target"])
    row = connection_state(connect, setup["connection"]["id"])
    assert result.category == TOKEN_INVALID and result.revoked is True
    assert row["state"] == "revoked" and row["revision"] == setup["connection"]["revision"] + 1


async def test_a_custody_fault_makes_the_connection_unavailable_and_recovery_reconnects(
    setup, connect, tmp_path
):
    other = tmp_path / "elsewhere"
    other.mkdir()
    stranger = nf.adapter(setup["repo"], nf.vault(other), setup["fake"], setup["policy"])
    faulted = await stranger.identify(setup["target"])
    unavailable = connection_state(connect, setup["connection"]["id"])
    recovered = await setup["adapter"].identify(setup["target"])
    connected = connection_state(connect, setup["connection"]["id"])

    assert faulted.category == PROTECTION_UNAVAILABLE
    assert len(setup["fake"].requests) == 1  # only the recovered operation reached Notion
    assert unavailable["state"] == "unavailable"
    assert unavailable["revision"] == setup["connection"]["revision"]
    assert recovered.category == OK and connected["state"] == "connected"
    assert connected["revision"] == setup["connection"]["revision"]


async def test_the_pending_row_holds_no_envelope_and_the_candidate_is_never_stored(
    setup, connect, authority_b, operator
):
    token = nf.synthetic_token()
    setup["fake"].add_token(token, bot_id=nf.bot_id(), workspace_id=nf.WORKSPACE_ID)
    candidate, slot = nf.pending_candidate(setup["repo"], connect, authority_b, token)

    result = await setup["adapter"].identify(candidate)

    assert result.category == OK
    assert setup["repo"].open_token_envelope(authority_b.account_id, slot.connection_id) is None
    row = operator.execute(
        "SELECT state,sealed_token IS NULL AS empty FROM export.connection WHERE id=%s",
        (slot.connection_id,),
    ).fetchone()
    assert row == {"state": "pending", "empty": True}
    stored = operator.execute(
        "SELECT count(*) AS n FROM (SELECT to_jsonb(c)::text AS t FROM export.connection c "
        "UNION ALL SELECT to_jsonb(r)::text FROM export.replay_record r) rows "
        "WHERE t LIKE %s",
        (f"%{token}%",),
    ).fetchone()
    assert stored["n"] == 0
