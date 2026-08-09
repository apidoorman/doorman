import time

import pytest


@pytest.mark.asyncio
async def test_group_crud_permissions(authed_client):
    # Limited user
    uname = f'grp_limited_{int(time.time())}'
    pwd = 'GrpLimitStrongPass1!!'
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
    gname = f'g_{int(time.time())}'
    c403 = await limited.post(
        '/platform/group', json={'group_name': gname, 'group_description': 'x'}
    )
    assert c403.status_code == 403

    # Role with manage_groups
    rname = f'grpmgr_{int(time.time())}'
    cr = await authed_client.post(
        '/platform/role', json={'role_name': rname, 'manage_groups': True}
    )
    assert cr.status_code in (200, 201)
    uname2 = f'grp_mgr_user_{int(time.time())}'
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

    # Create
    c = await mgr.post('/platform/group', json={'group_name': gname, 'group_description': 'x'})
    assert c.status_code in (200, 201)
    # Get
    g = await mgr.get(f'/platform/group/{gname}')
    assert g.status_code == 200
    # Update
    u = await mgr.put(f'/platform/group/{gname}', json={'group_description': 'y'})
    assert u.status_code == 200
    # Delete
    d = await mgr.delete(f'/platform/group/{gname}')
    assert d.status_code == 200
