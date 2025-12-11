import asyncio

from utils.limit_throttle_util import InMemoryWindowCounter


async def _inc(counter: InMemoryWindowCounter, key: str, times: int, ttl: int):
    counts = []
    for _ in range(times):
        c = await counter.incr(key)
        counts.append(c)
    await counter.expire(key, ttl)
    return counts


def test_inmemory_counter_increments_and_expires(event_loop):
    c = InMemoryWindowCounter()
    counts = event_loop.run_until_complete(_inc(c, 'k1', 3, 1))
    assert counts == [1, 2, 3]

    event_loop.run_until_complete(asyncio.sleep(1.1))
    counts2 = event_loop.run_until_complete(_inc(c, 'k1', 2, 1))
    assert counts2[0] == 1
    assert counts2[1] == 2
