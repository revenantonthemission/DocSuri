"""D6: two transaction pools sharing one connection stay at or below 2 requests per
second, measured at the fake Notion, with the real 500 ms pace on the database clock."""

import asyncio

import pytest
from backend.transactions import OwnerTransactions
from backend.u6_policy import ExportPolicy

from tests.u6_approved_export import notion_flows as nf

REAL_PACE = ExportPolicy()
OPERATIONS_PER_POOL = 3
# The slot is reserved on the database clock and observed on this process's clock.
JITTER = 0.05


@pytest.fixture
def second_pool(realm):
    pool = OwnerTransactions(realm)
    yield pool
    pool.close()


async def test_two_pools_on_one_connection_stay_within_two_requests_per_second(
    transactions, second_pool, connect, authority, tmp_path
):
    assert REAL_PACE.pace_interval_ms == 500
    first_repo = nf.repository(transactions, REAL_PACE)
    second_repo = nf.repository(second_pool, REAL_PACE)
    opener = nf.vault(tmp_path)
    token, bot = nf.synthetic_token(), nf.bot_id()
    fake = nf.fake_with(token, bot)
    target, _ = nf.stored_connection(first_repo, connect, authority, opener, token, user=bot)
    adapters = [nf.adapter(repo, opener, fake, REAL_PACE) for repo in (first_repo, second_repo)]

    results = await asyncio.gather(
        *(adapter.identify(target) for adapter in adapters for _ in range(OPERATIONS_PER_POOL))
    )

    assert [result.category for result in results] == ["ok"] * 2 * OPERATIONS_PER_POOL
    times = sorted(entry.at for entry in fake.requests)
    assert len(times) == 2 * OPERATIONS_PER_POOL
    gaps = [later - earlier for earlier, later in zip(times, times[1:], strict=False)]
    assert min(gaps) >= 0.5 - JITTER
    windows = [times[i + 2] - times[i] for i in range(len(times) - 2)]
    assert min(windows) >= 1.0 - JITTER
