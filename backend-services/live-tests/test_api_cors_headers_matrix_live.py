import os
import pytest

_RUN_LIVE = os.getenv('DOORMAN_RUN_LIVE', '0') in ('1', 'true', 'True')
if not _RUN_LIVE:
    pytestmark = pytest.mark.skip(reason='Requires live backend service; set DOORMAN_RUN_LIVE=1 to enable')


def test_api_cors_allow_origins_allow_methods_headers_credentials_expose_live(client):
    import time
    api_name = f'corslive-{int(time.time())}'
    ver = 'v1'
    client.post('/platform/api', json={
        'api_name': api_name,
        'api_version': ver,
        'api_description': 'cors live',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://upstream.example'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_cors_allow_origins': ['http://ok.example'],
        'api_cors_allow_methods': ['GET','POST'],
        'api_cors_allow_headers': ['Content-Type','X-CSRF-Token'],
        'api_cors_allow_credentials': True,
        'api_cors_expose_headers': ['X-Resp-Id'],
    })
    client.post('/platform/endpoint', json={'api_name': api_name, 'api_version': ver, 'endpoint_method': 'GET', 'endpoint_uri': '/q', 'endpoint_description': 'q'})
    client.post('/platform/subscription/subscribe', json={'username': 'admin', 'api_name': api_name, 'api_version': ver})
    # Preflight
    r = client.options(f'/api/rest/{api_name}/{ver}/q', headers={'Origin': 'http://ok.example', 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'X-CSRF-Token'})
    assert r.status_code == 204
    assert r.headers.get('Access-Control-Allow-Origin') == 'http://ok.example'
    assert 'GET' in (r.headers.get('Access-Control-Allow-Methods') or '')
    # Actual
    r2 = client.get(f'/api/rest/{api_name}/{ver}/q', headers={'Origin': 'http://ok.example'})
    assert r2.status_code in (200, 404)
    assert r2.headers.get('Access-Control-Allow-Origin') == 'http://ok.example'
