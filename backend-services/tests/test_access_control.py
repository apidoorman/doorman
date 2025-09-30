# External imports
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient

@pytest_asyncio.fixture
async def login_client() :
    async def _login(username: str, password: str, email: str = None) -> AsyncClient:
        from doorman import doorman
        client = AsyncClient(app=doorman, base_url='http://testserver')
        cred = {'email': email or f'{username}@example.com', 'password': password}
        r = await client.post('/platform/authorization', json=cred)
        assert r.status_code == 200, r.text
        return client
    return _login

@pytest.mark.asyncio
async def test_roles_and_permissions_enforced(authed_client, login_client):

    cr = await authed_client.post(
        '/platform/role',
        json={
            'role_name': 'viewer',
            'role_description': 'Read-only',
            'manage_users': False,
            'manage_apis': False,
            'manage_endpoints': False,
            'manage_groups': False,
            'manage_roles': False,
            'manage_routings': False,
            'manage_gateway': False,
            'manage_subscriptions': False,
            'manage_security': False,
            'view_logs': False,
            'export_logs': False,
        },
    )
    assert cr.status_code in (200, 201)

    g = await authed_client.post(
        '/platform/group',
        json={'group_name': 'team1', 'group_description': 'team one', 'api_access': []},
    )
    assert g.status_code in (200, 201)

    cu = await authed_client.post(
        '/platform/user',
        json={
            'username': 'viewer1',
            'email': 'viewer1@example.com',
            'password': 'StrongViewerPwd!1234',
            'role': 'viewer',
            'groups': ['team1'],
            'active': True,
        },
    )
    assert cu.status_code in (200, 201), cu.text

    viewer_client = await login_client('viewer1', 'StrongViewerPwd!1234')

    create_api = await viewer_client.post(
        '/platform/api',
        json={
            'api_name': 'blocked',
            'api_version': 'v1',
            'api_description': 'blocked',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://example'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
        },
    )
    assert create_api.status_code == 403

    logs = await viewer_client.get('/platform/logging/logs')
    assert logs.status_code in (401, 403, 500)

    await viewer_client.aclose()

@pytest.mark.asyncio
async def test_group_and_subscription_enforcement(login_client, authed_client, monkeypatch):

    c = await authed_client.post(
        '/platform/api',
        json={
            'api_name': 'secure',
            'api_version': 'v1',
            'api_description': 'secure api',
            'api_allowed_roles': ['admin', 'viewer'],
            'api_allowed_groups': ['team1'],
            'api_servers': ['http://fake-upstream'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
        },
    )
    assert c.status_code in (200, 201)

    ep = await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': 'secure',
            'api_version': 'v1',
            'endpoint_method': 'GET',
            'endpoint_uri': '/res',
            'endpoint_description': 'resource',
        },
    )
    assert ep.status_code in (200, 201)

    g2 = await authed_client.post(
        '/platform/group',
        json={'group_name': 'team2', 'group_description': 'team two', 'api_access': []},
    )
    assert g2.status_code in (200, 201)

    bobu = await authed_client.post(
        '/platform/user',
        json={
            'username': 'bob',
            'email': 'bob@example.com',
            'password': 'StrongBobPwd!1234',
            'role': 'viewer',
            'groups': ['team2'],
            'active': True,
        },
    )
    assert bobu.status_code in (200, 201)

    s1 = await authed_client.post(
        '/platform/subscription/subscribe',
        json={'username': 'viewer1', 'api_name': 'secure', 'api_version': 'v1'},
    )
    assert s1.status_code in (200, 201)

    s2 = await authed_client.post(
        '/platform/subscription/subscribe',
        json={'username': 'bob', 'api_name': 'secure', 'api_version': 'v1'},
    )
    assert s2.status_code in (401, 403)

    import services.gateway_service as gs
    class _FakeHTTPResponse:
        def __init__(self, status_code=200, json_body=None):
            self.status_code = status_code
            self._json_body = json_body or {'ok': True}
            self.headers = {'Content-Type': 'application/json'}
        def json(self):
            return self._json_body
    class _FakeAsyncClient:
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def get(self, url, params=None, headers=None): return _FakeHTTPResponse(200)
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)
    import routes.gateway_routes as gr
    async def _no_limit(req): return None
    monkeypatch.setattr(gr, 'limit_and_throttle', _no_limit)

    viewer1_client = await login_client('viewer1', 'StrongViewerPwd!1234')
    bob_client = await login_client('bob', 'StrongBobPwd!1234')

    ok = await viewer1_client.get('/api/rest/secure/v1/res')
    assert ok.status_code in (200, 500)

    denied = await bob_client.get('/api/rest/secure/v1/res')
    assert denied.status_code in (401, 403)

    await viewer1_client.aclose()
    await bob_client.aclose()
