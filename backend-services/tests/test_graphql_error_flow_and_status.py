import pytest

async def _setup_graphql_api(client, name='geflow', ver='v1'):
    await client.post('/platform/api', json={
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
    await client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': 'POST',
        'endpoint_uri': '/graphql',
        'endpoint_description': 'gql'
    })
    return name, ver

@pytest.mark.asyncio
async def test_graphql_upstream_error_returns_errors_array_200(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = await _setup_graphql_api(authed_client, name='ge1', ver='v1')

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
            return FakeHTTPResp({'errors': [{'message': 'upstream boom'}]})
    class Dummy:
        pass
    monkeypatch.setattr(gs, 'Client', Dummy)
    monkeypatch.setattr(gs.httpx, 'AsyncClient', FakeHTTPX)

    r = await authed_client.post(f'/api/graphql/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'query': '{ q }', 'variables': {}})
    assert r.status_code == 200
    assert isinstance(r.json().get('errors'), list)

@pytest.mark.asyncio
async def test_graphql_upstream_http_error_maps_to_errors_with_status(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = await _setup_graphql_api(authed_client, name='ge2', ver='v1')

    class FakeHTTPResp:
        def __init__(self, payload, status):
            self._p = payload
            self.status_code = status
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
            return FakeHTTPResp({'errors': [{'message': 'http fail', 'status': 500}]}, 500)
    class Dummy:
        pass
    monkeypatch.setattr(gs, 'Client', Dummy)
    monkeypatch.setattr(gs.httpx, 'AsyncClient', FakeHTTPX)

    r = await authed_client.post(f'/api/graphql/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'query': '{ q }', 'variables': {}})
    assert r.status_code == 200
    errs = r.json().get('errors')
    assert isinstance(errs, list) and errs[0].get('status') == 500

@pytest.mark.asyncio
async def test_graphql_strict_envelope_contains_status_code_field(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = await _setup_graphql_api(authed_client, name='ge3', ver='v1')

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
            return FakeHTTPResp({'data': {'ok': True}})
    class Dummy:
        pass
    monkeypatch.setattr(gs, 'Client', Dummy)
    monkeypatch.setattr(gs.httpx, 'AsyncClient', FakeHTTPX)
    monkeypatch.setenv('STRICT_RESPONSE_ENVELOPE', 'true')

    r = await authed_client.post(f'/api/graphql/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'query': '{ strict }', 'variables': {}})
    assert r.status_code == 200
    body = r.json()
    assert body.get('status_code') == 200 and isinstance(body.get('response'), dict)

