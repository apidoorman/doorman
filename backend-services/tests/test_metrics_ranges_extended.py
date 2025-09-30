# External imports
import pytest

@pytest.mark.asyncio
async def test_metrics_range_parameters(monkeypatch, authed_client):
    from conftest import create_api, create_endpoint, subscribe_self
    name, ver = 'mrange', 'v1'
    await create_api(authed_client, name, ver)
    await create_endpoint(authed_client, name, ver, 'GET', '/p')
    await subscribe_self(authed_client, name, ver)

    import services.gateway_service as gs
    class _FakeHTTPResponse:
        def __init__(self):
            self.status_code = 200
            self.headers = {'Content-Type': 'application/json'}
            self.text = '{}'
            self.content = b'{}'
        def json(self): return {'ok': True}
    class _FakeAsyncClient:
        def __init__(self, timeout=None): pass
        async def __aenter__(self): return self
        async def __aexit__(self, exc_type, exc, tb): return False
        async def get(self, url, params=None, headers=None): return _FakeHTTPResponse()
    monkeypatch.setattr(gs.httpx, 'AsyncClient', _FakeAsyncClient)

    await authed_client.get(f'/api/rest/{name}/{ver}/p')

    for rg in ('1h', '24h', '7d', '30d'):
        r = await authed_client.get(f'/platform/monitor/metrics?range={rg}')
        assert r.status_code == 200
        try:
            j = r.json()
        except Exception:
            j = {}
        data = j.get('response', j)
        assert isinstance(data, dict)
        if 'series' in data:
            assert isinstance(data.get('series'), list)
        if 'status_counts' in data:
            assert isinstance(data.get('status_counts'), dict)
