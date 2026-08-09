import pytest
import uuid

@pytest.mark.asyncio
async def test_crud_builder_flow(authed_client):
    # 1. Create a CRUD-enabled API
    api_payload = {
        'api_name': 'mydata',
        'api_version': 'v1',
        'api_description': 'Internal CRUD API',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': [], # No servers needed for CRUD
        'api_type': 'REST',
        'api_is_crud': True,
        'api_crud_collection': 'crud_data_mydata_test'
    }
    r = await authed_client.post('/platform/api', json=api_payload)
    assert r.status_code in (200, 201)

    # 2. Add endpoints for the CRUD API
    # We need to define the endpoints so the gateway allows the requests
    endpoints = [
        {'method': 'GET', 'uri': '/items'},
        {'method': 'POST', 'uri': '/items'},
        {'method': 'GET', 'uri': '/items/{id}'},
        {'method': 'PUT', 'uri': '/items/{id}'},
        {'method': 'DELETE', 'uri': '/items/{id}'},
    ]
    for ep in endpoints:
        ep_payload = {
            'api_name': 'mydata',
            'api_version': 'v1',
            'endpoint_method': ep['method'],
            'endpoint_uri': ep['uri'],
            'endpoint_description': f"CRUD {ep['method']} {ep['uri']}",
        }
        r = await authed_client.post('/platform/endpoint', json=ep_payload)
        assert r.status_code in (200, 201)

    # 3. Test POST (Create)
    item_payload = {'name': 'test-item', 'value': 123}
    r = await authed_client.post('/api/rest/mydata/v1/items', json=item_payload)
    assert r.status_code == 201
    created_item = r.json()
    assert created_item['name'] == 'test-item'
    item_id = created_item['_id']
    assert item_id is not None

    # 4. Test GET (List)
    r = await authed_client.get('/api/rest/mydata/v1/items')
    assert r.status_code == 200
    response_data = r.json()
    items = response_data.get('items', [])
    assert any(i['_id'] == item_id for i in items)

    # 5. Test GET (One)
    r = await authed_client.get(f'/api/rest/mydata/v1/items/{item_id}')
    assert r.status_code == 200
    item = r.json()
    assert item['_id'] == item_id
    assert item['name'] == 'test-item'

    # 6. Test PUT (Update)
    update_payload = {'name': 'updated-item', 'value': 456}
    r = await authed_client.put(f'/api/rest/mydata/v1/items/{item_id}', json=update_payload)
    assert r.status_code == 200
    updated_item = r.json()
    assert updated_item['name'] == 'updated-item'
    assert updated_item['value'] == 456

    # 7. Test DELETE
    r = await authed_client.delete(f'/api/rest/mydata/v1/items/{item_id}')
    assert r.status_code == 200
    # For DELETE, the response might be a message, not the deleted item
    response_data = r.json()
    assert 'message' in response_data or response_data.get('message')

    # 8. Verify deletion
    r = await authed_client.get(f'/api/rest/mydata/v1/items/{item_id}')
    assert r.status_code == 404
