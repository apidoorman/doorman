# External imports
import pytest

@pytest.mark.asyncio
async def test_unauthorized_access_rejected(client):

    me = await client.get('/platform/user/me')
    assert me.status_code in (401, 500)
