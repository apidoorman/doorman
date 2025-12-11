import time

import pytest
from httpx import AsyncClient


async def _login(email: str, password: str) -> AsyncClient:
    from doorman import doorman

    c = AsyncClient(app=doorman, base_url='http://testserver')
    r = await c.post('/platform/authorization', json={'email': email, 'password': password})
    assert r.status_code == 200
    body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
    token = body.get('access_token')
    if token:
        c.cookies.set('access_token_cookie', token, domain='testserver', path='/')
    return c


@pytest.mark.asyncio
async def test_non_admin_cannot_create_admin_role(authed_client):
    # Create a user with manage_roles but not admin
    rname = f'mgr_roles_{int(time.time())}'
    cr = await authed_client.post('/platform/role', json={'role_name': rname, 'manage_roles': True})
    assert cr.status_code in (200, 201)
    uname = f'role_mgr_{int(time.time())}'
    pwd = 'RoleMgrStrongPass1!!'
    cu = await authed_client.post(
        '/platform/user',
        json={
            'username': uname,
            'email': f'{uname}@example.com',
            'password': pwd,
            'role': rname,
            'groups': ['ALL'],
            'ui_access': True,
        },
    )
    assert cu.status_code in (200, 201)
    mgr = await _login(f'{uname}@example.com', pwd)
    # Attempt to create 'admin' role (should be forbidden for non-admin)
    admin_create = await mgr.post(
        '/platform/role', json={'role_name': 'admin', 'manage_roles': True}
    )
    assert admin_create.status_code == 403
