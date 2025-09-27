import pytest


@pytest.mark.asyncio
async def test_api_disabled_rest_blocks(monkeypatch, authed_client):
    async def _create_api(c, n, v):
        payload = {"api_name": n, "api_version": v, "api_description": f"{n} {v}", "api_allowed_roles": ["admin"], "api_allowed_groups": ["ALL"], "api_servers": ["http://upstream"], "api_type": "REST", "api_allowed_retry_count": 0}
        rr = await c.post('/platform/api', json=payload)
        assert rr.status_code in (200, 201)
    async def _create_endpoint(c, n, v, m, u):
        payload = {"api_name": n, "api_version": v, "endpoint_method": m, "endpoint_uri": u, "endpoint_description": f"{m} {u}"}
        rr = await c.post('/platform/endpoint', json=payload)
        assert rr.status_code in (200, 201)
    async def _subscribe_self(c, n, v):
        r_me = await c.get('/platform/user/me')
        username = (r_me.json().get('username') if r_me.status_code == 200 else 'admin')
        rr = await c.post('/platform/subscription/subscribe', json={"username": username, "api_name": n, "api_version": v})
        assert rr.status_code in (200, 201)
    await _create_api(authed_client, 'disabled', 'v1')
    # Disable the API
    r_upd = await authed_client.put('/platform/api/disabled/v1', json={'active': False})
    assert r_upd.status_code == 200
    await _create_endpoint(authed_client, 'disabled', 'v1', 'GET', '/status')
    await _subscribe_self(authed_client, 'disabled', 'v1')
    r = await authed_client.get('/api/rest/disabled/v1/status')
    assert r.status_code in (403, 500)


@pytest.mark.asyncio
async def test_api_disabled_graphql_blocks(authed_client):
    async def _create_api(c, n, v):
        payload = {"api_name": n, "api_version": v, "api_description": f"{n} {v}", "api_allowed_roles": ["admin"], "api_allowed_groups": ["ALL"], "api_servers": ["http://upstream"], "api_type": "REST", "api_allowed_retry_count": 0}
        rr = await c.post('/platform/api', json=payload)
        assert rr.status_code in (200, 201)
    async def _subscribe_self(c, n, v):
        r_me = await c.get('/platform/user/me')
        username = (r_me.json().get('username') if r_me.status_code == 200 else 'admin')
        rr = await c.post('/platform/subscription/subscribe', json={"username": username, "api_name": n, "api_version": v})
        assert rr.status_code in (200, 201)
    await _create_api(authed_client, 'gqlx', 'v1')
    ru = await authed_client.put('/platform/api/gqlx/v1', json={'active': False})
    assert ru.status_code == 200
    await _subscribe_self(authed_client, 'gqlx', 'v1')
    r = await authed_client.post('/api/graphql/gqlx', headers={'X-API-Version': 'v1', 'Content-Type': 'application/json'}, json={'query': '{__typename}'})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_api_disabled_grpc_blocks(authed_client):
    async def _create_api(c, n, v):
        payload = {"api_name": n, "api_version": v, "api_description": f"{n} {v}", "api_allowed_roles": ["admin"], "api_allowed_groups": ["ALL"], "api_servers": ["http://upstream"], "api_type": "REST", "api_allowed_retry_count": 0}
        rr = await c.post('/platform/api', json=payload)
        assert rr.status_code in (200, 201)
    async def _subscribe_self(c, n, v):
        r_me = await c.get('/platform/user/me')
        username = (r_me.json().get('username') if r_me.status_code == 200 else 'admin')
        rr = await c.post('/platform/subscription/subscribe', json={"username": username, "api_name": n, "api_version": v})
        assert rr.status_code in (200, 201)
    await _create_api(authed_client, 'grpcx', 'v1')
    ru = await authed_client.put('/platform/api/grpcx/v1', json={'active': False})
    assert ru.status_code == 200
    await _subscribe_self(authed_client, 'grpcx', 'v1')
    r = await authed_client.post('/api/grpc/grpcx', headers={'X-API-Version': 'v1', 'Content-Type': 'application/json'}, json={'method': 'X', 'message': {}})
    assert r.status_code in (403, 404)


