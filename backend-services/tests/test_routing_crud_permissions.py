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
async def test_routing_crud_requires_manage_routings(authed_client):
    client_key = f'client_{int(time.time())}'
    # Limited user
    uname = f'route_limited_{int(time.time())}'
    pwd = 'RouteLimitStrong1!!'
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
    limited = await _login(f'{uname}@example.com', pwd)
    # Create denied
    cr = await limited.post(
        '/platform/routing',
        json={'client_key': client_key, 'routing_name': 'r1', 'routing_servers': ['http://up']},
    )
    assert cr.status_code == 403

    # Grant manage_routings
    rname = f'route_mgr_{int(time.time())}'
    rr = await authed_client.post(
        '/platform/role', json={'role_name': rname, 'manage_routings': True}
    )
    assert rr.status_code in (200, 201)
    uname2 = f'route_mgr_user_{int(time.time())}'
    cu2 = await authed_client.post(
        '/platform/user',
        json={
            'username': uname2,
            'email': f'{uname2}@example.com',
            'password': pwd,
            'role': rname,
            'groups': ['ALL'],
            'ui_access': True,
        },
    )
    assert cu2.status_code in (200, 201)
    mgr = await _login(f'{uname2}@example.com', pwd)

    # Create allowed
    ok = await mgr.post(
        '/platform/routing',
        json={'client_key': client_key, 'routing_name': 'r1', 'routing_servers': ['http://up']},
    )
    assert ok.status_code in (200, 201)
    # Get allowed
    gl = await mgr.get('/platform/routing/all')
    assert gl.status_code == 200
    # Update allowed
    up = await mgr.put(f'/platform/routing/{client_key}', json={'routing_description': 'updated'})
    assert up.status_code == 200
    # Delete allowed
    de = await mgr.delete(f'/platform/routing/{client_key}')
    assert de.status_code == 200
