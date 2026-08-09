import pytest

from servers import start_rest_sequence_server


@pytest.mark.asyncio
async def test_rest_retries_on_500_then_success(authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    # Upstream returns 500 first, then 200
    srv = start_rest_sequence_server([500, 200])
    try:
        name, ver = 'rlive500', 'v1'
        await create_api(authed_client, name, ver)
        # Point the API to our sequence server
        await authed_client.put(f'/platform/api/{name}/{ver}', json={'api_servers': [srv.url]})
        await create_endpoint(authed_client, name, ver, 'GET', '/r')
        await subscribe_self(authed_client, name, ver)
        # Allow a single retry
        await authed_client.put(
            f'/platform/api/{name}/{ver}', json={'api_allowed_retry_count': 1}
        )
        await authed_client.delete('/api/caches')

        r = await authed_client.get(f'/api/rest/{name}/{ver}/r')
        assert r.status_code == 200 and r.json().get('ok') is True
    finally:
        srv.stop()


@pytest.mark.asyncio
async def test_rest_retries_on_503_then_success(authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    srv = start_rest_sequence_server([503, 200])
    try:
        name, ver = 'rlive503', 'v1'
        await create_api(authed_client, name, ver)
        await authed_client.put(f'/platform/api/{name}/{ver}', json={'api_servers': [srv.url]})
        await create_endpoint(authed_client, name, ver, 'GET', '/r')
        await subscribe_self(authed_client, name, ver)
        await authed_client.put(
            f'/platform/api/{name}/{ver}', json={'api_allowed_retry_count': 1}
        )
        await authed_client.delete('/api/caches')

        r = await authed_client.get(f'/api/rest/{name}/{ver}/r')
        assert r.status_code == 200
    finally:
        srv.stop()


@pytest.mark.asyncio
async def test_rest_no_retry_when_retry_count_zero(authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    # Upstream always returns 500
    srv = start_rest_sequence_server([500, 500, 500])
    try:
        name, ver = 'rlivez0', 'v1'
        await create_api(authed_client, name, ver)
        await authed_client.put(f'/platform/api/{name}/{ver}', json={'api_servers': [srv.url]})
        await create_endpoint(authed_client, name, ver, 'GET', '/r')
        await subscribe_self(authed_client, name, ver)
        # Ensure retry count is zero
        await authed_client.put(
            f'/platform/api/{name}/{ver}', json={'api_allowed_retry_count': 0}
        )
        await authed_client.delete('/api/caches')

        r = await authed_client.get(f'/api/rest/{name}/{ver}/r')
        assert r.status_code == 500
    finally:
        srv.stop()
