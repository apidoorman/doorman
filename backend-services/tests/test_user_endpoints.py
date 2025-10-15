import pytest

@pytest.mark.asyncio
async def test_user_me_and_crud(authed_client):

    me = await authed_client.get('/platform/user/me')
    assert me.status_code == 200
    assert me.json().get('username') == 'admin'

    cu = await authed_client.post(
        '/platform/user',
        json={
            'username': 'testuser1',
            'email': 'testuser1@example.com',
            'password': 'ThisIsAStrongPwd!123',
            'role': 'admin',
            'groups': ['ALL'],
            'active': True,
            'ui_access': False,
        },
    )
    assert cu.status_code in (200, 201)

    uu = await authed_client.put('/platform/user/testuser1', json={'email': 'new@mail.com'})
    assert uu.status_code == 200

    up = await authed_client.put(
        '/platform/user/testuser1/update-password',
        json={'new_password': 'ThisIsANewPwd!456'},
    )
    assert up.status_code == 200

    du = await authed_client.delete('/platform/user/testuser1')
    assert du.status_code == 200
