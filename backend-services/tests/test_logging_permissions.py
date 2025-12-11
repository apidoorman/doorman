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
async def test_logging_routes_permissions(authed_client):
    # Limited user without view_logs/export_logs
    uname = f'log_limited_{int(time.time())}'
    pwd = 'LogLimitStrongPass1!!'
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
    for ep in (
        '/platform/logging/logs',
        '/platform/logging/logs/files',
        '/platform/logging/logs/statistics',
    ):
        r = await limited.get(ep)
        assert r.status_code == 403
    exp = await limited.get('/platform/logging/logs/export')
    assert exp.status_code == 403

    # Role with view_logs only
    rname = f'view_logs_{int(time.time())}'
    cr = await authed_client.post('/platform/role', json={'role_name': rname, 'view_logs': True})
    assert cr.status_code in (200, 201)
    vuser = f'log_viewer_{int(time.time())}'
    cu2 = await authed_client.post(
        '/platform/user',
        json={
            'username': vuser,
            'email': f'{vuser}@example.com',
            'password': pwd,
            'role': rname,
            'groups': ['ALL'],
            'ui_access': True,
        },
    )
    assert cu2.status_code in (200, 201)
    viewer = await _login(f'{vuser}@example.com', pwd)
    for ep in (
        '/platform/logging/logs',
        '/platform/logging/logs/files',
        '/platform/logging/logs/statistics',
    ):
        r = await viewer.get(ep)
        assert r.status_code == 200
    # But export still forbidden without export_logs
    exp2 = await viewer.get('/platform/logging/logs/export')
    assert exp2.status_code == 403

    # Role with export_logs
    rname2 = f'export_logs_{int(time.time())}'
    cr2 = await authed_client.post(
        '/platform/role', json={'role_name': rname2, 'export_logs': True}
    )
    assert cr2.status_code in (200, 201)
    euser = f'log_exporter_{int(time.time())}'
    cu3 = await authed_client.post(
        '/platform/user',
        json={
            'username': euser,
            'email': f'{euser}@example.com',
            'password': pwd,
            'role': rname2,
            'groups': ['ALL'],
            'ui_access': True,
        },
    )
    assert cu3.status_code in (200, 201)
    exporter = await _login(f'{euser}@example.com', pwd)
    exp3 = await exporter.get('/platform/logging/logs/export')
    assert exp3.status_code == 200
