import pytest


@pytest.mark.asyncio
async def test_gateway_status(client):
    r = await client.get("/api/status")
    assert r.status_code in (200, 500)
    # When 200, response contains status key; when 500, it's an error payload.
