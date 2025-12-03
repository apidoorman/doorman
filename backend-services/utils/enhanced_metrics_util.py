"""
Enhanced metrics utilities with analytics support.

Extends the existing metrics_util.py with:
- Per-endpoint tracking
- Full percentile calculations (p50, p75, p90, p95, p99)
- Unique user counting
- Request/response size tracking
- Multi-level aggregation support
"""

from __future__ import annotations
import time
import os
from collections import defaultdict, deque
from typing import Dict, List, Optional, Deque

from models.analytics_models import (
    EnhancedMinuteBucket,
    PercentileMetrics,
    EndpointMetrics,
    AnalyticsSnapshot
)
from utils.analytics_aggregator import analytics_aggregator


class EnhancedMetricsStore:
    """
    Enhanced version of MetricsStore with analytics capabilities.
    
    Backward compatible with existing metrics_util.py while adding:
    - Per-endpoint performance tracking
    - Full percentile calculations
    - Unique user counting
    - Automatic aggregation to 5-min/hourly/daily buckets
    """
    
    def __init__(self, max_minutes: int = 60 * 24):  # 24 hours of minute-level data
        # Global counters (backward compatible)
        self.total_requests: int = 0
        self.total_ms: float = 0.0
        self.total_bytes_in: int = 0
        self.total_bytes_out: int = 0
        self.total_upstream_timeouts: int = 0
        self.total_retries: int = 0
        self.status_counts: Dict[int, int] = defaultdict(int)
        self.username_counts: Dict[str, int] = defaultdict(int)
        self.api_counts: Dict[str, int] = defaultdict(int)
        
        # Enhanced: Use EnhancedMinuteBucket instead of MinuteBucket
        self._buckets: Deque[EnhancedMinuteBucket] = deque()
        self._max_minutes = max_minutes
        
        # Track last aggregation times
        self._last_aggregation_check = 0
    
    @staticmethod
    def _minute_floor(ts: float) -> int:
        """Floor timestamp to nearest minute."""
        return int(ts // 60) * 60
    
    def _ensure_bucket(self, minute_start: int) -> EnhancedMinuteBucket:
        """Get or create bucket for the given minute."""
        if self._buckets and self._buckets[-1].start_ts == minute_start:
            return self._buckets[-1]
        
        # Create new enhanced bucket
        mb = EnhancedMinuteBucket(start_ts=minute_start)
        self._buckets.append(mb)
        
        # Maintain max size
        while len(self._buckets) > self._max_minutes:
            old_bucket = self._buckets.popleft()
            # Trigger aggregation for old buckets
            self._maybe_aggregate()
        
        return mb
    
    def record(
        self,
        status: int,
        duration_ms: float,
        username: Optional[str] = None,
        api_key: Optional[str] = None,
        endpoint_uri: Optional[str] = None,
        method: Optional[str] = None,
        bytes_in: int = 0,
        bytes_out: int = 0
    ) -> None:
        """
        Record a request with enhanced tracking.
        
        Backward compatible with existing record() calls while supporting
        new parameters for per-endpoint tracking.
        """
        now = time.time()
        minute_start = self._minute_floor(now)
        bucket = self._ensure_bucket(minute_start)
        
        # Record with enhanced tracking
        bucket.add_request(
            ms=duration_ms,
            status=status,
            username=username,
            api_key=api_key,
            endpoint_uri=endpoint_uri,
            method=method,
            bytes_in=bytes_in,
            bytes_out=bytes_out
        )
        
        # Update global counters (backward compatible)
        self.total_requests += 1
        self.total_ms += duration_ms
        try:
            self.total_bytes_in += int(bytes_in or 0)
            self.total_bytes_out += int(bytes_out or 0)
        except Exception:
            pass
        
        self.status_counts[status] += 1
        if username:
            self.username_counts[username] += 1
        if api_key:
            self.api_counts[api_key] += 1
        
        # Check if aggregation should run
        self._maybe_aggregate()
    
    def record_retry(self, api_key: Optional[str] = None) -> None:
        """Record a retry event."""
        now = time.time()
        minute_start = self._minute_floor(now)
        bucket = self._ensure_bucket(minute_start)
        try:
            bucket.retries += 1
            self.total_retries += 1
        except Exception:
            pass
    
    def record_upstream_timeout(self, api_key: Optional[str] = None) -> None:
        """Record an upstream timeout event."""
        now = time.time()
        minute_start = self._minute_floor(now)
        bucket = self._ensure_bucket(minute_start)
        try:
            bucket.upstream_timeouts += 1
            self.total_upstream_timeouts += 1
        except Exception:
            pass
    
    def _maybe_aggregate(self) -> None:
        """
        Check if aggregation should run and trigger if needed.
        
        Runs aggregation jobs based on time elapsed:
        - 5-minute aggregation: Every 5 minutes
        - Hourly aggregation: Every hour
        - Daily aggregation: Once per day
        """
        now = int(time.time())
        
        # Only check every minute to avoid overhead
        if now - self._last_aggregation_check < 60:
            return
        
        self._last_aggregation_check = now
        
        # Check what aggregations should run
        should_run = analytics_aggregator.should_aggregate()
        
        if should_run.get('5minute'):
            # Get last 5 minutes of buckets
            minute_buckets = list(self._buckets)[-5:]
            if minute_buckets:
                analytics_aggregator.aggregate_to_5minute(minute_buckets)
        
        if should_run.get('hourly'):
            analytics_aggregator.aggregate_to_hourly()
        
        if should_run.get('daily'):
            analytics_aggregator.aggregate_to_daily()
    
    def get_snapshot(
        self,
        start_ts: int,
        end_ts: int,
        granularity: str = 'auto'
    ) -> AnalyticsSnapshot:
        """
        Get analytics snapshot for a time range.
        
        Automatically selects best aggregation level based on range.
        """
        # Determine which buckets to use
        if granularity == 'auto':
            range_seconds = end_ts - start_ts
            if range_seconds <= 86400:  # <= 24 hours
                # Use minute-level buckets
                buckets = [b for b in self._buckets if start_ts <= b.start_ts <= end_ts]
            else:
                # Use aggregated buckets
                buckets = analytics_aggregator.get_buckets_for_range(start_ts, end_ts)
        else:
            # Use specified granularity
            if granularity == 'minute':
                buckets = [b for b in self._buckets if start_ts <= b.start_ts <= end_ts]
            else:
                buckets = analytics_aggregator.get_buckets_for_range(start_ts, end_ts)
        
        if not buckets:
            # Return empty snapshot
            return AnalyticsSnapshot(
                start_ts=start_ts,
                end_ts=end_ts,
                total_requests=0,
                total_errors=0,
                error_rate=0.0,
                avg_response_ms=0.0,
                percentiles=PercentileMetrics(),
                total_bytes_in=0,
                total_bytes_out=0,
                unique_users=0,
                series=[],
                top_apis=[],
                top_users=[],
                top_endpoints=[],
                status_distribution={}
            )
        
        # Aggregate data from buckets
        total_requests = sum(b.count for b in buckets)
        total_errors = sum(b.error_count for b in buckets)
        total_ms = sum(b.total_ms for b in buckets)
        total_bytes_in = sum(b.bytes_in for b in buckets)
        total_bytes_out = sum(b.bytes_out for b in buckets)
        
        # Collect all latencies for percentile calculation
        all_latencies: List[float] = []
        for bucket in buckets:
            all_latencies.extend(list(bucket.latencies))
        
        percentiles = PercentileMetrics.calculate(all_latencies) if all_latencies else PercentileMetrics()
        
        # Count unique users
        unique_users = set()
        for bucket in buckets:
            unique_users.update(bucket.unique_users)
        
        # Aggregate status counts
        status_distribution: Dict[str, int] = defaultdict(int)
        for bucket in buckets:
            for status, count in bucket.status_counts.items():
                status_distribution[str(status)] += count
        
        # Aggregate API counts
        api_counts: Dict[str, int] = defaultdict(int)
        for bucket in buckets:
            for api, count in bucket.api_counts.items():
                api_counts[api] += count
        
        # Aggregate user counts
        user_counts: Dict[str, int] = defaultdict(int)
        for bucket in buckets:
            for user, count in bucket.user_counts.items():
                user_counts[user] += count
        
        # Aggregate endpoint metrics
        endpoint_metrics: Dict[str, Dict] = defaultdict(lambda: {
            'count': 0,
            'error_count': 0,
            'total_ms': 0.0,
            'latencies': []
        })
        for bucket in buckets:
            for endpoint_key, ep_metrics in bucket.endpoint_metrics.items():
                endpoint_metrics[endpoint_key]['count'] += ep_metrics.count
                endpoint_metrics[endpoint_key]['error_count'] += ep_metrics.error_count
                endpoint_metrics[endpoint_key]['total_ms'] += ep_metrics.total_ms
                endpoint_metrics[endpoint_key]['latencies'].extend(list(ep_metrics.latencies))
        
        # Build top endpoints list
        top_endpoints = []
        for endpoint_key, metrics in endpoint_metrics.items():
            method, uri = endpoint_key.split(':', 1)
            avg_ms = metrics['total_ms'] / metrics['count'] if metrics['count'] > 0 else 0.0
            ep_percentiles = PercentileMetrics.calculate(metrics['latencies']) if metrics['latencies'] else PercentileMetrics()
            
            top_endpoints.append({
                'endpoint_uri': uri,
                'method': method,
                'count': metrics['count'],
                'error_count': metrics['error_count'],
                'error_rate': metrics['error_count'] / metrics['count'] if metrics['count'] > 0 else 0.0,
                'avg_ms': avg_ms,
                'percentiles': ep_percentiles.to_dict()
            })
        
        # Sort by count (most used)
        top_endpoints.sort(key=lambda x: x['count'], reverse=True)
        
        # Build time-series data
        series = []
        for bucket in buckets:
            avg_ms = bucket.total_ms / bucket.count if bucket.count > 0 else 0.0
            bucket_percentiles = bucket.get_percentiles()
            
            series.append({
                'timestamp': bucket.start_ts,
                'count': bucket.count,
                'error_count': bucket.error_count,
                'error_rate': bucket.error_count / bucket.count if bucket.count > 0 else 0.0,
                'avg_ms': avg_ms,
                'percentiles': bucket_percentiles.to_dict(),
                'bytes_in': bucket.bytes_in,
                'bytes_out': bucket.bytes_out,
                'unique_users': bucket.get_unique_user_count()
            })
        
        # Create snapshot
        return AnalyticsSnapshot(
            start_ts=start_ts,
            end_ts=end_ts,
            total_requests=total_requests,
            total_errors=total_errors,
            error_rate=total_errors / total_requests if total_requests > 0 else 0.0,
            avg_response_ms=total_ms / total_requests if total_requests > 0 else 0.0,
            percentiles=percentiles,
            total_bytes_in=total_bytes_in,
            total_bytes_out=total_bytes_out,
            unique_users=len(unique_users),
            series=series,
            top_apis=sorted(api_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            top_users=sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            top_endpoints=top_endpoints[:10],
            status_distribution=dict(status_distribution)
        )
    
    def snapshot(self, range_key: str, group: str = 'minute', sort: str = 'asc') -> Dict:
        """
        Backward compatible snapshot method for existing monitor endpoints.
        """
        range_to_minutes = {
            '1h': 60,
            '24h': 60 * 24,
            '7d': 60 * 24 * 7,
            '30d': 60 * 24 * 30,
        }
        minutes = range_to_minutes.get(range_key, 60 * 24)
        buckets: List[EnhancedMinuteBucket] = list(self._buckets)[-minutes:]
        series = []
        
        if group == 'day':
            from collections import defaultdict
            day_map: Dict[int, Dict[str, float]] = defaultdict(lambda: {
                'count': 0,
                'error_count': 0,
                'total_ms': 0.0,
                'bytes_in': 0,
                'bytes_out': 0,
            })
            for b in buckets:
                day_ts = int((b.start_ts // 86400) * 86400)
                d = day_map[day_ts]
                d['count'] += b.count
                d['error_count'] += b.error_count
                d['total_ms'] += b.total_ms
                d['bytes_in'] += b.bytes_in
                d['bytes_out'] += b.bytes_out
            for day_ts, d in day_map.items():
                avg_ms = (d['total_ms'] / d['count']) if d['count'] else 0.0
                series.append({
                    'timestamp': day_ts,
                    'count': int(d['count']),
                    'error_count': int(d['error_count']),
                    'avg_ms': avg_ms,
                    'bytes_in': int(d['bytes_in']),
                    'bytes_out': int(d['bytes_out']),
                    'error_rate': (int(d['error_count']) / int(d['count'])) if d['count'] else 0.0,
                })
        else:
            for b in buckets:
                avg_ms = (b.total_ms / b.count) if b.count else 0.0
                percentiles = b.get_percentiles()
                series.append({
                    'timestamp': b.start_ts,
                    'count': b.count,
                    'error_count': b.error_count,
                    'avg_ms': avg_ms,
                    'p95_ms': percentiles.p95,
                    'bytes_in': b.bytes_in,
                    'bytes_out': b.bytes_out,
                    'error_rate': (b.error_count / b.count) if b.count else 0.0,
                    'upstream_timeouts': b.upstream_timeouts,
                    'retries': b.retries,
                })
        
        reverse = (str(sort).lower() == 'desc')
        try:
            series.sort(key=lambda x: x.get('timestamp', 0), reverse=reverse)
        except Exception:
            pass
        
        total = self.total_requests
        avg_total_ms = (self.total_ms / total) if total else 0.0
        status = {str(k): v for k, v in self.status_counts.items()}
        return {
            'total_requests': total,
            'avg_response_ms': avg_total_ms,
            'total_bytes_in': self.total_bytes_in,
            'total_bytes_out': self.total_bytes_out,
            'total_upstream_timeouts': self.total_upstream_timeouts,
            'total_retries': self.total_retries,
            'status_counts': status,
            'series': series,
            'top_users': sorted(self.username_counts.items(), key=lambda kv: kv[1], reverse=True)[:10],
            'top_apis': sorted(self.api_counts.items(), key=lambda kv: kv[1], reverse=True)[:10],
        }
    
    def save_to_file(self, path: str) -> None:
        """Save metrics to file for persistence."""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except Exception:
            pass
        
        try:
            import json
            tmp = path + '.tmp'
            data = {
                'total_requests': self.total_requests,
                'total_ms': self.total_ms,
                'total_bytes_in': self.total_bytes_in,
                'total_bytes_out': self.total_bytes_out,
                'buckets': [b.to_dict() for b in list(self._buckets)]
            }
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            os.replace(tmp, path)
        except Exception:
            pass
    
    def load_from_file(self, path: str) -> None:
        """Load metrics from file."""
        # Note: Simplified version - full implementation would reconstruct
        # EnhancedMinuteBucket objects from saved data
        pass


# Global enhanced metrics store instance
enhanced_metrics_store = EnhancedMetricsStore()
