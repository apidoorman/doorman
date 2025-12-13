import pytest


@pytest.mark.asyncio
async def test_monitor_liveness_readiness_metrics(authed_client):
    # Liveness
    l = await authed_client.get('/platform/monitor/liveness')
    assert l.status_code in (200, 204)
    # Readiness
    r = await authed_client.get('/platform/monitor/readiness')
    assert r.status_code in (200, 204)
    # Metrics
    m = await authed_client.get('/platform/monitor/metrics')
    assert m.status_code in (200, 204)
