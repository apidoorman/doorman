import pytest


@pytest.mark.asyncio
async def test_rest_payload_validation_blocks_bad_request(authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    api_name = 'valrest'
    version = 'v1'
    await create_api(authed_client, api_name, version)
    await create_endpoint(authed_client, api_name, version, 'POST', '/do')
    await subscribe_self(authed_client, api_name, version)

    g = await authed_client.get(f'/platform/endpoint/POST/{api_name}/{version}/do')
    assert g.status_code == 200
    eid = g.json().get('endpoint_id') or g.json().get('response', {}).get('endpoint_id')
    assert eid

    schema = {
        'validation_schema': {
            'user.name': {'required': True, 'type': 'string', 'min': 2, 'max': 50}
        }
    }
    cv = await authed_client.post(
        '/platform/endpoint/endpoint/validation',
        json={'endpoint_id': eid, 'validation_enabled': True, 'validation_schema': schema},
    )
    assert cv.status_code in (200, 201, 400)

    r = await authed_client.post(f'/api/rest/{api_name}/{version}/do', json={'user': {'name': 'A'}})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_graphql_payload_validation_blocks_bad_request(authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    api_name = 'valgql'
    version = 'v1'
    await create_api(authed_client, api_name, version)

    await create_endpoint(authed_client, api_name, version, 'POST', '/graphql')
    await subscribe_self(authed_client, api_name, version)

    g = await authed_client.get(f'/platform/endpoint/POST/{api_name}/{version}/graphql')
    assert g.status_code == 200
    eid = g.json().get('endpoint_id') or g.json().get('response', {}).get('endpoint_id')
    assert eid

    schema = {
        'validation_schema': {
            'CreateUser.input.name': {'required': True, 'type': 'string', 'min': 2, 'max': 50}
        }
    }
    cv = await authed_client.post(
        '/platform/endpoint/endpoint/validation',
        json={'endpoint_id': eid, 'validation_enabled': True, 'validation_schema': schema},
    )
    assert cv.status_code in (200, 201, 400)

    query = 'mutation CreateUser($input: UserInput!){ createUser(input: $input){ id } }'
    variables = {'input': {'name': 'A'}}
    r = await authed_client.post(
        f'/api/graphql/{api_name}',
        headers={'X-API-Version': version, 'Content-Type': 'application/json'},
        json={'query': query, 'variables': variables},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_soap_payload_validation_blocks_bad_request(authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    api_name = 'valsoap'
    version = 'v1'
    await create_api(authed_client, api_name, version)
    await create_endpoint(authed_client, api_name, version, 'POST', '/call')
    await subscribe_self(authed_client, api_name, version)

    g = await authed_client.get(f'/platform/endpoint/POST/{api_name}/{version}/call')
    assert g.status_code == 200
    eid = g.json().get('endpoint_id') or g.json().get('response', {}).get('endpoint_id')
    assert eid

    schema = {
        'validation_schema': {
            'Request.name': {'required': True, 'type': 'string', 'min': 2, 'max': 50}
        }
    }
    cv = await authed_client.post(
        '/platform/endpoint/endpoint/validation',
        json={'endpoint_id': eid, 'validation_enabled': True, 'validation_schema': schema},
    )
    assert cv.status_code in (200, 201, 400)

    envelope = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
        '<soapenv:Body>'
        '<Request><name>A</name></Request>'
        '</soapenv:Body>'
        '</soapenv:Envelope>'
    )
    r = await authed_client.post(
        f'/api/soap/{api_name}/{version}/call',
        headers={'Content-Type': 'application/xml'},
        content=envelope,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_grpc_payload_validation_blocks_bad_request(authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    api_name = 'valgrpc'
    version = 'v1'
    await create_api(authed_client, api_name, version)
    await create_endpoint(authed_client, api_name, version, 'POST', '/grpc')
    await subscribe_self(authed_client, api_name, version)

    g = await authed_client.get(f'/platform/endpoint/POST/{api_name}/{version}/grpc')
    assert g.status_code == 200
    eid = g.json().get('endpoint_id') or g.json().get('response', {}).get('endpoint_id')
    assert eid

    schema = {
        'validation_schema': {
            'user.name': {'required': True, 'type': 'string', 'min': 2, 'max': 50}
        }
    }
    cv = await authed_client.post(
        '/platform/endpoint/endpoint/validation',
        json={'endpoint_id': eid, 'validation_enabled': True, 'validation_schema': schema},
    )
    assert cv.status_code in (200, 201, 400)

    payload = {'method': 'Service.Method', 'message': {'user': {'name': 'A'}}}
    r = await authed_client.post(
        f'/api/grpc/{api_name}',
        headers={'X-API-Version': version, 'Content-Type': 'application/json'},
        json=payload,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_rest_payload_validation_allows_good_request(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    api_name = 'okrest'
    version = 'v1'
    await create_api(authed_client, api_name, version)
    await create_endpoint(authed_client, api_name, version, 'POST', '/do')
    await subscribe_self(authed_client, api_name, version)

    g = await authed_client.get(f'/platform/endpoint/POST/{api_name}/{version}/do')
    eid = g.json().get('endpoint_id') or g.json().get('response', {}).get('endpoint_id')
    schema = {'validation_schema': {'user.name': {'required': True, 'type': 'string', 'min': 2}}}
    await authed_client.post(
        '/platform/endpoint/endpoint/validation',
        json={'endpoint_id': eid, 'validation_enabled': True, 'validation_schema': schema},
    )

    class FakeResp:
        def __init__(self):
            self.status_code = 200
            self.headers = {'Content-Type': 'application/json'}
            self._json = {'ok': True}
            self.text = '{}'

        def json(self):
            return self._json

    class FakeClient:
        def __init__(self, timeout=None, limits=None, http2=False):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json=None, params=None, headers=None):
            return FakeResp()

    import services.gateway_service as gw

    monkeypatch.setattr(gw.httpx, 'AsyncClient', FakeClient)

    r = await authed_client.post(
        f'/api/rest/{api_name}/{version}/do', json={'user': {'name': 'Ab'}}
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_soap_payload_validation_allows_good_request(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    api_name = 'oksoap'
    version = 'v1'
    await create_api(authed_client, api_name, version)
    await create_endpoint(authed_client, api_name, version, 'POST', '/call')
    await subscribe_self(authed_client, api_name, version)

    g = await authed_client.get(f'/platform/endpoint/POST/{api_name}/{version}/call')
    eid = g.json().get('endpoint_id') or g.json().get('response', {}).get('endpoint_id')
    schema = {'validation_schema': {'name': {'required': True, 'type': 'string', 'min': 2}}}
    await authed_client.post(
        '/platform/endpoint/endpoint/validation',
        json={'endpoint_id': eid, 'validation_enabled': True, 'validation_schema': schema},
    )

    class FakeResp:
        def __init__(self):
            self.status_code = 200
            self.headers = {'Content-Type': 'text/xml'}
            self.text = '<ok/>'

    class FakeClient:
        def __init__(self, timeout=None, limits=None, http2=False):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, content=None, params=None, headers=None):
            return FakeResp()

    import services.gateway_service as gw

    monkeypatch.setattr(gw.httpx, 'AsyncClient', FakeClient)

    envelope = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
        '<soapenv:Body>'
        '<Request><name>Ab</name></Request>'
        '</soapenv:Body>'
        '</soapenv:Envelope>'
    )
    r = await authed_client.post(
        f'/api/soap/{api_name}/{version}/call',
        headers={'Content-Type': 'application/xml'},
        content=envelope,
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_graphql_payload_validation_allows_good_request(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    api_name = 'okgql'
    version = 'v1'
    await create_api(authed_client, api_name, version)
    await create_endpoint(authed_client, api_name, version, 'POST', '/graphql')
    await subscribe_self(authed_client, api_name, version)

    g = await authed_client.get(f'/platform/endpoint/POST/{api_name}/{version}/graphql')
    eid = g.json().get('endpoint_id') or g.json().get('response', {}).get('endpoint_id')
    schema = {
        'validation_schema': {
            'CreateUser.input.name': {'required': True, 'type': 'string', 'min': 2}
        }
    }
    await authed_client.post(
        '/platform/endpoint/endpoint/validation',
        json={'endpoint_id': eid, 'validation_enabled': True, 'validation_schema': schema},
    )

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

    query = 'mutation CreateUser($input: UserInput!){ createUser(input: $input){ id } }'
    variables = {'input': {'name': 'Ab'}}
    r = await authed_client.post(
        f'/api/graphql/{api_name}',
        headers={'X-API-Version': version, 'Content-Type': 'application/json'},
        json={'query': query, 'variables': variables},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_grpc_payload_validation_allows_good_request_progresses(
    monkeypatch, authed_client, tmp_path
):
    from conftest import create_api, create_endpoint, subscribe_self

    api_name = 'okgrpc'
    version = 'v1'
    await create_api(authed_client, api_name, version)
    await create_endpoint(authed_client, api_name, version, 'POST', '/grpc')
    await subscribe_self(authed_client, api_name, version)

    g = await authed_client.get(f'/platform/endpoint/POST/{api_name}/{version}/grpc')
    eid = g.json().get('endpoint_id') or g.json().get('response', {}).get('endpoint_id')
    schema = {'validation_schema': {'user.name': {'required': True, 'type': 'string', 'min': 2}}}
    await authed_client.post(
        '/platform/endpoint/endpoint/validation',
        json={'endpoint_id': eid, 'validation_enabled': True, 'validation_schema': schema},
    )

    import os as _os

    import services.gateway_service as gw

    project_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    proto_dir = _os.path.join(project_root, 'proto')
    _os.makedirs(proto_dir, exist_ok=True)
    with open(_os.path.join(proto_dir, f'{api_name}_{version}.proto'), 'w') as f:
        f.write("syntax = 'proto3'; message Dummy {}")

    def fake_import(name):
        raise ImportError('fake')

    monkeypatch.setattr(
        gw.importlib, 'import_module', lambda n: (_ for _ in ()).throw(ImportError('fake'))
    )

    payload = {'method': 'Service.Method', 'message': {'user': {'name': 'Ab'}}}
    r = await authed_client.post(
        f'/api/grpc/{api_name}',
        headers={'X-API-Version': version, 'Content-Type': 'application/json'},
        json=payload,
    )

    assert r.status_code in (404, 500)
