import time

import pytest
from tests.test_gateway_routing_limits import _FakeAsyncClient


@pytest.mark.asyncio
async def test_rate_limit_blocks_second_request_in_window(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    name, ver = 'rlblock', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/p')
    await subscribe_self(authed_client, name, ver)

    from utils.database import user_collection

    user_collection.update_one(
        {'username': 'admin'},
        {'$set': {'rate_limit_duration': 1, 'rate_limit_duration_type': 'second'}},
    )
    await authed_client.delete('/api/caches')

    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    ok = await authed_client.get(f'/api/rest/{name}/{ver}/p')
    assert ok.status_code == 200
    blocked = await authed_client.get(f'/api/rest/{name}/{ver}/p')
    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_throttle_queue_limit_exceeded_returns_429(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    name, ver = 'tqex', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/t')
    await subscribe_self(authed_client, name, ver)

    from utils.database import user_collection

    user_collection.update_one(
        {'username': 'admin'}, {'$set': {'throttle_duration': 1, 'throttle_queue_limit': 1}}
    )
    await authed_client.delete('/api/caches')
    from utils.limit_throttle_util import reset_counters

    reset_counters()
    now_ms = int(time.time() * 1000)
    wait_ms = 1000 - (now_ms % 1000) + 350
    time.sleep(wait_ms / 1000.0)

    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    r1 = await authed_client.get(f'/api/rest/{name}/{ver}/t')
    assert r1.status_code == 200, f'First request failed with {r1.status_code}'

    r2 = await authed_client.get(f'/api/rest/{name}/{ver}/t')
    assert r2.status_code == 429, (
        f'Second request should have been throttled but got {r2.status_code}'
    )


@pytest.mark.asyncio
async def test_throttle_dynamic_wait_increases_latency(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    name, ver = 'twait', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/w')
    await subscribe_self(authed_client, name, ver)

    from utils.database import user_collection

    user_collection.update_one(
        {'username': 'admin'},
        {
            '$set': {
                'throttle_duration': 1,
                'throttle_duration_type': 'second',
                'throttle_queue_limit': 10,
                'throttle_wait_duration': 0.1,
                'throttle_wait_duration_type': 'second',
                'rate_limit_duration': 1000,
                'rate_limit_duration_type': 'second',
            }
        },
    )
    await authed_client.delete('/api/caches')
    from utils.limit_throttle_util import reset_counters

    reset_counters()
    now_ms = int(time.time() * 1000)
    wait_ms = 1000 - (now_ms % 1000) + 350
    time.sleep(wait_ms / 1000.0)

    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    t0 = time.perf_counter()
    r1 = await authed_client.get(f'/api/rest/{name}/{ver}/w')
    t1 = time.perf_counter()
    assert r1.status_code == 200
    dur1 = t1 - t0

    t2 = time.perf_counter()
    r2 = await authed_client.get(f'/api/rest/{name}/{ver}/w')
    t3 = time.perf_counter()
    assert r2.status_code == 200
    dur2 = t3 - t2

    assert dur2 >= dur1 + 0.08


@pytest.mark.asyncio
async def test_rate_limit_window_rollover_allows_requests(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    name, ver = 'rlroll', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/x')
    await subscribe_self(authed_client, name, ver)

    from utils.database import user_collection

    user_collection.update_one(
        {'username': 'admin'},
        {'$set': {'rate_limit_duration': 1, 'rate_limit_duration_type': 'second'}},
    )
    await authed_client.delete('/api/caches')

    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    r1 = await authed_client.get(f'/api/rest/{name}/{ver}/x')
    assert r1.status_code == 200
    r2 = await authed_client.get(f'/api/rest/{name}/{ver}/x')
    assert r2.status_code == 429

    time.sleep(1.1)
    r3 = await authed_client.get(f'/api/rest/{name}/{ver}/x')
    assert r3.status_code == 200
