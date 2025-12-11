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
async def test_export_roles_allowed_manage_roles_only(authed_client):
    uname = f'roles_mgr_{int(time.time())}'
    role_name = f'roles_manager_{int(time.time())}'
    pwd = 'ManAgeRoleSStrong1!!'

    cr = await authed_client.post(
        '/platform/role', json={'role_name': role_name, 'manage_roles': True}
    )
    assert cr.status_code in (200, 201)

    cu = await authed_client.post(
        '/platform/user',
        json={
            'username': uname,
            'email': f'{uname}@example.com',
            'password': pwd,
            'role': role_name,
            'groups': ['ALL'],
            'ui_access': True,
        },
    )
    assert cu.status_code in (200, 201), cu.text

    client = await _login(f'{uname}@example.com', pwd)
    # Allowed
    ok = await client.get('/platform/config/export/roles')
    assert ok.status_code == 200
    # Forbidden
    no = await client.get('/platform/config/export/apis')
    assert no.status_code == 403


@pytest.mark.asyncio
async def test_export_groups_allowed_manage_groups_only(authed_client):
    uname = f'groups_mgr_{int(time.time())}'
    role_name = f'groups_manager_{int(time.time())}'
    pwd = 'ManAgeGroupSStrong1!!'

    cr = await authed_client.post(
        '/platform/role', json={'role_name': role_name, 'manage_groups': True}
    )
    assert cr.status_code in (200, 201)
    cu = await authed_client.post(
        '/platform/user',
        json={
            'username': uname,
            'email': f'{uname}@example.com',
            'password': pwd,
            'role': role_name,
            'groups': ['ALL'],
            'ui_access': True,
        },
    )
    assert cu.status_code in (200, 201)
    client = await _login(f'{uname}@example.com', pwd)
    ok = await client.get('/platform/config/export/groups')
    assert ok.status_code == 200
    no = await client.get('/platform/config/export/roles')
    assert no.status_code == 403


@pytest.mark.asyncio
async def test_export_routings_allowed_manage_routings_only(authed_client):
    uname = f'rout_mgr_{int(time.time())}'
    role_name = f'rout_manager_{int(time.time())}'
    pwd = 'ManAgeRoutIngS1!!'

    cr = await authed_client.post(
        '/platform/role', json={'role_name': role_name, 'manage_routings': True}
    )
    assert cr.status_code in (200, 201)
    cu = await authed_client.post(
        '/platform/user',
        json={
            'username': uname,
            'email': f'{uname}@example.com',
            'password': pwd,
            'role': role_name,
            'groups': ['ALL'],
            'ui_access': True,
        },
    )
    assert cu.status_code in (200, 201)
    client = await _login(f'{uname}@example.com', pwd)
    ok = await client.get('/platform/config/export/routings')
    assert ok.status_code == 200
    no = await client.get('/platform/config/export/endpoints')
    assert no.status_code == 403


@pytest.mark.asyncio
async def test_export_all_and_import_allowed_manage_gateway(authed_client):
    uname = f'gate_mgr_{int(time.time())}'
    role_name = f'gate_manager_{int(time.time())}'
    pwd = 'ManAgeGateWayStrong1!!'

    cr = await authed_client.post(
        '/platform/role', json={'role_name': role_name, 'manage_gateway': True}
    )
    assert cr.status_code in (200, 201)
    cu = await authed_client.post(
        '/platform/user',
        json={
            'username': uname,
            'email': f'{uname}@example.com',
            'password': pwd,
            'role': role_name,
            'groups': ['ALL'],
            'ui_access': True,
        },
    )
    assert cu.status_code in (200, 201)
    client = await _login(f'{uname}@example.com', pwd)
    ok = await client.get('/platform/config/export/all')
    assert ok.status_code == 200
    imp = await client.post('/platform/config/import', json={'apis': []})
    assert imp.status_code == 200
