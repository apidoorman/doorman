import time

from servers import start_rest_echo_server


def test_rate_limiting_blocks_excess_requests(client):
    srv = start_rest_echo_server()
    try:
        api_name = f'rl-{int(time.time())}'
        api_version = 'v1'
        client.put(
            '/platform/user/admin',
            json={
                'rate_limit_duration': 1,
                'rate_limit_duration_type': 'second',
                'throttle_duration': 999,
                'throttle_duration_type': 'second',
                'throttle_queue_limit': 999,
                'throttle_wait_duration': 0,
                'throttle_wait_duration_type': 'second',
            },
        )
        try:
            client.delete('/api/caches')
        except Exception:
            pass

        client.post(
            '/platform/api',
            json={
                'api_name': api_name,
                'api_version': api_version,
                'api_description': 'rl test',
                'api_allowed_roles': ['admin'],
                'api_allowed_groups': ['ALL'],
                'api_servers': [srv.url],
                'api_type': 'REST',
                'active': True,
            },
        )
        client.post(
            '/platform/endpoint',
            json={
                'api_name': api_name,
                'api_version': api_version,
                'endpoint_method': 'GET',
                'endpoint_uri': '/hit',
                'endpoint_description': 'hit',
            },
        )
        client.post(
            '/platform/subscription/subscribe',
            json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'},
        )

        time.sleep(1.1)

        r1 = client.get(f'/api/rest/{api_name}/{api_version}/hit')
        assert r1.status_code == 200
        r2 = client.get(f'/api/rest/{api_name}/{api_version}/hit')
        assert r2.status_code == 429
        time.sleep(1.1)
        r3 = client.get(f'/api/rest/{api_name}/{api_version}/hit')
        assert r3.status_code == 200
    finally:
        try:
            client.delete(f'/platform/endpoint/GET/{api_name}/{api_version}/hit')
        except Exception:
            pass
        try:
            client.delete(f'/platform/api/{api_name}/{api_version}')
        except Exception:
            pass
        srv.stop()
        try:
            client.put(
                '/platform/user/admin',
                json={
                    'rate_limit_duration': 1000000,
                    'rate_limit_duration_type': 'second',
                    'throttle_duration': 1000000,
                    'throttle_duration_type': 'second',
                    'throttle_queue_limit': 1000000,
                    'throttle_wait_duration': 0,
                    'throttle_wait_duration_type': 'second',
                },
            )
        except Exception:
            pass
