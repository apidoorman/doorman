import os
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
async def test_memory_dump_restore_permissions(authed_client, monkeypatch, tmp_path):
    monkeypatch.setenv('MEM_ENCRYPTION_KEY', 'test-encryption-key-32-characters-min')

    # Limited user cannot dump/restore
    uname = f'mem_limited_{int(time.time())}'
    pwd = 'MemoryUserStrong1!!'
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
    d = await limited.post('/platform/memory/dump', json={})
    assert d.status_code == 403
    r = await limited.post('/platform/memory/restore', json={})
    assert r.status_code == 403

    # Role with manage_security can dump/restore
    rname = f'sec_manager_{int(time.time())}'
    cr = await authed_client.post(
        '/platform/role', json={'role_name': rname, 'manage_security': True}
    )
    assert cr.status_code in (200, 201)
    uname2 = f'mem_mgr_{int(time.time())}'
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

    # Dump to temp
    target = str(tmp_path / 'memdump.bin')
    dump = await mgr.post('/platform/memory/dump', json={'path': target})
    assert dump.status_code == 200
    body = dump.json().get('response', dump.json())
    path = body.get('response', {}).get('path') or body.get('path')
    assert path and os.path.exists(path)

    # Restore
    res = await mgr.post('/platform/memory/restore', json={'path': path})
    assert res.status_code == 200
