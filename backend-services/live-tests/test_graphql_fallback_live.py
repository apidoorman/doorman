import os
import pytest

# Enable by running with DOORMAN_RUN_LIVE=1
_RUN_LIVE = os.getenv('DOORMAN_RUN_LIVE', '0') in ('1', 'true', 'True')
if not _RUN_LIVE:
    pytestmark = pytest.mark.skip(reason='Requires live backend service; set DOORMAN_RUN_LIVE=1 to enable')


async def _setup(client, name='gllive', ver='v1'):
    await client.post('/platform/api', json={
        'api_name': name,
        'api_version': ver,
        'api_description': f'{name} {ver}',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': ['http://gql.up'],
        'api_type': 'REST',
        'api_allowed_retry_count': 0,
        'api_public': True,
    })
    await client.post('/platform/endpoint', json={
        'api_name': name,
        'api_version': ver,
        'endpoint_method': 'POST',
        'endpoint_uri': '/graphql',
        'endpoint_description': 'gql'
    })
    return name, ver


@pytest.mark.asyncio
async def test_graphql_client_fallback_to_httpx_live(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = await _setup(authed_client, name='gll1')
    class Dummy:
        pass
    class FakeHTTPResp:
        def __init__(self, payload):
            self._p = payload
        def json(self):
            return self._p
    class H:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def post(self, url, json=None, headers=None):
            return FakeHTTPResp({'ok': True})
    monkeypatch.setattr(gs, 'Client', Dummy)
    monkeypatch.setattr(gs.httpx, 'AsyncClient', H)
    r = await authed_client.post(f'/api/graphql/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'query': '{ ping }', 'variables': {}})
    assert r.status_code == 200 and r.json().get('ok') is True


@pytest.mark.asyncio
async def test_graphql_errors_live_strict_and_loose(monkeypatch, authed_client):
    import services.gateway_service as gs
    name, ver = await _setup(authed_client, name='gll2')
    class Dummy:
        pass
    class FakeHTTPResp:
        def __init__(self, payload):
            self._p = payload
        def json(self):
            return self._p
    class H:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def post(self, url, json=None, headers=None):
            return FakeHTTPResp({'errors': [{'message': 'boom'}]})
    monkeypatch.setattr(gs, 'Client', Dummy)
    monkeypatch.setattr(gs.httpx, 'AsyncClient', H)
    # Loose
    monkeypatch.delenv('STRICT_RESPONSE_ENVELOPE', raising=False)
    r1 = await authed_client.post(f'/api/graphql/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'query': '{ err }', 'variables': {}})
    assert r1.status_code == 200 and isinstance(r1.json().get('errors'), list)
    # Strict
    monkeypatch.setenv('STRICT_RESPONSE_ENVELOPE', 'true')
    r2 = await authed_client.post(f'/api/graphql/{name}', headers={'X-API-Version': ver, 'Content-Type': 'application/json'}, json={'query': '{ err }', 'variables': {}})
    assert r2.status_code == 200 and r2.json().get('status_code') == 200
