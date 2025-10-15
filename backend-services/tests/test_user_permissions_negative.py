import pytest

@pytest.mark.asyncio
async def test_update_other_user_denied_without_permission(authed_client):

    await authed_client.post(
        '/platform/role',
        json={'role_name': 'user', 'role_description': 'Standard user'},
    )

    cu = await authed_client.post(
        '/platform/user',
        json={'username': 'qa_user', 'email': 'qa@doorman.dev', 'password': 'QaPass123_ValidLen!!', 'role': 'user'},
    )
    assert cu.status_code in (200, 201), cu.text

    r = await authed_client.put('/platform/role/admin', json={'manage_users': False})
    assert r.status_code in (200, 201)

    up = await authed_client.put(
        '/platform/user/qa_user',
        json={'email': 'qa2@doorman.dev'},
    )
    assert up.status_code == 403

    r2 = await authed_client.put('/platform/role/admin', json={'manage_users': True})
    assert r2.status_code in (200, 201)
    up2 = await authed_client.put(
        '/platform/user/qa_user',
        json={'email': 'qa3@doorman.dev'},
    )
    assert up2.status_code in (200, 201)
