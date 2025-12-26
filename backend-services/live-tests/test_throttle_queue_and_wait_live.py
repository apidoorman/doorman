import os
import time

import pytest

from servers import start_rest_echo_server

_RUN_LIVE = os.getenv('DOORMAN_RUN_LIVE', '0') in ('1', 'true', 'True')


def _restore_user_limits(client):
    """Restore generous user limits after tests."""
    client.put(
        '/platform/user/admin',
        json={
            'throttle_duration': 1000000,
            'throttle_duration_type': 'second',
            'throttle_queue_limit': 1000000,
            'throttle_wait_duration': 0,
            'throttle_wait_duration_type': 'second',
            'rate_limit_duration': 1000000,
            'rate_limit_duration_type': 'second',
        },
    )


def test_throttle_queue_limit_exceeded_429_live(client):
    srv = start_rest_echo_server()
    try:
        name, ver = f'throtq-{int(time.time())}', 'v1'
        client.post(
            '/platform/api',
            json={
                'api_name': name,
                'api_version': ver,
                'api_description': 'live throttle',
                'api_allowed_roles': ['admin'],
                'api_allowed_groups': ['ALL'],
                'api_servers': [srv.url],
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
                'endpoint_uri': '/t',
                'endpoint_description': 't',
            },
        )
        client.post(
            '/platform/subscription/subscribe',
            json={'username': 'admin', 'api_name': name, 'api_version': ver},
        )
        client.put('/platform/user/admin', json={'throttle_queue_limit': 1})
        client.delete('/api/caches')
        client.get(f'/api/rest/{name}/{ver}/t')
        r2 = client.get(f'/api/rest/{name}/{ver}/t')
        assert r2.status_code == 429
    finally:
        _restore_user_limits(client)
        srv.stop()


def test_throttle_dynamic_wait_live(client):
    srv = start_rest_echo_server()
    try:
        name, ver = f'throtw-{int(time.time())}', 'v1'
        client.post(
            '/platform/api',
            json={
                'api_name': name,
                'api_version': ver,
                'api_description': 'live throttle wait',
                'api_allowed_roles': ['admin'],
                'api_allowed_groups': ['ALL'],
                'api_servers': [srv.url],
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
                'endpoint_uri': '/w',
                'endpoint_description': 'w',
            },
        )
        client.post(
            '/platform/subscription/subscribe',
            json={'username': 'admin', 'api_name': name, 'api_version': ver},
        )
        client.put(
            '/platform/user/admin',
            json={
                'throttle_duration': 1,
                'throttle_duration_type': 'minute',
                'throttle_queue_limit': 10,
                'throttle_wait_duration': 0.1,
                'throttle_wait_duration_type': 'second',
                'rate_limit_duration': 1000,
                'rate_limit_duration_type': 'second',
            },
        )
        client.delete('/api/caches')

        t0 = time.perf_counter()
        r1 = client.get(f'/api/rest/{name}/{ver}/w')
        t1 = time.perf_counter()
        r2 = client.get(f'/api/rest/{name}/{ver}/w')
        t2 = time.perf_counter()
        assert r1.status_code == 200 and r2.status_code == 200
        assert (t2 - t1) >= (t1 - t0) + 0.08
    finally:
        _restore_user_limits(client)
        srv.stop()
