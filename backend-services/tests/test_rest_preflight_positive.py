import pytest


@pytest.mark.asyncio
async def test_rest_preflight_positive_allows(authed_client):
    name, ver = 'restpos', 'v1'
    c = await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'REST preflight positive',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://up.invalid'],
            'api_type': 'REST',
            'api_cors_allow_origins': ['http://ok.example'],
            'api_cors_allow_methods': ['GET'],
            'api_cors_allow_headers': ['Content-Type'],
            'api_allowed_retry_count': 0,
        },
    )
    assert c.status_code in (200, 201)
    ce = await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'GET',
            'endpoint_uri': '/p',
            'endpoint_description': 'p',
        },
    )
    assert ce.status_code in (200, 201)

    r = await authed_client.options(
        f'/api/rest/{name}/{ver}/p',
        headers={
            'Origin': 'http://ok.example',
            'Access-Control-Request-Method': 'GET',
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
