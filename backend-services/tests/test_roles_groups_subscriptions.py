import pytest


@pytest.mark.asyncio
async def test_roles_crud(authed_client):
    # Create role
    r = await authed_client.post(
        "/platform/role",
        json={
            "role_name": "qa",
            "role_description": "QA Role",
            "manage_users": False,
            "manage_apis": True,
            "manage_endpoints": True,
            "manage_groups": False,
            "manage_roles": False,
            "manage_routings": False,
            "manage_gateway": False,
            "manage_subscriptions": True,
            "manage_security": False,
            "view_logs": True,
            "export_logs": False,
        },
    )
    assert r.status_code in (200, 201)

    # Get role
    g = await authed_client.get("/platform/role/qa")
    assert g.status_code == 200

    # List roles
    roles = await authed_client.get("/platform/role/all")
    assert roles.status_code == 200

    # Update role
    u = await authed_client.put("/platform/role/qa", json={"manage_groups": True})
    assert u.status_code == 200

    # Delete role
    d = await authed_client.delete("/platform/role/qa")
    assert d.status_code == 200


@pytest.mark.asyncio
async def test_groups_crud(authed_client):
    # Create group
    cg = await authed_client.post(
        "/platform/group",
        json={"group_name": "qa-group", "group_description": "QA", "api_access": []},
    )
    assert cg.status_code in (200, 201)

    # Get group
    g = await authed_client.get("/platform/group/qa-group")
    assert g.status_code == 200

    # List groups
    lst = await authed_client.get("/platform/group/all")
    assert lst.status_code == 200

    # Update group
    ug = await authed_client.put(
        "/platform/group/qa-group", json={"group_description": "Quality Group"}
    )
    assert ug.status_code == 200

    # Delete group
    dg = await authed_client.delete("/platform/group/qa-group")
    assert dg.status_code == 200


@pytest.mark.asyncio
async def test_subscriptions_flow(authed_client):
    # Prepare API to subscribe to
    api_payload = {
        "api_name": "orders",
        "api_version": "v1",
        "api_description": "Orders API",
        "api_allowed_roles": ["admin"],
        "api_allowed_groups": ["ALL"],
        "api_servers": ["http://upstream.local"],
        "api_type": "REST",
        "api_allowed_retry_count": 0,
    }
    c = await authed_client.post("/platform/api", json=api_payload)
    assert c.status_code in (200, 201)

    # Subscribe admin to orders/v1
    s = await authed_client.post(
        "/platform/subscription/subscribe",
        json={"username": "admin", "api_name": "orders", "api_version": "v1"},
    )
    assert s.status_code in (200, 201)

    # List subscriptions for current user
    ls = await authed_client.get("/platform/subscription/subscriptions")
    assert ls.status_code == 200
    subs = ls.json().get("subscriptions", {})
    apis = subs.get("apis") or []
    assert "orders/v1" in apis or "echo/v1" in apis

    # Unsubscribe
    us = await authed_client.post(
        "/platform/subscription/unsubscribe",
        json={"username": "admin", "api_name": "orders", "api_version": "v1"},
    )
    assert us.status_code in (200, 400)
