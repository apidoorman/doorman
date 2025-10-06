import pytest


@pytest.mark.asyncio
async def test_platform_cors_wildcard_origin_with_credentials_strict_false(monkeypatch, client):
    # Allow all origins, allow credentials, not strict → echo Origin
    monkeypatch.setenv('ALLOWED_ORIGINS', '*')
    monkeypatch.setenv('ALLOW_CREDENTIALS', 'true')
    monkeypatch.setenv('CORS_STRICT', 'false')

    r = await client.options('/platform/api', headers={
        'Origin': 'http://evil.example',
        'Access-Control-Request-Method': 'GET'
    })
    assert r.status_code == 204
    assert r.headers.get('Access-Control-Allow-Origin') == 'http://evil.example'
    assert r.headers.get('Access-Control-Allow-Credentials') == 'true'
    assert r.headers.get('Vary') == 'Origin'


@pytest.mark.asyncio
async def test_platform_cors_wildcard_origin_with_credentials_strict_true_restricts(monkeypatch, client):
    # With strict=true and origins='*', only safe list is allowed; random origin should be denied
    monkeypatch.setenv('ALLOWED_ORIGINS', '*')
    monkeypatch.setenv('ALLOW_CREDENTIALS', 'true')
    monkeypatch.setenv('CORS_STRICT', 'true')

    r = await client.options('/platform/api', headers={
        'Origin': 'http://evil.example',
        'Access-Control-Request-Method': 'GET'
    })
    assert r.status_code == 204
    # Should not reflect the arbitrary origin
    assert r.headers.get('Access-Control-Allow-Origin') is None


@pytest.mark.asyncio
async def test_platform_cors_methods_empty_env_falls_back_default(monkeypatch, client):
    # Empty methods env → default full list
    monkeypatch.setenv('ALLOW_METHODS', '')
    # Use permissive origins so origin_allowed calculation doesn't block headers population
    monkeypatch.setenv('ALLOWED_ORIGINS', 'http://localhost:3000')

    r = await client.options('/platform/api', headers={
        'Origin': 'http://localhost:3000',
        'Access-Control-Request-Method': 'GET'
    })
    assert r.status_code == 204
    methods = [m.strip() for m in (r.headers.get('Access-Control-Allow-Methods') or '').split(',') if m.strip()]
    expected = {'GET','POST','PUT','DELETE','OPTIONS','PATCH','HEAD'}
    assert set(methods) == expected


@pytest.mark.asyncio
async def test_platform_cors_headers_asterisk_defaults_to_known_list(monkeypatch, client):
    # ALLOW_HEADERS='*' → known default list
    monkeypatch.setenv('ALLOW_HEADERS', '*')
    monkeypatch.setenv('ALLOWED_ORIGINS', 'http://localhost:3000')

    r = await client.options('/platform/api', headers={
        'Origin': 'http://localhost:3000',
        'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'X-Anything'
    })
    assert r.status_code == 204
    headers = [h.strip() for h in (r.headers.get('Access-Control-Allow-Headers') or '').split(',') if h.strip()]
    assert set(headers) == {'Accept','Content-Type','X-CSRF-Token','Authorization'}


@pytest.mark.asyncio
async def test_platform_cors_sets_vary_origin(monkeypatch, authed_client):
    # Specific allowed origin should set Vary: Origin on actual responses
    monkeypatch.setenv('ALLOWED_ORIGINS', 'http://ok.example')
    r = await authed_client.get('/platform/user/me', headers={'Origin': 'http://ok.example'})
    assert r.status_code == 200
    assert r.headers.get('Access-Control-Allow-Origin') == 'http://ok.example'
    assert r.headers.get('Vary') == 'Origin'

