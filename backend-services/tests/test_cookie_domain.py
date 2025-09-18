import os
import pytest


@pytest.mark.asyncio
async def test_cookie_domain_set_on_login(client, monkeypatch):
    # Ensure domain matches test base host so cookie jar respects it
    monkeypatch.setenv("COOKIE_DOMAIN", "testserver")
    resp = await client.post(
        "/platform/authorization",
        json={
            "email": os.environ["STARTUP_ADMIN_EMAIL"],
            "password": os.environ["STARTUP_ADMIN_PASSWORD"],
        },
    )
    assert resp.status_code == 200
    # Validate cookie set with domain attribute
    cookies = [c for c in client.cookies.jar if c.name == "access_token_cookie"]
    assert cookies, "Auth cookie missing"
    assert cookies[0].domain in ("testserver", ".testserver")
