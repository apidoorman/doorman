import pytest


@pytest.mark.asyncio
async def test_tools_cors_checker_strict_with_credentials_blocks_wildcard(
    monkeypatch, authed_client
):
    monkeypatch.setenv('ALLOWED_ORIGINS', '*')
    monkeypatch.setenv('ALLOW_CREDENTIALS', 'true')
    monkeypatch.setenv('CORS_STRICT', 'true')

    r = await authed_client.post(
        '/platform/tools/cors/check',
        json={
            'origin': 'http://evil.example',
            'with_credentials': True,
            'method': 'GET',
            'request_headers': ['Content-Type'],
        },
    )
    assert r.status_code == 200
    body = r.json().get('response', r.json())
    pre = body.get('preflight', {})
    hdrs = pre.get('response_headers', {})
    assert hdrs.get('Access-Control-Allow-Origin') in (None, '')
    assert hdrs.get('Access-Control-Allow-Credentials') == 'true'


@pytest.mark.asyncio
async def test_tools_cors_checker_non_strict_wildcard_with_credentials_allows(
    monkeypatch, authed_client
):
    monkeypatch.setenv('ALLOWED_ORIGINS', '*')
    monkeypatch.setenv('ALLOW_CREDENTIALS', 'true')
    monkeypatch.setenv('CORS_STRICT', 'false')

    r = await authed_client.post(
        '/platform/tools/cors/check',
        json={
            'origin': 'http://ok.example',
            'with_credentials': True,
            'method': 'GET',
            'request_headers': ['Content-Type'],
        },
    )
    assert r.status_code == 200
    body = r.json().get('response', r.json())
    pre = body.get('preflight', {})
    hdrs = pre.get('response_headers', {})
    assert hdrs.get('Access-Control-Allow-Origin') == 'http://ok.example'
    assert hdrs.get('Access-Control-Allow-Credentials') == 'true'
