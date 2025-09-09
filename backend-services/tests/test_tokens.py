import pytest


@pytest.mark.asyncio
async def test_token_def_and_user_tokens_flow(authed_client):
    # Grant token management to admin
    r = await authed_client.put(
        "/platform/role/admin",
        json={"manage_tokens": True},
    )
    assert r.status_code == 200

    # Create token definition
    td = await authed_client.post(
        "/platform/token",
        json={
            "api_token_group": "ai-group-1",
            "api_key": "K-123",
            "api_key_header": "X-API-Key",
            "token_tiers": [
                {"tier_name": "basic", "tokens": 10, "input_limit": 100, "output_limit": 100, "reset_frequency": "monthly"}
            ],
        },
    )
    assert td.status_code in (200, 201)

    # Add user tokens for admin
    ut = await authed_client.post(
        "/platform/token/admin",
        json={
            "username": "admin",
            "users_tokens": {
                "ai-group-1": {"tier_name": "basic", "available_tokens": 5}
            },
        },
    )
    assert ut.status_code == 200

    # List all user tokens
    allu = await authed_client.get("/platform/token/all?page=1&page_size=10")
    assert allu.status_code == 200

    # Get admin tokens
    gu = await authed_client.get("/platform/token/admin")
    assert gu.status_code == 200

    # Delete token definition
    dt = await authed_client.delete("/platform/token/ai-group-1")
    assert dt.status_code == 200

