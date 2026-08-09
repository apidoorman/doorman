import pytest
from tests.test_gateway_routing_limits import _FakeAsyncClient


async def _setup_api_public(client, name, ver, mode='allow_all', wl=None, bl=None):
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://up'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_public': True,
        'api_ip_mode': mode,
    }
    if wl is not None:
        payload['api_ip_whitelist'] = wl
    if bl is not None:
        payload['api_ip_blacklist'] = bl
    r = await client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201)
    r2 = await client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'GET',
            'endpoint_uri': '/res',
            'endpoint_description': 'res',
        },
    )
    assert r2.status_code in (200, 201)
    return name, ver


@pytest.mark.asyncio
async def test_ip_policy_allows_exact_ip(monkeypatch, authed_client):
    import services.gateway_service as gs

    name, ver = await _setup_api_public(
        authed_client, 'ipok1', 'v1', mode='whitelist', wl=['127.0.0.1']
    )
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/res')
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_ip_policy_denies_exact_ip(monkeypatch, authed_client):
    import services.gateway_service as gs

    monkeypatch.setenv('LOCAL_HOST_IP_BYPASS', 'false')
    name, ver = await _setup_api_public(
        authed_client, 'ipdeny1', 'v1', mode='allow_all', bl=['127.0.0.1']
    )
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/res')
    assert r.status_code == 403
    body = r.json()
    assert body.get('error_code') == 'API011'


@pytest.mark.asyncio
async def test_ip_policy_allows_cidr(monkeypatch, authed_client):
    import services.gateway_service as gs

    name, ver = await _setup_api_public(
        authed_client, 'ipok2', 'v1', mode='whitelist', wl=['127.0.0.0/24']
    )
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/res')
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_ip_policy_denies_cidr(monkeypatch, authed_client):
    import services.gateway_service as gs

    monkeypatch.setenv('LOCAL_HOST_IP_BYPASS', 'false')
    name, ver = await _setup_api_public(
        authed_client, 'ipdeny2', 'v1', mode='allow_all', bl=['127.0.0.0/24']
    )
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/res')
    assert r.status_code == 403
    assert r.json().get('error_code') == 'API011'


@pytest.mark.asyncio
async def test_ip_policy_denylist_precedence_over_allowlist(monkeypatch, authed_client):
    import services.gateway_service as gs

    monkeypatch.setenv('LOCAL_HOST_IP_BYPASS', 'false')
    name, ver = await _setup_api_public(
        authed_client, 'ipdeny3', 'v1', mode='whitelist', wl=['127.0.0.1'], bl=['127.0.0.1']
    )
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/res')
    assert r.status_code == 403
    assert r.json().get('error_code') == 'API011'


@pytest.mark.asyncio
async def test_ip_policy_enforced_early_returns_http_error(monkeypatch, authed_client):
    import services.gateway_service as gs

    monkeypatch.setenv('LOCAL_HOST_IP_BYPASS', 'false')
    name, ver = await _setup_api_public(
        authed_client, 'ipdeny4', 'v1', mode='whitelist', wl=['203.0.113.5']
    )
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/res')
    assert r.status_code == 403
    assert r.json().get('error_code') == 'API010'
