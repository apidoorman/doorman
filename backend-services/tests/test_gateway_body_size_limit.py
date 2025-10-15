import pytest

@pytest.mark.asyncio
async def test_request_exceeding_max_body_size_returns_413(monkeypatch, authed_client):
    from conftest import create_endpoint
    import services.gateway_service as gs
    from tests.test_gateway_routing_limits import _FakeAsyncClient
    await authed_client.post('/platform/api', json={
        'api_name': 'bpub', 'api_version': 'v1', 'api_description': 'b',
        'api_allowed_roles': ['admin'], 'api_allowed_groups': ['ALL'], 'api_servers': ['http://up'], 'api_type': 'REST', 'api_allowed_retry_count': 0, 'api_public': True
    })
    await create_endpoint(authed_client, 'bpub', 'v1', 'POST', '/p')
    monkeypatch.setenv('MAX_BODY_SIZE_BYTES', '10')
    headers = {'Content-Type': 'application/json', 'Content-Length': '11'}
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.post('/api/rest/bpub/v1/p', headers=headers, content='12345678901')
    assert r.status_code == 413
    body = r.json()
    assert body.get('error_code') == 'REQ001'

@pytest.mark.asyncio
async def test_request_at_limit_is_allowed(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self
    import services.gateway_service as gs
    from tests.test_gateway_routing_limits import _FakeAsyncClient
    name, ver = 'bsz', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'POST', '/p')
    await subscribe_self(authed_client, name, ver)
    monkeypatch.setenv('MAX_BODY_SIZE_BYTES', '10')
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    headers = {'Content-Type': 'application/json', 'Content-Length': '10'}
    r = await authed_client.post(f'/api/rest/{name}/{ver}/p', headers=headers, content='1234567890')
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_request_without_content_length_is_allowed(monkeypatch, authed_client):
    """Test that GET requests (no body, no Content-Length) are allowed regardless of limit.

    Note: httpx automatically adds Content-Length when content/json is provided,
    so we test with a GET request instead which naturally has no Content-Length.
    """
    from conftest import create_api, create_endpoint, subscribe_self
    import services.gateway_service as gs
    from tests.test_gateway_routing_limits import _FakeAsyncClient
    name, ver = 'bsz2', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/p')
    await subscribe_self(authed_client, name, ver)
    monkeypatch.setenv('MAX_BODY_SIZE_BYTES', '10')
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/p')
    assert r.status_code == 200
