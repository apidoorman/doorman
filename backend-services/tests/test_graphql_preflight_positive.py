import pytest


@pytest.mark.asyncio
async def test_graphql_preflight_positive_allows(authed_client):
    name, ver = 'gqlpos', 'v1'
    cr = await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'graphql preflight positive',
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
            'Access-Control-Request-Headers': 'Content-Type',
        },
    )
    assert r.status_code == 204
    acao = r.headers.get('Access-Control-Allow-Origin') or r.headers.get(
        'access-control-allow-origin'
    )
    assert acao == 'http://ok.example'
    ach = (
        r.headers.get('Access-Control-Allow-Headers')
        or r.headers.get('access-control-allow-headers')
        or ''
    )
    assert 'Content-Type' in ach
