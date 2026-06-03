import pytest
from tests.test_gateway_routing_limits import _FakeAsyncClient


async def _setup_basic_rest(client, name='bw', ver='v1', method='GET', uri='/p'):
    from conftest import create_api, create_endpoint, subscribe_self

    await create_api(client, name, ver)
    await create_endpoint(client, name, ver, method, uri)
    await subscribe_self(client, name, ver)
    return name, ver, uri


@pytest.mark.asyncio
async def test_bandwidth_limit_blocks_when_exceeded(monkeypatch, authed_client):
    name, ver, uri = await _setup_basic_rest(authed_client, name='bw1', method='GET', uri='/g')
    from utils.database import user_collection

    user_collection.update_one(
        {'username': 'admin'},
        {
            '$set': {
                'bandwidth_limit_bytes': 1,
                'bandwidth_limit_window': 'second',
                'bandwidth_limit_enabled': True,
            }
        },
    )
    await authed_client.delete('/api/caches')
    from utils.doorman_cache_util import doorman_cache

    try:
        for k in list(doorman_cache.cache.keys('bandwidth_usage:admin*')):
            doorman_cache.cache.delete(k)
    except Exception:
        pass

    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    ok = await authed_client.get(f'/api/rest/{name}/{ver}{uri}')
    assert ok.status_code == 200
    blocked = await authed_client.get(f'/api/rest/{name}/{ver}{uri}')
    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_bandwidth_limit_resets_after_window(monkeypatch, authed_client):
    name, ver, uri = await _setup_basic_rest(authed_client, name='bw2', method='GET', uri='/g')
    from utils.database import user_collection
    import utils.bandwidth_util as bu

    fake_now = {'value': 1_700_000_000}

    def _fake_bucket_key(username: str, window: str, now: int | None = None):
        sec = bu._window_to_seconds(window)
        current = int(fake_now['value'] if now is None else now)
        bucket = (current // sec) * sec
        return f'bandwidth_usage:{username}:{sec}:{bucket}', sec

    monkeypatch.setattr(bu, '_bucket_key', _fake_bucket_key)

    user_collection.update_one(
        {'username': 'admin'},
        {
            '$set': {
                'bandwidth_limit_bytes': 1,
                'bandwidth_limit_window': 'second',
                'bandwidth_limit_enabled': True,
            }
        },
    )
    await authed_client.delete('/api/caches')
    from utils.doorman_cache_util import doorman_cache

    try:
        for k in list(doorman_cache.cache.keys('bandwidth_usage:admin*')):
            doorman_cache.cache.delete(k)
    except Exception:
        pass

    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    r1 = await authed_client.get(f'/api/rest/{name}/{ver}{uri}')
    assert r1.status_code == 200
    r2 = await authed_client.get(f'/api/rest/{name}/{ver}{uri}')
    assert r2.status_code == 429
    fake_now['value'] += 2
    r3 = await authed_client.get(f'/api/rest/{name}/{ver}{uri}')
    assert r3.status_code == 200


@pytest.mark.asyncio
async def test_bandwidth_limit_counts_request_and_response_bytes(monkeypatch, authed_client):
    name, ver, uri = await _setup_basic_rest(authed_client, name='bw3', method='POST', uri='/p')
    from utils.database import user_collection

    user_collection.update_one(
        {'username': 'admin'},
        {
            '$set': {
                'bandwidth_limit_bytes': 1_000_000,
                'bandwidth_limit_window': 'second',
                'bandwidth_limit_enabled': True,
            }
        },
    )
    await authed_client.delete('/api/caches')
    from utils.doorman_cache_util import doorman_cache

    try:
        for k in list(doorman_cache.cache.keys('bandwidth_usage:admin*')):
            doorman_cache.cache.delete(k)
    except Exception:
        pass

    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    from utils.bandwidth_util import get_current_usage

    before = get_current_usage('admin', 'second')
    payload = 'x' * 1234
    r = await authed_client.post(f'/api/rest/{name}/{ver}{uri}', json={'data': payload})
    assert r.status_code == 200
    after = get_current_usage('admin', 'second')
    delta = after - before
    assert delta >= len(payload)
    assert delta > len(payload)
