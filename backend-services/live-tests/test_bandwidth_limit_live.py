import os

import pytest

_RUN_LIVE = os.getenv('DOORMAN_RUN_LIVE', '0') in ('1', 'true', 'True')
if not _RUN_LIVE:
    pytestmark = pytest.mark.skip(
        reason='Requires live backend service; set DOORMAN_RUN_LIVE=1 to enable'
    )


def test_bandwidth_limit_enforced_and_window_resets_live(client):
    name, ver = 'bwlive', 'v1'
    client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'bw live',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://up.example'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
        },
    )
    client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'GET',
            'endpoint_uri': '/p',
            'endpoint_description': 'p',
        },
    )
    client.post(
        '/platform/subscription/subscribe',
        json={'username': 'admin', 'api_name': name, 'api_version': ver},
    )
    client.put(
        '/platform/user/admin',
        json={
            'bandwidth_limit_bytes': 1,
            'bandwidth_limit_window': 'second',
            'bandwidth_limit_enabled': True,
        },
    )
    client.delete('/api/caches')
    r1 = client.get(f'/api/rest/{name}/{ver}/p')
    r2 = client.get(f'/api/rest/{name}/{ver}/p')
    assert r1.status_code == 200 and r2.status_code == 429
    import time

    time.sleep(1.1)
    r3 = client.get(f'/api/rest/{name}/{ver}/p')
    assert r3.status_code == 200
