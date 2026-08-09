import time

import pytest


@pytest.mark.asyncio
async def test_security_settings_get_put_permissions(authed_client):
    # Limited user: 403 on get/put
    uname = f'sec_limited_{int(time.time())}'
    pwd = 'SecLimitStrongPass1!!'
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

    from httpx import AsyncClient

    from doorman import doorman

    limited = AsyncClient(app=doorman, base_url='http://testserver')
    r = await limited.post(
        '/platform/authorization', json={'email': f'{uname}@example.com', 'password': pwd}
    )
    assert r.status_code == 200
    get403 = await limited.get('/platform/security/settings')
    assert get403.status_code == 403
    put403 = await limited.put('/platform/security/settings', json={'trust_x_forwarded_for': True})
    assert put403.status_code == 403

    # Role manage_security: 200 on get/put
    rname = f'sec_mgr_{int(time.time())}'
    cr = await authed_client.post(
        '/platform/role', json={'role_name': rname, 'manage_security': True}
    )
    assert cr.status_code in (200, 201)
    uname2 = f'sec_mgr_user_{int(time.time())}'
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
    mgr = AsyncClient(app=doorman, base_url='http://testserver')
    r2 = await mgr.post(
        '/platform/authorization', json={'email': f'{uname2}@example.com', 'password': pwd}
    )
    assert r2.status_code == 200
    g = await mgr.get('/platform/security/settings')
    assert g.status_code == 200
    u = await mgr.put('/platform/security/settings', json={'trust_x_forwarded_for': True})
    assert u.status_code == 200
