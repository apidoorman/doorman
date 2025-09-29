import pytest


@pytest.mark.asyncio
async def test_rest_public_api_allows_unauthenticated(client, authed_client):
    # Create a public REST API and endpoint using authed client
    name, ver = "pubrest", "v1"
    cr = await authed_client.post(
        "/platform/api",
        json={
            "api_name": name,
            "api_version": ver,
            "api_description": "Public REST API",
            "api_servers": ["http://upstream.invalid"],
            "api_type": "REST",
            "api_public": True,
        },
    )
    assert cr.status_code in (200, 201), cr.text
    ce = await authed_client.post(
        "/platform/endpoint",
        json={
            "api_name": name,
            "api_version": ver,
            "endpoint_method": "GET",
            "endpoint_uri": "/ping",
            "endpoint_description": "ping",
        },
    )
    assert ce.status_code in (200, 201), ce.text

    # Call gateway without authentication
    r = await client.get(f"/api/rest/{name}/{ver}/ping")
    # Should not be blocked by 401/403 auth checks
    assert r.status_code in (200, 400, 404, 429, 500)


@pytest.mark.asyncio
async def test_graphql_public_api_allows_unauthenticated(client, authed_client):
    name, ver = "pubgql", "v1"
    cr = await authed_client.post(
        "/platform/api",
        json={
            "api_name": name,
            "api_version": ver,
            "api_description": "Public GraphQL API",
            "api_servers": ["http://upstream.invalid"],
            "api_type": "GRAPHQL",
            "api_public": True,
        },
    )
    assert cr.status_code in (200, 201), cr.text

    # No need to create endpoint for GraphQL pre-check
    # Call gateway without authentication
    r = await client.post(
        f"/api/graphql/{name}",
        headers={"X-API-Version": ver, "Content-Type": "application/json"},
        json={"query": "{ ping }"},
    )
    assert r.status_code in (200, 400, 404, 429, 500)


@pytest.mark.asyncio
async def test_public_api_bypasses_credits_check(client, authed_client):
    name, ver = "pubcredits", "v1"
    cr = await authed_client.post(
        "/platform/api",
        json={
            "api_name": name,
            "api_version": ver,
            "api_description": "Public REST with credits",
            "api_servers": ["http://upstream.invalid"],
            "api_type": "REST",
            "api_public": True,
            "api_credits_enabled": True,
            "api_credit_group": "any-group",
        },
    )
    assert cr.status_code in (200, 201), cr.text
    ce = await authed_client.post(
        "/platform/endpoint",
        json={
            "api_name": name,
            "api_version": ver,
            "endpoint_method": "GET",
            "endpoint_uri": "/ping",
            "endpoint_description": "ping",
        },
    )
    assert ce.status_code in (200, 201), ce.text

    r = await client.get(f"/api/rest/{name}/{ver}/ping")
    # Should not 401 due to credits check since API is public
    assert r.status_code != 401


@pytest.mark.asyncio
async def test_auth_not_required_but_not_public(client, authed_client):
    name, ver = "noauthsub", "v1"
    # Create API with auth not required but not public
    cr = await authed_client.post(
        "/platform/api",
        json={
            "api_name": name,
            "api_version": ver,
            "api_description": "Auth not required",
            "api_servers": ["http://upstream.invalid"],
            "api_type": "REST",
            "api_public": False,
            "api_auth_required": False,
        },
    )
    assert cr.status_code in (200, 201), cr.text
    ce = await authed_client.post(
        "/platform/endpoint",
        json={
            "api_name": name,
            "api_version": ver,
            "endpoint_method": "GET",
            "endpoint_uri": "/ping",
            "endpoint_description": "ping",
        },
    )
    assert ce.status_code in (200, 201), ce.text

    # Can call without auth, but not public; our current behavior allows it without JWT
    r = await client.get(f"/api/rest/{name}/{ver}/ping")
    assert r.status_code in (200, 400, 404, 429, 500)
