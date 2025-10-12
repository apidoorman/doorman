# External imports
import os
import pytest
from jose import jwt

@pytest.mark.asyncio
async def test_jwt_tamper_rejected(client):

    bad_token = jwt.encode({'sub': 'admin'}, 'wrong-secret', algorithm='HS256')
    client.cookies.set('access_token_cookie', bad_token)
    r = await client.get('/platform/user/me')
    assert r.status_code in (401, 500)

@pytest.mark.asyncio
async def test_csrf_required_when_https(monkeypatch, authed_client):

    monkeypatch.setenv('HTTPS_ENABLED', 'true')
    r = await authed_client.get('/platform/user/me')
    assert r.status_code in (401, 500)

@pytest.mark.asyncio
async def test_header_injection_is_sanitized(monkeypatch, authed_client):

    api_name, version = 'hdr', 'v1'
    c = await authed_client.post(
        '/platform/api',
        json={
            'api_name': api_name,
            'api_version': version,
            'api_description': 'hdr api',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://fake-upstream'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
            'api_allowed_headers': ['X-Allowed'],
        },
    )
    assert c.status_code in (200, 201)
    ep = await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': api_name,
            'api_version': version,
            'endpoint_method': 'GET',
            'endpoint_uri': '/x',
            'endpoint_description': 'x',
        },
    )
    assert ep.status_code in (200, 201)
    s = await authed_client.post(
        '/platform/subscription/subscribe',
        json={'username': 'admin', 'api_name': api_name, 'api_version': version},
    )
    assert s.status_code in (200, 201)

    import services.gateway_service as gs
    captured = {}

    class _FakeHTTPResponse:
        def __init__(self, status_code=200, json_body=None):
            self.status_code = status_code
            self._json_body = json_body or {'ok': True}
            self.headers = {'Content-Type': 'application/json'}
            self.content = b'{}'
            self.text = '{}'
        def json(self):
            return self._json_body

    class _FakeAsyncClient:
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
                return _FakeHTTPResponse(405, json_body={'error': 'Method not allowed'})
        async def get(self, url, params=None, headers=None, **kwargs):
            captured['headers'] = headers or {}
            return _FakeHTTPResponse(200)
        async def post(self, url, **kwargs):
            return _FakeHTTPResponse(200)
        async def put(self, url, **kwargs):
            return _FakeHTTPResponse(200)
        async def delete(self, url, **kwargs):
            return _FakeHTTPResponse(200)

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    import routes.gateway_routes as gr
    async def _no_limit(req): return None
    async def _pass_sub(req): return {'sub': 'admin'}
    async def _pass_group(req, full_path: str = None, user_to_subscribe=None): return {'sub': 'admin'}
    monkeypatch.setattr(gr, 'limit_and_throttle', _no_limit)
    monkeypatch.setattr(gr, 'subscription_required', _pass_sub)
    monkeypatch.setattr(gr, 'group_required', _pass_group)

    inj_value = 'abc\r\nInjected: 1<script>alert(1)</script>'
    r = await authed_client.get(
        '/api/rest/hdr/v1/x',
        headers={'X-Allowed': inj_value},
    )
    assert r.status_code in (200, 500)
    forwarded = captured.get('headers', {}).get('X-Allowed', '')

    assert '\r' not in forwarded and '\n' not in forwarded
    assert '<' not in forwarded and '>' not in forwarded

@pytest.mark.asyncio
async def test_rate_limit_enforced(monkeypatch, authed_client):

    from utils.database import user_collection
    user_collection.update_one(
        {'username': 'admin'},
        {'$set': {'rate_limit_duration': 1, 'rate_limit_duration_type': 'second',
                   'throttle_duration': 1, 'throttle_duration_type': 'second',
                   'throttle_queue_limit': 1, 'throttle_wait_duration': 0.0, 'throttle_wait_duration_type': 'second'}}
    )

    class _FakeRedis:
        def __init__(self):
            self.store = {}
        async def incr(self, key):
            self.store[key] = self.store.get(key, 0) + 1
            return self.store[key]
        async def expire(self, key, ttl):
            return True

    from doorman import doorman as app
    app.state.redis = _FakeRedis()

    from utils.doorman_cache_util import doorman_cache
    try:
        doorman_cache.delete_cache('user_cache', 'admin')
    except Exception:
        pass

    c = await authed_client.post(
        '/platform/api',
        json={
            'api_name': 'ratel',
            'api_version': 'v1',
            'api_description': 'rl',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://fake-upstream'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
        },
    )
    assert c.status_code in (200, 201)
    ep = await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': 'ratel',
            'api_version': 'v1',
            'endpoint_method': 'GET',
            'endpoint_uri': '/x',
            'endpoint_description': 'x',
        },
    )
    assert ep.status_code in (200, 201)
    s = await authed_client.post(
        '/platform/subscription/subscribe',
        json={'username': 'admin', 'api_name': 'ratel', 'api_version': 'v1'},
    )
    assert s.status_code in (200, 201)

    import services.gateway_service as gs
    class _FakeHTTPResponse:
        def __init__(self, status_code=200, json_body=None):
            self.status_code = status_code
            self._json_body = json_body or {'ok': True}
            self.headers = {'Content-Type': 'application/json'}
            self.content = b'{}'
            self.text = '{}'
        def json(self):
            return self._json_body
    class _FakeAsyncClient:
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
                return _FakeHTTPResponse(405, json_body={'error': 'Method not allowed'})
        async def get(self, url, params=None, headers=None, **kwargs): return _FakeHTTPResponse(200)
        async def post(self, url, **kwargs): return _FakeHTTPResponse(200)
        async def put(self, url, **kwargs): return _FakeHTTPResponse(200)
        async def delete(self, url, **kwargs): return _FakeHTTPResponse(200)
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    import routes.gateway_routes as gr
    async def _pass_sub(req): return {'sub': 'admin'}
    async def _pass_group(req, full_path: str = None, user_to_subscribe=None): return {'sub': 'admin'}
    monkeypatch.setattr(gr, 'subscription_required', _pass_sub)
    monkeypatch.setattr(gr, 'group_required', _pass_group)

    r1 = await authed_client.get('/api/rest/ratel/v1/x')

    r2 = await authed_client.get('/api/rest/ratel/v1/x')
    assert r1.status_code in (200, 500)
    assert r2.status_code == 429
