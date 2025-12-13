import os
import time

import pytest

from servers import start_rest_echo_server

_RUN_LIVE = os.getenv('DOORMAN_RUN_LIVE', '0') in ('1', 'true', 'True')


@pytest.mark.asyncio
@pytest.mark.skip(reason='Bandwidth tracking requires separate investigation - not related to rate limiting')
async def test_bandwidth_limit_enforced_and_window_resets_live(authed_client):
    """Test bandwidth limiting using in-process client for reliable request/response tracking."""
    srv = start_rest_echo_server()
    try:
        name, ver = f'bwlive-{int(time.time())}', 'v1'
        await authed_client.post(
            '/platform/api',
            json={
                'api_name': name,
                'api_version': ver,
                'api_description': 'bw live',
                'api_allowed_roles': ['admin'],
                'api_allowed_groups': ['ALL'],
                'api_servers': [srv.url],
                'api_type': 'REST',
                'api_allowed_retry_count': 0,
            },
        )
        await authed_client.post(
            '/platform/endpoint',
            json={
                'api_name': name,
                'api_version': ver,
                'endpoint_method': 'GET',
                'endpoint_uri': '/p',
                'endpoint_description': 'p',
            },
        )
        await authed_client.post(
            '/platform/subscription/subscribe',
            json={'username': 'admin', 'api_name': name, 'api_version': ver},
        )
        await authed_client.put(
            '/platform/user/admin',
            json={
                'bandwidth_limit_bytes': 1,
                'bandwidth_limit_window': 'second',
                'bandwidth_limit_enabled': True,
            },
        )
        await authed_client.delete('/api/caches')
        r1 = await authed_client.get(f'/api/rest/{name}/{ver}/p')
        r2 = await authed_client.get(f'/api/rest/{name}/{ver}/p')
        assert r1.status_code == 200 and r2.status_code == 429

        time.sleep(1.1)
        r3 = await authed_client.get(f'/api/rest/{name}/{ver}/p')
        assert r3.status_code == 200
    finally:
        # Restore generous bandwidth limits
        await authed_client.put(
            '/platform/user/admin',
            json={
                'bandwidth_limit_bytes': 0,
                'bandwidth_limit_window': 'day',
                'bandwidth_limit_enabled': False,
            },
        )
        srv.stop()
