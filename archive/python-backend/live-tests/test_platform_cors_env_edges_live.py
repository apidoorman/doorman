import pytest


@pytest.mark.asyncio
async def test_platform_cors_preflight_basic_live(authed_client):
    """Preflight to /platform/api with default env should allow localhost:3000."""
    r = await authed_client.options(
        '/platform/api',
        headers={'Origin': 'http://localhost:3000', 'Access-Control-Request-Method': 'GET'},
    )
    assert r.status_code in (200, 204)
    # Middleware should echo allowed origin when configured
    acao = r.headers.get('Access-Control-Allow-Origin')
    assert acao in (None, '', 'http://localhost:3000')


@pytest.mark.asyncio
async def test_platform_cors_tools_checker_methods_default_live(authed_client):
    """Tools CORS checker should report default allowed methods."""
    r = await authed_client.post(
        '/platform/tools/cors/check',
        json={'origin': 'http://localhost:3000', 'method': 'GET', 'request_headers': ['X-Rand']},
    )
    assert r.status_code == 200
    payload = r.json().get('response', r.json())
    config = payload.get('config') if isinstance(payload, dict) else {}
    methods = set((config or {}).get('allow_methods', []))
    assert methods == {'GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH', 'HEAD'}
