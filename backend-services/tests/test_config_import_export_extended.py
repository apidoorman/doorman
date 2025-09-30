# External imports
import json
import pytest

@pytest.mark.asyncio
async def test_export_all_basic(authed_client):
    r = await authed_client.get('/platform/config/export/all')
    assert r.status_code == 200
    data = r.json().get('response') or r.json()
    assert isinstance(data.get('apis'), list)
    assert isinstance(data.get('roles'), list)
    assert isinstance(data.get('groups'), list)
    assert isinstance(data.get('routings'), list)
    assert isinstance(data.get('endpoints'), list)

@pytest.mark.asyncio
@pytest.mark.parametrize('path', [
    '/platform/config/export/apis',
    '/platform/config/export/roles',
    '/platform/config/export/groups',
    '/platform/config/export/routings',
    '/platform/config/export/endpoints',
])
async def test_export_lists(authed_client, path):
    r = await authed_client.get(path)
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_export_single_api_with_endpoints(authed_client):
    async def _create_api(c, n, v):
        payload = {'api_name': n, 'api_version': v, 'api_description': f'{n} {v}', 'api_allowed_roles': ['admin'], 'api_allowed_groups': ['ALL'], 'api_servers': ['http://upstream'], 'api_type': 'REST', 'api_allowed_retry_count': 0}
        rr = await c.post('/platform/api', json=payload)
        assert rr.status_code in (200, 201)
    async def _create_endpoint(c, n, v, m, u):
        payload = {'api_name': n, 'api_version': v, 'endpoint_method': m, 'endpoint_uri': u, 'endpoint_description': f'{m} {u}'}
        rr = await c.post('/platform/endpoint', json=payload)
        assert rr.status_code in (200, 201)
    await _create_api(authed_client, 'exapi', 'v1')
    await _create_endpoint(authed_client, 'exapi', 'v1', 'GET', '/status')
    r = await authed_client.get('/platform/config/export/apis', params={'api_name': 'exapi', 'api_version': 'v1'})
    assert r.status_code == 200
    payload = r.json().get('response') or r.json()
    assert payload.get('api') and payload.get('endpoints') is not None

@pytest.mark.asyncio
async def test_export_endpoints_filter(authed_client):
    async def _create_api(c, n, v):
        payload = {'api_name': n, 'api_version': v, 'api_description': f'{n} {v}', 'api_allowed_roles': ['admin'], 'api_allowed_groups': ['ALL'], 'api_servers': ['http://upstream'], 'api_type': 'REST', 'api_allowed_retry_count': 0}
        rr = await c.post('/platform/api', json=payload)
        assert rr.status_code in (200, 201)
    async def _create_endpoint(c, n, v, m, u):
        payload = {'api_name': n, 'api_version': v, 'endpoint_method': m, 'endpoint_uri': u, 'endpoint_description': f'{m} {u}'}
        rr = await c.post('/platform/endpoint', json=payload)
        assert rr.status_code in (200, 201)
    await _create_api(authed_client, 'filterapi', 'v1')
    await _create_endpoint(authed_client, 'filterapi', 'v1', 'GET', '/x')
    r = await authed_client.get('/platform/config/export/endpoints', params={'api_name': 'filterapi', 'api_version': 'v1'})
    assert r.status_code == 200
    eps = (r.json().get('response') or r.json()).get('endpoints')
    assert isinstance(eps, list) and len(eps) >= 1

@pytest.mark.asyncio
@pytest.mark.parametrize('sections', [
    {'apis': []},
    {'roles': []},
    {'groups': []},
    {'routings': []},
    {'endpoints': []},
    {'apis': [], 'endpoints': []},
    {'roles': [], 'groups': []},
])
async def test_import_various_sections(authed_client, sections):
    r = await authed_client.post('/platform/config/import', json=sections)
    assert r.status_code == 200

@pytest.mark.asyncio
async def test_security_restart_pid_missing(authed_client):
    r = await authed_client.post('/platform/security/restart')
    assert r.status_code in (202, 409, 403)

@pytest.mark.asyncio
async def test_audit_called_on_export(monkeypatch, authed_client):
    calls = []
    import utils.audit_util as au
    orig = au._logger
    class _L:
        def info(self, msg):
            calls.append(msg)
    au._logger = _L()
    try:
        r = await authed_client.get('/platform/config/export/all')
        assert r.status_code == 200
        assert calls, 'Audit logger should be invoked'
    finally:
        au._logger = orig
