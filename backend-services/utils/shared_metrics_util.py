"""Merge Rust gateway Redis buckets into the legacy monitor response."""

from __future__ import annotations

import time
from collections import defaultdict

from utils.doorman_cache_util import doorman_cache


def merge_rust_gateway_metrics(
    snapshot: dict, range_key: str, group: str = 'minute', sort: str = 'asc'
) -> dict:
    if not getattr(doorman_cache, 'is_redis', False):
        return snapshot

    minutes = {'1h': 60, '24h': 1440, '7d': 10080, '30d': 43200}.get(range_key, 1440)
    cutoff = int(time.time() // 60) * 60 - (minutes - 1) * 60
    records: list[tuple[int, dict]] = []
    try:
        for raw_key in doorman_cache.cache.scan_iter(match='gateway_metrics:*', count=500):
            key = raw_key.decode() if isinstance(raw_key, bytes) else str(raw_key)
            try:
                timestamp = int(key.rsplit(':', 1)[1])
            except (IndexError, ValueError):
                continue
            if timestamp < cutoff:
                continue
            raw = doorman_cache.cache.hgetall(raw_key) or {}
            data = {
                (k.decode() if isinstance(k, bytes) else str(k)): (
                    v.decode() if isinstance(v, bytes) else str(v)
                )
                for k, v in raw.items()
            }
            records.append((timestamp, data))
    except Exception:
        return snapshot

    if not records:
        return snapshot

    api_counts: dict[str, int] = defaultdict(int)
    endpoint_counts: dict[str, int] = defaultdict(int)
    users: set[str] = set()
    series_map = {int(item.get('timestamp', 0)): dict(item) for item in snapshot.get('series', [])}
    for timestamp, data in records:
        bucket_ts = timestamp if group != 'day' else timestamp // 86400 * 86400
        item = series_map.setdefault(
            bucket_ts,
            {
                'timestamp': bucket_ts,
                'count': 0,
                'test_count': 0,
                'error_count': 0,
                'avg_ms': 0.0,
                'p95_ms': 0.0,
                'bytes_in': 0,
                'bytes_out': 0,
                'error_rate': 0.0,
                'upstream_timeouts': 0,
                'retries': 0,
            },
        )
        old_count = int(item.get('count', 0) or 0)
        rust_count = int(data.get('count', 0) or 0)
        total_ms = float(item.get('avg_ms', 0.0) or 0.0) * old_count
        total_ms += int(data.get('total_micros', 0) or 0) / 1000.0
        item['count'] = old_count + rust_count
        item['test_count'] = int(item.get('test_count', 0) or 0) + int(
            data.get('test_count', 0) or 0
        )
        item['error_count'] = int(item.get('error_count', 0) or 0) + int(
            data.get('error_count', 0) or 0
        )
        item['bytes_in'] = int(item.get('bytes_in', 0) or 0) + int(
            data.get('bytes_in', 0) or 0
        )
        item['bytes_out'] = int(item.get('bytes_out', 0) or 0) + int(
            data.get('bytes_out', 0) or 0
        )
        item['avg_ms'] = total_ms / item['count'] if item['count'] else 0.0
        item['error_rate'] = item['error_count'] / item['count'] if item['count'] else 0.0
        for field, raw_value in data.items():
            value = int(raw_value or 0)
            if field.startswith('status:'):
                status = field.split(':', 1)[1]
                counts = snapshot.setdefault('status_counts', {})
                counts[status] = int(counts.get(status, 0) or 0) + value
            elif field.startswith('api:'):
                api_counts[field.split(':', 1)[1]] += value
            elif field.startswith('user:'):
                users.add(field.split(':', 1)[1])
            elif field.startswith('endpoint:'):
                endpoint_counts[field.split(':', 1)[1]] += value

    snapshot['series'] = sorted(
        series_map.values(), key=lambda item: item.get('timestamp', 0), reverse=sort == 'desc'
    )
    snapshot['total_requests'] = sum(int(item.get('count', 0) or 0) for item in snapshot['series'])
    snapshot['total_test_requests'] = sum(
        int(item.get('test_count', 0) or 0) for item in snapshot['series']
    )
    snapshot['total_bytes_in'] = sum(
        int(item.get('bytes_in', 0) or 0) for item in snapshot['series']
    )
    snapshot['total_bytes_out'] = sum(
        int(item.get('bytes_out', 0) or 0) for item in snapshot['series']
    )
    total_ms = sum(
        float(item.get('avg_ms', 0.0) or 0.0) * int(item.get('count', 0) or 0)
        for item in snapshot['series']
    )
    snapshot['avg_response_ms'] = (
        total_ms / snapshot['total_requests'] if snapshot['total_requests'] else 0.0
    )
    top = defaultdict(int, dict(snapshot.get('top_apis') or []))
    for api, count in api_counts.items():
        top[api] += count
    snapshot['top_apis'] = sorted(top.items(), key=lambda pair: pair[1], reverse=True)[:10]
    top_endpoints = defaultdict(int, dict(snapshot.get('top_endpoints') or []))
    for endpoint, count in endpoint_counts.items():
        top_endpoints[endpoint] += count
    snapshot['top_endpoints'] = sorted(
        top_endpoints.items(), key=lambda pair: pair[1], reverse=True
    )[:10]
    snapshot['unique_users'] = int(snapshot.get('unique_users', 0) or 0) + len(users)
    return snapshot
