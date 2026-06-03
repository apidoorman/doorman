import json
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from utils.async_db import db_insert_one
from utils.database_async import db as async_db


def _unique(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:8]}'


async def _create_table(authed_client, *, schema=None, rules=None):
    collection_name = f'crud_data_{_unique("table")}'
    payload = {
        'table_name': collection_name,
        'collection_name': collection_name,
        'schema': schema if schema is not None else {'name': {'type': 'string'}},
    }
    if rules is not None:
        payload['rules'] = rules
    response = await authed_client.post('/platform/api-builder/tables', json=payload)
    assert response.status_code == 201, response.text
    return collection_name


async def _create_crud_api(authed_client, collection_name: str):
    api_name = _unique('rulesapi')
    api_payload = {
        'api_name': api_name,
        'api_version': 'v1',
        'api_description': 'rules api',
        'api_allowed_roles': ['admin'],
        'api_allowed_groups': ['ALL'],
        'api_servers': [],
        'api_type': 'REST',
        'api_is_crud': True,
        'api_crud_collection': collection_name,
        'api_crud_schema': {
            'name': {'type': 'string', 'required': True},
            'owner': {'type': 'string', 'required': True},
        },
    }
    response = await authed_client.post('/platform/api', json=api_payload)
    assert response.status_code in (200, 201), response.text

    for method, uri in [
        ('POST', '/items'),
        ('GET', '/items'),
        ('GET', '/items/{id}'),
    ]:
        endpoint = await authed_client.post(
            '/platform/endpoint',
            json={
                'api_name': api_name,
                'api_version': 'v1',
                'endpoint_method': method,
                'endpoint_uri': uri,
                'endpoint_description': f'{method} {uri}',
            },
        )
        assert endpoint.status_code in (200, 201), endpoint.text
    return api_name


@pytest.mark.asyncio
async def test_crud_table_rules_allow_deny_and_owner_resource_rule(authed_client):
    collection_name = await _create_table(
        authed_client,
        schema={
            'name': {'type': 'string', 'required': True},
            'owner': {'type': 'string', 'required': True},
        },
        rules={
            'create': 'request.resource.data.owner == auth.uid',
            'list': "auth.uid == 'admin'",
            'read': 'resource.data.owner == auth.uid',
        },
    )
    api_name = await _create_crud_api(authed_client, collection_name)

    denied = await authed_client.post(
        f'/api/rest/{api_name}/v1/items',
        json={'name': 'denied', 'owner': 'someone-else'},
    )
    assert denied.status_code == 403, denied.text

    created = await authed_client.post(
        f'/api/rest/{api_name}/v1/items',
        json={'name': 'allowed', 'owner': 'admin'},
    )
    assert created.status_code == 201, created.text
    item_id = created.json().get('_id')

    readable = await authed_client.get(f'/api/rest/{api_name}/v1/items/{item_id}')
    assert readable.status_code == 200, readable.text

    coll = async_db.get_collection(collection_name)
    await db_insert_one(coll, {'_id': 'not-owned', 'name': 'private', 'owner': 'someone-else'})
    blocked_read = await authed_client.get(f'/api/rest/{api_name}/v1/items/not-owned')
    assert blocked_read.status_code == 403, blocked_read.text


@pytest.mark.asyncio
async def test_import_export_and_index_routes_require_registered_table(authed_client):
    collection_name = await _create_table(authed_client)
    coll = async_db.get_collection(collection_name)
    await db_insert_one(coll, {'_id': 'row-1', 'name': 'exported'})

    exported = await authed_client.get(
        f'/platform/api-builder/tables/{collection_name}/export?format=json'
    )
    assert exported.status_code == 200, exported.text
    assert exported.json()[0]['name'] == 'exported'

    missing_export = await authed_client.get('/platform/api-builder/tables/users/export')
    assert missing_export.status_code == 404

    imported = await authed_client.post(
        f'/platform/api-builder/tables/{collection_name}/import',
        files={'file': ('rows.json', json.dumps([{'name': 'imported'}]), 'application/json')},
    )
    assert imported.status_code == 200, imported.text

    missing_import = await authed_client.post(
        '/platform/api-builder/tables/users/import',
        files={'file': ('rows.json', json.dumps([{'name': 'blocked'}]), 'application/json')},
    )
    assert missing_import.status_code == 404

    indexes = await authed_client.get(f'/platform/api-builder/tables/{collection_name}/indexes')
    assert indexes.status_code == 200, indexes.text
    assert any(index.get('name') == '_id_' for index in indexes.json().get('indexes', []))

    created_index = await authed_client.post(
        f'/platform/api-builder/tables/{collection_name}/indexes',
        json={'keys': [['name', 'asc']], 'name': 'name_idx'},
    )
    assert created_index.status_code == 201, created_index.text

    drop_id = await authed_client.delete(
        f'/platform/api-builder/tables/{collection_name}/indexes/_id_'
    )
    assert drop_id.status_code == 400

    missing_indexes = await authed_client.get('/platform/api-builder/tables/users/indexes')
    assert missing_indexes.status_code == 404


