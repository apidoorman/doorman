# External imports
import pytest

@pytest.mark.asyncio
async def test_roles_crud(authed_client):

    r = await authed_client.post(
        '/platform/role',
        json={
            'role_name': 'qa',
            'role_description': 'QA Role',
            'manage_users': False,
            'manage_apis': True,
            'manage_endpoints': True,
            'manage_groups': False,
            'manage_roles': False,
            'manage_routings': False,
            'manage_gateway': False,
            'manage_subscriptions': True,
            'manage_security': False,
            'view_logs': True,
            'export_logs': False,
        },
    )
    assert r.status_code in (200, 201)

    g = await authed_client.get('/platform/role/qa')
    assert g.status_code == 200

    roles = await authed_client.get('/platform/role/all')
    assert roles.status_code == 200

    u = await authed_client.put('/platform/role/qa', json={'manage_groups': True})
    assert u.status_code == 200

    d = await authed_client.delete('/platform/role/qa')
    assert d.status_code == 200

@pytest.mark.asyncio
async def test_groups_crud(authed_client):

    cg = await authed_client.post(
        '/platform/group',
        json={'group_name': 'qa-group', 'group_description': 'QA', 'api_access': []},
    )
    assert cg.status_code in (200, 201)

    g = await authed_client.get('/platform/group/qa-group')
    assert g.status_code == 200

    lst = await authed_client.get('/platform/group/all')
    assert lst.status_code == 200

    ug = await authed_client.put(
        '/platform/group/qa-group', json={'group_description': 'Quality Group'}
    )
    assert ug.status_code == 200

    dg = await authed_client.delete('/platform/group/qa-group')
    assert dg.status_code == 200

@pytest.mark.asyncio
async def test_subscriptions_flow(authed_client):

    api_payload = {
        'api_name': 'orders',
        'api_version': 'v1',
        'api_description': 'Orders API',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://upstream.local'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    }
    c = await authed_client.post('/platform/api', json=api_payload)
    assert c.status_code in (200, 201)

    s = await authed_client.post(
        '/platform/subscription/subscribe',
        json={'username': 'admin', 'api_name': 'orders', 'api_version': 'v1'},
    )
    assert s.status_code in (200, 201)

    ls = await authed_client.get('/platform/subscription/subscriptions')
    assert ls.status_code == 200
    subs = ls.json().get('subscriptions', {})
    apis = subs.get('apis') or []
    assert 'orders/v1' in apis or 'echo/v1' in apis

    us = await authed_client.post(
        '/platform/subscription/unsubscribe',
        json={'username': 'admin', 'api_name': 'orders', 'api_version': 'v1'},
    )
    assert us.status_code in (200, 400)

@pytest.mark.asyncio
async def test_token_defs_and_deduction_on_gateway(monkeypatch, authed_client):

    credit_group = 'ai-group'
    cd = await authed_client.post(
        '/platform/credit',
        json={
            'api_credit_group': credit_group,
            'api_key': 'sk-test-123',
            'api_key_header': 'x-api-key',
            'credit_tiers': [
                {'tier_name': 'basic', 'credits': 100, 'input_limit': 150, 'output_limit': 150, 'reset_frequency': 'monthly'}
            ],
        },
    )
    assert cd.status_code in (200, 201), cd.text

    api_name, version = 'aiapi', 'v1'
    c = await authed_client.post(
        '/platform/api',
        json={
            'api_name': api_name,
            'api_version': version,
            'api_description': 'AI API',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': ['http://fake-upstream'],
            'api_type': 'REST',
            'api_allowed_retry_count': 0,
            'api_credits_enabled': True,
            'api_credit_group': credit_group,
        },
    )
    assert c.status_code in (200, 201), c.text
    ep = await authed_client.post(
        '/platform/endpoint',
        json={
            'api_name': api_name,
            'api_version': version,
            'endpoint_method': 'GET',
            'endpoint_uri': '/ping',
            'endpoint_description': 'ping',
        },
    )
    assert ep.status_code in (200, 201)
    s = await authed_client.post(
        '/platform/subscription/subscribe',
        json={'username': 'admin', 'api_name': api_name, 'api_version': version},
    )
    assert s.status_code in (200, 201)

    uc = await authed_client.post(
        f'/platform/credit/admin',
        json={
            'username': 'admin',
            'users_credits': {
                credit_group: {'tier_name': 'basic', 'available_credits': 2}
            },
        },
    )
    assert uc.status_code in (200, 201), uc.text

    async def _remaining():
        r = await authed_client.get('/platform/credit/admin')
        assert r.status_code == 200, r.text
        body = r.json()
        users_credits = body.get('users_credits') or body.get('response', {}).get('users_credits', {})
        return int(users_credits.get(credit_group, {}).get('available_credits', 0))

    import services.gateway_service as gs

    class _FakeHTTPResponse:
        def __init__(self, status_code=200, json_body=None):
            self.status_code = status_code
            self._json_body = json_body or {'ok': True}
            self.headers = {'Content-Type': 'application/json'}
            self.content = b'{}'
            self.text = '{}'

        def json(self):
            return self._json_body

    class _FakeAsyncClient:
        def __init__(self, timeout=None, limits=None, http2=False):
            self._timeout = timeout
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params=None, headers=None):
            return _FakeHTTPResponse(200)

    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    assert await _remaining() == 2

    r1 = await authed_client.get(f'/api/rest/{api_name}/{version}/ping')
    assert r1.status_code in (200, 500)
    assert await _remaining() == 1

    r2 = await authed_client.get(f'/api/rest/{api_name}/{version}/ping')
    assert r2.status_code in (200, 500)
    assert await _remaining() == 0

    r3 = await authed_client.get(f'/api/rest/{api_name}/{version}/ping')
    assert r3.status_code == 401
