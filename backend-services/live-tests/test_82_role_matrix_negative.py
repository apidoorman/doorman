import time

import pytest

pytestmark = [pytest.mark.security, pytest.mark.roles]


def _mk_user(client, role_name: str):
    ts = int(time.time())
    uname = f'perm_{ts}'
    email = f'{uname}@example.com'
    pwd = 'Strong!Passw0rd1234'
    r = client.post(
        '/platform/user',
        json={
            'username': uname,
            'email': email,
            'password': pwd,
            'role': role_name,
            'groups': ['ALL'],
            'ui_access': True,
            'rate_limit_duration': 1000000,
            'rate_limit_duration_type': 'second',
            'throttle_duration': 1000000,
            'throttle_duration_type': 'second',
            'throttle_queue_limit': 1000000,
            'throttle_wait_duration': 0,
            'throttle_wait_duration_type': 'second',
        },
    )
    assert r.status_code in (200, 201), r.text
    return uname, email, pwd


def _login(base_client, email, pwd):
    from client import LiveClient

    c = LiveClient(base_client.base_url)
    c.login(email, pwd)
    return c


def test_permission_matrix_block_then_allow(client):
    api_name = f'permapi-{int(time.time())}'
    api_version = 'v1'
    client.post(
        '/platform/api',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'perm',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://127.0.0.1:9'],
            'api_type': 'REST',
            'active': True,
        },
    )

    def try_manage_apis(c):
        return c.post(
            '/platform/api',
            json={
                'api_name': f'pa-{int(time.time())}',
                'api_version': 'v1',
                'api_description': 'x',
                'api_allowed_roles': ['admin'],
                'api_allowed_groups': ['ALL'],
                'api_servers': ['http://127.0.0.1:9'],
                'api_type': 'REST',
            },
        )

    def try_manage_endpoints(c):
        return c.post(
            '/platform/endpoint',
            json={
                'api_name': api_name,
                'api_version': api_version,
                'endpoint_method': 'GET',
                'endpoint_uri': f'/p{int(time.time())}',
                'endpoint_description': 'x',
            },
        )

    def try_manage_users(c):
        return c.post(
            '/platform/user',
            json={
                'username': f'u{int(time.time())}',
                'email': f'u{int(time.time())}@ex.com',
                'password': 'Strong!Passw0rd1234',
                'role': 'viewer',
                'groups': ['ALL'],
                'ui_access': False,
            },
        )

    def try_manage_groups(c):
        return c.post(
            '/platform/group', json={'group_name': f'g{int(time.time())}', 'group_description': 'x'}
        )

    def try_manage_roles(c):
        return c.post(
            '/platform/role', json={'role_name': f'r{int(time.time())}', 'role_description': 'x'}
        )

    matrix = [
        ('manage_apis', try_manage_apis, 'API007'),
        ('manage_endpoints', try_manage_endpoints, 'END010'),
        ('manage_users', try_manage_users, 'USR006'),
        ('manage_groups', try_manage_groups, 'GRP008'),
        ('manage_roles', try_manage_roles, 'ROLE009'),
    ]

    for perm_field, attempt, expected_code in matrix:
        role_name = f'role_{perm_field}_{int(time.time())}'
        r = client.post(
            '/platform/role',
            json={'role_name': role_name, 'role_description': 'matrix', perm_field: False},
        )
        assert r.status_code in (200, 201), r.text
        uname, email, pwd = _mk_user(client, role_name)
        uc = _login(client, email, pwd)
        resp = attempt(uc)
        assert resp.status_code == 403, f'{perm_field} should be blocked: {resp.text}'
        data = resp.json()
        code = data.get('error_code') or (data.get('response') or {}).get('error_code')
        assert code == expected_code

        client.put(f'/platform/role/{role_name}', json={perm_field: True})
        resp2 = attempt(uc)
        assert resp2.status_code != 403, f'{perm_field} still blocked after enable: {resp2.text}'

        client.delete(f'/platform/user/{uname}')
        client.delete(f'/platform/role/{role_name}')

    client.delete(f'/platform/api/{api_name}/{api_version}')
