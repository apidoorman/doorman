import time
import pytest


@pytest.mark.order(-10)
def test_redis_outage_during_requests(client):
    # Warm up a platform endpoint that touches cache minimally
    r = client.get('/platform/authorization/status')
    assert r.status_code in (200, 204)

    # Trigger redis outage for a short duration
    r = client.post('/platform/tools/chaos/toggle', json={'backend': 'redis', 'enabled': True, 'duration_ms': 1500})
    assert r.status_code == 200

    t0 = time.time()
    # During outage: app should not block; responses should come back quickly
    r1 = client.get('/platform/authorization/status')
    dt1 = time.time() - t0
    assert dt1 < 2.0, f'request blocked too long during redis outage: {dt1}s'
    assert r1.status_code in (200, 204, 500, 503)

    # Wait for auto-recover
    time.sleep(2.0)
    r2 = client.get('/platform/authorization/status')
    assert r2.status_code in (200, 204)

    # Check error budget burn recorded
    s = client.get('/platform/tools/chaos/stats')
    assert s.status_code == 200
    js = s.json()
    data = js.get('response', js)
    assert isinstance(data.get('error_budget_burn'), int)


@pytest.mark.order(-9)
def test_mongo_outage_during_requests(client):
    # Ensure a DB-backed endpoint is hit (user profile)
    t0 = time.time()
    r0 = client.get('/platform/user/me')
    assert r0.status_code in (200, 204)

    # Simulate mongo outage and immediately hit the same endpoint
    r = client.post('/platform/tools/chaos/toggle', json={'backend': 'mongo', 'enabled': True, 'duration_ms': 1500})
    assert r.status_code == 200

    t1 = time.time()
    r1 = client.get('/platform/user/me')
    dt1 = time.time() - t1
    # Do not block the event loop excessively; return fast with error if needed
    assert dt1 < 2.0, f'request blocked too long during mongo outage: {dt1}s'
    assert r1.status_code in (200, 400, 401, 403, 404, 500)

    # After recovery window
    time.sleep(2.0)
    r2 = client.get('/platform/user/me')
    assert r2.status_code in (200, 204)

    s = client.get('/platform/tools/chaos/stats')
    assert s.status_code == 200
    js = s.json()
    data = js.get('response', js)
    assert isinstance(data.get('error_budget_burn'), int)

