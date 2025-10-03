def test_token_refresh_and_invalidate(client):
    # Refresh token (should succeed and keep session valid)
    r = client.post('/platform/authorization/refresh', json={})
    assert r.status_code in (200, 204)
    # Status endpoint should still be accessible
    r = client.get('/platform/authorization/status')
    assert r.status_code in (200, 204)

    # Invalidate
    r = client.post('/platform/authorization/invalidate', json={})
    assert r.status_code in (200, 204)
    # Now protected route should be unauthorized
    r = client.get('/platform/user/me')
    assert r.status_code == 401

    # Re-login to restore session for subsequent tests
    from config import ADMIN_EMAIL, ADMIN_PASSWORD
    client.login(ADMIN_EMAIL, ADMIN_PASSWORD)


def test_admin_revoke_tokens_for_user(client):
    # Create a new user and login
    import time, random, string
    ts = int(time.time())
    uname = f'revoke_{ts}_{random.randint(1000,9999)}'
    email = f'{uname}@example.com'
    pwd = 'Strong!Passw0rd1234'
    r = client.post('/platform/user', json={
        'username': uname,
        'email': email,
        'password': pwd,
        'role': 'admin',
        'groups': ['ALL'],
        'ui_access': True
    })
    assert r.status_code in (200, 201), r.text
    from client import LiveClient
    user_client = LiveClient(client.base_url)
    user_client.login(email, pwd)
    # Revoke tokens as admin
    r = client.post(f'/platform/authorization/admin/revoke/{uname}', json={})
    assert r.status_code == 200
    # User client should now be unauthorized
    r = user_client.get('/platform/user/me')
    assert r.status_code == 401
    # Cleanup
    client.delete(f'/platform/user/{uname}')
import pytest
pytestmark = [pytest.mark.auth]
