import pytest

@pytest.mark.asyncio
async def test_refresh_requires_auth(client):
    r = await client.post('/platform/authorization/refresh')
    assert r.status_code == 401

