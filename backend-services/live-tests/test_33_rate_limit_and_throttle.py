import time

from servers import start_rest_echo_server


def _assert_rate_limited_within_burst(client, path: str, attempts: int = 6):
    statuses = []
    for _ in range(max(2, attempts)):
        resp = client.get(path)
        statuses.append(resp.status_code)
        if len(statuses) == 1:
            assert resp.status_code == 200, resp.text
        elif resp.status_code == 429:
            return
    assert False, f'Expected at least one 429 within burst; got statuses={statuses}'


def test_rate_limiting_blocks_excess_requests(client):
    srv = start_rest_echo_server()
    try:
        api_name = f'rl-{int(time.time())}'
        api_version = 'v1'
        user_upd = client.put(
            '/platform/user/admin',
            json={
                'rate_limit_duration': 1,
                # Use a wider window so assertion is robust even when
                # live environment request latency is several seconds.
                'rate_limit_duration_type': 'minute',
                'throttle_duration': 999,
                'throttle_duration_type': 'second',
                'throttle_queue_limit': 999,
                'throttle_wait_duration': 0,
                'throttle_wait_duration_type': 'second',
            },
        )
        assert user_upd.status_code in (200, 201, 400), user_upd.text
        try:
            client.delete('/api/caches')
        except Exception:
            pass

        api_create = client.post(
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
        assert api_create.status_code in (200, 201), api_create.text
        ep_create = client.post(
            '/platform/endpoint',
            json={
                'api_name': api_name,
                'api_version': api_version,
                'endpoint_method': 'GET',
                'endpoint_uri': '/hit',
                'endpoint_description': 'hit',
            },
        )
        assert ep_create.status_code in (200, 201), ep_create.text
        sub = client.post(
            '/platform/subscription/subscribe',
            json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'},
        )
        assert sub.status_code in (200, 201), sub.text

        time.sleep(0.2)
        _assert_rate_limited_within_burst(client, f'/api/rest/{api_name}/{api_version}/hit')
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
