"""NotionSession: one client per operation, no SDK retries, budgets, gate and pace (D5,
D10, D15, R-14), through the real SDK over the fake Notion and the real store."""

import asyncio
import logging

import notion_client
import notion_client.helpers
import pytest
from backend.modules.export import notion_adapter as adapter_module
from backend.modules.export.classification import (
    CAUSE_BUDGET,
    COULD_NOT_CHECK,
    OK,
    RETRYABLE,
    UNCERTAIN,
)
from backend.modules.export.fake_notion import HANG, Answer
from backend.modules.export.notion_adapter import LISTING_INCOMPLETE, ScanRequest

from tests.u6_approved_export import notion_flows as nf

LOGGERS = ("", "httpx", "httpcore", "notion_client", "docsuri.export.notion_sdk")


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
    }


def pace_slot(connect, connection_id):
    with connect("export") as conn:
        return conn.execute(
            "SELECT next_slot_at FROM export.connection_pace WHERE connection_id=%s",
            (connection_id,),
        ).fetchone()["next_slot_at"]


async def test_two_operations_with_different_tokens_never_share_authorization(
    setup, connect, authority_b
):
    other = nf.synthetic_token()
    setup["fake"].add_token(other, bot_id=nf.bot_id(), workspace_id=nf.WORKSPACE_ID)
    candidate, _ = nf.pending_candidate(setup["repo"], connect, authority_b, other)
    adapter = nf.adapter(setup["repo"], setup["vault"], setup["fake"], setup["policy"])

    first = await adapter.identify(setup["target"])
    second = await adapter.identify(candidate)

    assert first.category == OK and second.category == OK
    authorizations = [entry.authorization for entry in setup["fake"].requests]
    assert authorizations == [f"Bearer {setup['token']}", f"Bearer {other}"]


@pytest.mark.parametrize("answer", [Answer.rate_limited(wait=0), Answer.error(500)])
async def test_retry_false_makes_exactly_one_attempt(setup, answer):
    setup["fake"].queue("users.me", answer)
    session = nf.session(setup["repo"], setup["vault"], setup["fake"], setup["policy"])

    result = await session.run(setup["target"], 5, lambda sdk, ctx: sdk.users.me())

    assert result.category in (RETRYABLE, COULD_NOT_CHECK)
    assert len(setup["fake"].requests) == 1


async def test_the_sdk_client_is_never_entered_and_pagination_helpers_are_never_used(
    setup, monkeypatch
):
    calls = []

    def spy(name):
        def record(*args, **kwargs):
            calls.append(name)
            raise AssertionError(name)

        return record

    monkeypatch.setattr(notion_client.AsyncClient, "__aenter__", spy("aenter"))
    monkeypatch.setattr(notion_client.AsyncClient, "__aexit__", spy("aexit"))
    monkeypatch.setattr(notion_client.helpers, "iterate_paginated_api", spy("iterate"))
    monkeypatch.setattr(notion_client.helpers, "collect_paginated_api", spy("collect"))
    adapter = nf.adapter(setup["repo"], setup["vault"], setup["fake"], setup["policy"])
    target, destination = setup["target"], setup["destination"]

    assert (await adapter.identify(target)).category == OK
    assert (await adapter.list_destinations(target)).complete is True
    assert (await adapter.read_destination(target, destination)).readable is True
    scan = await adapter.scan(
        target,
        ScanRequest(
            setup["connection"]["id"], destination, "marker", frozenset({setup["bot"]}), nf.now()
        ),
    )
    assert scan.result == "not-found"
    assert calls == []
    assert not hasattr(adapter_module, "iterate_paginated_api")
    assert not hasattr(adapter_module, "collect_paginated_api")


async def test_every_spent_budget_gives_its_stated_outcome(setup):
    policy = nf.policy(
        read_timeout_seconds=1,
        token_check_budget_seconds=1,
        listing_budget_seconds=1,
        page_read_budget_seconds=1,
        read_back_budget_seconds=1,
        scan_budget_seconds=1,
    )
    fake = setup["fake"]
    for operation in ("users.me", "search", "pages.retrieve", "pages.retrieve", "blocks.children"):
        fake.queue(operation, Answer.of(HANG))
    adapter = nf.adapter(setup["repo"], setup["vault"], fake, policy)
    target, destination = setup["target"], setup["destination"]

    identity = await adapter.identify(target)
    listing = await adapter.list_destinations(target)
    read = await adapter.read_destination(target, destination)
    back = await adapter.read_back(
        target, page_id=destination, destination_id=destination,
        writer_identity=setup["bot"], marker="m",
    )
    scan = await adapter.scan(
        target,
        ScanRequest(
            setup["connection"]["id"], destination, "m", frozenset({setup["bot"]}), nf.now()
        ),
    )

    assert identity.category == COULD_NOT_CHECK
    assert listing.category == COULD_NOT_CHECK and listing.complete is False
    assert read.category == COULD_NOT_CHECK and read.readable is None
    assert back.category == COULD_NOT_CHECK and back.passed is False
    assert scan.result == LISTING_INCOMPLETE and scan.evidence.scanComplete is False


