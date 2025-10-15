import pytest

async def _login_new_client(email: str, password: str):
    from doorman import doorman
    from httpx import AsyncClient
    import os
    client = AsyncClient(app=doorman, base_url='http://testserver')
    r = await client.post('/platform/authorization', json={'email': email, 'password': password})
    assert r.status_code == 200, r.text
    try:
        has_cookie = any(c.name == 'access_token_cookie' for c in client.cookies.jar)
        if not has_cookie:
            body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
            token = body.get('access_token')
            if token:
                client.cookies.set('access_token_cookie', token, domain=os.environ.get('COOKIE_DOMAIN') or 'testserver', path='/')
    except Exception:
        pass
    return client

async def _provision_limited_user(authed_client, role_name: str, username: str, email: str, password: str):
    role_payload = {
        'role_name': role_name,
        'role_description': 'Limited role (no permissions)',
        'manage_users': False,
        'manage_apis': False,
        'manage_endpoints': False,
        'manage_groups': False,
        'manage_roles': False,
        'manage_routings': False,
        'manage_gateway': False,
        'manage_subscriptions': False,
        'manage_security': False,
        'manage_credits': False,
        'manage_auth': False,
        'view_logs': False,
        'export_logs': False,
    }
    await authed_client.post('/platform/role', json=role_payload)

    user_payload = {
        'username': username,
        'email': email,
        'password': password,
        'role': role_name,
        'groups': ['ALL'],
        'active': True,
        'ui_access': False,
    }
    r = await authed_client.post('/platform/user', json=user_payload)
    assert r.status_code in (200, 201), r.text
    return await _login_new_client(email, password)

@pytest.mark.asyncio
async def test_manage_users_required_for_user_crud(authed_client):
    limited = await _provision_limited_user(
        authed_client,
        role_name='limited_users_role',
        username='limited_users',
        email='limited_users@doorman.dev',
        password='StrongPassword123!!',
    )

    target_payload = {
        'username': 'target_user1',
        'email': 'target_user1@doorman.dev',
        'password': 'AnotherStrongPwd123!!',
        'role': 'admin',
        'groups': ['ALL'],
    }
    await authed_client.post('/platform/user', json=target_payload)

    r_create = await limited.post('/platform/user', json={
        'username': 'should_forbid',
        'email': 'should_forbid@doorman.dev',
        'password': 'ThisIsAVeryStrongPwd!!',
        'role': 'admin',
        'groups': ['ALL'],
    })
    assert r_create.status_code == 403

    r_update = await limited.put('/platform/user/target_user1', json={'ui_access': True})
    assert r_update.status_code == 403

    r_delete = await limited.delete('/platform/user/target_user1')
    assert r_delete.status_code == 403

@pytest.mark.asyncio
async def test_manage_apis_required_for_api_crud(authed_client):
    limited = await _provision_limited_user(
        authed_client,
        role_name='limited_apis_role',
        username='limited_apis',
        email='limited_apis@doorman.dev',
        password='StrongPassword123!!',
    )

    r_create = await limited.post('/platform/api', json={
        'api_name': 'negapi',
        'api_version': 'v1',
        'api_description': 'negative api',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://upstream.test'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    })
    assert r_create.status_code == 403

    await authed_client.post('/platform/api', json={
        'api_name': 'negapi',
        'api_version': 'v1',
        'api_description': 'baseline',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://upstream.test'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    })
    r_update = await limited.put('/platform/api/negapi/v1', json={'api_description': 'should not update'})
    assert r_update.status_code == 403

@pytest.mark.asyncio
async def test_manage_endpoints_required_for_endpoint_crud(authed_client):
    limited = await _provision_limited_user(
        authed_client,
        role_name='limited_endpoints_role',
        username='limited_endpoints',
        email='limited_endpoints@doorman.dev',
        password='StrongPassword123!!',
    )

    await authed_client.post('/platform/api', json={
        'api_name': 'negep',
        'api_version': 'v1',
        'api_description': 'baseline',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://upstream.test'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
    })
    await authed_client.post('/platform/endpoint', json={
        'api_name': 'negep',
        'api_version': 'v1',
        'endpoint_method': 'GET',
        'endpoint_uri': '/s',
        'endpoint_description': 'status',
    })

    r_create = await limited.post('/platform/endpoint', json={
        'api_name': 'negep',
        'api_version': 'v1',
        'endpoint_method': 'POST',
        'endpoint_uri': '/p',
        'endpoint_description': 'post',
    })
    assert r_create.status_code == 403

    r_update = await limited.put('/platform/endpoint/GET/negep/v1/s', json={'endpoint_description': 'nope'})
    assert r_update.status_code == 403

    r_delete = await limited.delete('/platform/endpoint/GET/negep/v1/s')
    assert r_delete.status_code == 403

@pytest.mark.asyncio
async def test_manage_gateway_required_for_cache_clear(authed_client):
    limited = await _provision_limited_user(
        authed_client,
        role_name='limited_gateway_role',
        username='limited_gateway',
        email='limited_gateway@doorman.dev',
        password='StrongPassword123!!',
    )

    r = await limited.delete('/api/caches')
    assert r.status_code == 403

@pytest.mark.asyncio
async def test_view_logs_required_for_log_export(authed_client):
    limited = await _provision_limited_user(
        authed_client,
        role_name='limited_logs_role',
        username='limited_logs',
        email='limited_logs@doorman.dev',
        password='StrongPassword123!!',
    )

    r_logs = await limited.get('/platform/logging/logs')
    assert r_logs.status_code == 403

    r_export = await limited.get('/platform/logging/logs/export')
    assert r_export.status_code == 403

