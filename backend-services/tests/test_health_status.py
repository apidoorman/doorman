# External imports
import pytest

@pytest.mark.asyncio
async def test_gateway_status(client):
    r = await client.get('/api/status')
    assert r.status_code in (200, 500)

