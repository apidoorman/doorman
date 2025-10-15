import pytest

@pytest.mark.asyncio
async def test_grpc_requires_version_header(authed_client):

    r = await authed_client.post('/api/grpc/service/do', json={'data': '{}'})
    assert r.status_code == 400

@pytest.mark.asyncio
async def test_graphql_requires_version_header(authed_client):

    r = await authed_client.post('/api/graphql/graph', json={'query': '{ ping }'})
    assert r.status_code == 400

