import pytest


@pytest.mark.asyncio
async def test_large_response_is_compressed(authed_client):
    # Export all config typically returns a payload above compression threshold.
    r = await authed_client.get('/platform/config/export/all')
    assert r.status_code == 200
    ce = (r.headers.get('content-encoding') or '').lower()
    assert ce == 'gzip'
