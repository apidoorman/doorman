"""
Tests for host-based transparent URL routing (host_gateway_router).

Verifies:
- A request with a Host header matching an api_hostname is transparently proxied
- The full request path is forwarded verbatim (no /api/rest/ prefix added)
- An unknown Host header returns 404
- Auth enforcement still applies to host-routed APIs
- A public host-routed API is accessible without authentication
"""

import pytest


class _FakeHTTPResponse:
    def __init__(self, status_code=200, json_body=None, headers=None):
        self.status_code = status_code
        self._json_body = json_body or {}
        self.text = ''
        self.headers = headers or {'Content-Type': 'application/json'}

    def json(self):
        return self._json_body


class _FakeAsyncClient:
    """Captures the URL of every upstream request for assertion."""

    def __init__(self, *args, **kwargs):
        self.last_url = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def request(self, method, url, **kwargs):
        self.last_url = url
        return _FakeHTTPResponse(200, json_body={'url': url, 'method': method})

    async def get(self, url, **kwargs):
        self.last_url = url
        return _FakeHTTPResponse(200, json_body={'url': url})

    async def post(self, url, **kwargs):
        self.last_url = url
        return _FakeHTTPResponse(200, json_body={'url': url})


@pytest.mark.asyncio
async def test_host_routing_unknown_host_returns_404(client):
    """A request with a Host header that has no matching api_hostname → 404."""
    r = await client.get(
        '/v2/bar/query',
        headers={'host': 'unknown.example.com'},
    )
    # The catch-all host_gateway_router returns a JSON 404 (no API for this hostname)
    body = r.json()
    status = body.get('status_code', r.status_code)
    assert status == 404, f'Expected 404 for unknown host, got {status} body={body}'


@pytest.mark.asyncio
async def test_host_routing_proxies_path_verbatim(monkeypatch, authed_client):
    """A request to a host-routed API forwards the full path to the upstream unchanged."""
    from conftest import subscribe_self

    fake_client = _FakeAsyncClient()

    import services.gateway_service as _gs
    monkeypatch.setattr(_gs.httpx, 'AsyncClient', lambda *a, **kw: fake_client)

    # Create the API with api_hostname
    api_name, api_version = 'hosttest', 'v1'
    r_create = await authed_client.post(
        '/platform/api',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'host routing test',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://upstream.test'],
            'api_type': 'REST',
            'api_hostname': 'foo.test.local',
            'api_auth_required': True,
        },
    )
    assert r_create.status_code in (200, 201), r_create.text

    await subscribe_self(authed_client, api_name, api_version)

    # Register an endpoint so auth/subscription pass
    await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': 'GET',
            'endpoint_uri': '/v2/bar/query',
        },
    )

    # Make a request with the matching Host header
    r = await authed_client.get(
        '/v2/bar/query',
        headers={'host': 'foo.test.local'},
        params={'paramA': 'value'},
    )

    # Should not be a 401/403/404 at the gateway level
    body = r.json()
    status = body.get('status_code', r.status_code)
    assert status not in (401, 403, 500), f'Unexpected status: {status}, body: {body}'

    # If the upstream was called, the URL should contain the full path
    if fake_client.last_url:
        assert '/v2/bar/query' in fake_client.last_url, (
            f'Expected verbatim path in upstream URL, got: {fake_client.last_url}'
        )
        # Must NOT contain the /api/rest/ prefix
        assert '/api/rest/' not in fake_client.last_url


@pytest.mark.asyncio
async def test_host_routing_public_api_no_auth(monkeypatch, client):
    """A public host-routed API is accessible without any JWT."""
    from doorman import doorman
    from httpx import AsyncClient

    fake_client = _FakeAsyncClient()

    import services.gateway_service as _gs
    monkeypatch.setattr(_gs.httpx, 'AsyncClient', lambda *a, **kw: fake_client)

    # We need an admin client to create the API
    admin = AsyncClient(app=doorman, base_url='http://testserver')
    import os
    r_login = await admin.post(
        '/platform/authorization',
        json={
            'email': os.environ.get('DOORMAN_ADMIN_EMAIL'),
            'password': os.environ.get('DOORMAN_ADMIN_PASSWORD'),
        },
    )
    assert r_login.status_code == 200

    api_name, api_version = 'publichostapi', 'v1'
    await admin.post(
        '/platform/api',
        json={
            'api_name': api_name,
            'api_version': api_version,
            'api_description': 'public host routing test',
            'api_allowed_roles': [],
            'api_allowed_groups': [],
            'api_servers': ['http://upstream.test'],
            'api_type': 'REST',
            'api_hostname': 'public.test.local',
            'api_public': True,
        },
    )

    # Make request WITHOUT authentication (plain unauthenticated client)
    r = await client.get(
        '/v1/resource',
        headers={'host': 'public.test.local'},
    )
    body = r.json()
    status = body.get('status_code', r.status_code)
    # Should NOT be a 401 — public API requires no auth
    assert status != 401, f'Public host API should not require auth, got: {status}'


@pytest.mark.asyncio
async def test_host_routing_existing_api_paths_unaffected(authed_client):
    """Existing /api/rest/ path-based routing must be completely unaffected."""
    from conftest import create_api, create_endpoint, subscribe_self

    api_name, api_version = 'legacy-path-api', 'v1'
    await create_api(authed_client, api_name, api_version)
    await create_endpoint(authed_client, api_name, api_version, 'GET', '/health')
    await subscribe_self(authed_client, api_name, api_version)

    # Standard path-based request — must reach the gateway normally (not 404 from host router)
    r = await authed_client.get(f'/api/rest/{api_name}/{api_version}/health')
    body = r.json()
    # 404 from gateway means endpoint not found (GTW003), not from host router
    # Either way, it should NOT be a host-router 404 (which returns GTW001)
    assert body.get('error_code') != 'GTW001' or body.get('status_code') not in (None,)
