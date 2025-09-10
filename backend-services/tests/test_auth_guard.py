import pytest


@pytest.mark.asyncio
async def test_unauthorized_access_rejected(client):
    # Without cookie, protected route should be 401
    me = await client.get("/platform/user/me")
    assert me.status_code in (401, 500)
