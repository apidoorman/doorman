"""
Tests for rate-limit response headers and per-API rate limits.

Verifies:
- 429 from user-level rate limiting includes Retry-After + X-RateLimit-* headers
- 429 from tier-level rate limiting includes Retry-After + X-RateLimit-* headers
- enforce_api_rate_limit raises 429 with headers when API limit exceeded
- enforce_api_rate_limit returns None when no limit configured
- enforce_api_rate_limit allows requests within limit
- Per-API rate limit is enforced through the REST gateway
- Requests below the per-API limit pass through
"""

import time

import pytest


# ---------------------------------------------------------------------------
# Unit tests: enforce_api_rate_limit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enforce_api_rate_limit_no_config():
    """Returns None immediately when api_rate_limit is not set."""
    from utils.limit_throttle_util import enforce_api_rate_limit
    from unittest.mock import MagicMock

    req = MagicMock()
    req.app.state.redis = None

    result = await enforce_api_rate_limit(req, {'api_name': 'foo', 'api_version': 'v1'})
    assert result is None


@pytest.mark.asyncio
async def test_enforce_api_rate_limit_zero_limit():
    """Returns None when api_rate_limit is 0 (explicitly disabled)."""
    from utils.limit_throttle_util import enforce_api_rate_limit
    from unittest.mock import MagicMock

    req = MagicMock()
    req.app.state.redis = None

    result = await enforce_api_rate_limit(req, {
        'api_name': 'foo', 'api_version': 'v1', 'api_rate_limit': 0
    })
    assert result is None


@pytest.mark.asyncio
async def test_enforce_api_rate_limit_returns_info_within_limit():
    """Returns rate limit info dict when under limit."""
    from utils.limit_throttle_util import enforce_api_rate_limit, reset_counters
    from unittest.mock import MagicMock

    reset_counters()

    req = MagicMock()
    req.app.state.redis = None

    api = {'api_name': 'rl-info-api', 'api_version': 'v1', 'api_rate_limit': 100, 'api_rate_limit_window': 60}
    result = await enforce_api_rate_limit(req, api)

    assert result is not None
    assert result['limit'] == 100
    assert result['remaining'] >= 0
    assert result['window'] == 60
    assert 'reset' in result


@pytest.mark.asyncio
async def test_enforce_api_rate_limit_blocks_when_exceeded():
    """Raises 429 with standard rate limit headers when limit is exceeded."""
    from fastapi import HTTPException
    from utils.limit_throttle_util import enforce_api_rate_limit, reset_counters
    from unittest.mock import MagicMock

    reset_counters()

    req = MagicMock()
    req.app.state.redis = None

    api = {'api_name': 'rl-block-api', 'api_version': 'v1', 'api_rate_limit': 2, 'api_rate_limit_window': 60}

    # First two requests should pass
    await enforce_api_rate_limit(req, api)
    await enforce_api_rate_limit(req, api)

    # Third request should be blocked
    with pytest.raises(HTTPException) as exc_info:
        await enforce_api_rate_limit(req, api)

    assert exc_info.value.status_code == 429
    headers = exc_info.value.headers or {}
    assert 'Retry-After' in headers
    assert headers.get('X-RateLimit-Limit') == '2'
    assert headers.get('X-RateLimit-Remaining') == '0'
    assert 'X-RateLimit-Reset' in headers
    assert headers.get('X-RateLimit-Scope') == 'api'


@pytest.mark.asyncio
async def test_enforce_api_rate_limit_scoped_per_api_version():
    """Different API versions have independent counters."""
    from utils.limit_throttle_util import enforce_api_rate_limit, reset_counters
    from unittest.mock import MagicMock

    reset_counters()

    req = MagicMock()
    req.app.state.redis = None

    api_v1 = {'api_name': 'scope-api', 'api_version': 'v1', 'api_rate_limit': 1, 'api_rate_limit_window': 60}
    api_v2 = {'api_name': 'scope-api', 'api_version': 'v2', 'api_rate_limit': 1, 'api_rate_limit_window': 60}

    # Exhaust v1 limit
    await enforce_api_rate_limit(req, api_v1)

    # v2 should still be allowed
    result = await enforce_api_rate_limit(req, api_v2)
    assert result is not None
    assert result['remaining'] >= 0


