import time

import pytest


@pytest.mark.asyncio
async def test_vault_routes_permissions(authed_client):
    # Limited user
    uname = f'vault_limited_{int(time.time())}'
    pwd = 'VaultLimitStrongPass1!!'
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
    # Vault operations require manage_security
    sk = await limited.post('/platform/vault', json={'key_name': 'k', 'value': 'v'})
    # Without manage_security and possibly without VAULT_KEY, expect 403 or 400/404/500 depending on env
    assert sk.status_code in (403, 400, 404, 500)
