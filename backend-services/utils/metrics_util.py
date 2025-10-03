"""
In-memory metrics for gateway requests.
Records count, status code distribution, and response time stats, with per-minute buckets.
"""

# External imports
from __future__ import annotations
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional

@dataclass
class MinuteBucket:
    start_ts: int
    count: int = 0
    error_count: int = 0
    total_ms: float = 0.0
    bytes_in: int = 0
    bytes_out: int = 0

    status_counts: Dict[int, int] = field(default_factory=dict)
    api_counts: Dict[str, int] = field(default_factory=dict)
    api_error_counts: Dict[str, int] = field(default_factory=dict)
    user_counts: Dict[str, int] = field(default_factory=dict)

    def add(self, ms: float, status: int, username: Optional[str], api_key: Optional[str], bytes_in: int = 0, bytes_out: int = 0) -> None:
        self.count += 1
        if status >= 400:
            self.error_count += 1
        self.total_ms += ms
        try:
            self.bytes_in += int(bytes_in or 0)
            self.bytes_out += int(bytes_out or 0)
        except Exception:
            pass

        try:
            self.status_counts[status] = self.status_counts.get(status, 0) + 1
        except Exception:
            pass

        if api_key:
            try:
                self.api_counts[api_key] = self.api_counts.get(api_key, 0) + 1
                if status >= 400:
                    self.api_error_counts[api_key] = self.api_error_counts.get(api_key, 0) + 1
            except Exception:
                pass

        if username:
            try:
                self.user_counts[username] = self.user_counts.get(username, 0) + 1
            except Exception:
                pass

class MetricsStore:
    def __init__(self, max_minutes: int = 60 * 24 * 30):
        self.total_requests: int = 0
        self.total_ms: float = 0.0
        self.total_bytes_in: int = 0
        self.total_bytes_out: int = 0
        self.status_counts: Dict[int, int] = defaultdict(int)
        self.username_counts: Dict[str, int] = defaultdict(int)
        self.api_counts: Dict[str, int] = defaultdict(int)
        self._buckets: Deque[MinuteBucket] = deque()
        self._max_minutes = max_minutes

    @staticmethod
    def _minute_floor(ts: float) -> int:
        return int(ts // 60) * 60

    def _ensure_bucket(self, minute_start: int) -> MinuteBucket:
        if self._buckets and self._buckets[-1].start_ts == minute_start:
            return self._buckets[-1]

        mb = MinuteBucket(start_ts=minute_start)
        self._buckets.append(mb)

        while len(self._buckets) > self._max_minutes:
            self._buckets.popleft()
        return mb

    def record(self, status: int, duration_ms: float, username: Optional[str] = None, api_key: Optional[str] = None, bytes_in: int = 0, bytes_out: int = 0) -> None:
        now = time.time()
        minute_start = self._minute_floor(now)
        bucket = self._ensure_bucket(minute_start)
        bucket.add(duration_ms, status, username, api_key, bytes_in=bytes_in, bytes_out=bytes_out)
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

    def snapshot(self, range_key: str, group: str = 'minute', sort: str = 'asc') -> Dict:

        range_to_minutes = {
            '1h': 60,
            '24h': 60 * 24,
            '7d': 60 * 24 * 7,
            '30d': 60 * 24 * 30,
        }
        minutes = range_to_minutes.get(range_key, 60 * 24)
        buckets: List[MinuteBucket] = list(self._buckets)[-minutes:]
        series = []

        if group == 'day':
            # Aggregate per UTC day
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
            # Build series
            for day_ts, d in day_map.items():
                avg_ms = (d['total_ms'] / d['count']) if d['count'] else 0.0
                series.append({
                    'timestamp': day_ts,
                    'count': int(d['count']),
                    'error_count': int(d['error_count']),
                    'avg_ms': avg_ms,
                    'bytes_in': int(d['bytes_in']),
                    'bytes_out': int(d['bytes_out']),
                })
        else:
            # Default per-minute series
            for b in buckets:
                avg_ms = (b.total_ms / b.count) if b.count else 0.0
                series.append({
                    'timestamp': b.start_ts,
                    'count': b.count,
                    'error_count': b.error_count,
                    'avg_ms': avg_ms,
                    'bytes_in': b.bytes_in,
                    'bytes_out': b.bytes_out,
                })

        # Sort series by timestamp
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
            'status_counts': status,
            'series': series,
            'top_users': sorted(self.username_counts.items(), key=lambda kv: kv[1], reverse=True)[:10],
            'top_apis': sorted(self.api_counts.items(), key=lambda kv: kv[1], reverse=True)[:10],
        }

# Global metrics store
metrics_store = MetricsStore()
