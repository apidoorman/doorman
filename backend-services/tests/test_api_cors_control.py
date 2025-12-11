import pytest


@pytest.mark.asyncio
async def test_rest_preflight_per_api_cors_allows_blocks(authed_client):
    name, ver = 'corsrest', 'v1'

    r = await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'CORS test REST',
            'api_servers': ['http://upstream.invalid'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
            'api_cors_allow_origins': ['http://foo'],
            'api_cors_allow_methods': ['GET', 'POST'],
            'api_cors_allow_headers': ['Content-Type', 'Authorization'],
            'api_cors_allow_credentials': True,
            'api_cors_expose_headers': ['X-Trace-Id'],
        },
    )
    assert r.status_code in (200, 201), r.text

    pre = await authed_client.options(
        f'/api/rest/{name}/{ver}/ping',
        headers={
            'Origin': 'http://foo',
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'Content-Type, Authorization',
        },
    )
    assert pre.status_code == 204
    assert pre.headers.get('access-control-allow-origin') == 'http://foo'
    assert 'GET' in (pre.headers.get('access-control-allow-methods') or '')
    assert 'Content-Type' in (pre.headers.get('access-control-allow-headers') or '')
    assert pre.headers.get('access-control-allow-credentials') == 'true'

    blocked = await authed_client.options(
        f'/api/rest/{name}/{ver}/ping',
        headers={
            'Origin': 'http://bar',
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'Content-Type',
        },
    )
    assert blocked.status_code == 204

    assert blocked.headers.get('access-control-allow-origin') in (None, '')


@pytest.mark.asyncio
async def test_graphql_preflight_per_api_cors_allows(authed_client):
    name, ver = 'corsgql', 'v1'
    r = await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'CORS test GraphQL',
            'api_servers': ['http://upstream.invalid'],
            'api_type': 'GRAPHQL',
            'api_cors_allow_origins': ['http://foo'],
            'api_cors_allow_methods': ['POST'],
            'api_cors_allow_headers': ['Content-Type'],
            'api_cors_allow_credentials': True,
        },
    )
    assert r.status_code in (200, 201), r.text

    pre = await authed_client.options(
        f'/api/graphql/{name}',
        headers={
            'X-API-Version': ver,
            'Origin': 'http://foo',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'Content-Type',
        },
    )
    assert pre.status_code == 204
    assert pre.headers.get('access-control-allow-origin') == 'http://foo'
    assert 'POST' in (pre.headers.get('access-control-allow-methods') or '')
    assert 'Content-Type' in (pre.headers.get('access-control-allow-headers') or '')
    assert pre.headers.get('access-control-allow-credentials') == 'true'


@pytest.mark.asyncio
async def test_soap_preflight_per_api_cors_allows(authed_client):
    name, ver = 'corssoap', 'v1'
    r = await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'CORS test SOAP',
            'api_servers': ['http://upstream.invalid'],
            'api_type': 'SOAP',
            'api_cors_allow_origins': ['http://foo'],
            'api_cors_allow_methods': ['POST'],
            'api_cors_allow_headers': ['Content-Type'],
            'api_cors_allow_credentials': False,
        },
    )
    assert r.status_code in (200, 201), r.text

    pre = await authed_client.options(
        f'/api/soap/{name}/{ver}/op',
        headers={
            'Origin': 'http://foo',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'Content-Type',
        },
    )
    assert pre.status_code == 204
    assert pre.headers.get('access-control-allow-origin') == 'http://foo'
    assert 'POST' in (pre.headers.get('access-control-allow-methods') or '')
    assert 'Content-Type' in (pre.headers.get('access-control-allow-headers') or '')

    assert pre.headers.get('access-control-allow-credentials') in (None, 'false')