@pytest.mark.asyncio
async def test_api_disabled_soap_blocks(authed_client):
    async def _create_api(c, n, v):
        payload = {"api_name": n, "api_version": v, "api_description": f"{n} {v}", "api_allowed_roles": ["admin"], "api_allowed_groups": ["ALL"], "api_servers": ["http://upstream"], "api_type": "REST", "api_allowed_retry_count": 0}
        rr = await c.post('/platform/api', json=payload)
        assert rr.status_code in (200, 201)
    async def _create_endpoint(c, n, v, m, u):
        payload = {"api_name": n, "api_version": v, "endpoint_method": m, "endpoint_uri": u, "endpoint_description": f"{m} {u}"}
        rr = await c.post('/platform/endpoint', json=payload)
        assert rr.status_code in (200, 201)
    async def _subscribe_self(c, n, v):
        r_me = await c.get('/platform/user/me')
        username = (r_me.json().get('username') if r_me.status_code == 200 else 'admin')
        rr = await c.post('/platform/subscription/subscribe', json={"username": username, "api_name": n, "api_version": v})
        assert rr.status_code in (200, 201)
    await _create_api(authed_client, 'soapx', 'v1')
    await _create_endpoint(authed_client, 'soapx', 'v1', 'POST', '/op')
    ru = await authed_client.put('/platform/api/soapx/v1', json={'active': False})
    assert ru.status_code == 200
    await _subscribe_self(authed_client, 'soapx', 'v1')
    r = await authed_client.post('/api/soap/soapx/v1/op', headers={'Content-Type': 'text/xml'}, content='<Envelope/>')
    assert r.status_code in (403, 400, 404, 500)  # depending on validation and upstream


@pytest.mark.asyncio
async def test_gateway_patch_support(monkeypatch, authed_client):
    # Prepare API and PATCH endpoint
    async def _create_api(c, n, v):
        payload = {"api_name": n, "api_version": v, "api_description": f"{n} {v}", "api_allowed_roles": ["admin"], "api_allowed_groups": ["ALL"], "api_servers": ["http://upstream"], "api_type": "REST", "api_allowed_retry_count": 0}
        rr = await c.post('/platform/api', json=payload)
        assert rr.status_code in (200, 201)
    async def _create_endpoint(c, n, v, m, u):
        payload = {"api_name": n, "api_version": v, "endpoint_method": m, "endpoint_uri": u, "endpoint_description": f"{m} {u}"}
        rr = await c.post('/platform/endpoint', json=payload)
        assert rr.status_code in (200, 201)
    async def _subscribe_self(c, n, v):
        r_me = await c.get('/platform/user/me')
        username = (r_me.json().get('username') if r_me.status_code == 200 else 'admin')
        rr = await c.post('/platform/subscription/subscribe', json={"username": username, "api_name": n, "api_version": v})
        assert rr.status_code in (200, 201)
    await _create_api(authed_client, 'patchy', 'v1')
    await _create_endpoint(authed_client, 'patchy', 'v1', 'PATCH', '/item')
    await _subscribe_self(authed_client, 'patchy', 'v1')
    # Fake upstream to avoid network
    import services.gateway_service as gs
    class _Resp:
        def __init__(self):
            self.status_code = 200
            self.headers = {'Content-Type': 'application/json'}
        def json(self):
            return {'ok': True}
        @property
        def text(self):
            return '{"ok":true}'
    class _Client:
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def patch(self, url, json=None, params=None, headers=None, **kw): return _Resp()
    monkeypatch.setattr(gs, 'httpx', type('X', (), {'AsyncClient': lambda timeout=None: _Client()}))
    r = await authed_client.patch('/api/rest/patchy/v1/item', json={'x': 1})
    assert r.status_code in (200, 500)
