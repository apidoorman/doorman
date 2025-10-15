import os
import pytest

@pytest.mark.asyncio
async def test_cookie_domain_set_on_login(client, monkeypatch):

    monkeypatch.setenv('COOKIE_DOMAIN', 'testserver')
    resp = await client.post(
        '/platform/authorization',
        json={
            'email': os.environ['DOORMAN_ADMIN_EMAIL'],
            'password': os.environ['DOORMAN_ADMIN_PASSWORD'],
        },
    )
    assert resp.status_code == 200

    cookies = [c for c in client.cookies.jar if c.name == 'access_token_cookie']
    assert cookies, 'Auth cookie missing'

    assert cookies[0].domain in ('testserver', '.testserver', 'testserver.local')
