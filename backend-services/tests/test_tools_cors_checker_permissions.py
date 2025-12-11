import time

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
async def test_tools_cors_checker_requires_manage_security(authed_client):
    uname = f'sec_check_{int(time.time())}'
    # Must meet password policy: >=16 chars, upper, lower, digit, special
    pwd = 'SecCheckStrongPass1!!'
    # No manage_security
    cu = await authed_client.post(
        '/platform/user',
        json={
            'username': uname,
            'email': f'{uname}@example.com',
            'password': pwd,
            'role': 'user',
            'groups': ['ALL'],
            'ui_access': True,
        },
    )
    assert cu.status_code in (200, 201)
    client = await _login(f'{uname}@example.com', pwd)
    r = await client.post(
        '/platform/tools/cors/check', json={'origin': 'http://x', 'method': 'GET'}
    )
    assert r.status_code == 403

    # Grant manage_security via role and new user
    role = f'sec_mgr_{int(time.time())}'
    cr = await authed_client.post(
        '/platform/role', json={'role_name': role, 'manage_security': True}
    )
    assert cr.status_code in (200, 201)
    uname2 = f'sec_check2_{int(time.time())}'
    cu2 = await authed_client.post(
        '/platform/user',
        json={
            'username': uname2,
            'email': f'{uname2}@example.com',
            'password': pwd,
            'role': role,
            'groups': ['ALL'],
            'ui_access': True,
        },
    )
    assert cu2.status_code in (200, 201)
    client2 = await _login(f'{uname2}@example.com', pwd)
    r2 = await client2.post(
        '/platform/tools/cors/check', json={'origin': 'http://x', 'method': 'GET'}
    )
    assert r2.status_code == 200
