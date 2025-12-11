import pytest


@pytest.mark.asyncio
async def test_graphql_preflight_header_mismatch_removes_acao(authed_client):
    name, ver = 'gqlneg', 'v1'
    # Create GraphQL API config
    cr = await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'graphql preflight',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://up.invalid'],
            'api_type': 'GRAPHQL',
            'api_cors_allow_origins': ['http://ok.example'],
            'api_cors_allow_methods': ['POST'],
            'api_cors_allow_headers': ['Content-Type'],
            'api_allowed_retry_count': 0,
        },
    )
    assert cr.status_code in (200, 201)

    r = await authed_client.options(
        f'/api/graphql/{name}',
        headers={
            'X-API-Version': ver,
            'Origin': 'http://ok.example',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'X-Not-Allowed',
        },
    )
    assert r.status_code == 204
    acao = r.headers.get('Access-Control-Allow-Origin') or r.headers.get(
        'access-control-allow-origin'
    )
    assert acao in (None, '')


@pytest.mark.asyncio
async def test_soap_preflight_header_mismatch_removes_acao(authed_client):
    name, ver = 'soapneg', 'v1'
    cr = await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'soap preflight',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://up.invalid'],
            'api_type': 'SOAP',
            'api_cors_allow_origins': ['http://ok.example'],
            'api_cors_allow_methods': ['POST'],
            'api_cors_allow_headers': ['Content-Type'],
            'api_allowed_retry_count': 0,
        },
    )
    assert cr.status_code in (200, 201)

    r = await authed_client.options(
        f'/api/soap/{name}/{ver}/x',
        headers={
            'Origin': 'http://ok.example',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'X-Not-Allowed',
        },
    )
    assert r.status_code == 204
    acao = r.headers.get('Access-Control-Allow-Origin') or r.headers.get(
        'access-control-allow-origin'
    )
    assert acao in (None, '')
