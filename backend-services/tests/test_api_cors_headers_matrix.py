import pytest


async def _setup_api_and_endpoint(client, name, ver, api_overrides=None, method='GET', uri='/status'):
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://up'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    }
    if api_overrides:
        payload.update(api_overrides)
    r = await client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201), r.text
    r2 = await client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': method,
        'endpoint_uri': uri,
        'endpoint_description': f'{method} {uri}',
    })
    assert r2.status_code in (200, 201), r2.text


@pytest.mark.asyncio
async def test_api_cors_allow_origins_exact_match_allowed(authed_client):
    name, ver = 'corsm1', 'v1'
    await _setup_api_and_endpoint(authed_client, name, ver, api_overrides={
        'api_cors_allow_origins': ['http://ok.example'],
        'api_cors_allow_methods': ['GET'],
        'api_cors_allow_headers': ['Content-Type'],
    })
    r = await authed_client.options(
        f'/api/rest/{name}/{ver}/status',
        headers={'Origin': 'http://ok.example', 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'Content-Type'}
    )
    assert r.status_code == 204
    assert r.headers.get('Access-Control-Allow-Origin') == 'http://ok.example'
    assert r.headers.get('Vary') == 'Origin'


@pytest.mark.asyncio
async def test_api_cors_allow_origins_wildcard_allowed(authed_client):
    name, ver = 'corsm2', 'v1'
    await _setup_api_and_endpoint(authed_client, name, ver, api_overrides={
        'api_cors_allow_origins': ['*'],
        'api_cors_allow_methods': ['GET'],
        'api_cors_allow_headers': ['Content-Type'],
    })
    r = await authed_client.options(
        f'/api/rest/{name}/{ver}/status',
        headers={'Origin': 'http://any.example', 'Access-Control-Request-Method': 'GET'}
    )
    assert r.status_code == 204
    assert r.headers.get('Access-Control-Allow-Origin') == 'http://any.example'


@pytest.mark.asyncio
async def test_api_cors_allow_methods_contains_options_appended(authed_client):
    name, ver = 'corsm3', 'v1'
    await _setup_api_and_endpoint(authed_client, name, ver, api_overrides={
        'api_cors_allow_origins': ['http://ok.example'],
        'api_cors_allow_methods': ['GET'],
        'api_cors_allow_headers': ['Content-Type'],
    })
    r = await authed_client.options(
        f'/api/rest/{name}/{ver}/status',
        headers={'Origin': 'http://ok.example', 'Access-Control-Request-Method': 'GET'}
    )
    assert r.status_code == 204
    methods = [m.strip().upper() for m in (r.headers.get('Access-Control-Allow-Methods') or '').split(',') if m.strip()]
    assert 'OPTIONS' in methods


@pytest.mark.asyncio
async def test_api_cors_allow_headers_asterisk_allows_any(authed_client):
    name, ver = 'corsm4', 'v1'
    await _setup_api_and_endpoint(authed_client, name, ver, api_overrides={
        'api_cors_allow_origins': ['http://ok.example'],
        'api_cors_allow_methods': ['GET'],
        'api_cors_allow_headers': ['*'],
    })
    r = await authed_client.options(
        f'/api/rest/{name}/{ver}/status',
        headers={'Origin': 'http://ok.example', 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'X-Random-Header'}
    )
    assert r.status_code == 204
    ach = r.headers.get('Access-Control-Allow-Headers') or ''
    assert '*' in ach


@pytest.mark.asyncio
async def test_api_cors_allow_headers_specific_disallows_others(authed_client):
    name, ver = 'corsm5', 'v1'
    await _setup_api_and_endpoint(authed_client, name, ver, api_overrides={
        'api_cors_allow_origins': ['http://ok.example'],
        'api_cors_allow_methods': ['GET'],
        'api_cors_allow_headers': ['Content-Type'],
    })
    r = await authed_client.options(
        f'/api/rest/{name}/{ver}/status',
        headers={'Origin': 'http://ok.example', 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'X-Other'}
    )
    assert r.status_code == 204
    ach = r.headers.get('Access-Control-Allow-Headers') or ''
    assert 'Content-Type' in ach and 'X-Other' not in ach


@pytest.mark.asyncio
async def test_api_cors_allow_credentials_true_sets_header(authed_client):
    name, ver = 'corsm6', 'v1'
    await _setup_api_and_endpoint(authed_client, name, ver, api_overrides={
        'api_cors_allow_origins': ['http://ok.example'],
        'api_cors_allow_methods': ['GET'],
        'api_cors_allow_headers': ['Content-Type'],
        'api_cors_allow_credentials': True,
    })
    r = await authed_client.options(
        f'/api/rest/{name}/{ver}/status',
        headers={'Origin': 'http://ok.example', 'Access-Control-Request-Method': 'GET'}
    )
    assert r.status_code == 204
    assert r.headers.get('Access-Control-Allow-Credentials') == 'true'


@pytest.mark.asyncio
async def test_api_cors_expose_headers_propagated(authed_client):
    name, ver = 'corsm7', 'v1'
    expose = ['X-Resp-Id', 'X-Trace-Id']
    await _setup_api_and_endpoint(authed_client, name, ver, api_overrides={
        'api_cors_allow_origins': ['http://ok.example'],
        'api_cors_allow_methods': ['GET'],
        'api_cors_allow_headers': ['Content-Type'],
        'api_cors_expose_headers': expose,
    })
    r = await authed_client.options(
        f'/api/rest/{name}/{ver}/status',
        headers={'Origin': 'http://ok.example', 'Access-Control-Request-Method': 'GET'}
    )
    assert r.status_code == 204
    aceh = r.headers.get('Access-Control-Expose-Headers') or ''
    for h in expose:
        assert h in aceh

