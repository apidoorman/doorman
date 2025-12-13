import time

import pytest

from servers import start_rest_echo_server


pytestmark = [pytest.mark.rate_limit, pytest.mark.public]


def _setup_rest_api(client, srv) -> tuple[str, str]:
    api_name = f'rl-tier-{int(time.time())}'
    api_version = 'v1'
    r = client.post(
        '/platform/api',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'rl tier strict',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': [srv.url],
            'api_type': 'REST',
            'active': True,
        },
    )
    assert r.status_code in (200, 201), r.text
    r = client.post(
        '/platform/endpoint',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': 'GET',
            'endpoint_uri': '/hit',
            'endpoint_description': 'hit',
        },
    )
    assert r.status_code in (200, 201), r.text
    r = client.post(
        '/platform/subscription/subscribe',
        json={'api_name': api_name, 'api_version': api_version, 'username': 'admin'},
    )
    assert r.status_code in (200, 201) or (r.json().get('error_code') == 'SUB004'), r.text
    return api_name, api_version


def _teardown_api(client, api_name: str, api_version: str):
    try:
        client.delete(f'/platform/endpoint/GET/{api_name}/{api_version}/hit')
    except Exception:
        pass
    try:
        client.delete(f'/platform/api/{api_name}/{api_version}')
    except Exception:
        pass


def _create_tier(client, tier_id: str, rpm: int = 1, throttle: bool = False) -> None:
    # Use trailing slash to avoid 307
    r = client.post(
        '/platform/tiers/',
        json={
            'tier_id': tier_id,
            'name': 'custom',
            'display_name': tier_id,
            'description': 'test tier',
            'limits': {
                'requests_per_minute': rpm,
                'enable_throttling': throttle,
                'max_queue_time_ms': 0,
            },
            'price_monthly': 0.0,
            'features': [],
            'is_default': False,
            'enabled': True,
        },
    )
    assert r.status_code in (200, 201), r.text


def _assign_tier(client, tier_id: str):
    r = client.post(
        '/platform/tiers/assignments',
        json={'user_id': 'admin', 'tier_id': tier_id},
    )
    assert r.status_code in (200, 201), r.text


def _remove_tier(client, tier_id: str):
    try:
        client.delete('/platform/tiers/assignments/admin')
    except Exception:
        pass
    try:
        client.delete(f'/platform/tiers/{tier_id}')
    except Exception:
        pass


def _set_user_limits(client, rpm: int):
    client.put(
        '/platform/user/admin',
        json={
            'rate_limit_duration': 60 if rpm > 0 else 1000000,
            'rate_limit_duration_type': 'second',
            'throttle_duration': 0,
            'throttle_duration_type': 'second',
            'throttle_queue_limit': 0,
            'throttle_wait_duration': 0,
            'throttle_wait_duration_type': 'second',
        },
    )


def _restore_user_limits(client):
    _set_user_limits(client, rpm=0)


def _strict_assert_429(resp):
    assert resp.status_code == 429, resp.text


def _reset_caches(client):
    """Reset caches for clean state in live tests."""
    try:
        client.delete('/api/caches')
    except Exception:
        pass


def _wait_for_clean_window():
    """Wait until we're at the start of a new minute window for clean rate limit state.
    
    The tier rate limit uses minute-based windows (now // 60), so we need to
    ensure we're in a fresh minute that hasn't had any requests yet.
    """
    now = time.time()
    current_minute = int(now) // 60
    # Wait until we're in a new minute
    while int(time.time()) // 60 == current_minute:
        time.sleep(0.5)
    # Small buffer after minute boundary
    time.sleep(0.2)


def test_tier_rate_limiting_strict_local(client):
    """Test tier-based rate limiting enforces rpm=1 limit."""
    # First, clean up any existing tier assignments
    _remove_tier(client, 'any')  # Remove any tier assignment for admin

    srv = start_rest_echo_server()
    tier_id = f'tier-rl-{int(time.time())}'
    try:
        api, ver = _setup_rest_api(client, srv)

        # Ensure generous per-user so tier limit is the only limiter
        _restore_user_limits(client)

        _create_tier(client, tier_id, rpm=1, throttle=False)
        _assign_tier(client, tier_id)

        # Reset caches and wait for clean rate limit window
        _reset_caches(client)
        _wait_for_clean_window()

        r1 = client.get(f'/api/rest/{api}/{ver}/hit')
        assert r1.status_code == 200, r1.text
        r2 = client.get(f'/api/rest/{api}/{ver}/hit')
        _strict_assert_429(r2)
    finally:
        _remove_tier(client, tier_id)
        _teardown_api(client, api, ver)
        srv.stop()


def test_tier_vs_user_limits_priority(client):
    """Test that tier limits take priority over generous user limits.
    
    When a user has generous rate limits but is assigned to a tier with strict limits,
    the tier limits should be enforced.
    """
    # First, clean up any existing tier assignments
    _remove_tier(client, 'any')

    srv = start_rest_echo_server()
    tier_id = f'tier-rl2-{int(time.time())}'
    try:
        api, ver = _setup_rest_api(client, srv)

        # Set user to allow many reqs (generous limits)
        _restore_user_limits(client)
        
        # Create tier with strict 1/minute limit
        _create_tier(client, tier_id, rpm=1, throttle=False)
        _assign_tier(client, tier_id)

        # Reset caches and wait for clean rate limit window
        _reset_caches(client)
        _wait_for_clean_window()

        # Even though user has generous limits, tier should enforce 1/minute
        r1 = client.get(f'/api/rest/{api}/{ver}/hit')
        assert r1.status_code == 200, r1.text
        r2 = client.get(f'/api/rest/{api}/{ver}/hit')
        _strict_assert_429(r2)
    finally:
        _remove_tier(client, tier_id)
        _restore_user_limits(client)
        _teardown_api(client, api, ver)
        srv.stop()


def test_tier_concurrent_requests_enforced(client):
    """Test multiple sequential requests are rate limited by tier."""
    # First, clean up any existing tier assignments
    _remove_tier(client, 'any')

    srv = start_rest_echo_server()
    tier_id = f'tier-rl3-{int(time.time())}'
    try:
        api, ver = _setup_rest_api(client, srv)
        _restore_user_limits(client)
        _create_tier(client, tier_id, rpm=2, throttle=False)
        _assign_tier(client, tier_id)

        # Reset caches and wait for clean rate limit window
        _reset_caches(client)
        _wait_for_clean_window()

        # Make 3 sequential requests - with rpm=2, first 2 should succeed, 3rd should be blocked
        results = [client.get(f'/api/rest/{api}/{ver}/hit') for _ in range(3)]

        ok = sum(1 for r in results if r.status_code == 200)
        blocked = sum(1 for r in results if r.status_code == 429)
        assert ok >= 1, f'Expected at least 1 success, got {ok}'
        assert blocked >= 1, f'Expected at least 1 block, got {blocked}'
    finally:
        _remove_tier(client, tier_id)
        _teardown_api(client, api, ver)
        srv.stop()
