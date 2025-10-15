import pytest

@pytest.mark.asyncio
async def test_endpoint_create_requires_fields(authed_client):

    c = await authed_client.post('/platform/endpoint', json={'api_name': 'x'})
    assert c.status_code in (400, 422)

@pytest.mark.asyncio
async def test_endpoint_get_nonexistent(authed_client):
    g = await authed_client.get('/platform/endpoint/GET/na/v1/does/not/exist')
    assert g.status_code in (400, 404)