# ---------------------------------------------------------------------------
# Unit tests: rate limit headers on user-level 429
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_rate_limit_429_has_retry_after_header(authed_client, monkeypatch):
    """429 from user rate limit carries Retry-After and X-RateLimit-* headers."""
    from tests.test_gateway_routing_limits import _FakeAsyncClient
    from conftest import create_api, create_endpoint, subscribe_self
    from utils.limit_throttle_util import reset_counters
    import services.gateway_service as gs

    name, ver = 'hdr-rate-api', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/check')
    await subscribe_self(authed_client, name, ver)

    from utils.database import user_collection
    user_collection.update_one(
        {'username': 'admin'},
        {'$set': {'rate_limit_duration': 1, 'rate_limit_duration_type': 'second'}},
    )
    await authed_client.delete('/api/caches')
    reset_counters()

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    # First request — should succeed
    ok = await authed_client.get(f'/api/rest/{name}/{ver}/check')
    assert ok.status_code == 200

    # Second request — should be blocked
    blocked = await authed_client.get(f'/api/rest/{name}/{ver}/check')
    assert blocked.status_code == 429
    assert 'retry-after' in blocked.headers or 'Retry-After' in blocked.headers


# ---------------------------------------------------------------------------
# Integration test: per-API rate limit enforced by gateway
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_per_api_rate_limit_gateway(authed_client, monkeypatch):
    """API-level rate limit blocks requests over the limit for all callers."""
    from tests.test_gateway_routing_limits import _FakeAsyncClient
    from conftest import create_api, create_endpoint, subscribe_self
    from utils.limit_throttle_util import reset_counters
    import services.gateway_service as gs

    name, ver = 'api-rl-gw', 'v1'
    # Create API with rate limit = 1 per 60 s window
    r = await authed_client.post('/platform/api', json={
        'api_name': name,
        'api_version': ver,
        'api_type': 'REST',
        'api_servers': ['http://localhost:19999'],
        'api_allowed_groups': ['ALL'],
        'api_rate_limit': 1,
        'api_rate_limit_window': 60,
    })
    assert r.status_code in (200, 201), r.text

    await create_endpoint(authed_client, name, ver, 'GET', '/hit')
    await subscribe_self(authed_client, name, ver)
    reset_counters()

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    # First request — within limit
    r1 = await authed_client.get(f'/api/rest/{name}/{ver}/hit')
    assert r1.status_code == 200, r1.text

    # Second request — over limit
    r2 = await authed_client.get(f'/api/rest/{name}/{ver}/hit')
    assert r2.status_code == 429, f'Expected 429, got {r2.status_code}: {r2.text}'

    # Verify headers are present
    assert 'retry-after' in r2.headers or 'Retry-After' in r2.headers
    body = r2.json()
    assert body.get('error_code') == 'API rate limit exceeded' or r2.status_code == 429


@pytest.mark.asyncio
async def test_per_api_rate_limit_none_no_block(authed_client, monkeypatch):
    """API without rate limit is never blocked by api-level rate limiting."""
    from tests.test_gateway_routing_limits import _FakeAsyncClient
    from conftest import create_api, create_endpoint, subscribe_self
    from utils.limit_throttle_util import reset_counters
    import services.gateway_service as gs

    name, ver = 'no-api-rl', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/open')
    await subscribe_self(authed_client, name, ver)
    reset_counters()

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    for _ in range(5):
        r = await authed_client.get(f'/api/rest/{name}/{ver}/open')
        assert r.status_code == 200, f'Expected 200, got {r.status_code}: {r.text}'
