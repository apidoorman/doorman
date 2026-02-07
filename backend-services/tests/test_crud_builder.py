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


@pytest.mark.asyncio
async def test_crud_builder_multi_table_bindings(authed_client):
    api_payload = {
        'api_name': 'multitable',
        'api_version': 'v1',
        'api_description': 'Multi-table CRUD API',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': [],
        'api_type': 'REST',
        'api_is_crud': True,
        'api_crud_collection': 'crud_data_multitable_customers',
        'api_crud_schema': {'name': {'type': 'string', 'required': True}},
        'api_crud_bindings': [
            {
                'resource_name': 'customers',
                'collection_name': 'crud_data_multitable_customers',
                'table_name': 'Customers',
                'schema': {'name': {'type': 'string', 'required': True}},
            },
            {
                'resource_name': 'orders',
                'collection_name': 'crud_data_multitable_orders',
                'table_name': 'Orders',
                'schema': {'order_no': {'type': 'string', 'required': True}},
            },
        ],
    }
    r = await authed_client.post('/platform/api', json=api_payload)
    assert r.status_code in (200, 201), r.text

    endpoints = [
        {'method': 'GET', 'uri': '/customers'},
        {'method': 'POST', 'uri': '/customers'},
        {'method': 'GET', 'uri': '/customers/{id}'},
        {'method': 'GET', 'uri': '/orders'},
        {'method': 'POST', 'uri': '/orders'},
        {'method': 'GET', 'uri': '/orders/{id}'},
    ]
    for ep in endpoints:
        ep_payload = {
            'api_name': 'multitable',
            'api_version': 'v1',
            'endpoint_method': ep['method'],
            'endpoint_uri': ep['uri'],
            'endpoint_description': f"CRUD {ep['method']} {ep['uri']}",
        }
        r = await authed_client.post('/platform/endpoint', json=ep_payload)
        assert r.status_code in (200, 201), r.text

    bad_customer = await authed_client.post('/api/rest/multitable/v1/customers', json={'foo': 'bar'})
    assert bad_customer.status_code == 400, bad_customer.text

    bad_order = await authed_client.post('/api/rest/multitable/v1/orders', json={'foo': 'bar'})
    assert bad_order.status_code == 400, bad_order.text

    created_customer = await authed_client.post(
        '/api/rest/multitable/v1/customers', json={'name': 'alice'}
    )
    assert created_customer.status_code == 201, created_customer.text

    created_order = await authed_client.post(
        '/api/rest/multitable/v1/orders', json={'order_no': 'SO-1001'}
    )
    assert created_order.status_code == 201, created_order.text

    customers = await authed_client.get('/api/rest/multitable/v1/customers')
    assert customers.status_code == 200, customers.text
    customer_items = customers.json().get('items') or []
    assert any(i.get('name') == 'alice' for i in customer_items)
    assert all('order_no' not in i for i in customer_items)

    orders = await authed_client.get('/api/rest/multitable/v1/orders')
    assert orders.status_code == 200, orders.text
    order_items = orders.json().get('items') or []
    assert any(i.get('order_no') == 'SO-1001' for i in order_items)
    assert all('name' not in i for i in order_items)


@pytest.mark.asyncio
async def test_crud_builder_custom_json_path_mapping(authed_client):
    api_payload = {
        'api_name': 'mappedjson',
        'api_version': 'v1',
        'api_description': 'CRUD API with nested JSON path mapping',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': [],
        'api_type': 'REST',
        'api_is_crud': True,
        'api_crud_collection': 'crud_data_mappedjson_customers',
        'api_crud_schema': {'full_name': {'type': 'string', 'required': True}},
        'api_crud_bindings': [
            {
                'resource_name': 'customers',
                'collection_name': 'crud_data_mappedjson_customers',
                'table_name': 'Customers',
                'schema': {
                    'full_name': {'type': 'string', 'required': True},
                    'age': {'type': 'number', 'required': False},
                },
                'field_mappings': [
                    {'field': 'full_name', 'request_path': 'profile.name', 'response_path': 'profile.name'},
                    {'field': 'age', 'request_path': 'meta.demographics.age', 'response_path': 'meta.demographics.age'},
                ],
            }
        ],
    }
    r = await authed_client.post('/platform/api', json=api_payload)
    assert r.status_code in (200, 201), r.text

    for method, uri in [('POST', '/customers'), ('GET', '/customers'), ('GET', '/customers/{id}')]:
        ep_payload = {
            'api_name': 'mappedjson',
            'api_version': 'v1',
            'endpoint_method': method,
            'endpoint_uri': uri,
            'endpoint_description': f"CRUD {method} {uri}",
        }
        r = await authed_client.post('/platform/endpoint', json=ep_payload)
        assert r.status_code in (200, 201), r.text

    created = await authed_client.post(
        '/api/rest/mappedjson/v1/customers',
        json={
            'profile': {'name': 'Ada Lovelace'},
            'meta': {'demographics': {'age': 36}},
        },
    )
    assert created.status_code == 201, created.text
    created_payload = created.json()
    assert created_payload.get('profile', {}).get('name') == 'Ada Lovelace'
    assert created_payload.get('meta', {}).get('demographics', {}).get('age') == 36
    assert created_payload.get('full_name') is None

    listed = await authed_client.get('/api/rest/mappedjson/v1/customers')
    assert listed.status_code == 200, listed.text
    items = listed.json().get('items') or []
    assert len(items) >= 1
    first = items[0]
    assert first.get('profile', {}).get('name') == 'Ada Lovelace'
    assert first.get('meta', {}).get('demographics', {}).get('age') == 36
    assert first.get('full_name') is None
