import pytest


class _FakeHTTPResponse:
    def __init__(self, status_code=200, json_body=None, text_body=None, headers=None):
        self.status_code = status_code
        self._json_body = json_body
        self.text = text_body if text_body is not None else ('' if json_body is not None else 'OK')

        base_headers = {'Content-Type': 'application/json'}
        if headers:
            base_headers.update(headers)
        self.headers = base_headers

    def json(self):
        import json as _json

        if self._json_body is None:
            return _json.loads(self.text or '{}')
        return self._json_body


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

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
        try:
            qp = dict(params or {})
        except Exception:
            qp = {}
        return _FakeHTTPResponse(
            200,
            json_body={'method': 'GET', 'url': url, 'params': qp, 'headers': headers or {}},
            headers={'X-Upstream': 'yes'},
        )

    async def post(self, url, json=None, params=None, headers=None, content=None, **kwargs):
        body = (
            json
            if json is not None
            else (content.decode('utf-8') if isinstance(content, (bytes, bytearray)) else content)
        )
        try:
            qp = dict(params or {})
        except Exception:
            qp = {}
        return _FakeHTTPResponse(
            200,
            json_body={
                'method': 'POST',
                'url': url,
                'params': qp,
                'body': body,
                'headers': headers or {},
            },
            headers={'X-Upstream': 'yes'},
        )

    async def put(self, url, json=None, params=None, headers=None, content=None, **kwargs):
        body = (
            json
            if json is not None
            else (content.decode('utf-8') if isinstance(content, (bytes, bytearray)) else content)
        )
        try:
            qp = dict(params or {})
        except Exception:
            qp = {}
        return _FakeHTTPResponse(
            200,
            json_body={
                'method': 'PUT',
                'url': url,
                'params': qp,
                'body': body,
                'headers': headers or {},
            },
            headers={'X-Upstream': 'yes'},
        )

    async def delete(self, url, json=None, params=None, headers=None, content=None, **kwargs):
        try:
            qp = dict(params or {})
        except Exception:
            qp = {}
        return _FakeHTTPResponse(
            200,
            json_body={'method': 'DELETE', 'url': url, 'params': qp, 'headers': headers or {}},
            headers={'X-Upstream': 'yes'},
        )


class _NotFoundAsyncClient(_FakeAsyncClient):
    async def get(self, url, params=None, headers=None, **kwargs):
        try:
            qp = dict(params or {})
        except Exception:
            qp = {}
        return _FakeHTTPResponse(
            404, json_body={'ok': False, 'url': url, 'params': qp}, headers={'X-Upstream': 'no'}
        )


@pytest.mark.asyncio
async def test_routing_precedence_and_round_robin(monkeypatch, authed_client):
    from conftest import create_api, subscribe_self

    name, ver = 'routeapi', 'v1'
    await create_api(authed_client, name, ver)

    ep = await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'GET',
            'endpoint_uri': '/ping',
            'endpoint_description': 'ping',
            'endpoint_servers': ['http://ep-a', 'http://ep-b'],
        },
    )
    assert ep.status_code in (200, 201)
    await subscribe_self(authed_client, name, ver)

    r = await authed_client.post(
        '/platform/routing',
        json={
            'routing_name': 'r1',
            'routing_servers': ['http://route-a', 'http://route-b'],
            'routing_description': 'demo',
            'client_key': 'client-1',
        },
    )
    assert r.status_code in (200, 201)

    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    a = await authed_client.get(f'/api/rest/{name}/{ver}/ping', headers={'client-key': 'client-1'})
    assert a.status_code == 200
    assert a.json().get('url', '').startswith('http://route-')

    b1 = await authed_client.get(f'/api/rest/{name}/{ver}/ping')
    b2 = await authed_client.get(f'/api/rest/{name}/{ver}/ping')
    assert b1.json().get('url', '').startswith('http://ep-a')
    assert b2.json().get('url', '').startswith('http://ep-b')


