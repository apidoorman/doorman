import os

import pytest

_RUN_LIVE = os.getenv('DOORMAN_RUN_LIVE', '0') in ('1', 'true', 'True')
if not _RUN_LIVE:
    pytestmark = pytest.mark.skip(
        reason='Requires live backend service; set DOORMAN_RUN_LIVE=1 to enable'
    )


@pytest.mark.asyncio
async def test_soap_content_types_matrix(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    import services.gateway_service as gs

    name, ver = 'soapct', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'POST', '/s')
    await subscribe_self(authed_client, name, ver)

    class Resp:
        def __init__(self):
            self.status_code = 200
            self.headers = {'Content-Type': 'application/xml'}
            self.text = '<ok/>'

        def json(self):
            return {'ok': True}

    class HC:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json=None, params=None, headers=None, content=None):
            return Resp()

    monkeypatch.setattr(gs.httpx, 'AsyncClient', HC)
    for ct in ['application/xml', 'text/xml']:
        r = await authed_client.post(
            f'/api/soap/{name}/{ver}/s', headers={'Content-Type': ct}, content='<a/>'
        )
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_soap_retries_then_success(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self

    import services.gateway_service as gs

    name, ver = 'soaprt', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'POST', '/s')
    await subscribe_self(authed_client, name, ver)
    from utils.database import api_collection

    api_collection.update_one(
        {'api_name': name, 'api_version': ver}, {'$set': {'api_allowed_retry_count': 1}}
    )
    await authed_client.delete('/api/caches')

    class Resp:
        def __init__(self, status):
            self.status_code = status
            self.headers = {'Content-Type': 'application/xml'}
            self.text = '<ok/>'

        def json(self):
            return {'ok': True}

    seq = [Resp(503), Resp(200)]

    class HC:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json=None, params=None, headers=None, content=None):
            return seq.pop(0)

    monkeypatch.setattr(gs.httpx, 'AsyncClient', HC)
    r = await authed_client.post(
        f'/api/soap/{name}/{ver}/s', headers={'Content-Type': 'application/xml'}, content='<a/>'
    )
    assert r.status_code == 200
