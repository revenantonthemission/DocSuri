"""NFR3.4, NFR3.6, NFR3.9: no token in any log record, exception text, result or stored
row after forced failures of every kind, and no reduced error carries a chain."""

import dataclasses
import json
import logging
from collections.abc import Mapping

import httpx
import pytest
from backend.modules.export.classification import ReducedError, Verdict
from backend.modules.export.fake_notion import (
    HANG,
    LOST_AFTER_SUCCESS,
    OVERSIZE_DECLARED,
    OVERSIZE_STREAMED,
    REDIRECT,
    SAVED_BUSY,
    TIMEOUT_AFTER_SUCCESS,
    Answer,
)
from backend.modules.export.notion_adapter import ScanRequest
from notion_client.errors import build_request_error

from tests.u6_approved_export import notion_flows as nf

LOGGERS = ("", "httpx", "httpcore", "notion_client", "docsuri.export.notion_sdk")
FAILURES = [
    Answer.error(401),
    Answer.error(403),
    Answer.block_limit(),
    Answer.error(404),
    Answer.error(400),
    Answer.error(409),
    Answer.error(500),
    Answer.error(502),
    Answer.error(503),
    Answer.error(504),
    Answer.rate_limited(wait=0),
    Answer.rate_limited(wait=0, blocked=True),
    Answer.overloaded(wait=0),
    Answer.of(SAVED_BUSY),
    Answer.of(TIMEOUT_AFTER_SUCCESS),
    Answer.of(LOST_AFTER_SUCCESS),
    Answer.of(OVERSIZE_DECLARED),
    Answer.of(OVERSIZE_STREAMED),
    Answer.of(REDIRECT),
    Answer.of(HANG),
]


def walk(value, seen=None):
    """Every value reachable from a result: dataclass fields, mappings and sequences."""
    seen = seen if seen is not None else set()
    if id(value) in seen:
        return
    seen.add(id(value))
    yield value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        children = [getattr(value, f.name) for f in dataclasses.fields(value)]
    elif isinstance(value, Mapping):
        children = list(value.values())
    elif isinstance(value, (list, tuple, set, frozenset)):
        children = list(value)
    elif hasattr(value, "model_dump"):
        children = [value.model_dump()]
    else:
        children = []
    for child in children:
        yield from walk(child, seen)


def assert_clean(results, token):
    for result in results:
        for value in walk(result):
            assert not isinstance(value, BaseException)
            assert not isinstance(value, str) or token not in value
        assert token not in repr(result)


@pytest.fixture
def setup(transactions, connect, authority, tmp_path, caplog):
    for name in LOGGERS:
        caplog.set_level(logging.DEBUG, logger=name)
    policy = nf.policy(
        read_timeout_seconds=1,
        token_check_budget_seconds=1,
        listing_budget_seconds=1,
        page_read_budget_seconds=1,
        read_back_budget_seconds=1,
        scan_budget_seconds=1,
    )
    repo = nf.repository(transactions, policy)
    opener = nf.vault(tmp_path)
    token, bot = nf.synthetic_token(), nf.bot_id()
    fake = nf.fake_with(token, bot)
    target, connection = nf.stored_connection(repo, connect, authority, opener, token, user=bot)
    destination = fake.add_page(title="대상")
    adapter = nf.adapter(repo, opener, fake, policy)
    return locals()


def captured_text(caplog) -> str:
    return caplog.text + json.dumps([str(vars(record)) for record in caplog.records])


@pytest.mark.parametrize("failure", FAILURES, ids=lambda answer: f"{answer.kind}-{answer.status}")
async def test_no_token_leaks_from_reads_after_any_failure(setup, caplog, failure):
    fake, adapter, target = setup["fake"], setup["adapter"], setup["target"]
    for operation in ("users.me", "search", "pages.retrieve", "blocks.children"):
        for _ in range(4):
            fake.queue(operation, failure)
    results = [
        await adapter.identify(target),
        await adapter.list_destinations(target, last_destination_id=setup["destination"]),
        await adapter.read_destination(target, setup["destination"]),
        await adapter.scan(
            target,
            ScanRequest(
                setup["connection"]["id"], setup["destination"], "m",
                frozenset({setup["bot"]}), nf.now(),
            ),
        ),
    ]
    assert_clean(results, setup["token"])
    assert setup["token"] not in captured_text(caplog)


@pytest.mark.parametrize("failure", FAILURES, ids=lambda answer: f"{answer.kind}-{answer.status}")
async def test_no_token_leaks_from_a_write_after_any_failure(
    setup, caplog, connect, authority, failure
):
    bound = nf.bound_effect(setup["repo"], authority, setup["connection"], setup["destination"])
    setup["fake"].queue("pages.create", failure)
    for _ in range(4):
        setup["fake"].queue("pages.retrieve", failure)
    result = await setup["adapter"].create_page(
        setup["target"],
        nf.write_request(bound, setup["connection"], setup["bot"]),
        deadline_seconds=1,
    )
    assert_clean([result, result.provider_result(), result.provider_outcome()], setup["token"])
    assert setup["token"] not in captured_text(caplog)
    with connect("export") as conn:
        rows = conn.execute(
            "SELECT to_jsonb(e)::text AS t FROM export.effect e WHERE account_id=%s",
            (authority.account_id,),
        ).fetchall()
    assert all(setup["token"] not in row["t"] for row in rows)


async def test_a_candidate_refusal_and_a_custody_fault_leak_nothing(
    setup, caplog, connect, authority_b, tmp_path
):
    token = nf.synthetic_token()
    candidate, _ = nf.pending_candidate(setup["repo"], connect, authority_b, token)
    refused = await setup["adapter"].identify(candidate)
    other = tmp_path / "other-keys"
    other.mkdir()
    stranger = nf.adapter(setup["repo"], nf.vault(other), setup["fake"], setup["policy"])
    faulted = await stranger.identify(setup["target"])
    assert refused.category == "token-invalid" and faulted.category == "protection-unavailable"
    assert_clean([refused, faulted], token)
    assert_clean([refused, faulted], setup["token"])
    assert token not in repr(candidate)  # the caller holds it, but never shows it
    text = captured_text(caplog)
    assert token not in text and setup["token"] not in text


async def test_every_reduced_error_has_no_cause_and_no_context(setup):
    response = httpx.Response(
        401,
        text=json.dumps({"object": "error", "status": 401, "code": "unauthorized",
                         "message": "m"}),
        headers={"authorization": "Bearer " + setup["token"]},
    )

    async def refused():
        raise build_request_error(response, response.text)

    overloaded = httpx.Response(529, text=json.dumps({"code": "service_overload", "message": "m"}))

    async def retried():
        raise build_request_error(overloaded, overloaded.text)

    with pytest.raises(ReducedError) as raised:
        await setup["adapter"]._read(None, refused)
    assert raised.value.__cause__ is None and raised.value.__context__ is None
    assert raised.value.verdict == Verdict("token-invalid")
    assert setup["token"] not in str(raised.value) and setup["token"] not in repr(raised.value)
    session = setup["adapter"]._session

    async def work(sdk, ctx):
        return await setup["adapter"]._read(ctx, retried)

    result = await session.run(setup["target"], 1, work)
    assert result.category == "could-not-check" and result.verdict.cause == "retries-spent"
    assert_clean([result], setup["token"])
