import pytest

from utils.async_db import db_insert_one
from utils.database_async import db as async_db


@pytest.mark.asyncio
async def test_api_builder_tables_only_show_crud_builder_collections(authed_client):
    grant = await authed_client.put('/platform/role/admin', json={'view_builder_tables': True})
    assert grant.status_code in (200, 201), grant.text

    collection_name = 'crud_data_builder_tables_test'
    create_api = await authed_client.post(
        '/platform/api',
        json={
            'api_name': 'builder-tables',
            'api_version': 'v1',
            'api_description': 'CRUD API for table explorer test',
            'api_allowed_roles': ['admin'],
            'api_allowed_groups': ['ALL'],
            'api_servers': [],
            'api_type': 'REST',
            'api_is_crud': True,
            'api_crud_collection': collection_name,
        },
    )
    assert create_api.status_code in (200, 201), create_api.text

    for method, uri in [('POST', '/items'), ('GET', '/items')]:
        create_ep = await authed_client.post(
            '/platform/endpoint',
            json={
                'api_name': 'builder-tables',
                'api_version': 'v1',
                'endpoint_method': method,
                'endpoint_uri': uri,
                'endpoint_description': f'{method} {uri}',
            },
        )
        assert create_ep.status_code in (200, 201), create_ep.text

    created = await authed_client.post(
        '/api/rest/builder-tables/v1/items', json={'name': 'test-row', 'value': 123}
    )
    assert created.status_code == 201, created.text

    manual_collection = async_db.get_collection('manual_collection_not_builder')
    await db_insert_one(manual_collection, {'_id': 'manual-1', 'name': 'manual-doc'})

    list_tables = await authed_client.get('/platform/api-builder/tables')
    assert list_tables.status_code == 200, list_tables.text
    payload = list_tables.json()
    names = {t['collection_name'] for t in payload.get('tables', [])}

    assert collection_name in names
    assert 'manual_collection_not_builder' not in names

    rows = await authed_client.get(f'/platform/api-builder/tables/{collection_name}')
    assert rows.status_code == 200, rows.text
    items = rows.json().get('items') or []
    assert any(i.get('name') == 'test-row' for i in items)

    not_builder = await authed_client.get('/platform/api-builder/tables/manual_collection_not_builder')
    assert not_builder.status_code == 404


@pytest.mark.asyncio
async def test_table_registry_create_and_list_flow(authed_client):
    grant = await authed_client.put('/platform/role/admin', json={'view_builder_tables': True})
    assert grant.status_code in (200, 201), grant.text

    create_table = await authed_client.post(
        '/platform/api-builder/tables',
        json={
            'table_name': 'Customer Data',
            'schema': {
                'name': {'type': 'string', 'required': True},
                'age': {'type': 'number', 'required': False},
            },
        },
    )
    assert create_table.status_code == 201, create_table.text
    created = create_table.json().get('table') or {}
    collection_name = created.get('collection_name')
    assert collection_name
    assert collection_name.startswith('crud_data_customer_data')

    duplicate = await authed_client.post(
        '/platform/api-builder/tables',
        json={
            'table_name': 'Customer Data',
            'collection_name': collection_name,
            'schema': {'name': {'type': 'string'}},
        },
    )
    assert duplicate.status_code == 409, duplicate.text

    list_tables = await authed_client.get('/platform/api-builder/tables')
    assert list_tables.status_code == 200, list_tables.text
    payload = list_tables.json()
    tables = payload.get('tables', [])
    matching = [t for t in tables if t.get('collection_name') == collection_name]
    assert matching, payload
    assert matching[0].get('table_name') == 'Customer Data'
    assert set(matching[0].get('fields') or []) == {'name', 'age'}

    rows = await authed_client.get(f'/platform/api-builder/tables/{collection_name}')
    assert rows.status_code == 200, rows.text
    row_payload = rows.json()
    assert row_payload.get('collection_name') == collection_name
    assert row_payload.get('items') == []


@pytest.mark.asyncio
async def test_api_builder_tables_permission_required(authed_client):
    revoke = await authed_client.put('/platform/role/admin', json={'view_builder_tables': False})
    assert revoke.status_code in (200, 201), revoke.text

    denied = await authed_client.get('/platform/api-builder/tables')
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_table_registry_update_query_and_delete_flow(authed_client):
    grant = await authed_client.put('/platform/role/admin', json={'view_builder_tables': True})
    assert grant.status_code in (200, 201), grant.text

    create_table = await authed_client.post(
        '/platform/api-builder/tables',
        json={
            'table_name': 'Products',
            'schema': {
                'name': {'type': 'string', 'required': True},
                'price': {'type': 'number', 'required': False},
            },
        },
    )
    assert create_table.status_code == 201, create_table.text
    collection_name = (create_table.json().get('table') or {}).get('collection_name')
    assert collection_name

    update_table = await authed_client.put(
        f'/platform/api-builder/tables/{collection_name}',
        json={
            'table_name': 'Products Catalog',
            'schema': {
                'name': {'type': 'string', 'required': True},
                'price': {'type': 'number', 'required': False},
                'category': {'type': 'string', 'required': False},
            },
        },
    )
    assert update_table.status_code == 200, update_table.text
    updated_doc = update_table.json().get('table') or {}
    assert updated_doc.get('table_name') == 'Products Catalog'
    assert set(updated_doc.get('fields') or []) == {'name', 'price', 'category'}

    coll = async_db.get_collection(collection_name)
    await db_insert_one(coll, {'_id': 'p1', 'name': 'Mouse', 'price': 25, 'category': 'Accessories'})
    await db_insert_one(coll, {'_id': 'p2', 'name': 'Keyboard', 'price': 100, 'category': 'Accessories'})
    await db_insert_one(coll, {'_id': 'p3', 'name': 'Laptop', 'price': 1400, 'category': 'Computers'})

    queried = await authed_client.post(
        f'/platform/api-builder/tables/{collection_name}/query',
        json={
            'search': 'top',
            'filters': [
                {'field': 'price', 'op': 'gt', 'value': 200},
            ],
            'sort_by': 'price',
            'sort_order': 'desc',
            'page': 1,
            'page_size': 10,
        },
    )
    assert queried.status_code == 200, queried.text
    query_payload = queried.json()
    items = query_payload.get('items') or []
    assert len(items) == 1
    assert items[0].get('name') == 'Laptop'

    deleted = await authed_client.delete(
        f'/platform/api-builder/tables/{collection_name}',
        json={'drop_data': True},
    )
    assert deleted.status_code == 200, deleted.text

    list_tables = await authed_client.get('/platform/api-builder/tables')
    assert list_tables.status_code == 200, list_tables.text
    names = {t.get('collection_name') for t in (list_tables.json().get('tables') or [])}
    assert collection_name not in names


@pytest.mark.asyncio
async def test_table_registry_allows_empty_schema(authed_client):
    grant = await authed_client.put('/platform/role/admin', json={'view_builder_tables': True})
    assert grant.status_code in (200, 201), grant.text

    create_table = await authed_client.post(
        '/platform/api-builder/tables',
        json={
            'table_name': 'Schema Optional Table',
            'schema': {},
        },
    )
    assert create_table.status_code == 201, create_table.text
    created = create_table.json().get('table') or {}
    assert created.get('schema') == {}
    assert created.get('fields') == []