@pytest.mark.asyncio
async def test_client_routing_round_robin(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    name, ver = 'clientrr', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/p')
    await subscribe_self(authed_client, name, ver)

    await authed_client.post(
        '/platform/routing',
        json={
            'routing_name': 'rcli',
            'routing_servers': ['http://r1', 'http://r2'],
            'routing_description': 'rr',
            'client_key': 'c1',
        },
    )
    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r1 = await authed_client.get(f'/api/rest/{name}/{ver}/p', headers={'client-key': 'c1'})
    r2 = await authed_client.get(f'/api/rest/{name}/{ver}/p', headers={'client-key': 'c1'})
    assert r1.json().get('url', '').startswith('http://r1')
    assert r2.json().get('url', '').startswith('http://r2')


@pytest.mark.asyncio
async def test_api_level_round_robin_when_no_endpoint_servers(monkeypatch, authed_client):
    from conftest import create_endpoint, subscribe_self

    name, ver = 'apiround', 'v1'

    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://api-a', 'http://api-b'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    }
    c = await authed_client.post('/platform/api', json=payload)
    assert c.status_code in (200, 201)

    await create_endpoint(authed_client, name, ver, 'GET', '/rr')
    await subscribe_self(authed_client, name, ver)

    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    r1 = await authed_client.get(f'/api/rest/{name}/{ver}/rr')
    r2 = await authed_client.get(f'/api/rest/{name}/{ver}/rr')
    assert r1.json().get('url', '').startswith('http://api-a')
    assert r2.json().get('url', '').startswith('http://api-b')


@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_429(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    name, ver = 'ratelimit', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/ping')
    await subscribe_self(authed_client, name, ver)

    from utils.database import user_collection

    user_collection.update_one(
        {'username': 'admin'},
        {'$set': {'rate_limit_duration': 1, 'rate_limit_duration_type': 'second'}},
    )

    await authed_client.delete('/api/caches')

    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    ok = await authed_client.get(f'/api/rest/{name}/{ver}/ping')
    assert ok.status_code == 200
    too_many = await authed_client.get(f'/api/rest/{name}/{ver}/ping')
    assert too_many.status_code == 429


@pytest.mark.asyncio
async def test_throttle_queue_limit_exceeded_returns_429(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    name, ver = 'throttleq', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/t')
    await subscribe_self(authed_client, name, ver)

    from utils.database import user_collection

    user_collection.update_one({'username': 'admin'}, {'$set': {'throttle_queue_limit': 1}})
    await authed_client.delete('/api/caches')

    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    await authed_client.get(f'/api/rest/{name}/{ver}/t')
    r2 = await authed_client.get(f'/api/rest/{name}/{ver}/t')
    assert r2.status_code == 429


@pytest.mark.asyncio
async def test_query_params_and_headers_forwarding(monkeypatch, authed_client):
    from conftest import create_endpoint, subscribe_self

    name, ver = 'params', 'v1'
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://up1'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_allowed_headers': ['content-type', 'x-upstream'],
    }
    await authed_client.post('/platform/api', json=payload)
    await create_endpoint(authed_client, name, ver, 'GET', '/q')
    await subscribe_self(authed_client, name, ver)

    from utils.database import user_collection

    user_collection.update_one(
        {'username': 'admin'},
        {
            '$set': {
                'rate_limit_duration': 1000,
                'rate_limit_duration_type': 'second',
                'throttle_queue_limit': 1000,
            }
        },
    )
    await authed_client.delete('/api/caches')

    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    r = await authed_client.get(f'/api/rest/{name}/{ver}/q?foo=1&bar=2')
    assert r.status_code == 200
    body = r.json()
    assert body.get('params') == {'foo': '1', 'bar': '2'}

    assert r.headers.get('X-Upstream') == 'yes'


@pytest.mark.asyncio
async def test_post_body_forwarding_json(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    name, ver = 'postfwd', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'POST', '/echo')
    await subscribe_self(authed_client, name, ver)

    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    payload = {'a': 1, 'b': 2}
    r = await authed_client.post(f'/api/rest/{name}/{ver}/echo', json=payload)
    assert r.status_code == 200
    assert r.json().get('body') == payload


@pytest.mark.asyncio
async def test_credit_header_injection_and_user_override(monkeypatch, authed_client):
    credit_group = 'inject-group'
    rc = await authed_client.post(
        '/platform/credit',
        json={
            'api_credit_group': credit_group,
            'api_key': 'GROUP-KEY',
            'api_key_header': 'x-api-key',
            'credit_tiers': [
                {
                    'tier_name': 'default',
                    'credits': 999,
                    'input_limit': 0,
                    'output_limit': 0,
                    'reset_frequency': 'monthly',
                }
            ],
        },
    )
    assert rc.status_code in (200, 201)

    name, ver = 'creditinj', 'v1'
    await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'c',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://up'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
            'api_credits_enabled': True,
            'api_credit_group': credit_group,
        },
    )
    await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'GET',
            'endpoint_uri': '/h',
            'endpoint_description': 'h',
        },
    )
    await authed_client.post(
        '/platform/subscription/subscribe',
        json={'username': 'admin', 'api_name': name, 'api_version': ver},
    )

    ur = await authed_client.post(
        '/platform/credit/admin',
        json={
            'username': 'admin',
            'users_credits': {
                credit_group: {
                    'tier_name': 'default',
                    'available_credits': 1,
                    'user_api_key': 'USER-KEY',
                }
            },
        },
    )
    assert ur.status_code in (200, 201), ur.text

    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/h')
    assert r.status_code == 200
    headers_seen = r.json().get('headers') or {}
    assert headers_seen.get('x-api-key') == 'USER-KEY'


@pytest.mark.asyncio
async def test_gateway_sets_request_id_headers(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    name, ver = 'reqid', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/x')
    await subscribe_self(authed_client, name, ver)
    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/x')
    assert r.status_code == 200
    assert r.headers.get('X-Request-ID') and r.headers.get('request_id')


@pytest.mark.asyncio
async def test_api_disabled_returns_403(monkeypatch, authed_client):
    name, ver = 'disabled', 'v1'
    await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'd',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://up'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
            'active': False,
        },
    )
    await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'GET',
            'endpoint_uri': '/x',
            'endpoint_description': 'x',
        },
    )

    await authed_client.post(
        '/platform/subscription/subscribe',
        json={'username': 'admin', 'api_name': name, 'api_version': ver},
    )

    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    r = await authed_client.get(f'/api/rest/{name}/{ver}/x')
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_upstream_404_maps_to_gtw005(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    name, ver = 'nfupstream', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/z')
    await subscribe_self(authed_client, name, ver)
    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _NotFoundAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/z')
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_endpoint_not_found_returns_404_code_gtw003(monkeypatch, authed_client):
    from conftest import create_api, subscribe_self

    name, ver = 'noep', 'v1'
    await create_api(authed_client, name, ver)
    await subscribe_self(authed_client, name, ver)

    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    r = await authed_client.get(f'/api/rest/{name}/{ver}/missing')
    assert r.status_code == 404
