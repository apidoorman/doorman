import pytest

@pytest.mark.asyncio
async def test_rest_loose_envelope_returns_raw_message(monkeypatch, authed_client):
    name, ver = 'envrest', 'v1'
    await authed_client.post('/platform/api', json={
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://up'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_public': True,
    })
    await authed_client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': 'GET',
        'endpoint_uri': '/e',
        'endpoint_description': 'e'
    })
    import services.gateway_service as gs
    from tests.test_gateway_routing_limits import _FakeAsyncClient
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    monkeypatch.delenv('STRICT_RESPONSE_ENVELOPE', raising=False)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/e')
    assert r.status_code == 200
    body = r.json()
    assert 'status_code' not in body and body.get('method') == 'GET'

@pytest.mark.asyncio
async def test_rest_strict_envelope_wraps_message(monkeypatch, authed_client):
    monkeypatch.setenv('STRICT_RESPONSE_ENVELOPE', 'true')
    name, ver = 'envrest2', 'v1'
    await authed_client.post('/platform/api', json={
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://up'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_public': True,
    })
    await authed_client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': 'GET',
        'endpoint_uri': '/e',
        'endpoint_description': 'e'
    })
    import services.gateway_service as gs
    from tests.test_gateway_routing_limits import _FakeAsyncClient
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/e')
    assert r.status_code == 200
    body = r.json()
    assert body.get('status_code') == 200
    assert isinstance(body.get('response'), dict)
    assert body['response'].get('method') == 'GET'

async def _setup_graphql(client, name='envgql', ver='v1'):
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://gql.up'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    }
    await client.post('/platform/api', json=payload)
    await client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': 'POST',
        'endpoint_uri': '/graphql',
        'endpoint_description': 'gql',
    })
    from conftest import subscribe_self
    await subscribe_self(client, name, ver)
    return name, ver

@pytest.mark.asyncio
async def test_graphql_strict_and_loose_envelopes(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'envgql', 'v1'
    await authed_client.post('/platform/api', json={
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://gql.up'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_public': True,
    })
    await authed_client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': 'POST',
        'endpoint_uri': '/graphql',
        'endpoint_description': 'gql'
    })

    class FakeHTTPResp:
        def __init__(self, payload):
            self._p = payload
        def json(self):
            return self._p
    class FakeHTTPX:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def post(self, url, json=None, headers=None):
            return FakeHTTPResp({'data': {'pong': True}})
    # Force HTTPX path
    class Dummy:
        pass
    monkeypatch.setattr(gs, 'Client', Dummy)
    monkeypatch.setattr(gs.httpx, 'AsyncClient', FakeHTTPX)

    monkeypatch.delenv('STRICT_RESPONSE_ENVELOPE', raising=False)
    r1 = await authed_client.post(f'/api/graphql/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'query': '{ q }', 'variables': {}})
    assert r1.status_code == 200
    assert 'status_code' not in r1.json()

    monkeypatch.setenv('STRICT_RESPONSE_ENVELOPE', 'true')
    r2 = await authed_client.post(f'/api/graphql/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'query': '{ q }', 'variables': {}})
    assert r2.status_code == 200
    assert r2.json().get('status_code') == 200 and isinstance(r2.json().get('response'), dict)

@pytest.mark.asyncio
async def test_grpc_strict_and_loose_envelopes(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'envgrpc', 'v1'
    await authed_client.post('/platform/api', json={
        'api_name': name,
        'api_version': ver,
        'api_description': 'g',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['grpc://127.0.0.1:9'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    })
    await authed_client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': 'POST',
        'endpoint_uri': '/grpc',
        'endpoint_description': 'grpc'
    })
    from conftest import subscribe_self
    await subscribe_self(authed_client, name, ver)

    async def fake_grpc_gateway(username, request, request_id, start_time, path, api_name=None, url=None, retry=0):
        from models.response_model import ResponseModel
        return ResponseModel(status_code=200, response_headers={'request_id': request_id}, response={'ok': True}).dict()
    monkeypatch.setattr(gs.GatewayService, 'grpc_gateway', staticmethod(fake_grpc_gateway))

    monkeypatch.delenv('STRICT_RESPONSE_ENVELOPE', raising=False)
    r1 = await authed_client.post(f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}})
    assert r1.status_code == 200
    assert r1.json() == {'ok': True}

    monkeypatch.setenv('STRICT_RESPONSE_ENVELOPE', 'true')
    r2 = await authed_client.post(f'/api/grpc/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'method': 'Svc.M', 'message': {}})
    assert r2.status_code == 200
    assert r2.json().get('status_code') == 200 and r2.json().get('response', {}).get('ok') is True

@pytest.mark.asyncio
async def test_header_normalization_sets_x_request_id_from_request_id(monkeypatch, authed_client):
    name, ver = 'hdrnorm', 'v1'
    await authed_client.post('/platform/api', json={
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://up'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_public': True,
    })
    await authed_client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': 'GET',
        'endpoint_uri': '/h',
        'endpoint_description': 'h'
    })
    import services.gateway_service as gs
    from tests.test_gateway_routing_limits import _FakeAsyncClient
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/h')
    assert r.status_code == 200
    assert r.headers.get('X-Request-ID')

@pytest.mark.asyncio
async def test_header_normalization_preserves_existing_x_request_id(monkeypatch, authed_client):
    name, ver = 'hdrnorm2', 'v1'
    await authed_client.post('/platform/api', json={
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://up'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_public': True,
    })
    await authed_client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': 'GET',
        'endpoint_uri': '/h',
        'endpoint_description': 'h'
    })
    import services.gateway_service as gs
    from tests.test_gateway_routing_limits import _FakeAsyncClient
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/h', headers={'X-Request-ID': 'my-req-id'})
    assert r.status_code == 200
    assert r.headers.get('X-Request-ID')
