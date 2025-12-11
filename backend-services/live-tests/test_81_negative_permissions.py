import random
import time

import pytest

pytestmark = [pytest.mark.security]


def _mk_user_payload(role_name: str) -> tuple[str, str, str, dict]:
    ts = int(time.time())
    uname = f'min_{ts}_{random.randint(1000, 9999)}'
    email = f'{uname}@example.com'
    pwd = 'Strong!Passw0rd1234'
    payload = {
        'username': uname,
        'email': email,
        'password': pwd,
        'role': role_name,
        'groups': ['ALL'],
        'ui_access': True,
    }
    return uname, email, pwd, payload


def test_negative_permissions_for_logs_and_config(client):
    role_name = f'minrole_{int(time.time())}'
    r = client.post('/platform/role', json={'role_name': role_name, 'role_description': 'minimal'})
    assert r.status_code in (200, 201)

    uname, email, pwd, payload = _mk_user_payload(role_name)
    r = client.post('/platform/user', json=payload)
    assert r.status_code in (200, 201)

    from client import LiveClient

    u = LiveClient(client.base_url)
    u.login(email, pwd)

    r = u.get('/platform/logging/logs')
    assert r.status_code == 403
    r = u.get('/platform/config/export/all')
    assert r.status_code == 403
    r = u.get('/platform/routing/all')
    assert r.status_code == 403

    client.delete(f'/platform/user/{uname}')
    client.delete(f'/platform/role/{role_name}')
