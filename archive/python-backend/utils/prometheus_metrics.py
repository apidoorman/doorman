import os
from typing import Any


class _NoopMetric:
    def labels(self, **kwargs: Any):
        return self

    def inc(self, *args: Any, **kwargs: Any) -> None:
        return None

    def observe(self, *args: Any, **kwargs: Any) -> None:
        return None


try:
    from prometheus_client import Counter, Histogram, CONTENT_TYPE_LATEST, generate_latest

    _import_ok = True
except Exception:  # pragma: no cover - best-effort fallback
    Counter = Histogram = lambda *a, **k: _NoopMetric()  # type: ignore
    CONTENT_TYPE_LATEST = 'text/plain; version=0.0.4; charset=utf-8'

    def generate_latest() -> bytes:  # type: ignore
        return b''

    _import_ok = False


PROMETHEUS_ENABLED = _import_ok and os.getenv('PROMETHEUS_ENABLED', 'true').lower() not in (
    '0',
    'false',
    'no',
    'off',
)

if PROMETHEUS_ENABLED:
    REQUEST_DURATION = Histogram(
        'doorman_http_request_duration_seconds',
        'Gateway request duration in seconds',
        buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    )
    REQUESTS_TOTAL = Counter(
        'doorman_http_requests_total',
        'Gateway request count',
        ['code'],
    )
    UPSTREAM_TIMEOUTS = Counter(
        'doorman_upstream_timeouts_total',
        'Upstream timeout count',
    )
    RETRIES_TOTAL = Counter(
        'doorman_http_retries_total',
        'HTTP retry count',
    )
else:  # pragma: no cover - fallback path
    REQUEST_DURATION = _NoopMetric()
    REQUESTS_TOTAL = _NoopMetric()
    UPSTREAM_TIMEOUTS = _NoopMetric()
    RETRIES_TOTAL = _NoopMetric()


def observe_request(duration_ms: float, status_code: int) -> None:
    if not PROMETHEUS_ENABLED:
        return
    try:
        REQUEST_DURATION.observe(max(float(duration_ms), 0.0) / 1000.0)
        REQUESTS_TOTAL.labels(code=str(status_code)).inc()
    except Exception:
        pass


def record_retry() -> None:
    if not PROMETHEUS_ENABLED:
        return
    try:
        RETRIES_TOTAL.inc()
    except Exception:
        pass


def record_upstream_timeout() -> None:
    if not PROMETHEUS_ENABLED:
        return
    try:
        UPSTREAM_TIMEOUTS.inc()
    except Exception:
        pass


def render_latest() -> bytes:
    try:
        return generate_latest()
    except Exception:
        return b''
