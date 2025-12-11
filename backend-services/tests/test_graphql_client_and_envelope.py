import pytest


async def _setup_graphql(client, name, ver, allowed_headers=None):
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
    if allowed_headers is not None:
        payload['api_allowed_headers'] = allowed_headers
    r = await client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201)
    r2 = await client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'POST',
            'endpoint_uri': '/graphql',
            'endpoint_description': 'graphql',
        },
    )
    assert r2.status_code in (200, 201)
    from conftest import subscribe_self

    await subscribe_self(client, name, ver)


@pytest.mark.asyncio
async def test_graphql_uses_gql_client_when_available(monkeypatch, authed_client):
    import services.gateway_service as gs

    name, ver = 'gqlclient', 'v1'
    await _setup_graphql(authed_client, name, ver)

    calls = {}

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def execute(self, query, variable_values=None):
            calls['query'] = query
            calls['vars'] = variable_values
            return {'ok': True, 'from': 'client'}

    class FakeClient:
        def __init__(self, transport=None, fetch_schema_from_transport=False):
            pass

        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(gs, 'Client', FakeClient)
    r = await authed_client.post(
        f'/api/graphql/{name}',
        headers={'X-API-Version': ver, 'Content-Type': 'application/json'},
        json={'query': '{ ping }', 'variables': {'a': 1}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get('ok') is True and body.get('from') == 'client'
    assert calls.get('vars') == {'a': 1}


@pytest.mark.asyncio
async def test_graphql_fallback_to_httpx_when_client_unavailable(monkeypatch, authed_client):
    import services.gateway_service as gs

    name, ver = 'gqlhttpx', 'v1'
    await _setup_graphql(authed_client, name, ver)

    # Make Client unusable for async context
    class Dummy:
        pass

    monkeypatch.setattr(gs, 'Client', Dummy)

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
            return FakeHTTPResp({'ok': True, 'from': 'httpx', 'url': url})

    monkeypatch.setattr(gs.httpx, 'AsyncClient', FakeHTTPX)
    r = await authed_client.post(
        f'/api/graphql/{name}',
        headers={'X-API-Version': ver, 'Content-Type': 'application/json'},
        json={'query': '{ pong }', 'variables': {}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get('from') == 'httpx'


@pytest.mark.asyncio
async def test_graphql_errors_returned_in_errors_array(monkeypatch, authed_client):
    import services.gateway_service as gs

    name, ver = 'gqlerrors', 'v1'
    await _setup_graphql(authed_client, name, ver)

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
            return FakeHTTPResp({'errors': [{'message': 'boom'}]})

    monkeypatch.setattr(gs.httpx, 'AsyncClient', FakeHTTPX)

    # Force HTTPX path
    class Dummy:
        pass

    monkeypatch.setattr(gs, 'Client', Dummy)

    r = await authed_client.post(
        f'/api/graphql/{name}',
        headers={'X-API-Version': ver, 'Content-Type': 'application/json'},
        json={'query': '{ err }', 'variables': {}},
    )
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get('errors'), list) and body['errors'][0]['message'] == 'boom'


@pytest.mark.asyncio
async def test_graphql_strict_envelope_wraps_response(monkeypatch, authed_client):
    import services.gateway_service as gs

    name, ver = 'gqlstrict', 'v1'
    await _setup_graphql(authed_client, name, ver)

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

    monkeypatch.setenv('STRICT_RESPONSE_ENVELOPE', 'true')
    monkeypatch.setattr(gs.httpx, 'AsyncClient', FakeHTTPX)

    # Use httpx path by disabling Client
    class Dummy:
        pass

    monkeypatch.setattr(gs, 'Client', Dummy)

    r = await authed_client.post(
        f'/api/graphql/{name}',
        headers={'X-API-Version': ver, 'Content-Type': 'application/json'},
        json={'query': '{ strict }', 'variables': {}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get('status_code') == 200 and isinstance(body.get('response'), dict)


@pytest.mark.asyncio
async def test_graphql_loose_envelope_returns_raw_response(monkeypatch, authed_client):
    import services.gateway_service as gs

    name, ver = 'gqlloose', 'v1'
    await _setup_graphql(authed_client, name, ver)

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

    monkeypatch.delenv('STRICT_RESPONSE_ENVELOPE', raising=False)
    monkeypatch.setattr(gs.httpx, 'AsyncClient', FakeHTTPX)

    # Use httpx path by disabling Client
    class Dummy:
        pass

    monkeypatch.setattr(gs, 'Client', Dummy)

    r = await authed_client.post(
        f'/api/graphql/{name}',
        headers={'X-API-Version': ver, 'Content-Type': 'application/json'},
        json={'query': '{ loose }', 'variables': {}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get('data', {}).get('ok') is True
