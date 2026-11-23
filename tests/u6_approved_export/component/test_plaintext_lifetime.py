"""U6:security-design:plaintext-lifetime and U6:NFR3.5: the token lives only inside one
operation, and its client is closed however the operation ends.

The configured composition holds no token after a call, the bearer exists only on the
client of the operation in flight, the stored envelope is ciphertext under its key
version, refused configures leave no trace of the value, and the two target types never
render it (NFR3.1-NFR3.6, security design §5.1).
"""

import asyncio
import base64
import dataclasses
import gc
import logging
from types import ModuleType
from uuid import uuid4

import httpx
import notion_client
import pytest

from backend.modules.export.classification import (
    CAUSE_BUDGET,
    CAUSE_RESPONSE,
    CAUSE_TRANSPORT,
    COULD_NOT_CHECK,
    OK,
)
from backend.modules.export.errors import ProtectionUnavailable
from backend.modules.export.fake_notion import HANG, OVERSIZE_STREAMED, Answer, FakeNotion
from backend.modules.export.notion_session import CandidateToken, StoredConnection
from backend.modules.export.token_vault import envelope_version
from backend.transactions import OwnerTransactions
from tests.u6_approved_export import notion_flows as nf
from tests.u6_approved_export import service_flows as sf

CONTAINERS = (list, tuple, set, frozenset)


def deep_walk(*roots):
    """Every string reachable inside the composition's own objects.

    Descends builtin containers, dataclasses and objects whose type lives in
    `backend.modules.export` or `backend.u6`; stops at the fake Notion (its request log
    keeps Authorization values by design), the owner transactions, modules and types."""
    seen, pending = set(), list(roots)
    while pending:
        value = pending.pop()
        if id(value) in seen:
            continue
        seen.add(id(value))
        if isinstance(value, (FakeNotion, OwnerTransactions, ModuleType, type)):
            continue
        if isinstance(value, str):
            yield value
            continue
        if dataclasses.is_dataclass(value):
            pending.extend(getattr(value, item.name) for item in dataclasses.fields(value))
            continue
        if isinstance(value, CONTAINERS):
            pending.extend(value)
            continue
        if isinstance(value, dict):
            pending.extend(value.values())
            continue
        module = getattr(type(value), "__module__", "") or ""
        if module.startswith(("backend.modules.export", "backend.u6")):
            pending.extend(vars(value).values())


@pytest.fixture
def setup(transactions, connect, authority, tmp_path):
    policy = nf.policy()
    repo = nf.repository(transactions, policy)
    opener = nf.vault(tmp_path)
    token, bot = nf.synthetic_token(), nf.bot_id()
    fake = nf.fake_with(token, bot)
    target, connection = nf.stored_connection(repo, connect, authority, opener, token, user=bot)
    destination = fake.add_page(title="대상")
    return {
        "policy": policy,
        "repo": repo,
        "vault": opener,
        "authority": authority,
        "token": token,
        "bot": bot,
        "fake": fake,
        "target": target,
        "connection": connection,
        "destination": destination,
    }


