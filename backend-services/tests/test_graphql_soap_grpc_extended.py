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
        self.content = self.text.encode('utf-8')

    def json(self):
        import json as _json

        if self._json_body is None:
            return _json.loads(self.text or '{}')
        return self._json_body


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
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
            return _FakeHTTPResponse(405, json_body={'error': 'Method not allowed'})

    async def get(self, url, params=None, headers=None, **kwargs):
        return _FakeHTTPResponse(
            200, json_body={'ok': True, 'url': url}, headers={'X-Upstream': 'yes'}
        )

    async def post(self, url, json=None, params=None, headers=None, content=None, **kwargs):
        body = (
            json
            if json is not None
            else (content.decode('utf-8') if isinstance(content, (bytes, bytearray)) else content)
        )
        return _FakeHTTPResponse(
            200, json_body={'ok': True, 'url': url, 'body': body}, headers={'X-Upstream': 'yes'}
        )

    async def put(self, url, json=None, params=None, headers=None, content=None, **kwargs):
        body = (
            json
            if json is not None
            else (content.decode('utf-8') if isinstance(content, (bytes, bytearray)) else content)
        )
        return _FakeHTTPResponse(
            200, json_body={'ok': True, 'url': url, 'body': body}, headers={'X-Upstream': 'yes'}
        )

    async def delete(self, url, **kwargs):
        return _FakeHTTPResponse(200, json_body={'ok': True}, headers={'X-Upstream': 'yes'})


class _NotFoundAsyncClient(_FakeAsyncClient):
    async def post(self, url, json=None, params=None, headers=None, content=None, **kwargs):
        return _FakeHTTPResponse(404, json_body={'ok': False}, headers={'X-Upstream': 'no'})


@pytest.mark.asyncio
async def test_grpc_missing_version_header_returns_400(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    name, ver = 'grpcver', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'POST', '/grpc')
    await subscribe_self(authed_client, name, ver)
    r = await authed_client.post(f'/api/grpc/{name}', json={'method': 'Svc.M', 'message': {}})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_graphql_lowercase_version_header_works(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    name, ver = 'gqllower', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'POST', '/graphql')
    await subscribe_self(authed_client, name, ver)

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, *args, **kwargs):
            return {'ping': 'pong'}

    class FakeClient:
        def __init__(self, transport=None, fetch_schema_from_transport=False):
            pass

        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    import services.gateway_service as gw

    monkeypatch.setattr(gw, 'Client', FakeClient)

    r = await authed_client.post(
        f'/api/graphql/{name}',
        headers={'x-api-version': ver, 'Content-Type': 'application/json'},
        json={'query': '{ __typename }'},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_soap_text_xml_validation_allows_good_request(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    name, ver = 'soaptext', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'POST', '/call')
    await subscribe_self(authed_client, name, ver)

    g = await authed_client.get(f'/platform/endpoint/POST/{name}/{ver}/call')
    eid = g.json().get('endpoint_id') or g.json().get('response', {}).get('endpoint_id')

    schema = {'validation_schema': {'name': {'required': True, 'type': 'string', 'min': 2}}}
    await authed_client.post(
        '/platform/endpoint/endpoint/validation',
        json={'endpoint_id': eid, 'validation_enabled': True, 'validation_schema': schema},
    )

    envelope = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
        '<soapenv:Body>'
        '<Request><name>Ab</name></Request>'
        '</soapenv:Body>'
        '</soapenv:Envelope>'
    )

    class _FakeXMLResponse:
        def __init__(self):
            self.status_code = 200
            self.headers = {'Content-Type': 'text/xml'}
            self.text = '<ok/>'
            self.content = self.text.encode('utf-8')

    class _FakeXMLClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, content=None, params=None, headers=None):
            return _FakeXMLResponse()

    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeXMLClient)
    r = await authed_client.post(
        f'/api/soap/{name}/{ver}/call', headers={'Content-Type': 'text/xml'}, content=envelope
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_soap_upstream_404_maps_to_404(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    name, ver = 'soap404', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'POST', '/call')
    await subscribe_self(authed_client, name, ver)
    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _NotFoundAsyncClient)
    r = await authed_client.post(
        f'/api/soap/{name}/{ver}/call',
        headers={'Content-Type': 'application/xml'},
        content='<Request/>',
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_grpc_upstream_404_maps_to_404(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    name, ver = 'grpc404', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'POST', '/grpc')
    await subscribe_self(authed_client, name, ver)
    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _NotFoundAsyncClient)
    r = await authed_client.post(
        f'/api/grpc/{name}',
        headers={'X-API-Version': ver, 'Content-Type': 'application/json'},
        json={'method': 'Svc.Method', 'message': {}},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_grpc_subscription_required(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint

    name, ver = 'grpcsub', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'POST', '/grpc')
    import services.gateway_service as gs

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.post(
        f'/api/grpc/{name}',
        headers={'X-API-Version': ver, 'Content-Type': 'application/json'},
        json={'method': 'Svc.Method', 'message': {}},
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_graphql_group_enforcement(monkeypatch, authed_client):
    name, ver = 'gqlgrp', 'v1'
    await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'gql',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['vip-only'],
            'api_servers': ['http://up'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
        },
    )
    await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'POST',
            'endpoint_uri': '/graphql',
            'endpoint_description': 'gql',
        },
    )

    import routes.gateway_routes as gr

    async def _pass_sub(req):
        return {'sub': 'admin'}

    monkeypatch.setattr(gr, 'subscription_required', _pass_sub)

    await authed_client.delete('/api/caches')

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, *args, **kwargs):
            return {'ok': True}

    class FakeClient:
        def __init__(self, transport=None, fetch_schema_from_transport=False):
            pass

        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    import services.gateway_service as gw

    monkeypatch.setattr(gw, 'Client', FakeClient)

    r = await authed_client.post(
        f'/api/graphql/{name}',
        headers={'X-API-Version': ver, 'Content-Type': 'application/json'},
        json={'query': '{ __typename }'},
    )
    assert r.status_code == 401
