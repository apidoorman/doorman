import asyncio

import pytest

from utils.limit_throttle_util import InMemoryWindowCounter


async def _inc(counter: InMemoryWindowCounter, key: str, times: int, ttl: int):
    counts = []
    for _ in range(times):
        c = await counter.incr(key)
        counts.append(c)
    await counter.expire(key, ttl)
    return counts


@pytest.mark.asyncio
async def test_inmemory_counter_increments_and_expires():
    c = InMemoryWindowCounter()
    counts = await _inc(c, 'k1', 3, 1)
    assert counts == [1, 2, 3]

    await asyncio.sleep(1.1)
    counts2 = await _inc(c, 'k1', 2, 1)
    assert counts2[0] == 1
    assert counts2[1] == 2
