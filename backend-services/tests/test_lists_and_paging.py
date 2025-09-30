# External imports
import pytest

@pytest.mark.asyncio
async def test_list_endpoints_roles_groups_apis(authed_client):

    await authed_client.post(
        '/platform/api',
        json={
            'api_name': 'listapi',
            'api_version': 'v1',
            'api_description': 'list api',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://up'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
        },
    )
    await authed_client.post(
        '/platform/group',
        json={'group_name': 'glist', 'group_description': 'gd', 'api_access': []},
    )
    await authed_client.post(
        '/platform/role',
        json={'role_name': 'rlist', 'role_description': 'rd'},
    )

    ra = await authed_client.get('/platform/api/all?page=1&page_size=5')
    assert ra.status_code == 200
    rg = await authed_client.get('/platform/group/all?page=1&page_size=5')
    assert rg.status_code == 200
    rr = await authed_client.get('/platform/role/all?page=1&page_size=5')
    assert rr.status_code == 200

