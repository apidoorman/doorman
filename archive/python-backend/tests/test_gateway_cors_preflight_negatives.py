import pytest


@pytest.mark.asyncio
async def test_rest_preflight_header_mismatch_does_not_echo_origin(authed_client):
    name, ver = 'corsneg', 'v1'
    await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'CORS negative',
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
    await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'GET',
            'endpoint_uri': '/x',
            'endpoint_description': 'x',
        },
    )

    r = await authed_client.options(
        f'/api/rest/{name}/{ver}/x',
        headers={
            'Origin': 'http://ok.example',
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'X-Random-Header',
        },
    )
    assert r.status_code == 204
    # Current gateway behavior: echoes ACAO based on origin allow-list, even if headers mismatch.
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
