# External imports
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

    async def get(self, url, params=None, headers=None):
        return _FakeHTTPResponse(200, json_body={'method': 'GET', 'url': url, 'params': dict(params or {}), 'headers': headers or {}}, headers={'X-Upstream': 'yes'})

    async def post(self, url, json=None, params=None, headers=None, content=None):
        body = json if json is not None else (content.decode('utf-8') if isinstance(content, (bytes, bytearray)) else content)
        return _FakeHTTPResponse(200, json_body={'method': 'POST', 'url': url, 'params': dict(params or {}), 'body': body, 'headers': headers or {}}, headers={'X-Upstream': 'yes'})

    async def put(self, url, json=None, params=None, headers=None, content=None):
        body = json if json is not None else (content.decode('utf-8') if isinstance(content, (bytes, bytearray)) else content)
        return _FakeHTTPResponse(200, json_body={'method': 'PUT', 'url': url, 'params': dict(params or {}), 'body': body, 'headers': headers or {}}, headers={'X-Upstream': 'yes'})

    async def delete(self, url, json=None, params=None, headers=None, content=None):
        return _FakeHTTPResponse(200, json_body={'method': 'DELETE', 'url': url, 'params': dict(params or {}), 'headers': headers or {}}, headers={'X-Upstream': 'yes'})

@pytest.mark.asyncio
async def test_subscription_required_blocks_without_subscription(monkeypatch, authed_client):

    name, ver = 'nosub', 'v1'
    await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'n',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
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
            'endpoint_method': 'GET',
            'endpoint_uri': '/x',
            'endpoint_description': 'x',
        },
    )

    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/x')
    assert r.status_code == 403

@pytest.mark.asyncio
async def test_group_required_blocks_when_disallowed_group(monkeypatch, authed_client):

    name, ver = 'nogroup', 'v1'
    await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'g',
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
            'endpoint_method': 'GET',
            'endpoint_uri': '/y',
            'endpoint_description': 'y',
        },
    )

    import routes.gateway_routes as gr
    async def _pass_sub(req):
        return {'sub': 'admin'}
    monkeypatch.setattr(gr, 'subscription_required', _pass_sub)
    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/y')
    assert r.status_code == 401

@pytest.mark.asyncio
async def test_path_template_matching(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self
    name, ver = 'pathapi', 'v1'
    await create_api(authed_client, name, ver)

    await create_endpoint(authed_client, name, ver, 'GET', '/res/{id}')
    await subscribe_self(authed_client, name, ver)

    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/res/abc123')
    assert r.status_code == 200
    assert r.json().get('url', '').endswith('/res/abc123')

@pytest.mark.asyncio
async def test_text_body_forwarding(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self
    name, ver = 'textapi', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'POST', '/echo')
    await subscribe_self(authed_client, name, ver)

    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    payload = b'hello-world'
    r = await authed_client.post(
        f'/api/rest/{name}/{ver}/echo',
        headers={'Content-Type': 'text/plain'},
        content=payload,
    )
    assert r.status_code == 200
    assert r.json().get('body') == payload.decode('utf-8')

@pytest.mark.asyncio
async def test_response_header_filtering_excludes_unlisted(monkeypatch, authed_client):

    name, ver = 'hdrfilter', 'v1'
    await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 'h',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://up'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
            'api_allowed_headers': ['content-type'],
        },
    )
    await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'GET',
            'endpoint_uri': '/p',
            'endpoint_description': 'p',
        },
    )
    await authed_client.post(
        '/platform/subscription/subscribe',
        json={'username': 'admin', 'api_name': name, 'api_version': ver},
    )

    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/p')
    assert r.status_code == 200

    assert r.headers.get('X-Upstream') is None

@pytest.mark.asyncio
async def test_authorization_field_swap(monkeypatch, authed_client):

    name, ver = 'authswap', 'v1'
    await authed_client.post(
        '/platform/api',
        json={
            'api_name': name,
            'api_version': ver,
            'api_description': 's',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://up'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
            'api_allowed_headers': ['authorization', 'x-token'],
            'api_authorization_field_swap': 'x-token',
        },
    )
    await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': name,
            'api_version': ver,
            'endpoint_method': 'GET',
            'endpoint_uri': '/s',
            'endpoint_description': 's',
        },
    )
    await authed_client.post(
        '/platform/subscription/subscribe',
        json={'username': 'admin', 'api_name': name, 'api_version': ver},
    )

    import services.gateway_service as gs
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/s', headers={'x-token': 'ABC123'})
    assert r.status_code == 200

    assert r.json().get('headers', {}).get('Authorization') == 'ABC123'
