# External imports
import pytest

@pytest.mark.asyncio
async def test_security_settings_requires_permission(authed_client):

    r = await authed_client.put('/platform/role/admin', json={'manage_security': False})
    assert r.status_code in (200, 201)

    gs = await authed_client.get('/platform/security/settings')
    assert gs.status_code == 403

    us = await authed_client.put('/platform/security/settings', json={'enable_auto_save': True})
    assert us.status_code == 403

    r2 = await authed_client.put('/platform/role/admin', json={'manage_security': True})
    assert r2.status_code in (200, 201)

    gs2 = await authed_client.get('/platform/security/settings')
    assert gs2.status_code == 200

