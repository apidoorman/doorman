import pytest


async def _allow_tools(client):
    await client.put('/platform/user/admin', json={'manage_security': True})


@pytest.mark.asyncio
async def test_tools_cors_checker_allows_when_method_and_headers_match(monkeypatch, authed_client):
    await _allow_tools(authed_client)
    monkeypatch.setenv('ALLOWED_ORIGINS', 'http://ok.example')
    monkeypatch.setenv('ALLOW_METHODS', 'GET,POST')
    monkeypatch.setenv('ALLOW_HEADERS', 'Content-Type,X-CSRF-Token')
    monkeypatch.setenv('ALLOW_CREDENTIALS', 'true')
    body = {
        'origin': 'http://ok.example',
        'method': 'GET',
        'request_headers': ['X-CSRF-Token'],
        'with_credentials': True,
    }
    r = await authed_client.post('/platform/tools/cors/check', json=body)
    assert r.status_code == 200
    data = r.json()
    assert data.get('preflight', {}).get('allowed') is True


@pytest.mark.asyncio
async def test_tools_cors_checker_denies_when_method_not_allowed(monkeypatch, authed_client):
    await _allow_tools(authed_client)
    monkeypatch.setenv('ALLOWED_ORIGINS', 'http://ok.example')
    monkeypatch.setenv('ALLOW_METHODS', 'GET')
    body = {'origin': 'http://ok.example', 'method': 'DELETE'}
    r = await authed_client.post('/platform/tools/cors/check', json=body)
    assert r.status_code == 200
    data = r.json()
    assert data.get('preflight', {}).get('allowed') is False
    assert data.get('preflight', {}).get('method_allowed') is False


@pytest.mark.asyncio
async def test_tools_cors_checker_denies_when_headers_not_allowed(monkeypatch, authed_client):
    await _allow_tools(authed_client)
    monkeypatch.setenv('ALLOWED_ORIGINS', 'http://ok.example')
    monkeypatch.setenv('ALLOW_METHODS', 'GET')
    monkeypatch.setenv('ALLOW_HEADERS', 'Content-Type')
    body = {'origin': 'http://ok.example', 'method': 'GET', 'request_headers': ['X-CSRF-Token']}
    r = await authed_client.post('/platform/tools/cors/check', json=body)
    assert r.status_code == 200
    data = r.json()
    assert data.get('preflight', {}).get('allowed') is False
    assert 'X-CSRF-Token' in (data.get('preflight', {}).get('not_allowed_headers') or [])


@pytest.mark.asyncio
async def test_tools_cors_checker_credentials_and_wildcard_interaction(monkeypatch, authed_client):
    await _allow_tools(authed_client)
    monkeypatch.setenv('ALLOWED_ORIGINS', '*')
    monkeypatch.setenv('ALLOW_CREDENTIALS', 'true')
    monkeypatch.setenv('CORS_STRICT', 'false')
    body = {'origin': 'http://arbitrary.example', 'method': 'GET', 'request_headers': []}
    r = await authed_client.post('/platform/tools/cors/check', json=body)
    assert r.status_code == 200
    data = r.json()
    assert data.get('preflight', {}).get('allow_origin') is True
    assert any('Wildcard origins' in n for n in data.get('notes') or [])
