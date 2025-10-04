import time
import random
import string

def _rand_user() -> tuple[str, str, str]:
    ts = int(time.time())
    uname = f"usr_{ts}_{random.randint(1000,9999)}"
    email = f"{uname}@example.com"
    upp = random.choice(string.ascii_uppercase)
    low = ''.join(random.choices(string.ascii_lowercase, k=8))
    dig = ''.join(random.choices(string.digits, k=4))
    spc = random.choice('!@#$%^&*()-_=+[]{};:,.<>?/')
    tail = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    pwd = ''.join(random.sample(upp + low + dig + spc + tail, len(upp + low + dig + spc + tail)))
    return uname, email, pwd

def test_role_permission_blocks_api_management(client):
    role_name = f"viewer_{int(time.time())}"
    r = client.post('/platform/role', json={
        'role_name': role_name,
        'role_description': 'temporary viewer',
        'view_logs': True
    })
    assert r.status_code in (200, 201), r.text

    uname, email, pwd = _rand_user()
    r = client.post('/platform/user', json={
        'username': uname,
        'email': email,
        'password': pwd,
        'role': role_name,
        'groups': ['ALL'],
        'ui_access': True
    })
    assert r.status_code in (200, 201), r.text

    from client import LiveClient
    user_client = LiveClient(client.base_url)
    user_client.login(email, pwd)

    api_name = f"nope-{int(time.time())}"
    r = user_client.post('/platform/api', json={
        'api_name': api_name,
        'api_version': 'v1',
        'api_description': 'should be blocked',
        'api_allowed_roles': [role_name],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://127.0.0.1:1'],
        'api_type': 'REST'
    })
    assert r.status_code == 403
    body = r.json()
    data = body.get('response', body)
    assert (data.get('error_code') or body.get('error_code')) in ('API007', 'API008')

    client.delete(f'/platform/user/{uname}')
    client.delete(f'/platform/role/{role_name}')
import pytest
pytestmark = [pytest.mark.security, pytest.mark.roles]