async def test_the_reduced_write_deadline_makes_an_attempt_uncertain(setup, connect, authority):
    fake, repo = setup["fake"], setup["repo"]
    bound = nf.bound_effect(repo, authority, setup["connection"], setup["destination"])
    fake.queue("pages.create", Answer.of(HANG))
    adapter = nf.adapter(repo, setup["vault"], fake, setup["policy"])

    result = await adapter.create_page(
        setup["target"],
        nf.write_request(bound, setup["connection"], setup["bot"]),
        deadline_seconds=0.3,
    )

    assert result.category == UNCERTAIN and result.sent is True
    assert result.outcome.response_class == "uncertain"
    assert len(fake.writes) == 1


async def test_cancellation_passes_through_and_releases_the_gate(setup):
    setup["fake"].queue("users.me", Answer.of(HANG))
    adapter = nf.adapter(setup["repo"], setup["vault"], setup["fake"], setup["policy"])
    gate = adapter._session.gate
    target = setup["target"]

    task = asyncio.create_task(adapter.identify(target, gate_key=target.connection_id))
    while not setup["fake"].requests:
        await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert gate.held == 0


class OpeningSpy:
    """Records how many gate slots are held when the envelope is opened."""

    def __init__(self, repo):
        self.repo = repo
        self.gate = None
        self.seen = []

    def reserve_pace_slot(self, *args, **kwargs):
        return self.repo.reserve_pace_slot(*args, **kwargs)

    def open_token_envelope(self, *args):
        self.seen.append(self.gate.held)
        return self.repo.open_token_envelope(*args)


async def test_the_gate_slot_is_taken_before_the_token_is_opened(setup):
    spy = OpeningSpy(setup["repo"])
    session = nf.session(spy, setup["vault"], setup["fake"], setup["policy"])
    spy.gate = session.gate
    target = setup["target"]

    async def work(sdk, ctx):
        return await sdk.users.me()

    gated = await session.run(target, 5, work, gate_key=target.connection_id)
    lane = await session.run(target, 5, work)

    assert gated.category == OK and lane.category == OK
    assert spy.seen == [1, 0]
    assert session.gate.held == 0


async def test_the_candidate_path_paces_on_its_own_row_and_keeps_no_token(
    setup, connect, authority_b, caplog
):
    token = nf.synthetic_token()
    setup["fake"].add_token(token, bot_id=nf.bot_id(), workspace_id=nf.WORKSPACE_ID)
    candidate, slot = nf.pending_candidate(setup["repo"], connect, authority_b, token)
    before = pace_slot(connect, slot.connection_id)
    adapter = nf.adapter(setup["repo"], setup["vault"], setup["fake"], setup["policy"])
    for name in LOGGERS:
        caplog.set_level(logging.DEBUG, logger=name)

    result = await adapter.identify(candidate, gate_key=candidate.connection_id)

    assert result.category == OK and result.workspace_id == nf.WORKSPACE_ID
    assert pace_slot(connect, slot.connection_id) > before
    assert token not in caplog.text and token not in repr(result)
    assert token not in repr(candidate)
    assert all(token not in str(vars(record)) for record in caplog.records)


async def test_an_unexpected_answer_is_reduced_not_raised(setup):
    from backend.modules.export.fake_notion import REDIRECT

    setup["fake"].queue("users.me", Answer.of(REDIRECT))
    adapter = nf.adapter(setup["repo"], setup["vault"], setup["fake"], setup["policy"])
    result = await adapter.identify(setup["target"])
    assert result.category == COULD_NOT_CHECK


async def test_a_spent_session_budget_is_reduced_with_the_budget_cause(setup):
    setup["fake"].queue("users.me", Answer.of(HANG))
    session = nf.session(setup["repo"], setup["vault"], setup["fake"], setup["policy"])
    result = await session.run(setup["target"], 0.3, lambda sdk, ctx: sdk.users.me())
    assert result.category == COULD_NOT_CHECK and result.cause == CAUSE_BUDGET
    assert result.value is None and result.opened.revision == setup["connection"]["revision"]