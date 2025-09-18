import pytest


@pytest.mark.asyncio
async def test_clear_caches_requires_manage_gateway(authed_client):
    # Ensure permission is disabled
    rd = await authed_client.put(
        "/platform/role/admin",
        json={"manage_gateway": False},
    )
    assert rd.status_code in (200, 201)

    deny = await authed_client.delete("/api/caches")
    assert deny.status_code == 403

    # Enable and retry
    re = await authed_client.put(
        "/platform/role/admin",
        json={"manage_gateway": True},
    )
    assert re.status_code in (200, 201)
    ok = await authed_client.delete("/api/caches")
    assert ok.status_code == 200

