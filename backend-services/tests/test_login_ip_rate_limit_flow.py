import os

import pytest


@pytest.mark.asyncio
async def test_login_ip_rate_limit_returns_429_and_headers(monkeypatch, client):
    monkeypatch.setenv('LOGIN_IP_RATE_LIMIT', '2')
    monkeypatch.setenv('LOGIN_IP_RATE_WINDOW', '60')
    monkeypatch.setenv('LOGIN_IP_RATE_DISABLED', 'false')

    creds = {
        'email': os.environ.get('DOORMAN_ADMIN_EMAIL', 'admin@doorman.dev'),
        'password': os.environ.get('DOORMAN_ADMIN_PASSWORD', 'Password123!Password'),
    }

    r1 = await client.post('/platform/authorization', json=creds)
    assert r1.status_code in (200, 400, 401)

    r2 = await client.post('/platform/authorization', json=creds)
    assert r2.status_code in (200, 400, 401)

    r3 = await client.post('/platform/authorization', json=creds)
    assert r3.status_code == 429

    assert 'Retry-After' in r3.headers
    assert 'X-RateLimit-Limit' in r3.headers
    assert 'X-RateLimit-Remaining' in r3.headers
    assert 'X-RateLimit-Reset' in r3.headers

    body = r3.json()
    payload = body.get('response', body)
    assert isinstance(payload, dict)
    assert 'error_code' in payload or 'error_message' in payload
