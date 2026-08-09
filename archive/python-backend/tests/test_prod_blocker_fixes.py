import os
import re
import uuid

import pytest
from fastapi.routing import APIWebSocketRoute
from fastapi.testclient import TestClient
from httpx import AsyncClient
from starlette.websockets import WebSocketDisconnect


def _unique(prefix: str) -> str:
    return f'{prefix}-{uuid.uuid4().hex[:8]}'


def _metric_value(payload: str, name: str, label: str | None = None) -> float | None:
    for line in (payload or '').splitlines():
        if not line.startswith(name):
            continue
        if label and label not in line:
            continue
        match = re.search(r'\s([0-9eE\.\+\-]+)\s*$', line)
        if match:
            try:
                return float(match.group(1))
            except Exception:
                return None
    return None


async def _login(email: str, password: str) -> AsyncClient:
    from doorman import doorman

    client = AsyncClient(app=doorman, base_url='http://testserver')
    r = await client.post('/platform/authorization', json={'email': email, 'password': password})
    assert r.status_code == 200, r.text
    body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
    token = body.get('access_token')
    if token:
        client.cookies.set(
            'access_token_cookie',
            token,
            domain=os.environ.get('COOKIE_DOMAIN') or 'testserver',
            path='/',
        )
    return client


async def _create_role_user(authed_client, overrides: dict) -> AsyncClient:
    role_name = _unique('role')
    username = _unique('user')
    payload = {
        'role_name': role_name,
        'role_description': role_name,
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
        'view_logs': False,
        'export_logs': False,
        'view_analytics': False,
    }
    payload.update(overrides or {})
    rrole = await authed_client.post('/platform/role', json=payload)
    assert rrole.status_code in (200, 201), rrole.text

    email = f'{username}@example.com'
    password = 'VeryStrongPassword123!'
    ruser = await authed_client.post(
        '/platform/user',
        json={
            'username': username,
            'email': email,
            'password': password,
            'role': role_name,
            'groups': ['ALL'],
            'active': True,
        },
    )
    assert ruser.status_code in (200, 201), ruser.text
    return await _login(email, password)


@pytest.mark.asyncio
async def test_mfa_routes_removed(authed_client):
    r = await authed_client.post('/platform/auth/mfa/verify', json={'totp': '123456'})
    assert r.status_code == 404


def test_mfa_routes_absent_from_router():
    from doorman import doorman

    paths = [route.path for route in doorman.router.routes if hasattr(route, 'path')]
    assert not any('/platform/auth/mfa' in path for path in paths)


def test_graphql_websocket_route_absent():
    from doorman import doorman

    ws_paths = [
        route.path
        for route in doorman.router.routes
        if isinstance(route, APIWebSocketRoute)
    ]
    assert not any('graphql' in path for path in ws_paths)


def test_websocket_upgrade_rejected():
    from doorman import doorman

    client = TestClient(doorman)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/graphql'):
            pass


@pytest.mark.asyncio
async def test_discovery_routes_require_manage_apis(authed_client):
    client = await _create_role_user(authed_client, {'manage_apis': False})
    name = _unique('api')
    ver = 'v1'
    paths = [
        f'/platform/api/{name}/{ver}/openapi',
        f'/platform/api/{name}/{ver}/wsdl',
        f'/platform/api/{name}/{ver}/grpc/services',
        f'/platform/api/{name}/{ver}/graphql/schema',
        f'/platform/api/{name}/{ver}/graphql/types',
    ]
    for path in paths:
        r = await client.get(path)
        assert r.status_code == 403
        body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        assert body.get('error_code') == 'AUTHZ001'


@pytest.mark.asyncio
async def test_discovery_routes_allow_manage_apis(authed_client):
    name = _unique('api')
    ver = 'v1'
    paths = [
        f'/platform/api/{name}/{ver}/openapi',
        f'/platform/api/{name}/{ver}/wsdl',
        f'/platform/api/{name}/{ver}/grpc/services',
        f'/platform/api/{name}/{ver}/graphql/schema',
    ]
    for path in paths:
        r = await authed_client.get(path)
        assert r.status_code == 404
        body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        assert body.get('error_code') == 'API001'


