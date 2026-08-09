import pytest
from httpx import AsyncClient


async def _login(email: str, password: str) -> AsyncClient:
    from doorman import doorman

    c = AsyncClient(app=doorman, base_url='http://testserver')
    r = await c.post('/platform/authorization', json={'email': email, 'password': password})
    assert r.status_code == 200, r.text
    body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
    token = body.get('access_token')
    if token:
        c.cookies.set('access_token_cookie', token, domain='testserver', path='/')
    return c


@pytest.mark.asyncio
async def test_config_export_import_forbidden_for_non_admin(authed_client):
    # Create a limited user
    uname = 'limited_user'
    pwd = 'limited-password-1A!'
    cu = await authed_client.post(
        '/platform/user',
        json={
            'username': uname,
            'email': 'limited@example.com',
            'password': pwd,
            'role': 'user',
            'groups': ['ALL'],
            # No manage_* permissions
            'ui_access': True,
            'manage_users': False,
            'manage_apis': False,
            'manage_endpoints': False,
            'manage_groups': False,
            'manage_roles': False,
            'manage_routings': False,
            'manage_gateway': False,
        },
    )
    assert cu.status_code in (200, 201), cu.text

    user_client = await _login('limited@example.com', pwd)

    # Export endpoints require manage_* permissions – assert 403s
    endpoints = [
        '/platform/config/export/all',
        '/platform/config/export/apis',
        '/platform/config/export/roles',
        '/platform/config/export/groups',
        '/platform/config/export/routings',
        '/platform/config/export/endpoints',
    ]
    for ep in endpoints:
        r = await user_client.get(ep)
        assert r.status_code == 403

    # Import also requires manage_gateway
    imp = await user_client.post('/platform/config/import', json={'apis': []})
    assert imp.status_code == 403
