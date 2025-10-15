import json as _json
from types import SimpleNamespace
import pytest

class _FakeHTTPResponse:
    def __init__(self, status_code=200, json_body=None, text_body=None, headers=None):
        self.status_code = status_code
        self._json_body = json_body
        self.text = text_body if text_body is not None else ('' if json_body is not None else 'OK')
        self.headers = headers or {'Content-Type': 'application/json' if json_body is not None else 'text/plain'}

    def json(self):
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
        return _FakeHTTPResponse(200, json_body={'method': 'GET', 'url': url, 'params': params or {}, 'ok': True})

    async def post(self, url, json=None, params=None, headers=None, content=None, **kwargs):
        body = json if json is not None else (content.decode('utf-8') if isinstance(content, (bytes, bytearray)) else content)
        return _FakeHTTPResponse(200, json_body={'method': 'POST', 'url': url, 'body': body, 'ok': True})

    async def put(self, url, json=None, params=None, headers=None, content=None, **kwargs):
        body = json if json is not None else (content.decode('utf-8') if isinstance(content, (bytes, bytearray)) else content)
        return _FakeHTTPResponse(200, json_body={'method': 'PUT', 'url': url, 'body': body, 'ok': True})

    async def delete(self, url, json=None, params=None, headers=None, content=None, **kwargs):
        return _FakeHTTPResponse(200, json_body={'method': 'DELETE', 'url': url, 'ok': True})

@pytest.mark.asyncio
async def test_gateway_rest_happy_path(monkeypatch, authed_client):

    api_payload = {
        'api_name': 'echo',
        'api_version': 'v1',
        'api_description': 'Echo API',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://fake-upstream'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    }
    c = await authed_client.post('/platform/api', json=api_payload)
    assert c.status_code in (200, 201)

    ep = await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': 'echo',
            'api_version': 'v1',
            'endpoint_method': 'GET',
            'endpoint_uri': '/hello',
            'endpoint_description': 'Echo hello',
            'endpoint_servers': ['http://fake-upstream'],
        },
    )
    assert ep.status_code in (200, 201)

    sub = await authed_client.post(
        '/platform/subscription/subscribe',
        json={'username': 'admin', 'api_name': 'echo', 'api_version': 'v1'},
    )
    assert sub.status_code in (200, 201)

    import services.gateway_service as gs

    import routes.gateway_routes as gr
    async def _no_limit(request):
        return None
    monkeypatch.setattr(gr, 'limit_and_throttle', _no_limit)
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    gw = await authed_client.get('/api/rest/echo/v1/hello')
    assert gw.status_code == 200
    data = gw.json()
    assert data.get('ok') is True

@pytest.mark.asyncio
async def test_gateway_clear_caches(authed_client):
    r = await authed_client.delete('/api/caches')
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_gateway_graphql_grpc_soap(monkeypatch, authed_client):

    for name in ('graph', 'grpcapi', 'soapapi'):
        c = await authed_client.post(
            '/platform/api',
            json={
                'api_name': name,
                'api_version': 'v1',
                'api_description': f'{name} API',
                'api_allowed_roles': ['admin'],
                'api_allowed_groups': ['ALL'],
                'api_servers': ['http://fake-upstream'],
                'api_type': 'REST',
                'api_allowed_retry_count': 0,
            },
        )
        assert c.status_code in (200, 201)
        s = await authed_client.post(
            '/platform/subscription/subscribe',
            json={'username': 'admin', 'api_name': name, 'api_version': 'v1'},
        )
        assert s.status_code in (200, 201)

    missing = await authed_client.post('/api/graphql/graph', json={'query': '{ping}'})
    assert missing.status_code == 400

    import services.gateway_service as gs
    import routes.gateway_routes as gr
    async def _no_limit2(request):
        return None
    monkeypatch.setattr(gr, 'limit_and_throttle', _no_limit2)

    async def fake_graphql_gateway(username, request, request_id, start_time, path):
        from models.response_model import ResponseModel
        return ResponseModel(status_code=200, response={'data': {'ping': 'pong'}}).dict()

    async def fake_grpc_gateway(username, request, request_id, start_time, path):
        from models.response_model import ResponseModel
        return ResponseModel(status_code=200, response={'ok': True}).dict()

    async def fake_soap_gateway(username, request, request_id, start_time, path):
        from models.response_model import ResponseModel
        return ResponseModel(status_code=200, response='<ok>true</ok>').dict()

    monkeypatch.setattr(gs.GatewayService, 'graphql_gateway', staticmethod(fake_graphql_gateway))
    monkeypatch.setattr(gs.GatewayService, 'grpc_gateway', staticmethod(fake_grpc_gateway))
    monkeypatch.setattr(gs.GatewayService, 'soap_gateway', staticmethod(fake_soap_gateway))

    async def _pass_sub(req):
        return {'sub': 'admin'}
    async def _pass_group(req: object, full_path: str = None, user_to_subscribe=None):
        return {'sub': 'admin'}
    monkeypatch.setattr(gr, 'subscription_required', _pass_sub)
    monkeypatch.setattr(gr, 'group_required', _pass_group)

    g = await authed_client.post(
        '/api/graphql/graph',
        headers={'X-API-Version': 'v1'},
        json={'query': '{ ping }'},
    )
    assert g.status_code == 200

    gr = await authed_client.post(
        '/api/grpc/grpcapi', headers={'X-API-Version': 'v1'}, json={'data': '{}'}
    )
    assert gr.status_code == 200

    sp = await authed_client.post('/api/soap/soapapi/v1/ping', content=b'<xml/>')
    assert sp.status_code == 200