@pytest.mark.asyncio
async def test_openapi_wsdl_import_requires_manage_endpoints(authed_client):
    from conftest import create_api

    name = _unique('importapi')
    ver = 'v1'
    await create_api(authed_client, name, ver)
    client = await _create_role_user(authed_client, {'manage_apis': True, 'manage_endpoints': False})
    ropen = await client.post(f'/platform/api/{name}/{ver}/openapi/import')
    rwsdl = await client.post(f'/platform/api/{name}/{ver}/wsdl/import')
    assert ropen.status_code == 403
    assert rwsdl.status_code == 403
    body_open = (
        ropen.json() if ropen.headers.get('content-type', '').startswith('application/json') else {}
    )
    body_wsdl = (
        rwsdl.json() if rwsdl.headers.get('content-type', '').startswith('application/json') else {}
    )
    assert body_open.get('error_code') == 'AUTHZ001'
    assert body_wsdl.get('error_code') == 'AUTHZ001'


@pytest.mark.asyncio
async def test_openapi_wsdl_import_allows_manage_endpoints(authed_client):
    from conftest import create_api

    name = _unique('importapi')
    ver = 'v1'
    await create_api(authed_client, name, ver)
    client = await _create_role_user(authed_client, {'manage_apis': False, 'manage_endpoints': True})
    ropen = await client.post(f'/platform/api/{name}/{ver}/openapi/import')
    rwsdl = await client.post(f'/platform/api/{name}/{ver}/wsdl/import')
    assert ropen.status_code == 404
    assert rwsdl.status_code == 404
    body_open = (
        ropen.json() if ropen.headers.get('content-type', '').startswith('application/json') else {}
    )
    body_wsdl = (
        rwsdl.json() if rwsdl.headers.get('content-type', '').startswith('application/json') else {}
    )
    assert body_open.get('error_code') == 'OPENAPI003'
    assert body_wsdl.get('error_code') == 'WSDL003'


@pytest.mark.asyncio
async def test_discovery_refresh_requires_manage_apis(authed_client):
    client = await _create_role_user(authed_client, {'manage_apis': False})
    name = _unique('api')
    ver = 'v1'
    paths = [
        f'/platform/api/{name}/{ver}/openapi/refresh',
        f'/platform/api/{name}/{ver}/wsdl/refresh',
        f'/platform/api/{name}/{ver}/graphql/schema/refresh',
    ]
    for path in paths:
        r = await client.post(path)
        assert r.status_code == 403
        body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
        assert body.get('error_code') == 'AUTHZ001'


@pytest.mark.asyncio
async def test_openapi_wsdl_refresh_missing_config_errors(authed_client):
    from conftest import create_api

    name = _unique('cfgapi')
    ver = 'v1'
    await create_api(authed_client, name, ver)
    ropen = await authed_client.post(f'/platform/api/{name}/{ver}/openapi/refresh')
    rwsdl = await authed_client.post(f'/platform/api/{name}/{ver}/wsdl/refresh')
    assert ropen.status_code == 404
    assert rwsdl.status_code == 404
    body_open = (
        ropen.json() if ropen.headers.get('content-type', '').startswith('application/json') else {}
    )
    body_wsdl = (
        rwsdl.json() if rwsdl.headers.get('content-type', '').startswith('application/json') else {}
    )
    assert body_open.get('error_code') == 'OPENAPI001'
    assert body_wsdl.get('error_code') == 'WSDL001'


@pytest.mark.asyncio
async def test_graphql_schema_cache_and_types(monkeypatch, authed_client):
    from conftest import create_api
    import routes.graphql_routes as gr

    name = _unique('gql')
    ver = 'v1'
    await create_api(authed_client, name, ver)
    schema = {
        'queryType': {'name': 'Query'},
        'mutationType': None,
        'subscriptionType': None,
        'types': [
            {
                'name': 'Query',
                'kind': 'OBJECT',
                'description': 'root',
                'fields': [{'name': 'ping', 'type': {'name': 'String', 'kind': 'SCALAR'}}],
            }
        ],
    }
    calls = {'n': 0}

    async def _fake_fetch(url):
        calls['n'] += 1
        return schema

    monkeypatch.setattr(gr, 'fetch_introspection_schema', _fake_fetch)

    r1 = await authed_client.get(f'/platform/api/{name}/{ver}/graphql/schema')
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1.get('cached') is False
    assert body1.get('schema') == schema
    assert body1.get('operation_types', {}).get('query') == 'Query'
    assert body1.get('has_subscriptions') is False

    r2 = await authed_client.get(f'/platform/api/{name}/{ver}/graphql/schema')
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2.get('cached') is True
    assert calls['n'] == 1

    r3 = await authed_client.get(f'/platform/api/{name}/{ver}/graphql/types')
    assert r3.status_code == 200
    body3 = r3.json()
    assert body3.get('types_count') == 1
    assert body3.get('types')[0].get('name') == 'Query'


