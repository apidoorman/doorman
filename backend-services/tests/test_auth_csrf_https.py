import pytest

@pytest.mark.asyncio
async def test_auth_rejects_missing_csrf_when_https_enabled(monkeypatch, authed_client):
    monkeypatch.setenv('HTTPS_ONLY', 'true')
    r = await authed_client.get('/platform/user/me')
    assert r.status_code == 401

@pytest.mark.asyncio
async def test_auth_rejects_mismatched_csrf_when_https_enabled(monkeypatch, authed_client):
    monkeypatch.setenv('HTTPS_ONLY', 'true')
    r = await authed_client.get('/platform/user/me', headers={'X-CSRF-Token': 'not-the-cookie'})
    assert r.status_code == 401

@pytest.mark.asyncio
async def test_auth_accepts_matching_csrf(monkeypatch, authed_client):
    monkeypatch.setenv('HTTPS_ONLY', 'true')
    csrf = None
    for c in authed_client.cookies.jar:
        if c.name == 'csrf_token':
            csrf = c.value
            break
    assert csrf, 'csrf_token cookie not found'
    r = await authed_client.get('/platform/user/me', headers={'X-CSRF-Token': csrf})
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_auth_http_mode_skips_csrf_validation(monkeypatch, authed_client):
    monkeypatch.setenv('HTTPS_ONLY', 'false')
    monkeypatch.setenv('HTTPS_ENABLED', 'false')
    r = await authed_client.get('/platform/user/me')
    assert r.status_code == 200

