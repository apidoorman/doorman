import os
import pytest

_RUN_LIVE = os.getenv('DOORMAN_RUN_LIVE', '0') in ('1', 'true', 'True')
if not _RUN_LIVE:
    pytestmark = pytest.mark.skip(reason='Requires live backend service; set DOORMAN_RUN_LIVE=1 to enable')

from tests.test_gateway_routing_limits import _FakeAsyncClient


@pytest.mark.asyncio
async def test_rest_retries_on_500_then_success(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self
    import services.gateway_service as gs
    name, ver = 'rlive500', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/r')
    await subscribe_self(authed_client, name, ver)

    # Set retry count to 1
    from utils.database import api_collection
    api_collection.update_one({'api_name': name, 'api_version': ver}, {'$set': {'api_allowed_retry_count': 1}})
    await authed_client.delete('/api/caches')

    class Resp:
        def __init__(self, status, body=None, headers=None):
            self.status_code = status
            self._json = body or {}
            self.text = ''
            self.headers = headers or {'Content-Type': 'application/json'}
        def json(self):
            return self._json
    seq = [Resp(500), Resp(200, {'ok': True})]
    class SeqClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def get(self, url, params=None, headers=None):
            return seq.pop(0)
    monkeypatch.setattr(gs.httpx, 'AsyncClient', SeqClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/r')
    assert r.status_code == 200 and r.json().get('ok') is True


@pytest.mark.asyncio
async def test_rest_retries_on_503_then_success(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self
    import services.gateway_service as gs
    name, ver = 'rlive503', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/r')
    await subscribe_self(authed_client, name, ver)
    from utils.database import api_collection
    api_collection.update_one({'api_name': name, 'api_version': ver}, {'$set': {'api_allowed_retry_count': 1}})
    await authed_client.delete('/api/caches')

    class Resp:
        def __init__(self, status):
            self.status_code = status
            self.headers = {'Content-Type': 'application/json'}
            self.text = ''
        def json(self):
            return {}
    seq = [Resp(503), Resp(200)]
    class SeqClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def get(self, url, params=None, headers=None):
            return seq.pop(0)
    monkeypatch.setattr(gs.httpx, 'AsyncClient', SeqClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/r')
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_rest_no_retry_when_retry_count_zero(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self
    import services.gateway_service as gs
    name, ver = 'rlivez0', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/r')
    await subscribe_self(authed_client, name, ver)
    await authed_client.delete('/api/caches')
    class Resp:
        def __init__(self, status):
            self.status_code = status
            self.headers = {'Content-Type': 'application/json'}
            self.text = ''
        def json(self):
            return {}
    class OneClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def get(self, url, params=None, headers=None):
            return Resp(500)
    monkeypatch.setattr(gs.httpx, 'AsyncClient', OneClient)
    r = await authed_client.get(f'/api/rest/{name}/{ver}/r')
    assert r.status_code == 500
