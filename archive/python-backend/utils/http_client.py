"""
HTTP client helper with per-API timeouts, jittered exponential backoff, and a
simple circuit breaker (with half-open probing) for httpx AsyncClient calls.

Usage:
    resp = await request_with_resilience(
        client, 'GET', url,
        api_key='api-name/v1',
        headers={...}, params={...},
        retries=api_retry_count,
        api_config=api_doc,
    )
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from dataclasses import dataclass
from typing import Any

import httpx

from utils.metrics_util import metrics_store
from utils.prometheus_metrics import record_retry, record_upstream_timeout

logger = logging.getLogger('doorman.gateway')


class CircuitOpenError(Exception):
    pass


@dataclass
class _BreakerState:
    failures: int = 0
    opened_at: float = 0.0
    state: str = 'closed'


class _CircuitManager:
    def __init__(self) -> None:
        self._states: dict[str, _BreakerState] = {}

    def reset(self, key: str | None = None) -> None:
        """Reset circuit breaker state. If key is None, reset all circuits."""
        if key is None:
            self._states.clear()
        elif key in self._states:
            del self._states[key]

    def get(self, key: str) -> _BreakerState:
        st = self._states.get(key)
        if st is None:
            st = _BreakerState()
            self._states[key] = st
        return st

    def now(self) -> float:
        return time.monotonic()

    def check(self, key: str, open_seconds: float) -> None:
        st = self.get(key)
        if st.state == 'open':
            if self.now() - st.opened_at >= open_seconds:
                st.state = 'half_open'
                st.failures = 0
            else:
                raise CircuitOpenError(f'Circuit open for {key}')

    def record_success(self, key: str) -> None:
        st = self.get(key)
        st.failures = 0
        st.state = 'closed'

    def record_failure(self, key: str, threshold: int) -> None:
        st = self.get(key)
        st.failures += 1
        if st.state == 'half_open':
            st.state = 'open'
            st.opened_at = self.now()
            return
        if st.state == 'closed' and st.failures >= max(1, threshold):
            st.state = 'open'
            st.opened_at = self.now()


circuit_manager = _CircuitManager()


def _build_timeout(api_config: dict | None) -> httpx.Timeout:
    # Per-API overrides if present on document; otherwise env defaults
    def _f(key: str, env_key: str, default: float) -> float:
        try:
            if api_config and key in api_config and api_config[key] is not None:
                return float(api_config[key])
            return float(os.getenv(env_key, default))
        except Exception:
            return default

    connect = _f('api_connect_timeout', 'HTTP_CONNECT_TIMEOUT', 5.0)
    read = _f('api_read_timeout', 'HTTP_READ_TIMEOUT', 30.0)
    write = _f('api_write_timeout', 'HTTP_WRITE_TIMEOUT', 30.0)
    pool = _f('api_pool_timeout', 'HTTP_TIMEOUT', 30.0)
    return httpx.Timeout(connect=connect, read=read, write=write, pool=pool)


def _should_retry_status(status: int) -> bool:
    return status in (500, 502, 503, 504)


def _backoff_delay(attempt: int) -> float:
    base = float(os.getenv('HTTP_RETRY_BASE_DELAY', 0.25))
    cap = float(os.getenv('HTTP_RETRY_MAX_DELAY', 2.0))
    delay = min(cap, base * (2 ** max(0, attempt - 1)))
    return random.uniform(0, delay)


async def request_with_resilience(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    api_key: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    data: Any = None,
    json: Any = None,
    content: Any = None,
    retries: int = 0,
    api_config: dict | None = None,
) -> httpx.Response:
    """Perform an HTTP request with retries, backoff, and circuit breaker.

    - Circuit breaker opens after threshold failures and remains open until timeout.
    - During half-open, a single attempt is allowed; success closes, failure re-opens.
    - Retries apply to transient 5xx responses and timeouts.
    """
    enabled = os.getenv('CIRCUIT_BREAKER_ENABLED', 'true').lower() != 'false'
    threshold = int(os.getenv('CIRCUIT_BREAKER_THRESHOLD', '5'))
    open_seconds = float(os.getenv('CIRCUIT_BREAKER_TIMEOUT', '30'))

    timeout = _build_timeout(api_config)
    attempts = max(1, int(retries) + 1)

    if enabled:
        circuit_manager.check(api_key, open_seconds)

    last_exc: BaseException | None = None
    response: httpx.Response | None = None
    for attempt in range(1, attempts + 1):
        if attempt > 1:
            try:
                metrics_store.record_retry(api_key)
            except Exception:
                pass
            record_retry()
            await asyncio.sleep(_backoff_delay(attempt))
        try:
            try:
                requester = client.request
            except Exception:
                requester = None
            if requester is not None:
                # Prefer the generic request() if available (httpx.AsyncClient)
                # Some monkeypatched clients (used in tests) may not accept all
                # httpx parameters like 'content'. Build kwargs defensively.
                kwargs = {
                    'headers': headers,
                    'params': params,
                    'timeout': timeout,
                }
                if json is not None:
                    kwargs['json'] = json
                if data is not None:
                    kwargs['data'] = data
                # Only include 'content' for clients that support it
                try:
                    if content is not None and 'content' in requester.__code__.co_varnames:
                        kwargs['content'] = content
                except Exception:
                    # Best-effort: many clients accept **kwargs; httpx supports 'content'
                    if content is not None:
                        kwargs['content'] = content
                response = await requester(method.upper(), url, **kwargs)
            else:
                meth = getattr(client, method.lower(), None)
                if meth is None:
                    raise AttributeError('HTTP client lacks request method')
                kwargs = {}
                if headers:
                    kwargs['headers'] = headers
                if params:
                    kwargs['params'] = params
                if json is not None:
                    kwargs['json'] = json
                elif data is not None:
                    kwargs['json'] = data
                response = await meth(url, **kwargs)

            if _should_retry_status(response.status_code) and attempt < attempts:
                if enabled:
                    circuit_manager.record_failure(api_key, threshold)
                continue

            if enabled:
                if _should_retry_status(response.status_code):
                    circuit_manager.record_failure(api_key, threshold)
                else:
                    circuit_manager.record_success(api_key)
            return response
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            last_exc = e
            if isinstance(e, httpx.TimeoutException):
                try:
                    metrics_store.record_upstream_timeout(api_key)
                except Exception:
                    pass
                record_upstream_timeout()
            if enabled:
                circuit_manager.record_failure(api_key, threshold)
            if attempt >= attempts:
                raise
        except Exception as e:
            last_exc = e
            if enabled:
                circuit_manager.record_failure(api_key, threshold)
            raise

    assert response is not None or last_exc is not None
    if response is not None:
        return response
    raise last_exc
