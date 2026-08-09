import os

import pytest


@pytest.mark.asyncio
async def test_authorization_login_and_status(client):
    resp = await client.post(
        '/platform/authorization',
        json={
            'email': os.environ['DOORMAN_ADMIN_EMAIL'],
            'password': os.environ['DOORMAN_ADMIN_PASSWORD'],
        },
    )
    assert resp.status_code == 200

    assert any(c.name == 'access_token_cookie' for c in client.cookies.jar)

    status = await client.get('/platform/authorization/status')
    assert status.status_code == 200
    body = status.json()
    assert body.get('message') == 'Token is valid'


@pytest.mark.asyncio
async def test_auth_refresh_and_invalidate(authed_client):
    r = await authed_client.post('/platform/authorization/refresh')
    assert r.status_code == 200

    inv = await authed_client.post('/platform/authorization/invalidate')
    assert inv.status_code == 200

    status = await authed_client.get('/platform/authorization/status')
    assert status.status_code in (401, 500)


@pytest.mark.asyncio
async def test_authorization_invalid_login(client):
    resp = await client.post(
        '/platform/authorization', json={'email': 'unknown@example.com', 'password': 'bad'}
    )
    assert resp.status_code in (400, 401)
