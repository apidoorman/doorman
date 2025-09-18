import pytest


@pytest.mark.asyncio
async def test_grpc_requires_version_header(authed_client):
    # Call gRPC passthrough without X-API-Version should fail fast with 400
    r = await authed_client.post("/api/grpc/service/do", json={"data": "{}"})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_graphql_requires_version_header(authed_client):
    # Already covered elsewhere but keep an explicit check here
    r = await authed_client.post("/api/graphql/graph", json={"query": "{ ping }"})
    assert r.status_code == 400

