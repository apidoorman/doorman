import time
import pytest

@pytest.mark.order(-10)
def test_redis_outage_during_requests(client):
    r = client.get('/platform/authorization/status')
    assert r.status_code in (200, 204)

    r = client.post('/platform/tools/chaos/toggle', json={'backend': 'redis', 'enabled': True, 'duration_ms': 1500})
    assert r.status_code == 200

    t0 = time.time()
    r1 = client.get('/platform/authorization/status')
    dt1 = time.time() - t0
    assert dt1 < 2.0, f'request blocked too long during redis outage: {dt1}s'
    assert r1.status_code in (200, 204, 500, 503)

    time.sleep(2.0)
    r2 = client.get('/platform/authorization/status')
    assert r2.status_code in (200, 204)

    s = client.get('/platform/tools/chaos/stats')
    assert s.status_code == 200
    js = s.json()
    data = js.get('response', js)
    assert isinstance(data.get('error_budget_burn'), int)

@pytest.mark.order(-9)
def test_mongo_outage_during_requests(client):
    t0 = time.time()
    r0 = client.get('/platform/user/me')
    assert r0.status_code in (200, 204)

    r = client.post('/platform/tools/chaos/toggle', json={'backend': 'mongo', 'enabled': True, 'duration_ms': 1500})
    assert r.status_code == 200

    t1 = time.time()
    r1 = client.get('/platform/user/me')
    dt1 = time.time() - t1
    assert dt1 < 2.0, f'request blocked too long during mongo outage: {dt1}s'
    assert r1.status_code in (200, 400, 401, 403, 404, 500)

    time.sleep(2.0)
    r2 = client.get('/platform/user/me')
    assert r2.status_code in (200, 204)

    s = client.get('/platform/tools/chaos/stats')
    assert s.status_code == 200
    js = s.json()
    data = js.get('response', js)
    assert isinstance(data.get('error_budget_burn'), int)

