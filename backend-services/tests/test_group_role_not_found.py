import pytest


@pytest.mark.asyncio
async def test_group_and_role_not_found(authed_client):
    gg = await authed_client.get('/platform/group/not-a-group')
    assert gg.status_code in (400, 404)

    gr = await authed_client.get('/platform/role/not-a-role')
    assert gr.status_code in (400, 404)

    dg = await authed_client.delete('/platform/group/not-a-group')
    assert dg.status_code in (400, 404)

    dr = await authed_client.delete('/platform/role/not-a-role')
    assert dr.status_code in (400, 404)
