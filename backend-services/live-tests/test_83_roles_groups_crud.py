import time
import pytest

pytestmark = [pytest.mark.security, pytest.mark.roles]


def test_roles_groups_crud_and_list(client):
    role = f"rolex-{int(time.time())}"
    group = f"groupx-{int(time.time())}"
    # Create
    r = client.post('/platform/role', json={'role_name': role, 'role_description': 'x', 'manage_users': True})
    assert r.status_code in (200, 201)
    r = client.post('/platform/group', json={'group_name': group, 'group_description': 'x'})
    assert r.status_code in (200, 201)
    # List
    r = client.get('/platform/role/all')
    assert r.status_code == 200
    roles = r.json().get('response', r.json())
    if isinstance(roles, dict) and 'roles' in roles:
        roles = roles['roles']
    assert isinstance(roles, list)
    r = client.get('/platform/group/all')
    assert r.status_code == 200
    groups = r.json().get('response', r.json())
    if isinstance(groups, dict) and 'groups' in groups:
        groups = groups['groups']
    assert isinstance(groups, list)
    # Delete
    client.delete(f'/platform/group/{group}')
    client.delete(f'/platform/role/{role}')
