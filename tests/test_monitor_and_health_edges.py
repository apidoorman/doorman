import pytest

@pytest.mark.asyncio
async def test_status_includes_uptime_and_memory_usage(authed_client):
    r = await authed_client.get('/api/status')
    assert r.status_code == 200
    body = r.json().get('response', r.json())
    assert 'uptime' in body and isinstance(body['uptime'], str)
    assert 'memory_usage' in body and isinstance(body['memory_usage'], str)

@pytest.mark.asyncio
async def test_status_handles_missing_dependency_gracefully(monkeypatch, authed_client):
    import routes.gateway_routes as gw
    async def _false():
        return False
    monkeypatch.setattr(gw, 'check_mongodb', _false, raising=True)
    monkeypatch.setattr(gw, 'check_redis', _false, raising=True)

    r = await authed_client.get('/api/status')
    assert r.status_code == 200
    body = r.json().get('response', r.json())
    assert body.get('mongodb') is False
    assert body.get('redis') is False

@pytest.mark.asyncio
async def test_metrics_store_records_request_and_response_sizes(monkeypatch, authed_client):
    m0 = await authed_client.get('/platform/monitor/metrics')
    assert m0.status_code == 200
    j0 = m0.json().get('response', m0.json())
    tout0 = int(j0.get('total_bytes_out', 0))

    r1 = await authed_client.get('/api/status')
    r2 = await authed_client.get('/api/status')
    assert r1.status_code == 200 and r2.status_code == 200

    m1 = await authed_client.get('/platform/monitor/metrics')
    assert m1.status_code == 200
    j1 = m1.json().get('response', m1.json())
    tout1 = int(j1.get('total_bytes_out', 0))
    assert tout1 > tout0
