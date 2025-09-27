import uuid
import pytest


@pytest.mark.asyncio
async def test_admin_can_view_admin_role_and_user(authed_client):
    # Admin should see the admin role by name
    r_role = await authed_client.get("/platform/role/admin")
    assert r_role.status_code == 200, r_role.text
    role = r_role.json()
    assert (role.get("response") or role).get("role_name") in ("admin",)

    # Admin should list roles and include admin
    r_roles = await authed_client.get("/platform/role/all?page=1&page_size=50")
    assert r_roles.status_code == 200
    roles = r_roles.json().get("roles") or r_roles.json().get("response", {}).get("roles") or []
    names = { (r.get("role_name") or "").lower() for r in roles }
    assert "admin" in names

    # Admin should see the admin user
    r_user = await authed_client.get("/platform/user/admin")
    assert r_user.status_code == 200, r_user.text
    u = r_user.json().get("response") or r_user.json()
    assert (u.get("username") or u.get("response", {}).get("username")) in ("admin",)


@pytest.mark.asyncio
async def test_admin_can_update_admin_role_description(authed_client):
    # Update a non-sensitive field on admin role
    desc = f"Administrator role ({uuid.uuid4().hex[:6]})"
    up = await authed_client.put("/platform/role/admin", json={"role_description": desc})
    assert up.status_code in (200, 201), up.text
    # Fetch and verify
    r = await authed_client.get("/platform/role/admin")
    assert r.status_code == 200
    body = r.json().get("response") or r.json()
    assert body.get("role_description") == desc


@pytest.mark.asyncio
async def test_admin_can_create_and_delete_admin_user(authed_client):
    uname = f"adm_{uuid.uuid4().hex[:8]}"
    create = await authed_client.post(
        "/platform/user",
        json={
            "username": uname,
            "email": f"{uname}@example.com",
            "password": "StrongAdmPwd!1234",
            "role": "admin",
            "groups": ["ALL", "admin"],
            "active": True,
            "ui_access": True,
        },
    )
    assert create.status_code in (200, 201), create.text

    # Verify visible
    r = await authed_client.get(f"/platform/user/{uname}")
    assert r.status_code == 200

    # Delete
    d = await authed_client.delete(f"/platform/user/{uname}")
    assert d.status_code in (200, 204)

    # Confirm gone
    r2 = await authed_client.get(f"/platform/user/{uname}")
    assert r2.status_code in (404, 500)

