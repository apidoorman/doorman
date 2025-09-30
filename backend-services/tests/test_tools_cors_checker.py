# External imports
import pytest

@pytest.mark.asyncio
async def test_cors_checker_allows_matching_origin(monkeypatch, authed_client):

    monkeypatch.setenv('ALLOWED_ORIGINS', 'http://localhost:3000')
    monkeypatch.setenv('ALLOW_METHODS', 'GET,POST')
    monkeypatch.setenv('ALLOW_HEADERS', 'Content-Type,X-CSRF-Token')
    monkeypatch.setenv('ALLOW_CREDENTIALS', 'true')
    monkeypatch.setenv('CORS_STRICT', 'true')

    body = {
        'origin': 'http://localhost:3000',
        'method': 'GET',
        'request_headers': ['Content-Type'],
        'with_credentials': True
    }
    r = await authed_client.post('/platform/tools/cors/check', json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get('preflight', {}).get('allowed') is True
    assert data.get('actual', {}).get('allowed') is True
    assert data.get('preflight', {}).get('response_headers', {}).get('Access-Control-Allow-Origin') == body['origin']

@pytest.mark.asyncio
async def test_cors_checker_denies_disallowed_header(monkeypatch, authed_client):
    monkeypatch.setenv('ALLOWED_ORIGINS', 'http://localhost:3000')
    monkeypatch.setenv('ALLOW_METHODS', 'GET,POST')
    monkeypatch.setenv('ALLOW_HEADERS', 'Content-Type')
    monkeypatch.setenv('ALLOW_CREDENTIALS', 'true')
    monkeypatch.setenv('CORS_STRICT', 'true')

    body = {
        'origin': 'http://localhost:3000',
        'method': 'GET',
        'request_headers': ['X-Custom-Header'],
        'with_credentials': True
    }
    r = await authed_client.post('/platform/tools/cors/check', json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get('preflight', {}).get('allowed') is False
    assert 'X-Custom-Header' in (data.get('preflight', {}).get('not_allowed_headers') or [])
