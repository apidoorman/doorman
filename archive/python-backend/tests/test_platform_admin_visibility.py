import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def login_client():
    async def _login(username: str, password: str, email: str = None) -> AsyncClient:
        from doorman import doorman

        client = AsyncClient(app=doorman, base_url='http://testserver')
        cred = {'email': email or f'{username}@example.com', 'password': password}
        r = await client.post('/platform/authorization', json=cred)
        assert r.status_code == 200, r.text
        return client

    return _login


async def _ensure_manager_role(authed_client: AsyncClient):
    payload = {
        'role_name': 'manager',
        'role_description': 'Manager role',
        'manage_users': True,
        'manage_apis': True,
        'manage_endpoints': True,
        'manage_groups': True,
        'manage_roles': True,
        'manage_routings': True,
        'manage_gateway': True,
        'manage_subscriptions': True,
        'manage_credits': True,
        'manage_auth': True,
        'view_logs': True,
        'export_logs': True,
    }
    r = await authed_client.post('/platform/role', json=payload)
    assert r.status_code in (200, 201, 400), r.text


async def _create_manager_user(authed_client: AsyncClient) -> dict:
    await _ensure_manager_role(authed_client)
    uname = f'mgr_{uuid.uuid4().hex[:8]}'
    payload = {
        'username': uname,
        'email': f'{uname}@example.com',
        'password': 'StrongManagerPwd!1234',
        'role': 'manager',
        'groups': ['ALL'],
        'active': True,
        'ui_access': True,
    }
    r = await authed_client.post('/platform/user', json=payload)
    assert r.status_code in (200, 201), r.text
    return payload


@pytest.mark.asyncio
async def test_non_admin_cannot_see_admin_role(authed_client, login_client):
    mgr = await _create_manager_user(authed_client)
    client = await login_client(mgr['username'], 'StrongManagerPwd!1234', mgr['email'])

    rr = await client.get('/platform/role/all?page=1&page_size=50')
    assert rr.status_code == 200, rr.text
    roles = rr.json().get('roles') or []
    names = {r.get('role_name', '').lower() for r in roles}
    assert 'admin' not in names and 'platform admin' not in names

    r1 = await client.get('/platform/role/admin')
    assert r1.status_code == 404

    await client.aclose()


@pytest.mark.asyncio
async def test_non_admin_cannot_see_or_modify_admin_users(authed_client, login_client):
    mgr = await _create_manager_user(authed_client)
    client = await login_client(mgr['username'], 'StrongManagerPwd!1234', mgr['email'])

    ru = await client.get('/platform/user/all?page=1&page_size=200')
    assert ru.status_code == 200, ru.text
    users = ru.json().get('users') or []
    assert all(u.get('role', '').lower() not in ('admin', 'platform admin') for u in users)

    r_detail = await client.get('/platform/user/admin')
    assert r_detail.status_code == 404

    r_upd = await client.put('/platform/user/admin', json={'ui_access': True})
    assert r_upd.status_code in (403, 404)
    r_del = await client.delete('/platform/user/admin')
    assert r_del.status_code in (403, 404)

    await client.aclose()


@pytest.mark.asyncio
async def test_non_admin_cannot_assign_admin_role(authed_client, login_client):
    mgr = await _create_manager_user(authed_client)
    client = await login_client(mgr['username'], 'StrongManagerPwd!1234', mgr['email'])

    newu = f'np_{uuid.uuid4().hex[:8]}'
    r_create = await client.post(
        '/platform/user',
        json={
            'username': newu,
            'email': f'{newu}@example.com',
            'password': 'StrongPwd!1234XYZ',
            'role': 'admin',
            'groups': ['ALL'],
            'active': True,
            'ui_access': True,
        },
    )
    assert r_create.status_code in (403, 404)

    r_update = await client.put(f'/platform/user/{mgr["username"]}', json={'role': 'admin'})
    assert r_update.status_code in (403, 404)

    await client.aclose()


@pytest.mark.asyncio
async def test_non_admin_auth_admin_ops_hidden(authed_client, login_client):
    mgr = await _create_manager_user(authed_client)
    client = await login_client(mgr['username'], 'StrongManagerPwd!1234', mgr['email'])

    for path in [
        '/platform/authorization/admin/status/admin',
        '/platform/authorization/admin/revoke/admin',
        '/platform/authorization/admin/unrevoke/admin',
        '/platform/authorization/admin/disable/admin',
        '/platform/authorization/admin/enable/admin',
    ]:
        if path.endswith('status/admin'):
            r = await client.get(path)
        else:
            r = await client.post(path)
        assert r.status_code in (404, 403), (
            f'Expected 404/403 for {path}, got {r.status_code}: {r.text}'
        )

    await client.aclose()
