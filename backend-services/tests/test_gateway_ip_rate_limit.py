"""
Tests for GatewayIPRateLimitMiddleware.

Verifies:
- /api/* requests are rate-limited by IP after exceeding the configured limit
- /platform/* requests are NOT rate-limited by this middleware
- The GATEWAY_IP_RATE_DISABLED flag bypasses the middleware entirely
- Rate-limit response headers are present on 429 responses
"""

import pytest


@pytest.mark.asyncio
async def test_gateway_ip_rate_limit_triggers_429(monkeypatch, client):
    monkeypatch.setenv('GATEWAY_IP_RATE_LIMIT', '2')
    monkeypatch.setenv('GATEWAY_IP_RATE_WINDOW', '60')
    monkeypatch.setenv('GATEWAY_IP_RATE_DISABLED', 'false')

    # Two requests are within the limit — they should reach the gateway (any status except 429)
    r1 = await client.get('/api/rest/nonexistent/v1/test')
    assert r1.status_code != 429, f'First request should not be rate-limited, got {r1.status_code}'

    r2 = await client.get('/api/rest/nonexistent/v1/test')
    assert r2.status_code != 429, f'Second request should not be rate-limited, got {r2.status_code}'

    # Third request exceeds the limit
    r3 = await client.get('/api/rest/nonexistent/v1/test')
    assert r3.status_code == 429, f'Third request should be rate-limited (429), got {r3.status_code}'


@pytest.mark.asyncio
async def test_gateway_ip_rate_limit_response_headers(monkeypatch, client):
    monkeypatch.setenv('GATEWAY_IP_RATE_LIMIT', '1')
    monkeypatch.setenv('GATEWAY_IP_RATE_WINDOW', '60')
    monkeypatch.setenv('GATEWAY_IP_RATE_DISABLED', 'false')

    await client.get('/api/rest/nonexistent/v1/test')
    r = await client.get('/api/rest/nonexistent/v1/test')

    assert r.status_code == 429
    assert 'Retry-After' in r.headers
    assert 'X-RateLimit-Limit' in r.headers
    assert 'X-RateLimit-Remaining' in r.headers
    assert 'X-RateLimit-Reset' in r.headers


@pytest.mark.asyncio
async def test_gateway_ip_rate_limit_disabled_flag(monkeypatch, client):
    monkeypatch.setenv('GATEWAY_IP_RATE_LIMIT', '1')
    monkeypatch.setenv('GATEWAY_IP_RATE_WINDOW', '60')
    monkeypatch.setenv('GATEWAY_IP_RATE_DISABLED', 'true')

    # With the middleware disabled, requests beyond the would-be limit go through normally
    r1 = await client.get('/api/rest/nonexistent/v1/test')
    r2 = await client.get('/api/rest/nonexistent/v1/test')
    r3 = await client.get('/api/rest/nonexistent/v1/test')

    assert r1.status_code != 429
    assert r2.status_code != 429
    assert r3.status_code != 429


@pytest.mark.asyncio
async def test_gateway_ip_rate_limit_does_not_affect_platform(monkeypatch, client):
    """Platform routes (/platform/*) must not be affected by gateway IP rate limiting."""
    monkeypatch.setenv('GATEWAY_IP_RATE_LIMIT', '1')
    monkeypatch.setenv('GATEWAY_IP_RATE_WINDOW', '60')
    monkeypatch.setenv('GATEWAY_IP_RATE_DISABLED', 'false')

    # Drive the gateway counter to the limit first
    await client.get('/api/rest/nonexistent/v1/test')
    r_limited = await client.get('/api/rest/nonexistent/v1/test')
    assert r_limited.status_code == 429

    # Platform endpoint must still be reachable
    r_platform = await client.get('/platform/monitor/liveness')
    assert r_platform.status_code != 429
