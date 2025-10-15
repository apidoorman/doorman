"""
In-memory metrics for gateway requests.
Records count, status code distribution, and response time stats, with per-minute buckets.
"""

from __future__ import annotations
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional
import json
import os

@dataclass
class MinuteBucket:
    start_ts: int
    count: int = 0
    error_count: int = 0
    total_ms: float = 0.0
    bytes_in: int = 0
    bytes_out: int = 0
    upstream_timeouts: int = 0
    retries: int = 0

    status_counts: Dict[int, int] = field(default_factory=dict)
    api_counts: Dict[str, int] = field(default_factory=dict)
    api_error_counts: Dict[str, int] = field(default_factory=dict)
    user_counts: Dict[str, int] = field(default_factory=dict)
    latencies: Deque[float] = field(default_factory=deque)

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

        try:
            if self.latencies is None:
                self.latencies = deque()
            self.latencies.append(ms)
            max_samples = int(os.getenv('METRICS_PCT_SAMPLES', '500'))
            while len(self.latencies) > max_samples:
                self.latencies.popleft()
        except Exception:
            pass

    def to_dict(self) -> Dict:
        return {
            'start_ts': self.start_ts,
            'count': self.count,
            'error_count': self.error_count,
            'total_ms': self.total_ms,
            'bytes_in': self.bytes_in,
            'bytes_out': self.bytes_out,
            'upstream_timeouts': self.upstream_timeouts,
            'retries': self.retries,
            'status_counts': dict(self.status_counts or {}),
            'api_counts': dict(self.api_counts or {}),
            'api_error_counts': dict(self.api_error_counts or {}),
            'user_counts': dict(self.user_counts or {}),
        }

    @staticmethod
    def from_dict(d: Dict) -> 'MinuteBucket':
        mb = MinuteBucket(
            start_ts=int(d.get('start_ts', 0)),
            count=int(d.get('count', 0)),
            error_count=int(d.get('error_count', 0)),
            total_ms=float(d.get('total_ms', 0.0)),
            bytes_in=int(d.get('bytes_in', 0)),
            bytes_out=int(d.get('bytes_out', 0)),
        )
        try:
            mb.upstream_timeouts = int(d.get('upstream_timeouts', 0))
            mb.retries = int(d.get('retries', 0))
            mb.status_counts = dict(d.get('status_counts') or {})
            mb.api_counts = dict(d.get('api_counts') or {})
            mb.api_error_counts = dict(d.get('api_error_counts') or {})
            mb.user_counts = dict(d.get('user_counts') or {})
        except Exception:
            pass
        return mb

class MetricsStore:
    def __init__(self, max_minutes: int = 60 * 24 * 30):
        self.total_requests: int = 0
        self.total_ms: float = 0.0
        self.total_bytes_in: int = 0
        self.total_bytes_out: int = 0
        self.total_upstream_timeouts: int = 0
        self.total_retries: int = 0
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

    def record_retry(self, api_key: Optional[str] = None) -> None:
        now = time.time()
        minute_start = self._minute_floor(now)
        bucket = self._ensure_bucket(minute_start)
        try:
            bucket.retries += 1
            self.total_retries += 1
        except Exception:
            pass

    def record_upstream_timeout(self, api_key: Optional[str] = None) -> None:
        now = time.time()
        minute_start = self._minute_floor(now)
        bucket = self._ensure_bucket(minute_start)
        try:
            bucket.upstream_timeouts += 1
            self.total_upstream_timeouts += 1
        except Exception:
            pass

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
                p95 = 0.0
                try:
                    arr = list(b.latencies)
                    if arr:
                        arr.sort()
                        k = max(0, int(0.95 * len(arr)) - 1)
                        p95 = float(arr[k])
                except Exception:
                    p95 = 0.0
                series.append({
                    'timestamp': b.start_ts,
                    'count': b.count,
                    'error_count': b.error_count,
                    'avg_ms': avg_ms,
                    'p95_ms': p95,
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

    def to_dict(self) -> Dict:
        return {
            'total_requests': int(self.total_requests),
            'total_ms': float(self.total_ms),
            'total_bytes_in': int(self.total_bytes_in),
            'total_bytes_out': int(self.total_bytes_out),
            'status_counts': dict(self.status_counts),
            'username_counts': dict(self.username_counts),
            'api_counts': dict(self.api_counts),
            'buckets': [b.to_dict() for b in list(self._buckets)],
        }

    def load_dict(self, data: Dict) -> None:
        try:
            self.total_requests = int(data.get('total_requests', 0))
            self.total_ms = float(data.get('total_ms', 0.0))
            self.total_bytes_in = int(data.get('total_bytes_in', 0))
            self.total_bytes_out = int(data.get('total_bytes_out', 0))
            self.total_upstream_timeouts = int(data.get('total_upstream_timeouts', 0))
            self.total_retries = int(data.get('total_retries', 0))
            self.status_counts = defaultdict(int, data.get('status_counts') or {})
            self.username_counts = defaultdict(int, data.get('username_counts') or {})
            self.api_counts = defaultdict(int, data.get('api_counts') or {})
            self._buckets.clear()
            for bd in data.get('buckets', []):
                try:
                    self._buckets.append(MinuteBucket.from_dict(bd))
                except Exception:
                    continue
        except Exception:
            pass

    def save_to_file(self, path: str) -> None:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except Exception:
            pass
        try:
            tmp = path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f)
            os.replace(tmp, path)
        except Exception:
            pass

    def load_from_file(self, path: str) -> None:
        try:
            if not os.path.exists(path):
                return
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.load_dict(data)
        except Exception:
            pass

metrics_store = MetricsStore()
