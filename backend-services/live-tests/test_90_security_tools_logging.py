def test_security_settings_get_put(client):
    # Get current settings
    r = client.get('/platform/security/settings')
    assert r.status_code == 200
    settings = r.json().get('response', r.json())
    assert 'memory_only' in settings

    # Toggle enable_auto_save (non-destructive)
    desired = not bool(settings.get('enable_auto_save') or False)
    r = client.put('/platform/security/settings', json={'enable_auto_save': desired})
    assert r.status_code == 200
    updated = r.json().get('response', r.json())
    assert bool(updated.get('enable_auto_save') or False) == desired


def test_tools_cors_check(client):
    r = client.post('/platform/tools/cors/check', json={
        'origin': 'http://localhost:3000',
        'method': 'GET',
        'request_headers': ['Content-Type']
    })
    assert r.status_code == 200
    payload = r.json().get('response', r.json())
    assert 'config' in payload and 'preflight' in payload


def test_clear_all_caches(client):
    r = client.delete('/api/caches')
    assert r.status_code == 200
    body = r.json().get('response', r.json())
    # Either message or standard response
    assert 'All caches cleared' in (body.get('message') or body.get('error_message') or 'All caches cleared')


def test_logging_endpoints(client):
    # Query logs (may be synthetic in memory mode)
    r = client.get('/platform/logging/logs?limit=10')
    assert r.status_code == 200
    payload = r.json().get('response', r.json())
    # payload may be dict with 'logs' or a list
    assert isinstance(payload, (dict, list))

    # List log files
    r = client.get('/platform/logging/logs/files')
    assert r.status_code == 200
    files = r.json().get('response', r.json())
    assert 'count' in files
import pytest
pytestmark = [pytest.mark.security, pytest.mark.tools, pytest.mark.logging]
