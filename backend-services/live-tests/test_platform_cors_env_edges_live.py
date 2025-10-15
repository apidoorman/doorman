import os
import pytest

_RUN_LIVE = os.getenv('DOORMAN_RUN_LIVE', '0') in ('1', 'true', 'True')
if not _RUN_LIVE:
    pytestmark = pytest.mark.skip(reason='Requires live backend service; set DOORMAN_RUN_LIVE=1 to enable')

def test_platform_cors_strict_wildcard_credentials_edges_live(client, monkeypatch):
    monkeypatch.setenv('ALLOWED_ORIGINS', '*')
    monkeypatch.setenv('ALLOW_CREDENTIALS', 'true')
    monkeypatch.setenv('CORS_STRICT', 'true')
    r = client.options('/platform/api', headers={'Origin': 'http://evil.example', 'Access-Control-Request-Method': 'GET'})
    assert r.status_code == 204
    assert r.headers.get('Access-Control-Allow-Origin') in (None, '')

def test_platform_cors_methods_headers_defaults_live(client, monkeypatch):
    monkeypatch.setenv('ALLOW_METHODS', '')
    monkeypatch.setenv('ALLOW_HEADERS', '*')
    r = client.options('/platform/api', headers={'Origin': 'http://localhost:3000', 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'X-Rand'})
    assert r.status_code == 204
    methods = [m.strip() for m in (r.headers.get('Access-Control-Allow-Methods') or '').split(',') if m.strip()]
    assert set(methods) == {'GET','POST','PUT','DELETE','OPTIONS','PATCH','HEAD'}
