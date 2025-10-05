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
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def patch(self, url, json=None, params=None, headers=None, content=None):
        body = json if json is not None else (content.decode('utf-8') if isinstance(content, (bytes, bytearray)) else content)
        return _FakeHTTPResponse(200, json_body={'method': 'PATCH', 'url': url, 'body': body, 'headers': headers or {}}, headers={'X-Upstream': 'yes'})

    async def head(self, url, params=None, headers=None):
        # Simulate a successful HEAD when called
        return _FakeHTTPResponse(200, json_body=None, headers={'X-Upstream': 'yes'})


async def _setup_api(client, name, ver, endpoint_method='GET', endpoint_uri='/p'):
    r = await client.post('/platform/api', json={
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://up.methods'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    })
    assert r.status_code in (200, 201)
    r2 = await client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': endpoint_method,
        'endpoint_uri': endpoint_uri,
        'endpoint_description': endpoint_method.lower(),
    })
    assert r2.status_code in (200, 201)
    # Subscribe admin
    rme = await client.get('/platform/user/me')
    username = (rme.json().get('username') if rme.status_code == 200 else 'admin')
    sr = await client.post('/platform/subscription/subscribe', json={'username': username, 'api_name': name, 'api_version': ver})
    assert sr.status_code in (200, 201)


@pytest.mark.asyncio
async def test_rest_head_supported_when_upstream_allows(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'headok', 'v1'
    await _setup_api(authed_client, name, ver, endpoint_method='GET', endpoint_uri='/p')
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.request('HEAD', f'/api/rest/{name}/{ver}/p')
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_rest_patch_supported_when_registered(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = 'patchok', 'v1'
    await _setup_api(authed_client, name, ver, endpoint_method='PATCH', endpoint_uri='/edit')
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.patch(f'/api/rest/{name}/{ver}/edit', json={'x': 1})
    assert r.status_code == 200
    j = r.json().get('response', r.json())
    assert j.get('method') == 'PATCH'


@pytest.mark.asyncio
async def test_rest_options_unregistered_endpoint_returns_405(monkeypatch, authed_client):
    # Enable strict OPTIONS behavior via env flag
    monkeypatch.setenv('STRICT_OPTIONS_405', 'true')
    # Create API without registering the specific endpoint
    name, ver = 'optunreg', 'v1'
    r = await authed_client.post('/platform/api', json={
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://up.methods'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    })
    assert r.status_code in (200, 201)
    resp = await authed_client.options(f'/api/rest/{name}/{ver}/not-made')
    assert resp.status_code == 405


@pytest.mark.asyncio
async def test_rest_unsupported_method_returns_405(authed_client):
    # Register a GET endpoint but call TRACE which is unsupported
    name, ver = 'unsup', 'v1'
    await _setup_api(authed_client, name, ver, endpoint_method='GET', endpoint_uri='/p')
    r = await authed_client.request('TRACE', f'/api/rest/{name}/{ver}/p')
    assert r.status_code == 405
