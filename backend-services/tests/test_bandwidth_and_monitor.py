# External imports
import json
import pytest


@pytest.mark.asyncio
async def test_bandwidth_enforcement_and_usage_tracking(monkeypatch, authed_client):
    # Set a small bandwidth limit for admin user
    # Set low limit then restore afterwards to avoid polluting other tests
    try:
        upd = await authed_client.put('/platform/user/admin', json={'bandwidth_limit_bytes': 80, 'bandwidth_limit_window': 'second'})
        assert upd.status_code in (200, 204)
    except AssertionError:
        # Best effort cleanup if update failed
        await authed_client.put('/platform/user/admin', json={'bandwidth_limit_bytes': None})
        raise

    # Create a small API and endpoint and subscribe admin
    from conftest import create_api, create_endpoint, subscribe_self
    name, ver = 'bwapi', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'POST', '/p')
    await subscribe_self(authed_client, name, ver)

    # Mock upstream to avoid real network and produce a small response
    import services.gateway_service as gs

    class _FakeHTTPResponse:
        def __init__(self, status_code=200, body=b'{"ok":true}'):
            self.status_code = status_code
            self.headers = {'Content-Type': 'application/json', 'Content-Length': str(len(body))}
            self.text = body.decode('utf-8')
            self.content = body
        def json(self):
            return json.loads(self.text)

    class _FakeAsyncClient:
        def __init__(self, timeout=None):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def post(self, url, data=None, json=None, headers=None, params=None):
            return _FakeHTTPResponse(200)

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    # Prepare JSON body around ~60 bytes
    payload = {'data': 'x' * 50}
    body = json.dumps(payload).encode('utf-8')
    assert len(body) >= 50

    # First request should succeed (under limit)
    r1 = await authed_client.post(f'/api/rest/{name}/{ver}/p', json=payload)
    assert r1.status_code == 200

    # Second request should be blocked (pre-request enforcement)
    r2 = await authed_client.post(f'/api/rest/{name}/{ver}/p', json=payload)
    assert r2.status_code == 429

    # User endpoint should show usage and reset time
    u = await authed_client.get('/platform/user/admin')
    assert u.status_code == 200
    data = u.json().get('response') or u.json()
    assert int(data.get('bandwidth_usage_bytes', 0)) > 0
    assert int(data.get('bandwidth_resets_at', 0)) > 0

    # Restore admin bandwidth settings to avoid 429s in subsequent tests (0 disables)
    await authed_client.put('/platform/user/admin', json={'bandwidth_limit_bytes': 0})


@pytest.mark.asyncio
async def test_monitor_tracks_bytes_in_out(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self
    name, ver = 'bwmon', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'POST', '/echo')
    await subscribe_self(authed_client, name, ver)

    # Mock upstream response with known bytes length
    import services.gateway_service as gs

    resp_body = b'{"ok":true,"pad":"' + b'y' * 20 + b'"}'

    class _FakeHTTPResponse:
        def __init__(self, status_code=200, body=resp_body):
            self.status_code = status_code
            self.headers = {'Content-Type': 'application/json', 'Content-Length': str(len(body))}
            self.text = body.decode('utf-8')
            self.content = body
        def json(self):
            return json.loads(self.text)

    class _FakeAsyncClient:
        def __init__(self, timeout=None): pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def post(self, url, data=None, json=None, headers=None, params=None): return _FakeHTTPResponse(200)

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    # Snapshot totals before
    m0 = await authed_client.get('/platform/monitor/metrics')
    assert m0.status_code == 200
    j0 = m0.json().get('response') or m0.json()
    tin0 = int(j0.get('total_bytes_in', 0))
    tout0 = int(j0.get('total_bytes_out', 0))

    # Send two POSTs with known input size
    payload = {'pad': 'z' * 30}
    body_len = len(json.dumps(payload).encode('utf-8'))
    r1 = await authed_client.post(f'/api/rest/{name}/{ver}/echo', json=payload)
    r2 = await authed_client.post(f'/api/rest/{name}/{ver}/echo', json=payload)
    assert r1.status_code == 200 and r2.status_code == 200

    # Snapshot after
    m1 = await authed_client.get('/platform/monitor/metrics')
    j1 = m1.json().get('response') or m1.json()
    tin1 = int(j1.get('total_bytes_in', 0))
    tout1 = int(j1.get('total_bytes_out', 0))

    # Validate deltas meet or exceed expected totals (some wrappers may add small overhead)
    assert tin1 - tin0 >= body_len * 2
    assert tout1 - tout0 >= len(resp_body) * 2
