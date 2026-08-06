import time

from utils import shared_metrics_util


class _FakeRedis:
    def __init__(self, timestamp: int):
        self.key = f'gateway_metrics:{timestamp}'.encode()

    def scan_iter(self, **_kwargs):
        return iter([self.key])

    def hgetall(self, _key):
        return {
            b'count': b'2',
            b'test_count': b'1',
            b'error_count': b'1',
            b'total_micros': b'5000',
            b'bytes_in': b'10',
            b'bytes_out': b'20',
            b'status:500': b'1',
            b'api:rest:customers': b'2',
            b'user:alice': b'2',
            b'endpoint:/customers': b'2',
        }


def test_merge_rust_gateway_metrics_adds_redis_bucket_once(monkeypatch):
    timestamp = int(time.time() // 60) * 60
    monkeypatch.setattr(shared_metrics_util.doorman_cache, 'is_redis', True)
    monkeypatch.setattr(shared_metrics_util.doorman_cache, 'cache', _FakeRedis(timestamp))
    snapshot = {
        'series': [],
        'status_counts': {},
        'top_apis': [],
        'top_endpoints': [],
        'unique_users': 0,
    }

    result = shared_metrics_util.merge_rust_gateway_metrics(snapshot, '1h')

    assert result['total_requests'] == 2
    assert result['total_test_requests'] == 1
    assert result['total_bytes_in'] == 10
    assert result['total_bytes_out'] == 20
    assert result['avg_response_ms'] == 2.5
    assert result['status_counts'] == {'500': 1}
    assert result['top_apis'] == [('rest:customers', 2)]
    assert result['top_endpoints'] == [('/customers', 2)]
    assert result['unique_users'] == 1