@pytest.mark.asyncio
async def test_schemaless_table_search_is_rejected(authed_client):
    collection_name = await _create_table(authed_client, schema={})
    response = await authed_client.post(
        f'/platform/api-builder/tables/{collection_name}/query',
        json={'search': 'anything'},
    )
    assert response.status_code == 400
    assert response.json().get('error_code') == 'ABT031'


def _login_test_client(client: TestClient):
    response = client.post(
        '/platform/authorization',
        json={
            'email': os.environ.get('DOORMAN_ADMIN_EMAIL'),
            'password': os.environ.get('DOORMAN_ADMIN_PASSWORD'),
        },
    )
    assert response.status_code == 200, response.text
    token = response.json().get('access_token')
    if token:
        client.headers.update({'Authorization': f'Bearer {token}'})
    return token


def _login_test_client_as(client: TestClient, email: str, password: str):
    response = client.post('/platform/authorization', json={'email': email, 'password': password})
    assert response.status_code == 200, response.text
    token = response.json().get('access_token')
    if token:
        client.headers.update({'Authorization': f'Bearer {token}'})
    return token


def test_api_builder_websocket_requires_auth_and_registered_table():
    from doorman import doorman

    unauthenticated = TestClient(doorman)
    with pytest.raises(WebSocketDisconnect) as no_auth:
        with unauthenticated.websocket_connect('/platform/api-builder/ws/subscribe/users'):
            pass
    assert no_auth.value.code == 1008

    client = TestClient(doorman)
    admin_token = _login_test_client(client)
    admin_ws_headers = {'Authorization': f'Bearer {admin_token}'}

    with pytest.raises(WebSocketDisconnect) as unknown_table:
        with client.websocket_connect(
            '/platform/api-builder/ws/subscribe/users', headers=admin_ws_headers
        ):
            pass
    assert unknown_table.value.code == 1008

    collection_name = f'crud_data_{_unique("ws")}'
    create_table = client.post(
        '/platform/api-builder/tables',
        json={
            'table_name': collection_name,
            'collection_name': collection_name,
            'schema': {'name': {'type': 'string'}},
        },
    )
    assert create_table.status_code == 201, create_table.text

    role_name = _unique('wsrole')
    username = _unique('wsuser')
    email = f'{username}@example.com'
    password = 'VeryStrongPassword123!'
    role_response = client.post(
        '/platform/role',
        json={'role_name': role_name, 'view_builder_tables': False},
    )
    assert role_response.status_code in (200, 201), role_response.text
    user_response = client.post(
        '/platform/user',
        json={
            'username': username,
            'email': email,
            'password': password,
            'role': role_name,
            'groups': ['ALL'],
            'active': True,
            'ui_access': True,
        },
    )
    assert user_response.status_code in (200, 201), user_response.text

    limited_client = TestClient(doorman)
    limited_token = _login_test_client_as(limited_client, email, password)
    limited_ws_headers = {'Authorization': f'Bearer {limited_token}'}
    with pytest.raises(WebSocketDisconnect) as no_permission:
        with limited_client.websocket_connect(
            f'/platform/api-builder/ws/subscribe/{collection_name}', headers=limited_ws_headers
        ):
            pass
    assert no_permission.value.code == 1008

    with client.websocket_connect(
        f'/platform/api-builder/ws/subscribe/{collection_name}', headers=admin_ws_headers
    ) as ws:
        ws.send_text('ping')