@pytest.mark.asyncio
async def test_graphql_types_without_cache_returns_error(authed_client):
    name = _unique('gql')
    ver = 'v1'
    r = await authed_client.get(f'/platform/api/{name}/{ver}/graphql/types')
    assert r.status_code == 404
    body = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
    assert body.get('error_code') == 'GQL003'


@pytest.mark.asyncio
async def test_openapi_cache_fetch_and_reuse(monkeypatch, authed_client):
    import routes.openapi_routes as oroutes

    name = _unique('openapi')
    ver = 'v1'
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://openapi.test'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_openapi_url': '/openapi.json',
    }
    r = await authed_client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201), r.text

    spec = {'openapi': '3.0.0', 'info': {'title': 'Test API', 'version': '1.0.0'}}
    calls = {'n': 0}

    async def _fake_fetch(base_url, openapi_path):
        calls['n'] += 1
        return spec

    monkeypatch.setattr(oroutes, '_fetch_upstream_openapi', _fake_fetch)

    r1 = await authed_client.get(f'/platform/api/{name}/{ver}/openapi')
    assert r1.status_code == 200
    assert r1.json() == spec
    r2 = await authed_client.get(f'/platform/api/{name}/{ver}/openapi')
    assert r2.status_code == 200
    assert r2.json() == spec
    assert calls['n'] == 1


@pytest.mark.asyncio
async def test_wsdl_cache_fetch_and_reuse(monkeypatch, authed_client):
    import routes.wsdl_routes as wroutes

    name = _unique('wsdl')
    ver = 'v1'
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://wsdl.test'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_wsdl_url': '/service.wsdl',
    }
    r = await authed_client.post('/platform/api', json=payload)
    assert r.status_code in (200, 201), r.text

    wsdl = (
        '<definitions xmlns="http://schemas.xmlsoap.org/wsdl/" '
        'name="TestService" targetNamespace="http://example.com/">'
        '<portType name="TestPort"><operation name="Ping"/></portType>'
        '<service name="TestService"><port name="TestPort" binding="tns:TestBinding"/></service>'
        '</definitions>'
    )
    calls = {'n': 0}

    async def _fake_fetch(url):
        calls['n'] += 1
        return wsdl

    monkeypatch.setattr(wroutes, 'fetch_wsdl', _fake_fetch)

    r1 = await authed_client.get(f'/platform/api/{name}/{ver}/wsdl')
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1.get('wsdl') == wsdl
    assert body1.get('cached') is False

    r2 = await authed_client.get(f'/platform/api/{name}/{ver}/wsdl')
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2.get('wsdl') == wsdl
    assert body2.get('cached') is True
    assert calls['n'] == 1


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint_exposed(authed_client):
    r = await authed_client.get('/metrics')
    assert r.status_code in (200, 503)
    body = r.text or ''
    if r.status_code == 200:
        assert 'doorman_http_request_duration_seconds_bucket' in body
        assert 'doorman_http_requests_total' in body


@pytest.mark.asyncio
async def test_prometheus_metrics_emit_counters(authed_client):
    from utils.prometheus_metrics import observe_request, record_retry, record_upstream_timeout

    observe_request(12, 200)
    record_retry()
    record_upstream_timeout()
    r = await authed_client.get('/metrics')
    if r.status_code == 503:
        pytest.skip('Prometheus disabled')
    assert r.status_code == 200
    body = r.text or ''
    assert (_metric_value(body, 'doorman_http_requests_total', 'code="200"') or 0) >= 1
    assert (_metric_value(body, 'doorman_http_retries_total') or 0) >= 1
    assert (_metric_value(body, 'doorman_upstream_timeouts_total') or 0) >= 1


@pytest.mark.asyncio
async def test_prometheus_metrics_allowlist_and_token(monkeypatch, authed_client):
    import routes.metrics_routes as mr

    monkeypatch.setattr(mr, 'PROMETHEUS_ENABLED', True)
    monkeypatch.setenv('PROMETHEUS_PUBLIC', 'false')
    monkeypatch.setenv('PROMETHEUS_ALLOWLIST', '10.0.0.0/8')
    monkeypatch.setenv('PROMETHEUS_TRUST_XFF', 'true')
    monkeypatch.setenv('PROMETHEUS_BEARER_TOKEN', 'secret-token')

    r = await authed_client.get('/metrics', headers={'X-Forwarded-For': '203.0.113.10'})
    assert r.status_code == 403

    r2 = await authed_client.get(
        '/metrics',
        headers={
            'X-Forwarded-For': '10.1.2.3',
            'Authorization': 'Bearer secret-token',
        },
    )
    assert r2.status_code in (200, 503)
