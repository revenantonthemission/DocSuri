"""D15: at most two interactive Notion operations per process and one per connection."""

import asyncio
from uuid import uuid4

import pytest
from backend.modules.export.classification import CAUSE_INTERACTIVE_CAP, COULD_NOT_CHECK, OK
from backend.modules.export.fake_notion import FakeNotion
from backend.modules.export.notion_adapter import NotionAdapter
from backend.modules.export.notion_session import (
    CandidateToken,
    InteractiveGate,
    NotionSession,
    StoredConnection,
)

from tests.u6_approved_export import notion_flows as nf

POLICY = nf.policy()


def session_without_store(gate: InteractiveGate) -> NotionSession:
    """Work here sends no request, so no pace slot or envelope is ever needed."""
    fake = FakeNotion()
    return NotionSession(
        store=None, vault=None, policy=POLICY, gate=gate, transport_factory=lambda: fake
    )


def candidate(connection=None) -> CandidateToken:
    return CandidateToken(connection or uuid4(), nf.synthetic_token())


def test_the_process_cap_refuses_a_third_operation_at_once():
    gate = InteractiveGate(2, 1)
    assert gate.try_acquire(uuid4()) and gate.try_acquire(uuid4())
    assert not gate.try_acquire(uuid4())
    assert gate.held == 2


def test_the_connection_cap_refuses_a_second_operation_on_the_same_connection():
    gate = InteractiveGate(2, 1)
    connection = uuid4()
    assert gate.try_acquire(connection)
    assert not gate.try_acquire(connection)
    assert gate.try_acquire(uuid4())
    gate.release(connection)
    assert gate.held == 1
    assert gate.try_acquire(connection)
    assert gate.held == 2


@pytest.mark.parametrize("outcome", ["success", "exception", "cancellation"])
async def test_a_slot_is_released_on_every_ending(outcome):
    gate = InteractiveGate(2, 1)
    session = session_without_store(gate)
    target = candidate()
    started = asyncio.Event()

    async def work(sdk, ctx):
        started.set()
        assert gate.held == 1
        if outcome == "exception":
            raise ValueError("synthetic failure")
        if outcome == "cancellation":
            await asyncio.sleep(3600)
        return "done"

    task = asyncio.create_task(session.run(target, 5, work, gate_key=target.connection_id))
    await started.wait()
    if outcome == "cancellation":
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        result = await task
        assert result.category == (OK if outcome == "success" else COULD_NOT_CHECK)
    assert gate.held == 0


async def test_a_refusal_answers_could_not_check_at_once_without_running_the_work():
    gate = InteractiveGate(1, 1)
    session = session_without_store(gate)
    held = uuid4()
    assert gate.try_acquire(held)
    ran = []

    async def work(sdk, ctx):
        ran.append(True)

    result = await session.run(candidate(), 5, work, gate_key=uuid4())
    assert result.category == COULD_NOT_CHECK and result.cause == CAUSE_INTERACTIVE_CAP
    assert ran == [] and gate.held == 1


async def test_a_refused_listing_is_an_unavailable_listing():
    gate = InteractiveGate(1, 1)
    assert gate.try_acquire(uuid4())
    adapter = NotionAdapter(session_without_store(gate), store=None)
    target = StoredConnection(uuid4(), uuid4())
    listing = await adapter.list_destinations(target, gate_key=target.connection_id)
    assert listing.category == COULD_NOT_CHECK
    assert listing.destinations == () and listing.complete is False


async def test_a_refused_destination_read_is_could_not_check():
    gate = InteractiveGate(1, 1)
    assert gate.try_acquire(uuid4())
    adapter = NotionAdapter(session_without_store(gate), store=None)
    target = StoredConnection(uuid4(), uuid4())
    read = await adapter.read_destination(target, uuid4().hex, gate_key=target.connection_id)
    assert read.category == COULD_NOT_CHECK and read.readable is None


async def test_an_operation_without_a_gate_key_takes_no_slot_even_when_full():
    gate = InteractiveGate(2, 1)
    assert gate.try_acquire(uuid4()) and gate.try_acquire(uuid4())
    seen = []

    async def work(sdk, ctx):
        seen.append(gate.held)
        return "lane"

    result = await session_without_store(gate).run(candidate(), 5, work)
    assert result.category == OK and result.value == "lane" and seen == [2]
    assert gate.held == 2


def test_the_caps_come_from_the_policy_and_refuse_nonsense():
    gate = InteractiveGate.for_policy(nf.policy(interactive_per_process=3))
    keys = [uuid4() for _ in range(4)]
    assert [gate.try_acquire(key) for key in keys] == [True, True, True, False]
    with pytest.raises(ValueError):
        InteractiveGate(1, 2)
    with pytest.raises(TypeError):
        InteractiveGate(2, 1).try_acquire("not-a-connection")
