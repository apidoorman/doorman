import pytest


@pytest.mark.asyncio
async def test_update_delete_nonexistent_api(authed_client):
    u = await authed_client.put("/platform/api/doesnot/v9", json={"api_description": "x"})
    assert u.status_code in (400, 404)

    d = await authed_client.delete("/platform/api/doesnot/v9")
    assert d.status_code in (400, 404)

