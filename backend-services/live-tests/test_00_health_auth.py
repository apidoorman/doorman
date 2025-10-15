import pytest

def test_status_ok(client):
    r = client.get('/api/health')
    assert r.status_code == 200
    j = r.json()
    data = j.get('response') if isinstance(j, dict) else None
    if not isinstance(data, dict):
        data = j if isinstance(j, dict) else {}
    if 'status' in data:
        assert data.get('status') in ('online', 'healthy')
    else:
        assert 'error_code' in (j or {})

def test_auth_status_me(client):
    r = client.get('/platform/authorization/status')
    assert r.status_code in (200, 204)

    r = client.get('/platform/user/me')
    assert r.status_code == 200
    me = r.json().get('response', r.json())
    assert me.get('username') == 'admin'
    assert me.get('ui_access') is True
import pytest
pytestmark = [pytest.mark.health, pytest.mark.auth]
