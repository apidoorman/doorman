"""
Analytics data models for enhanced metrics tracking.

This module extends the existing metrics_util.py with additional
analytics capabilities while maintaining backward compatibility.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum


class AggregationLevel(str, Enum):
    """Time-based aggregation levels for metrics."""

    MINUTE = 'minute'
    FIVE_MINUTE = '5minute'
    HOUR = 'hour'
    DAY = 'day'


class MetricType(str, Enum):
    """Types of metrics tracked."""

    REQUEST_COUNT = 'request_count'
    ERROR_RATE = 'error_rate'
    RESPONSE_TIME = 'response_time'
    BANDWIDTH = 'bandwidth'
    STATUS_CODE = 'status_code'
    LATENCY_PERCENTILE = 'latency_percentile'


@dataclass
class PercentileMetrics:
    """
    Latency percentile calculations.

    Stores multiple percentiles for comprehensive performance analysis.
    Uses a reservoir sampling approach to maintain a representative sample.
    """

    p50: float = 0.0  # Median
    p75: float = 0.0  # 75th percentile
    p90: float = 0.0  # 90th percentile
    p95: float = 0.0  # 95th percentile
    p99: float = 0.0  # 99th percentile
    min: float = 0.0  # Minimum latency
    max: float = 0.0  # Maximum latency

    @staticmethod
    def calculate(latencies: list[float]) -> PercentileMetrics:
        """Calculate percentiles from a list of latencies."""
        if not latencies:
            return PercentileMetrics()

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        def percentile(p: float) -> float:
            k = max(0, int(p * n) - 1)
            return float(sorted_latencies[k])

        return PercentileMetrics(
            p50=percentile(0.50),
            p75=percentile(0.75),
            p90=percentile(0.90),
            p95=percentile(0.95),
            p99=percentile(0.99),
            min=float(sorted_latencies[0]),
            max=float(sorted_latencies[-1]),
        )

    def to_dict(self) -> dict:
        return {
            'p50': self.p50,
            'p75': self.p75,
            'p90': self.p90,
            'p95': self.p95,
            'p99': self.p99,
            'min': self.min,
            'max': self.max,
        }


@dataclass
class EndpointMetrics:
    """
    Per-endpoint performance metrics.

    Tracks detailed metrics for individual API endpoints to identify
    performance bottlenecks at a granular level.
    """

    endpoint_uri: str
    method: str
    count: int = 0
    error_count: int = 0
    total_ms: float = 0.0
    latencies: deque[float] = field(default_factory=deque)
    status_counts: dict[int, int] = field(default_factory=dict)

    def add(self, ms: float, status: int, max_samples: int = 500) -> None:
        """Record a request for this endpoint."""
        self.count += 1
        if status >= 400:
            self.error_count += 1
        self.total_ms += ms

        self.status_counts[status] = self.status_counts.get(status, 0) + 1

        self.latencies.append(ms)
        while len(self.latencies) > max_samples:
            self.latencies.popleft()

    def get_percentiles(self) -> PercentileMetrics:
        """Calculate percentiles for this endpoint."""
        return PercentileMetrics.calculate(list(self.latencies))

    def to_dict(self) -> dict:
        percentiles = self.get_percentiles()
        return {
            'endpoint_uri': self.endpoint_uri,
            'method': self.method,
            'count': self.count,
            'error_count': self.error_count,
            'error_rate': (self.error_count / self.count) if self.count > 0 else 0.0,
            'avg_ms': (self.total_ms / self.count) if self.count > 0 else 0.0,
            'percentiles': percentiles.to_dict(),
            'status_counts': dict(self.status_counts),
        }


@dataclass
class EnhancedMinuteBucket:
    """
    Enhanced version of MinuteBucket with additional analytics.

    Extends the existing MinuteBucket from metrics_util.py with:
    - Per-endpoint tracking
    - Full percentile calculations (p50, p75, p90, p95, p99)
    - Unique user tracking
    - Request/response size tracking
    """

    start_ts: int
    count: int = 0
    error_count: int = 0
    total_ms: float = 0.0
    bytes_in: int = 0
    bytes_out: int = 0
    upstream_timeouts: int = 0
    retries: int = 0

    # Existing tracking (compatible with metrics_util.py)
    status_counts: dict[int, int] = field(default_factory=dict)
    api_counts: dict[str, int] = field(default_factory=dict)
    api_error_counts: dict[str, int] = field(default_factory=dict)
    user_counts: dict[str, int] = field(default_factory=dict)
    latencies: deque[float] = field(default_factory=deque)

    # NEW: Enhanced tracking
    endpoint_metrics: dict[str, EndpointMetrics] = field(default_factory=dict)
    unique_users: set = field(default_factory=set)
    request_sizes: deque[int] = field(default_factory=deque)
    response_sizes: deque[int] = field(default_factory=deque)

    def add_request(
        self,
        ms: float,
        status: int,
        username: str | None,
        api_key: str | None,
        endpoint_uri: str | None = None,
        method: str | None = None,
        bytes_in: int = 0,
        bytes_out: int = 0,
        max_samples: int = 500,
    ) -> None:
        """
        Record a request with enhanced tracking.

        Compatible with existing metrics_util.py while adding new capabilities.
        """
        # Existing tracking (backward compatible)
        self.count += 1
        if status >= 400:
            self.error_count += 1
        self.total_ms += ms
        self.bytes_in += bytes_in
        self.bytes_out += bytes_out

        self.status_counts[status] = self.status_counts.get(status, 0) + 1

        if api_key:
            self.api_counts[api_key] = self.api_counts.get(api_key, 0) + 1
            if status >= 400:
                self.api_error_counts[api_key] = self.api_error_counts.get(api_key, 0) + 1

        if username:
            self.user_counts[username] = self.user_counts.get(username, 0) + 1
            self.unique_users.add(username)

        self.latencies.append(ms)
        while len(self.latencies) > max_samples:
            self.latencies.popleft()

        # NEW: Per-endpoint tracking
        if endpoint_uri and method:
            endpoint_key = f'{method}:{endpoint_uri}'
            if endpoint_key not in self.endpoint_metrics:
                self.endpoint_metrics[endpoint_key] = EndpointMetrics(
                    endpoint_uri=endpoint_uri, method=method
                )
            self.endpoint_metrics[endpoint_key].add(ms, status, max_samples)

        # NEW: Request/response size tracking
        if bytes_in > 0:
            self.request_sizes.append(bytes_in)
            while len(self.request_sizes) > max_samples:
                self.request_sizes.popleft()

        if bytes_out > 0:
            self.response_sizes.append(bytes_out)
            while len(self.response_sizes) > max_samples:
                self.response_sizes.popleft()

    def get_percentiles(self) -> PercentileMetrics:
        """Calculate full percentiles for this bucket."""
        return PercentileMetrics.calculate(list(self.latencies))

    def get_unique_user_count(self) -> int:
        """Get count of unique users in this bucket."""
        return len(self.unique_users)

    def get_top_endpoints(self, limit: int = 10) -> list[dict]:
        """Get top N slowest/most-used endpoints."""
        endpoints = [ep.to_dict() for ep in self.endpoint_metrics.values()]
        # Sort by count (most used)
        endpoints.sort(key=lambda x: x['count'], reverse=True)
        return endpoints[:limit]

    def to_dict(self) -> dict:
        """Serialize to dictionary (backward compatible + enhanced)."""
        percentiles = self.get_percentiles()

        return {
            # Existing fields (backward compatible)
            'start_ts': self.start_ts,
            'count': self.count,
            'error_count': self.error_count,
            'total_ms': self.total_ms,
            'bytes_in': self.bytes_in,
            'bytes_out': self.bytes_out,
            'upstream_timeouts': self.upstream_timeouts,
            'retries': self.retries,
            'status_counts': dict(self.status_counts),
            'api_counts': dict(self.api_counts),
            'api_error_counts': dict(self.api_error_counts),
            'user_counts': dict(self.user_counts),
            # NEW: Enhanced fields
            'percentiles': percentiles.to_dict(),
            'unique_users': self.get_unique_user_count(),
            'endpoint_metrics': {k: v.to_dict() for k, v in self.endpoint_metrics.items()},
            'avg_request_size': sum(self.request_sizes) / len(self.request_sizes)
            if self.request_sizes
            else 0,
            'avg_response_size': sum(self.response_sizes) / len(self.response_sizes)
            if self.response_sizes
            else 0,
        }


@dataclass
class AggregatedMetrics:
    """
    Multi-level aggregated metrics (5-minute, hourly, daily).

    Used for efficient querying of historical data without
    scanning all minute-level buckets.
    """

    start_ts: int
    end_ts: int
    level: AggregationLevel
    count: int = 0
    error_count: int = 0
    total_ms: float = 0.0
    bytes_in: int = 0
    bytes_out: int = 0
    unique_users: int = 0

    status_counts: dict[int, int] = field(default_factory=dict)
    api_counts: dict[str, int] = field(default_factory=dict)
    percentiles: PercentileMetrics | None = None

    def to_dict(self) -> dict:
        return {
            'start_ts': self.start_ts,
            'end_ts': self.end_ts,
            'level': self.level.value,
            'count': self.count,
            'error_count': self.error_count,
            'error_rate': (self.error_count / self.count) if self.count > 0 else 0.0,
            'avg_ms': (self.total_ms / self.count) if self.count > 0 else 0.0,
            'bytes_in': self.bytes_in,
            'bytes_out': self.bytes_out,
            'unique_users': self.unique_users,
            'status_counts': dict(self.status_counts),
            'api_counts': dict(self.api_counts),
            'percentiles': self.percentiles.to_dict() if self.percentiles else None,
        }


@dataclass
class AnalyticsSnapshot:
    """
    Complete analytics snapshot for a time range.

    Used as the response format for analytics API endpoints.
    """

    start_ts: int
    end_ts: int
    total_requests: int
    total_errors: int
    error_rate: float
    avg_response_ms: float
    percentiles: PercentileMetrics
    total_bytes_in: int
    total_bytes_out: int
    unique_users: int

    # Time-series data
    series: list[dict]

    # Top N lists
    top_apis: list[tuple]
    top_users: list[tuple]
    top_endpoints: list[dict]

    # Status code distribution
    status_distribution: dict[str, int]

    def to_dict(self) -> dict:
        return {
            'start_ts': self.start_ts,
            'end_ts': self.end_ts,
            'summary': {
                'total_requests': self.total_requests,
                'total_errors': self.total_errors,
                'error_rate': self.error_rate,
                'avg_response_ms': self.avg_response_ms,
                'percentiles': self.percentiles.to_dict(),
                'total_bytes_in': self.total_bytes_in,
                'total_bytes_out': self.total_bytes_out,
                'unique_users': self.unique_users,
            },
            'series': self.series,
            'top_apis': [{'api': api, 'count': count} for api, count in self.top_apis],
            'top_users': [{'user': user, 'count': count} for user, count in self.top_users],
            'top_endpoints': self.top_endpoints,
            'status_distribution': self.status_distribution,
        }
