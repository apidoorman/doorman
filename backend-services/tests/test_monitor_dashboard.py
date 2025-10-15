import pytest

@pytest.mark.asyncio
async def test_monitor_metrics_and_dashboard(authed_client):

    d = await authed_client.get('/platform/dashboard')
    assert d.status_code == 200
    dj = d.json()
    assert 'activeUsers' in dj and 'newApis' in dj

    m = await authed_client.get('/platform/monitor/metrics?range=24h')
    assert m.status_code == 200
    mj = m.json()
    assert isinstance(mj, dict)

@pytest.mark.asyncio
async def test_liveness_and_readiness(client):
    l = await client.get('/platform/monitor/liveness')
    assert l.status_code == 200
    r = await client.get('/platform/monitor/readiness')
    assert r.status_code == 200
