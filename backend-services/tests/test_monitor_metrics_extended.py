import asyncio
import time
import pytest

@pytest.mark.asyncio
async def test_metrics_increment_on_gateway_requests(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    for name in ('mapi1', 'mapi2'):
        await create_api(authed_client, name, 'v1')
        await create_endpoint(authed_client, name, 'v1', 'GET', '/ping')
        await subscribe_self(authed_client, name, 'v1')

    import services.gateway_service as gs

    class _FakeHTTPResponse:
        def __init__(self, status_code=200):
            self.status_code = status_code
            self.headers = {'Content-Type': 'application/json'}
            self.text = '{}'
            self.content = b'{}'
        def json(self):
            return {'ok': True}

    class _FakeAsyncClient:
        def __init__(self, timeout=None, limits=None, http2=False):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def request(self, method, url, **kwargs):
            """Generic request method used by http_client.request_with_resilience"""
            method = method.upper()
            if method == 'GET':
                return await self.get(url, **kwargs)
            elif method == 'POST':
                return await self.post(url, **kwargs)
            elif method == 'PUT':
                return await self.put(url, **kwargs)
            elif method == 'DELETE':
                return await self.delete(url, **kwargs)
            elif method == 'HEAD':
                return await self.get(url, **kwargs)
            elif method == 'PATCH':
                return await self.put(url, **kwargs)
            else:
                return _FakeHTTPResponse(405)
        async def get(self, url, params=None, headers=None, **kwargs):
            return _FakeHTTPResponse(200)
        async def post(self, url, **kwargs):
            return _FakeHTTPResponse(200)
        async def put(self, url, **kwargs):
            return _FakeHTTPResponse(200)
        async def delete(self, url, **kwargs):
            return _FakeHTTPResponse(200)

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    await authed_client.get('/api/rest/mapi1/v1/ping')
    await authed_client.get('/api/rest/mapi2/v1/ping')
    await authed_client.get('/api/rest/mapi2/v1/ping')

    r = await authed_client.get('/platform/monitor/metrics')
    assert r.status_code == 200
    body = r.json().get('response') or r.json()
    assert (body.get('total_requests') or 0) >= 3
    status_counts = body.get('status_counts') or {}
    assert status_counts.get('200', 0) >= 3
    series = body.get('series') or []
    assert isinstance(series, list)

@pytest.mark.asyncio
async def test_metrics_top_apis_aggregate(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self
    name, ver = 'mapi3', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/x')
    await subscribe_self(authed_client, name, ver)

    import services.gateway_service as gs

    class _FakeHTTPResponse:
        def __init__(self, status_code=200):
            self.status_code = status_code
            self.headers = {'Content-Type': 'application/json'}
            self.text = '{}'
            self.content = b'{}'
        def json(self): return {'ok': True}

    class _FakeAsyncClient:
        def __init__(self, timeout=None, limits=None, http2=False): pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def request(self, method, url, **kwargs):
            """Generic request method used by http_client.request_with_resilience"""
            method = method.upper()
            if method == 'GET':
                return await self.get(url, **kwargs)
            elif method == 'POST':
                return await self.post(url, **kwargs)
            elif method == 'PUT':
                return await self.put(url, **kwargs)
            elif method == 'DELETE':
                return await self.delete(url, **kwargs)
            elif method == 'HEAD':
                return await self.get(url, **kwargs)
            elif method == 'PATCH':
                return await self.put(url, **kwargs)
            else:
                return _FakeHTTPResponse(405)
        async def get(self, url, params=None, headers=None, **kwargs): return _FakeHTTPResponse(200)
        async def post(self, url, **kwargs): return _FakeHTTPResponse(200)
        async def put(self, url, **kwargs): return _FakeHTTPResponse(200)
        async def delete(self, url, **kwargs): return _FakeHTTPResponse(200)

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    for _ in range(2):
        await authed_client.get(f'/api/rest/{name}/{ver}/x')

    r = await authed_client.get('/platform/monitor/metrics')
    assert r.status_code == 200
    body = r.json().get('response') or r.json()
    top_apis = body.get('top_apis') or []

    assert any(isinstance(a, list) and a[0].startswith('rest:') for a in top_apis)

@pytest.mark.asyncio
async def test_monitor_liveness_and_readiness(authed_client):
    live = await authed_client.get('/platform/monitor/liveness')
    assert live.status_code == 200
    assert (live.json() or {}).get('status') == 'alive'

    ready = await authed_client.get('/platform/monitor/readiness')
    assert ready.status_code == 200
    status = (ready.json() or {}).get('status')
    assert status in ('ready', 'degraded')

@pytest.mark.asyncio
async def test_monitor_report_csv(monkeypatch, authed_client):

    from conftest import create_api, create_endpoint, subscribe_self
    name, ver = 'mapi4', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/r')
    await subscribe_self(authed_client, name, ver)

    import services.gateway_service as gs
    class _FakeHTTPResponse:
        def __init__(self):
            self.status_code = 200
            self.headers = {'Content-Type': 'application/json'}
            self.text = '{}'
            self.content = b'{}'
        def json(self): return {'ok': True}

    class _FakeAsyncClient:
        def __init__(self, timeout=None, limits=None, http2=False): pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def request(self, method, url, **kwargs):
            """Generic request method used by http_client.request_with_resilience"""
            method = method.upper()
            if method == 'GET':
                return await self.get(url, **kwargs)
            elif method == 'POST':
                return await self.post(url, **kwargs)
            elif method == 'PUT':
                return await self.put(url, **kwargs)
            elif method == 'DELETE':
                return await self.delete(url, **kwargs)
            elif method == 'HEAD':
                return await self.get(url, **kwargs)
            elif method == 'PATCH':
                return await self.put(url, **kwargs)
            else:
                return _FakeHTTPResponse()
        async def get(self, url, params=None, headers=None, **kwargs): return _FakeHTTPResponse()
        async def post(self, url, **kwargs): return _FakeHTTPResponse()
        async def put(self, url, **kwargs): return _FakeHTTPResponse()
        async def delete(self, url, **kwargs): return _FakeHTTPResponse()

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    await authed_client.get(f'/api/rest/{name}/{ver}/r')

    from datetime import datetime
    now = datetime.utcnow()
    start = now.strftime('%Y-%m-%dT%H:%M')
    end = start
    csvr = await authed_client.get(f'/platform/monitor/report?start={start}&end={end}')
    assert csvr.status_code == 200

    text = csvr.text
    assert 'Report' in text and 'Overview' in text and 'Status Codes' in text and 'API Usage' in text