def test_the_configured_composition_holds_no_token_anywhere(
    transactions, connect, authority, tmp_path
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    rig.configure()
    gc.collect()
    service = rig.service

    view = rig.connection()
    strings = list(
        deep_walk(service, rig.repo, service.adapter, service.adapter._session,
                  service.vault, service.vault._keys)
    )
    assert all(rig.token not in value for value in strings)
    nf.assert_clean([view], rig.token)


async def test_the_bearer_lives_only_while_the_client_does(setup, monkeypatch):
    session = nf.session(setup["repo"], setup["vault"], setup["fake"], setup["policy"])
    authorizations, clients, closed = [], [], []
    original = httpx.AsyncClient.aclose

    async def tracked(self):
        closed.append(self)
        await original(self)

    monkeypatch.setattr(httpx.AsyncClient, "aclose", tracked)

    async def work(sdk, ctx):
        clients.append(sdk.client)
        authorizations.append(sdk.client.headers.get("Authorization"))
        return await sdk.users.me()

    result = await session.run(setup["target"], 5, work)

    assert result.category == "ok"
    assert authorizations == [f"Bearer {setup['token']}"]
    assert closed == clients and all(client.is_closed for client in clients)
    nf.assert_clean([result], setup["token"])
    assert not any(
        isinstance(value, (httpx.AsyncClient, notion_client.AsyncClient))
        for value in vars(session).values()
    )

    new_token = nf.synthetic_token()
    setup["fake"].add_token(new_token, bot_id=nf.bot_id(), workspace_id=nf.WORKSPACE_ID)
    nf.replace_token(
        setup["repo"], setup["authority"], setup["vault"], new_token, user=setup["bot"]
    )
    again = await session.run(setup["target"], 5, work)
    assert again.category == "ok"
    assert authorizations[1:] == [f"Bearer {new_token}"]


@pytest.fixture
def closed_clients(monkeypatch) -> list:
    """Every HTTP client closed while the test runs, closed through the original."""
    closed: list = []
    original = httpx.AsyncClient.aclose

    async def tracked(self):
        closed.append(self)
        await original(self)

    monkeypatch.setattr(httpx.AsyncClient, "aclose", tracked)
    return closed


def recording_work(clients: list, authorizations: list):
    async def work(sdk, ctx):
        clients.append(sdk.client)
        authorizations.append(sdk.client.headers.get("Authorization"))
        return await sdk.users.me()

    return work


def holds_no_client(session) -> bool:
    return not any(
        isinstance(value, (httpx.AsyncClient, notion_client.AsyncClient))
        for value in vars(session).values()
    )


@pytest.mark.parametrize(
    ("answer", "budget", "request_timeout", "cause"),
    [
        (Answer.error(500), 5, None, CAUSE_RESPONSE),
        (Answer.of(OVERSIZE_STREAMED), 5, None, CAUSE_TRANSPORT),
        (Answer.of(HANG), 5, 0.2, CAUSE_TRANSPORT),
        (Answer.of(HANG), 1, None, CAUSE_BUDGET),
    ],
    ids=["provider-500", "transport-error", "request-timeout", "operation-deadline"],
)
async def test_a_failed_operation_still_closes_its_client(
    setup, closed_clients, answer, budget, request_timeout, cause
):
    session = nf.session(setup["repo"], setup["vault"], setup["fake"], setup["policy"])
    setup["fake"].queue("users.me", answer)
    clients, authorizations = [], []
    work = recording_work(clients, authorizations)

    result = await session.run(setup["target"], budget, work, request_timeout=request_timeout)

    assert (result.category, result.verdict.cause, result.value) == (COULD_NOT_CHECK, cause, None)
    assert result.opened.revision == setup["connection"]["revision"]
    assert authorizations == [f"Bearer {setup['token']}"]
    assert [entry.path for entry in setup["fake"].requests] == ["/v1/users/me"]
    assert len(clients) == 1
    assert closed_clients == clients
    assert clients[0].is_closed
    nf.assert_clean([result], setup["token"])
    assert holds_no_client(session)

    again = await session.run(setup["target"], 5, work)
    assert again.category == OK
    assert len(clients) == 2 and clients[1] is not clients[0]
    assert closed_clients == clients
    assert all(client.is_closed for client in clients)


async def test_a_cancelled_operation_closes_its_client_before_the_cancellation_passes(
    setup, closed_clients
):
    session = nf.session(setup["repo"], setup["vault"], setup["fake"], setup["policy"])
    setup["fake"].queue("users.me", Answer.of(HANG))
    clients, authorizations = [], []
    target = setup["target"]
    task = asyncio.create_task(
        session.run(
            target, 10, recording_work(clients, authorizations), gate_key=target.connection_id
        )
    )
    try:
        async with asyncio.timeout(5):  # a hang guard, never a timing assertion
            while not setup["fake"].requests:
                await asyncio.sleep(0.01)
        assert len(clients) == 1 and clients[0].is_closed is False
        assert closed_clients == [] and session.gate.held == 1
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert task.cancelled()
    assert authorizations == [f"Bearer {setup['token']}"]
    assert [entry.path for entry in setup["fake"].requests] == ["/v1/users/me"]
    assert closed_clients == clients
    assert clients[0].is_closed
    assert session.gate.held == 0
    assert holds_no_client(session)


def test_the_stored_envelope_is_ciphertext_under_its_key_version(setup, operator):
    connection, token = setup["connection"], setup["token"]
    row = operator.execute(
        "SELECT sealed_token,token_key_version,revision FROM export.connection WHERE id=%s",
        (connection["id"],),
    ).fetchone()
    sealed = bytes(row["sealed_token"])
    encodings = (
        token,
        token.encode().hex(),
        base64.b64encode(token.encode()).decode(),
        base64.urlsafe_b64encode(token.encode()).decode(),
    )
    assert all(value.encode() not in sealed for value in encodings)
    assert token not in sealed.hex() and token not in base64.b64encode(sealed).decode()
    assert row["token_key_version"] == envelope_version(sealed)

    binding = {
        "account_id": setup["authority"].account_id,
        "connection_id": connection["id"],
        "revision": row["revision"],
    }
    assert setup["vault"].open(sealed, **binding) == token
    with pytest.raises(ProtectionUnavailable) as caught:
        setup["vault"].open(sealed, **{**binding, "revision": row["revision"] + 1})
    assert caught.value.category == "envelope-unopenable"


def test_refused_configures_leave_no_token_in_any_record(
    transactions, connect, authority, tmp_path, caplog, operator
):
    rig = sf.build(transactions, connect, authority, tmp_path)
    for name in ("", "docsuri.export", "docsuri.export.notion_sdk", "httpx", "httpcore",
                 "notion_client"):
        caplog.set_level(logging.DEBUG, logger=name)
    rig.fake.queue("users.me", Answer.error(500))
    first = sf.refusal(lambda: rig.configure())
    rig.fake.queue("users.me", Answer.error(401))
    second = sf.refusal(lambda: rig.configure())

    assert first[0] == "DEPENDENCY_UNAVAILABLE" and second[0] == "INVALID_TOKEN"
    for _, error in (first, second):
        assert error is not None
        assert error.__cause__ is None and error.__context__ is None
        assert rig.token not in str(error) and rig.token not in repr(error)
    connection_text = operator.execute(
        "SELECT coalesce(string_agg(to_jsonb(c)::text,' '),'') AS text FROM export.connection c"
    ).fetchone()["text"]
    with connect("export") as conn:
        replay_text = conn.execute(
            "SELECT coalesce(string_agg(to_jsonb(r)::text,' '),'') AS text "
            "FROM export.replay_record r"
        ).fetchone()["text"]
        pace_text = conn.execute(
            "SELECT coalesce(string_agg(to_jsonb(p)::text,' '),'') AS text "
            "FROM export.connection_pace p"
        ).fetchone()["text"]
    assert all(rig.token not in text for text in (connection_text, replay_text, pace_text))
    assert rig.token not in caplog.text
    assert all(
        rig.token not in value for value in deep_walk(rig.service, rig.repo)
    )


def test_the_target_types_never_render_the_value():
    connection_id = uuid4()
    value = "synthetic-secret-value"

    candidate = CandidateToken(connection_id, value)

    assert value not in repr(candidate) and value not in str(candidate)
    assert dataclasses.asdict(candidate)["value"] == value
    target = StoredConnection(uuid4(), connection_id)
    assert value not in repr(target)
    with pytest.raises(ValueError, match="candidate token"):
        CandidateToken(connection_id, "")
    with pytest.raises(TypeError, match="connection id"):
        CandidateToken("not-a-uuid", value)
