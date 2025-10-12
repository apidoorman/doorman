import asyncio
import os
from typing import Callable

import httpx
import pytest

from utils.http_client import request_with_resilience, circuit_manager, CircuitOpenError


def _mock_transport(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.MockTransport:
    return httpx.MockTransport(lambda req: handler(req))


@pytest.mark.asyncio
async def test_retries_on_503_then_success(monkeypatch):
    calls = {'n': 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls['n'] += 1
        if calls['n'] < 3:
            return httpx.Response(503, json={'error': 'unavailable'})
        return httpx.Response(200, json={'ok': True})

    transport = _mock_transport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        # Ensure short delays in tests
        monkeypatch.setenv('HTTP_RETRY_BASE_DELAY', '0.01')
        monkeypatch.setenv('HTTP_RETRY_MAX_DELAY', '0.02')
        monkeypatch.setenv('CIRCUIT_BREAKER_THRESHOLD', '5')

        resp = await request_with_resilience(
            client, 'GET', 'http://upstream.test/ok',
            api_key='test-api/v1', retries=2, api_config=None,
        )

        assert resp.status_code == 200
        assert resp.json() == {'ok': True}
        # Two failures + one success
        assert calls['n'] == 3


@pytest.mark.asyncio
async def test_circuit_opens_after_failures_and_half_open(monkeypatch):
    calls = {'n': 0}
    # Always return 503
    def handler(req: httpx.Request) -> httpx.Response:
        calls['n'] += 1
        return httpx.Response(503, json={'error': 'unavailable'})

    transport = _mock_transport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        # Configure low threshold and short open timeout
        monkeypatch.setenv('HTTP_RETRY_BASE_DELAY', '0.0')
        monkeypatch.setenv('HTTP_RETRY_MAX_DELAY', '0.0')
        monkeypatch.setenv('CIRCUIT_BREAKER_THRESHOLD', '2')
        monkeypatch.setenv('CIRCUIT_BREAKER_TIMEOUT', '0.1')

        api_key = 'breaker-api/v1'
        # Reset circuit state for isolation
        circuit_manager._states.clear()

        # First request: attempt 2 times (both 503) -> opens circuit
        resp = await request_with_resilience(client, 'GET', 'http://u.test/err', api_key=api_key, retries=1)
        assert resp.status_code == 503
        # Second request soon after should raise CircuitOpenError due to open state
        with pytest.raises(CircuitOpenError):
            await request_with_resilience(client, 'GET', 'http://u.test/err', api_key=api_key, retries=0)

        # Wait for half-open window
        await asyncio.sleep(0.11)

        # Half-open probe: still returns 503 -> immediately re-opens
        resp2 = await request_with_resilience(client, 'GET', 'http://u.test/err', api_key=api_key, retries=0)
        assert resp2.status_code == 503

        # Immediately calling again should be open
        with pytest.raises(CircuitOpenError):
            await request_with_resilience(client, 'GET', 'http://u.test/err', api_key=api_key, retries=0)
