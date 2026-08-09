def test_monitor_endpoints(client):
    r = client.get('/platform/monitor/liveness')
    assert r.status_code == 200
    assert r.json().get('status') == 'alive'

    r = client.get('/platform/monitor/readiness')
    assert r.status_code == 200
    body = r.json()
    assert body.get('status') in ('ready', 'degraded')

    r = client.get('/platform/monitor/metrics')
    assert r.status_code == 200
    metrics = r.json().get('response', r.json())
    assert isinstance(metrics, dict)


import pytest

pytestmark = [pytest.mark.monitor]
