import pytest
from httpx import AsyncClient


async def _login(email: str, password: str) -> AsyncClient:
    from doorman import doorman

    client = AsyncClient(app=doorman, base_url='http://testserver')
    r = await client.post('/platform/authorization', json={'email': email, 'password': password})
    assert r.status_code == 200, r.text

    body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
    token = body.get('access_token')
    if token:
        client.cookies.set('access_token_cookie', token, domain='testserver', path='/')
    return client


@pytest.mark.asyncio
async def test_non_admin_role_cannot_access_monitor_or_credits(monkeypatch, authed_client):
    rrole = await authed_client.post(
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
            'view_logs': True,
            'export_logs': False,
            'manage_credits': False,
        },
    )
    assert rrole.status_code in (200, 201), rrole.text

    ruser = await authed_client.post(
        '/platform/user',
        json={
            'username': 'viewer',
            'email': 'viewer@example.com',
            'password': 'VeryStrongPassword123!',
            'role': 'viewer',
            'groups': ['ALL'],
        },
    )
    assert ruser.status_code in (200, 201), ruser.text

    viewer = await _login('viewer@example.com', 'VeryStrongPassword123!')

    mm = await viewer.get('/platform/monitor/metrics')
    assert mm.status_code == 403

    cd = await viewer.post(
        '/platform/credit',
        json={
            'api_credit_group': 'limited',
            'api_key': 'x',
            'api_key_header': 'x-api-key',
            'credit_tiers': [
                {
                    'tier_name': 'basic',
                    'credits': 10,
                    'input_limit': 0,
                    'output_limit': 0,
                    'reset_frequency': 'monthly',
                }
            ],
        },
    )
    assert cd.status_code == 403

    cc = await viewer.delete('/api/caches')
    assert cc.status_code == 403


@pytest.mark.asyncio
async def test_endpoint_validation_management_requires_permission(authed_client):
    await authed_client.post(
        '/platform/role',
        json={'role_name': 'noend', 'role_description': 'No endpoints', 'manage_endpoints': False},
    )
    await authed_client.post(
        '/platform/user',
        json={
            'username': 'noend',
            'email': 'noend@example.com',
            'password': 'VeryStrongPassword123!',
            'role': 'noend',
            'groups': ['ALL'],
        },
    )

    from conftest import create_api, create_endpoint

    api_name, ver = 'permapi', 'v1'
    await create_api(authed_client, api_name, ver)
    await create_endpoint(authed_client, api_name, ver, 'POST', '/foo')
    ge = await authed_client.get(f'/platform/endpoint/POST/{api_name}/{ver}/foo')
    eid = ge.json().get('endpoint_id') or ge.json().get('response', {}).get('endpoint_id')
    assert eid
    client = await _login('noend@example.com', 'VeryStrongPassword123!')

    ev = await client.post(
        '/platform/endpoint/endpoint/validation',
        json={
            'endpoint_id': eid,
            'validation_enabled': True,
            'validation_schema': {'validation_schema': {}},
        },
    )
    assert ev.status_code == 403
