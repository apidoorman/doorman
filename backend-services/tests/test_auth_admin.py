import pytest


@pytest.mark.asyncio
async def test_auth_admin_endpoints(authed_client):
    # Ensure admin has manage_auth permission
    r = await authed_client.put(
        "/platform/role/admin",
        json={"manage_auth": True},
    )
    assert r.status_code == 200, r.text

    # Re-authenticate to get a token with updated permissions
    relog = await authed_client.post(
        "/platform/authorization",
        json={"email": "admin@doorman.dev", "password": "password1"},
    )
    assert relog.status_code == 200, relog.text

    # Create a target user to operate on
    create = await authed_client.post(
        "/platform/user",
        json={
            "username": "qa_auth",
            "email": "qa_auth@example.com",
            "password": "VerySecurePassword!123",
            "role": "admin",
            "groups": ["ALL"],
            "active": True
        },
    )
    assert create.status_code in (200, 201), create.text

    # Initial status
    st = await authed_client.get("/platform/authorization/admin/status/qa_auth")
    assert st.status_code == 200, st.text
    payload = st.json().get("response") or st.json()
    assert payload.get("active") is True
    assert payload.get("revoked") is False

    # Revoke all tokens for the user
    rv = await authed_client.post("/platform/authorization/admin/revoke/qa_auth")
    assert rv.status_code == 200, rv.text
    st2 = await authed_client.get("/platform/authorization/admin/status/qa_auth")
    assert st2.status_code == 200
    p2 = st2.json().get("response") or st2.json()
    assert p2.get("revoked") is True

    # Disable user
    dis = await authed_client.post("/platform/authorization/admin/disable/qa_auth")
    assert dis.status_code == 200, dis.text
    st3 = await authed_client.get("/platform/authorization/admin/status/qa_auth")
    assert st3.status_code == 200
    p3 = st3.json().get("response") or st3.json()
    assert p3.get("active") is False
    assert p3.get("revoked") is True

    # Enable user (revoked remains True until cleared)
    en = await authed_client.post("/platform/authorization/admin/enable/qa_auth")
    assert en.status_code == 200, en.text
    st4 = await authed_client.get("/platform/authorization/admin/status/qa_auth")
    assert st4.status_code == 200
    p4 = st4.json().get("response") or st4.json()
    assert p4.get("active") is True

    # Clear revocation
    ur = await authed_client.post("/platform/authorization/admin/unrevoke/qa_auth")
    assert ur.status_code == 200, ur.text
    st5 = await authed_client.get("/platform/authorization/admin/status/qa_auth")
    assert st5.status_code == 200
    p5 = st5.json().get("response") or st5.json()
    assert p5.get("revoked") is False
