import pytest


@pytest.mark.asyncio
async def test_multi_endpoints_per_api_and_listing(authed_client):
    # Create API
    c = await authed_client.post(
        "/platform/api",
        json={
            "api_name": "multi",
            "api_version": "v1",
            "api_description": "multi api",
            "api_allowed_roles": ["admin"],
            "api_allowed_groups": ["ALL"],
            "api_servers": ["http://up"],
            "api_type": "REST",
            "api_allowed_retry_count": 0,
        },
    )
    assert c.status_code in (200, 201)

    # Add several endpoints
    endpoints = [
        ("GET", "/a"),
        ("POST", "/b"),
        ("PUT", "/c"),
    ]
    for method, uri in endpoints:
        ep = await authed_client.post(
            "/platform/endpoint",
            json={
                "api_name": "multi",
                "api_version": "v1",
                "endpoint_method": method,
                "endpoint_uri": uri,
                "endpoint_description": f"{method} {uri}",
            },
        )
        assert ep.status_code in (200, 201)

    # List all endpoints for API
    le = await authed_client.get("/platform/endpoint/multi/v1")
    assert le.status_code == 200
    items = le.json()
    if isinstance(items, dict) and 'endpoints' in items:
        items = items['endpoints']
    assert isinstance(items, list)
    assert len(items) >= 3
