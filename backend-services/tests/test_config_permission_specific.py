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
async def test_export_apis_allowed_but_roles_forbidden(authed_client):
    uname = 'mgr_apis_only'
    pwd = 'PerM1ssionsMore!!'
    # Create role granting manage_apis only
    role_name = 'apis_manager'
    cr = await authed_client.post(
        '/platform/role',
        json={'role_name': role_name, 'role_description': 'Can export APIs', 'manage_apis': True},
    )
    assert cr.status_code in (200, 201), cr.text

    # Create user assigned to that role
    cu = await authed_client.post(
        '/platform/user',
        json={
            'username': uname,
            'email': 'mgr_apis@example.com',
            'password': pwd,
            'role': role_name,
            'groups': ['ALL'],
            'ui_access': True,
        },
    )
    assert cu.status_code in (200, 201)

    client = await _login('mgr_apis@example.com', pwd)

    # Allowed
    ok = await client.get('/platform/config/export/apis')
    assert ok.status_code == 200

    # Forbidden
    no = await client.get('/platform/config/export/roles')
    assert no.status_code == 403
