import pytest


@pytest.mark.asyncio
async def test_public_health_probe_ok(client):
    r = await client.get('/api/health')
    assert r.status_code == 200
    body = r.json().get('response', r.json())
    assert body.get('status') in ('online', 'healthy', 'ready')


@pytest.mark.asyncio
async def test_status_requires_auth(client):
    try:
        client.cookies.clear()
    except Exception:
        pass
    r = await client.get('/api/status')
    assert r.status_code in (401, 403)
