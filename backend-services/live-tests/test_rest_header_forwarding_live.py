import os
import pytest

_RUN_LIVE = os.getenv('DOORMAN_RUN_LIVE', '0') in ('1', 'true', 'True')
if not _RUN_LIVE:
    pytestmark = pytest.mark.skip(reason='Requires live backend service; set DOORMAN_RUN_LIVE=1 to enable')


@pytest.mark.asyncio
async def test_forward_allowed_headers_only(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self
    import services.gateway_service as gs
    name, ver = 'hforw', 'v1'
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://up'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_allowed_headers': ['x-allowed', 'content-type']
    }
    await authed_client.post('/platform/api', json=payload)
    await create_endpoint(authed_client, name, ver, 'GET', '/p')
    await subscribe_self(authed_client, name, ver)

    class Resp:
        def __init__(self):
            self.status_code = 200
            self._p = {'ok': True}
            self.headers = {'Content-Type': 'application/json'}
            self.text = ''
        def json(self):
            return self._p
    captured = {}
    class CapClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def get(self, url, params=None, headers=None):
            captured['headers'] = headers or {}
            return Resp()
    monkeypatch.setattr(gs.httpx, 'AsyncClient', CapClient)
    await authed_client.get(f'/api/rest/{name}/{ver}/p', headers={'X-Allowed': 'yes', 'X-Blocked': 'no'})
    ch = {k.lower(): v for k, v in (captured.get('headers') or {}).items()}
    assert 'x-allowed' in ch and 'x-blocked' not in ch


@pytest.mark.asyncio
async def test_response_headers_filtered_by_allowlist(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self
    import services.gateway_service as gs
    name, ver = 'hresp', 'v1'
    payload = {
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://up'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_allowed_headers': ['x-upstream']
    }
    await authed_client.post('/platform/api', json=payload)
    await create_endpoint(authed_client, name, ver, 'GET', '/p')
    await subscribe_self(authed_client, name, ver)

    class Resp:
        def __init__(self):
            self.status_code = 200
            self._p = {'ok': True}
            self.headers = {'Content-Type': 'application/json', 'X-Upstream': 'yes', 'X-Secret': 'no'}
            self.text = ''
        def json(self):
            return self._p
    class HC:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def get(self, url, params=None, headers=None):
            return Resp()
    monkeypatch.setattr(gs.httpx, 'AsyncClient', HC)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/p')
    assert r.status_code == 200
    # Only X-Upstream forwarded back per allowlist
    assert r.headers.get('X-Upstream') == 'yes'
    assert 'X-Secret' not in r.headers
