import os
import time
import random
import string

def _strong_password() -> str:
    upp = random.choice(string.ascii_uppercase)
    low = ''.join(random.choices(string.ascii_lowercase, k=8))
    dig = ''.join(random.choices(string.digits, k=4))
    spc = random.choice('!@#$%^&*()-_=+[]{};:,.<>?/')
    tail = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    raw = upp + low + dig + spc + tail
    return ''.join(random.sample(raw, len(raw)))

def test_user_onboarding_lifecycle(client):
    username = f"user_{int(time.time())}_{random.randint(1000,9999)}"
    email = f"{username}@example.com"
    pwd = _strong_password()

    payload = {
        'username': username,
        'email': email,
        'password': pwd,
        'role': 'developer',
        'groups': ['ALL'],
        'ui_access': False
    }
    r = client.post('/platform/user', json=payload)
    assert r.status_code in (200, 201), r.text

    r = client.get(f'/platform/user/{username}')
    assert r.status_code == 200
    data = r.json().get('response', r.json())
    assert data.get('email') == email
    assert data.get('ui_access') is False

    r = client.put(f'/platform/user/{username}', json={'ui_access': True})
    assert r.status_code in (200, 204), r.text

    new_pwd = _strong_password()
    r = client.put(f'/platform/user/{username}/update-password', json={
        'old_password': pwd,
        'new_password': new_pwd
    })
    assert r.status_code in (200, 204, 400), r.text

    from client import LiveClient
    user_client = LiveClient(client.base_url)
    auth = user_client.login(email, new_pwd if r.status_code in (200, 204) else pwd)
    assert 'access_token' in auth.get('response', auth)
    r = user_client.get('/platform/user/me')
    assert r.status_code == 200
    me = r.json().get('response', r.json())
    assert me.get('username') == username
    assert me.get('ui_access') is True

    r = client.delete(f'/platform/user/{username}')
    assert r.status_code in (200, 204), r.text
import pytest
pytestmark = [pytest.mark.users, pytest.mark.auth]
