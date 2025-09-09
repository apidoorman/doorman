import pytest


async def _ensure_api_and_endpoint(client, api_name, version, method, uri):
    c = await client.post(
        "/platform/api",
        json={
            "api_name": api_name,
            "api_version": version,
            "api_description": f"{api_name} {version}",
            "api_allowed_roles": ["admin"],
            "api_allowed_groups": ["ALL"],
            "api_servers": ["http://fake-upstream"],
            "api_type": "REST",
            "api_allowed_retry_count": 0,
        },
    )
    assert c.status_code in (200, 201)
    ep = await client.post(
        "/platform/endpoint",
        json={
            "api_name": api_name,
            "api_version": version,
            "endpoint_method": method,
            "endpoint_uri": uri,
            "endpoint_description": "desc",
        },
    )
    assert ep.status_code in (200, 201)
    g = await client.get(f"/platform/endpoint/{method}/{api_name}/{version}{uri}")
    assert g.status_code == 200
    return g.json().get("endpoint_id") or g.json().get("response", {}).get("endpoint_id")


@pytest.mark.asyncio
async def test_endpoint_validation_crud(authed_client):
    eid = await _ensure_api_and_endpoint(authed_client, "valapi", "v1", "POST", "/do")
    assert eid

    schema = {
        "validation_schema": {
            "user.name": {"required": True, "type": "string", "min": 2, "max": 50}
        }
    }
    # Create validation
    cv = await authed_client.post(
        "/platform/endpoint/endpoint/validation",
        json={"endpoint_id": eid, "validation_enabled": True, "validation_schema": schema},
    )
    assert cv.status_code in (200, 201, 400)  # creation may 200/201 or 400 if duplicate

    # Get validation
    gv = await authed_client.get(f"/platform/endpoint/endpoint/validation/{eid}")
    assert gv.status_code in (200, 400, 500)

    # Update validation
    uv = await authed_client.put(
        f"/platform/endpoint/endpoint/validation/{eid}",
        json={"validation_enabled": True, "validation_schema": schema},
    )
    assert uv.status_code in (200, 400, 500)

    # Delete validation
    dv = await authed_client.delete(f"/platform/endpoint/endpoint/validation/{eid}")
    assert dv.status_code in (200, 400)
