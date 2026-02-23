"""
Table explorer and table registry routes.
"""

import json
import logging
import re
import time
import uuid
from typing import Any

from fastapi import APIRouter, Request, Response, WebSocket, WebSocketDisconnect

from services.realtime_service import realtime_service

from models.response_model import ResponseModel
from utils.async_db import (
    db_count,
    db_delete_many,
    db_delete_one,
    db_find_list,
    db_find_one,
    db_find_paginated,
    db_insert_one,
    db_update_one,
)
from utils.auth_util import auth_required
from utils.constants import Defaults, Headers, Messages, Roles
from utils.database_async import api_collection, db as async_db
from utils.paging_util import validate_page_params
from utils.response_util import respond_rest
from utils.role_util import platform_role_required_bool

api_builder_router = APIRouter()
logger = logging.getLogger('doorman.gateway')

TABLE_REGISTRY_COLLECTION = 'api_builder_tables'
COLLECTION_NAME_PATTERN = re.compile(r'^[A-Za-z][A-Za-z0-9_]{2,127}$')


def _crud_collection_name(api_doc: dict[str, Any]) -> str | None:
    explicit = (api_doc.get('api_crud_collection') or '').strip()
    if explicit:
        return explicit
    api_id = (api_doc.get('api_id') or '').strip()
    if api_id:
        return f'crud_data_{api_id.replace("-", "_")}'
    return None


def _api_crud_bindings(api_doc: dict[str, Any]) -> list[dict[str, Any]]:
    raw = api_doc.get('api_crud_bindings')
    bindings: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            collection_name = str(item.get('collection_name') or '').strip()
            if not collection_name:
                continue
            bindings.append(
                {
                    'resource_name': str(item.get('resource_name') or '').strip(),
                    'collection_name': collection_name,
                    'table_name': str(item.get('table_name') or '').strip() or collection_name,
                    'schema': item.get('schema') if isinstance(item.get('schema'), dict) else {},
                }
            )

    if bindings:
        return bindings

    collection_name = _crud_collection_name(api_doc)
    if not collection_name:
        return []
    return [
        {
            'resource_name': '',
            'collection_name': collection_name,
            'table_name': collection_name,
            'schema': api_doc.get('api_crud_schema') or {},
        }
    ]


def _get_collection(collection_name: str):
    if hasattr(async_db, 'get_collection'):
        return async_db.get_collection(collection_name)
    try:
        return getattr(async_db, collection_name)
    except AttributeError:
        return async_db[collection_name]


def _table_registry_collection():
    return _get_collection(TABLE_REGISTRY_COLLECTION)


def _normalize_identifier(value: str) -> str:
    normalized = re.sub(r'[^a-zA-Z0-9_]+', '_', value.strip().lower())
    normalized = re.sub(r'_+', '_', normalized).strip('_')
    if not normalized:
        normalized = 'table'
    if normalized[0].isdigit():
        normalized = f'table_{normalized}'
    return normalized


def _derive_collection_name(table_name: str, explicit_collection_name: str | None) -> str:
    if explicit_collection_name and explicit_collection_name.strip():
        return explicit_collection_name.strip()
    return f'crud_data_{_normalize_identifier(table_name)}'


def _table_fields(schema: Any) -> list[str]:
    if not isinstance(schema, dict):
        return []
    return sorted(str(k) for k in schema.keys())


def _validate_schema(schema: Any) -> tuple[bool, str | None]:
    if not isinstance(schema, dict):
        return False, 'schema must be an object'
    for field_name, rules in schema.items():
        if not str(field_name).strip():
            return False, 'schema field names must be non-empty strings'
        if not isinstance(rules, dict):
            return False, 'schema field rules must be objects'
    return True, None


def _validate_rules(rules: Any) -> tuple[bool, str | None]:
    if not rules:
        return True, None
    if not isinstance(rules, dict):
        return False, 'rules must be an object'
    allowed_keys = {'read', 'write', 'create', 'update', 'delete', 'list'}
    for k, v in rules.items():
        if k not in allowed_keys:
            return False, f'Invalid rule type: {k}. Allowed: {", ".join(allowed_keys)}'
        if not isinstance(v, str):
            return False, f'Rule for {k} must be a string expression'
    return True, None


def _coerce_query_value(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        lower = stripped.lower()
        if lower == 'true':
            return True
        if lower == 'false':
            return False
        if lower in ('null', 'none'):
            return None
        try:
            if '.' in stripped:
                return float(stripped)
            return int(stripped)
        except Exception:
            return stripped
    return value


def _extract_field_value(doc: dict[str, Any], field: str) -> Any:
    if field == '_id':
        return doc.get('_id')
    current: Any = doc
    for part in field.split('.'):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current.get(part)
    return current


def _query_filter_match(doc: dict[str, Any], query_filter: dict[str, Any]) -> bool:
    field = str(query_filter.get('field') or '').strip()
    if not field:
        return True
    op = str(query_filter.get('op') or 'eq').strip().lower()
    value = _coerce_query_value(query_filter.get('value'))
    actual = _extract_field_value(doc, field)

    if op in ('eq', '=='):
        return actual == value
    if op in ('ne', '!='):
        return actual != value
    if op == 'contains':
        target = str(value or '').lower()
        if isinstance(actual, list):
            return any(target in str(item).lower() for item in actual)
        return target in str(actual or '').lower()
    if op == 'starts_with':
        return str(actual or '').lower().startswith(str(value or '').lower())
    if op == 'ends_with':
        return str(actual or '').lower().endswith(str(value or '').lower())
    if op in ('gt', '>'):
        try:
            return actual > value
        except Exception:
            return False
    if op in ('gte', '>='):
        try:
            return actual >= value
        except Exception:
            return False
    if op in ('lt', '<'):
        try:
            return actual < value
        except Exception:
            return False
    if op in ('lte', '<='):
        try:
            return actual <= value
        except Exception:
            return False
    if op == 'in':
        if isinstance(value, list):
            return actual in value
        if isinstance(value, str):
            options = [v.strip() for v in value.split(',') if v.strip()]
            return str(actual) in options
        return False
    if op == 'nin':
        if isinstance(value, list):
            return actual not in value
        if isinstance(value, str):
            options = [v.strip() for v in value.split(',') if v.strip()]
            return str(actual) not in options
        return True
    if op == 'exists':
        expect = bool(value) if value is not None else True
        exists = _extract_field_value(doc, field) is not None
        return exists if expect else not exists
    return False


def _sort_key(value: Any) -> tuple[int, Any]:
    if value is None:
        return (0, '')
    if isinstance(value, bool):
        return (1, int(value))
    if isinstance(value, (int, float)):
        return (2, value)
    if isinstance(value, str):
        return (3, value.lower())
    return (4, str(value))


async def _legacy_table_map() -> dict[str, dict[str, Any]]:
    apis = await db_find_list(
        api_collection, {'api_is_crud': True}, sort=[('api_name', 1), ('api_version', 1)]
    )
    table_map: dict[str, dict[str, Any]] = {}
    for api_doc in apis:
        bindings = _api_crud_bindings(api_doc)
        for binding in bindings:
            collection_name = binding.get('collection_name')
            if not collection_name:
                continue
            if collection_name not in table_map:
                table_map[collection_name] = {
                    'collection_name': collection_name,
                    'table_name': binding.get('table_name') or collection_name,
                    'api_refs': [],
                    'schema': binding.get('schema') or {},
                    'source': 'api_legacy',
                }
            table_map[collection_name]['api_refs'].append(
                {
                    'api_name': api_doc.get('api_name'),
                    'api_version': api_doc.get('api_version'),
                }
            )
            if not table_map[collection_name].get('schema') and binding.get('schema'):
                table_map[collection_name]['schema'] = binding.get('schema')
    return table_map


async def _table_map() -> dict[str, dict[str, Any]]:
    registry_docs = await db_find_list(
        _table_registry_collection(), {}, sort=[('table_name', 1), ('collection_name', 1)]
    )

    table_map: dict[str, dict[str, Any]] = {}
    for table_doc in registry_docs:
        collection_name = str(table_doc.get('collection_name') or '').strip()
        if not collection_name:
            continue
        table_map[collection_name] = {
            'collection_name': collection_name,
            'table_name': table_doc.get('table_name') or collection_name,
            'api_refs': [],
            'schema': table_doc.get('schema') or {},
            'source': 'table_registry',
            'created_at': table_doc.get('created_at'),
            'updated_at': table_doc.get('updated_at'),
            'created_by': table_doc.get('created_by'),
            'rules': table_doc.get('rules') or {},
        }

    legacy_map = await _legacy_table_map()
    for collection_name, legacy in legacy_map.items():
        existing = table_map.get(collection_name)
        if not existing:
            table_map[collection_name] = legacy
            continue

        existing['api_refs'] = legacy.get('api_refs') or []
        if not existing.get('schema') and legacy.get('schema'):
            existing['schema'] = legacy.get('schema')

    return table_map


@api_builder_router.post('/tables', description='Create a table definition')
async def create_table(request: Request) -> Response:
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')

        if not await platform_role_required_bool(username, Roles.MANAGE_APIS):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT010',
                    error_message='You do not have permission to create tables',
                )
            )

        try:
            body = await request.json()
        except Exception:
            body = {}

        table_name = str(body.get('table_name') or '').strip()
        if not table_name:
            return respond_rest(
                ResponseModel(
                    status_code=400,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT011',
                    error_message='table_name is required',
                )
            )

        schema = body.get('schema') or {}
        schema_valid, schema_error = _validate_schema(schema)
        if not schema_valid:
            return respond_rest(
                ResponseModel(
                    status_code=400,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT012',
                    error_message=schema_error or 'Invalid schema',
                )
            )

        collection_name = _derive_collection_name(
            table_name=table_name,
            explicit_collection_name=body.get('collection_name'),
        )
        if not COLLECTION_NAME_PATTERN.match(collection_name):
            return respond_rest(
                ResponseModel(
                    status_code=400,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT015',
                    error_message='Invalid collection_name format',
                )
            )

        rules = body.get('rules') or {}
        rules_valid, rules_error = _validate_rules(rules)
        if not rules_valid:
            return respond_rest(
                ResponseModel(
                    status_code=400,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT013',
                    error_message=rules_error or 'Invalid rules',
                )
            )

        existing = await db_find_one(_table_registry_collection(), {'collection_name': collection_name})
        if existing:
            return respond_rest(
                ResponseModel(
                    status_code=409,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT016',
                    error_message='Table already exists',
                )
            )

        now = int(time.time() * 1000)
        table_doc = {
            'table_name': table_name,
            'collection_name': collection_name,
            'schema': schema,
            'created_at': now,
            'updated_at': now,
            'created_by': username,
            'rules': rules,
        }
        inserted = await db_insert_one(_table_registry_collection(), table_doc)
        if not inserted or not getattr(inserted, 'acknowledged', False):
            return respond_rest(
                ResponseModel(
                    status_code=500,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT017',
                    error_message='Failed to create table',
                )
            )

        # Ensure underlying CRUD collection exists/accessible now.
        _ = _get_collection(collection_name)

        response_doc = dict(table_doc)
        response_doc['_id'] = str(getattr(inserted, 'inserted_id', ''))
        response_doc['fields'] = _table_fields(schema)
        response_doc['row_count'] = 0
        response_doc['api_refs'] = []
        response_doc['source'] = 'table_registry'
        response_doc['rules'] = rules

        return respond_rest(
            ResponseModel(
                status_code=201,
                response_headers={Headers.REQUEST_ID: request_id},
                response={'table': response_doc},
                message='Table created successfully',
            )
        )
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code='ABT999',
                error_message=Messages.UNEXPECTED,
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


@api_builder_router.get('/tables', description='List tables')
async def list_tables(request: Request) -> Response:
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, Roles.VIEW_BUILDER_TABLES):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT001',
                    error_message='You do not have permission to view tables',
                )
            )

        table_map = await _table_map()
        tables: list[dict[str, Any]] = []
        for table in table_map.values():
            row_count = 0
            try:
                row_count = await db_count(_get_collection(table['collection_name']), {})
            except Exception:
                row_count = 0
            table_copy = dict(table)
            table_copy['row_count'] = row_count
            table_copy['fields'] = _table_fields(table_copy.get('schema'))
            tables.append(table_copy)

        tables.sort(key=lambda x: (str(x.get('table_name') or ''), str(x.get('collection_name') or '')))
        return respond_rest(
            ResponseModel(
                status_code=200,
                response_headers={Headers.REQUEST_ID: request_id},
                response={'tables': tables, 'count': len(tables)},
            )
        )
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code='ABT999',
                error_message=Messages.UNEXPECTED,
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


@api_builder_router.put('/tables/{collection_name}', description='Update a table definition')
async def update_table(collection_name: str, request: Request) -> Response:
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, Roles.MANAGE_APIS):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT020',
                    error_message='You do not have permission to update tables',
                )
            )

        existing = await db_find_one(_table_registry_collection(), {'collection_name': collection_name})
        if not existing:
            table_map = await _table_map()
            if table_map.get(collection_name):
                return respond_rest(
                    ResponseModel(
                        status_code=409,
                        response_headers={Headers.REQUEST_ID: request_id},
                        error_code='ABT021',
                        error_message='Legacy tables cannot be updated here',
                    )
                )
            return respond_rest(
                ResponseModel(
                    status_code=404,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT404',
                    error_message='Table not found',
                )
            )

        try:
            body = await request.json()
        except Exception:
            body = {}

        updates: dict[str, Any] = {}
        if 'table_name' in body:
            table_name = str(body.get('table_name') or '').strip()
            if not table_name:
                return respond_rest(
                    ResponseModel(
                        status_code=400,
                        response_headers={Headers.REQUEST_ID: request_id},
                        error_code='ABT022',
                        error_message='table_name cannot be empty',
                    )
                )
            updates['table_name'] = table_name

        if 'schema' in body:
            schema_valid, schema_error = _validate_schema(body.get('schema'))
            if not schema_valid:
                return respond_rest(
                    ResponseModel(
                        status_code=400,
                        response_headers={Headers.REQUEST_ID: request_id},
                        error_code='ABT023',
                        error_message=schema_error or 'Invalid schema',
                    )
                )
            updates['schema'] = body.get('schema') or {}

        if 'rules' in body:
            rules_valid, rules_error = _validate_rules(body.get('rules'))
            if not rules_valid:
                return respond_rest(
                    ResponseModel(
                        status_code=400,
                        response_headers={Headers.REQUEST_ID: request_id},
                        error_code='ABT023',
                        error_message=rules_error or 'Invalid rules',
                    )
                )
            updates['rules'] = body.get('rules') or {}

        if not updates:
            return respond_rest(
                ResponseModel(
                    status_code=400,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT024',
                    error_message='No fields provided for update',
                )
            )

        now = int(time.time() * 1000)
        updates['updated_at'] = now
        result = await db_update_one(
            _table_registry_collection(), {'collection_name': collection_name}, {'$set': updates}
        )
        if not result or not getattr(result, 'acknowledged', False):
            return respond_rest(
                ResponseModel(
                    status_code=500,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT025',
                    error_message='Failed to update table',
                )
            )

        updated = await db_find_one(_table_registry_collection(), {'collection_name': collection_name}) or {}
        schema = updated.get('schema') or {}
        row_count = 0
        try:
            row_count = await db_count(_get_collection(collection_name), {})
        except Exception:
            row_count = 0

        response_doc = {
            'collection_name': collection_name,
            'table_name': updated.get('table_name') or collection_name,
            'schema': schema,
            'fields': _table_fields(schema),
            'row_count': row_count,
            'api_refs': (await _legacy_table_map()).get(collection_name, {}).get('api_refs') or [],
            'source': 'table_registry',
            'updated_at': updated.get('updated_at'),
            'created_at': updated.get('created_at'),
            'created_by': updated.get('created_by'),
        }
        return respond_rest(
            ResponseModel(
                status_code=200,
                response_headers={Headers.REQUEST_ID: request_id},
                response={'table': response_doc},
                message='Table updated successfully',
            )
        )
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code='ABT999',
                error_message=Messages.UNEXPECTED,
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


@api_builder_router.delete('/tables/{collection_name}', description='Delete a table definition')
async def delete_table(collection_name: str, request: Request) -> Response:
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, Roles.MANAGE_APIS):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT026',
                    error_message='You do not have permission to delete tables',
                )
            )

        existing = await db_find_one(_table_registry_collection(), {'collection_name': collection_name})
        if not existing:
            table_map = await _table_map()
            if table_map.get(collection_name):
                return respond_rest(
                    ResponseModel(
                        status_code=409,
                        response_headers={Headers.REQUEST_ID: request_id},
                        error_code='ABT027',
                        error_message='Legacy tables cannot be deleted here',
                    )
                )
            return respond_rest(
                ResponseModel(
                    status_code=404,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT404',
                    error_message='Table not found',
                )
            )

        try:
            body = await request.json()
        except Exception:
            body = {}

        drop_data = bool(body.get('drop_data')) if isinstance(body, dict) else False
        force = bool(body.get('force')) if isinstance(body, dict) else False

        table_map = await _table_map()
        refs = (table_map.get(collection_name) or {}).get('api_refs') or []
        if refs and not force:
            return respond_rest(
                ResponseModel(
                    status_code=409,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT028',
                    error_message='Table is attached to APIs. Retry with force=true to delete anyway.',
                )
            )

        deleted = await db_delete_one(_table_registry_collection(), {'collection_name': collection_name})
        if not deleted or not getattr(deleted, 'acknowledged', False):
            return respond_rest(
                ResponseModel(
                    status_code=500,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT029',
                    error_message='Failed to delete table',
                )
            )
        if getattr(deleted, 'deleted_count', 0) == 0:
            return respond_rest(
                ResponseModel(
                    status_code=404,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT404',
                    error_message='Table not found',
                )
            )

        if drop_data:
            try:
                await db_delete_many(_get_collection(collection_name), {})
            except Exception:
                logger.warning(f'Failed to purge records for collection {collection_name}', exc_info=True)

        return respond_rest(
            ResponseModel(
                status_code=200,
                response_headers={Headers.REQUEST_ID: request_id},
                response={
                    'collection_name': collection_name,
                    'drop_data': drop_data,
                    'force': force,
                },
                message='Table deleted successfully',
            )
        )
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code='ABT999',
                error_message=Messages.UNEXPECTED,
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


@api_builder_router.get('/tables/{collection_name}', description='List rows from a table')
async def list_table_rows(
    collection_name: str,
    request: Request,
    page: int = Defaults.PAGE,
    page_size: int = Defaults.PAGE_SIZE,
) -> Response:
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, Roles.VIEW_BUILDER_TABLES):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT001',
                    error_message='You do not have permission to view tables',
                )
            )

        try:
            page, page_size = validate_page_params(page, page_size)
        except Exception as e:
            return respond_rest(
                ResponseModel(
                    status_code=400,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT002',
                    error_message=(
                        Messages.PAGE_TOO_LARGE if 'page_size' in str(e) else Messages.INVALID_PAGING
                    ),
                )
            )

        table_map = await _table_map()
        table_meta = table_map.get(collection_name)
        if not table_meta:
            return respond_rest(
                ResponseModel(
                    status_code=404,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT404',
                    error_message='Table not found',
                )
            )

        collection = _get_collection(collection_name)
        skip = (page - 1) * page_size
        items = await db_find_paginated(
            collection, {}, skip=skip, limit=page_size, sort=[('_id', 1)]
        )
        for item in items:
            if item.get('_id') is not None:
                item['_id'] = str(item['_id'])

        try:
            total = await db_count(collection, {})
            has_next = (skip + len(items)) < total
        except Exception:
            total = None
            extra = await db_find_paginated(
                collection, {}, skip=skip, limit=page_size + 1, sort=[('_id', 1)]
            )
            has_next = len(extra) > page_size

        return respond_rest(
            ResponseModel(
                status_code=200,
                response_headers={Headers.REQUEST_ID: request_id},
                response={
                    'collection_name': collection_name,
                    'table_name': table_meta.get('table_name') or collection_name,
                    'api_refs': table_meta.get('api_refs') or [],
                    'schema': table_meta.get('schema') or {},
                    'fields': _table_fields(table_meta.get('schema')),
                    'source': table_meta.get('source') or 'table_registry',
                    'items': items,
                    'page': page,
                    'page_size': page_size,
                    'has_next': has_next,
                    **({'total': total} if total is not None else {}),
                },
            )
        )
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code='ABT999',
                error_message=Messages.UNEXPECTED,
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


@api_builder_router.post('/tables/{collection_name}/query', description='Query rows from a table')
async def query_table_rows(collection_name: str, request: Request) -> Response:
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, Roles.VIEW_BUILDER_TABLES):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT001',
                    error_message='You do not have permission to view tables',
                )
            )

        table_map = await _table_map()
        table_meta = table_map.get(collection_name)
        if not table_meta:
            return respond_rest(
                ResponseModel(
                    status_code=404,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT404',
                    error_message='Table not found',
                )
            )

        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}

        try:
            page, page_size = validate_page_params(
                int(body.get('page', Defaults.PAGE)),
                int(body.get('page_size', Defaults.PAGE_SIZE)),
            )
        except Exception as e:
            return respond_rest(
                ResponseModel(
                    status_code=400,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ABT002',
                    error_message=(
                        Messages.PAGE_TOO_LARGE if 'page_size' in str(e) else Messages.INVALID_PAGING
                    ),
                )
            )

        search_text = str(body.get('search') or '').strip().lower()
        filters = body.get('filters') if isinstance(body.get('filters'), list) else []
        logic = str(body.get('logic') or 'and').strip().lower()
        if logic not in ('and', 'or'):
            logic = 'and'
        sort_by = str(body.get('sort_by') or '_id').strip() or '_id'
        sort_order = str(body.get('sort_order') or 'asc').strip().lower()
        reverse = sort_order == 'desc'

        valid_ops = {
            'eq',
            '==',
            'ne',
            '!=',
            'contains',
            'starts_with',
            'ends_with',
            'gt',
            '>',
            'gte',
            '>=',
            'lt',
            '<',
            'lte',
            '<=',
            'in',
            'nin',
            'exists',
        }
        normalized_filters: list[dict[str, Any]] = []
        for raw_filter in filters:
            if not isinstance(raw_filter, dict):
                continue
            field = str(raw_filter.get('field') or '').strip()
            if not field:
                continue
            op = str(raw_filter.get('op') or 'eq').strip().lower()
            if op not in valid_ops:
                return respond_rest(
                    ResponseModel(
                        status_code=400,
                        response_headers={Headers.REQUEST_ID: request_id},
                        error_code='ABT030',
                        error_message=f'Unsupported query operator: {op}',
                    )
                )
            normalized_filters.append({'field': field, 'op': op, 'value': raw_filter.get('value')})

        collection = _get_collection(collection_name)
        docs = await db_find_list(collection, {}, sort=[('_id', 1)])

        if search_text:
            docs = [
                d
                for d in docs
                if search_text in json.dumps(d, default=str, separators=(',', ':')).lower()
            ]

        if normalized_filters:
            if logic == 'or':
                docs = [
                    d
                    for d in docs
                    if any(_query_filter_match(d, qf) for qf in normalized_filters)
                ]
            else:
                docs = [
                    d
                    for d in docs
                    if all(_query_filter_match(d, qf) for qf in normalized_filters)
                ]

        docs.sort(key=lambda d: _sort_key(_extract_field_value(d, sort_by)), reverse=reverse)
        total = len(docs)
        skip = (page - 1) * page_size
        items = docs[skip : skip + page_size]
        has_next = (skip + len(items)) < total
        for item in items:
            if item.get('_id') is not None:
                item['_id'] = str(item['_id'])

        return respond_rest(
            ResponseModel(
                status_code=200,
                response_headers={Headers.REQUEST_ID: request_id},
                response={
                    'collection_name': collection_name,
                    'table_name': table_meta.get('table_name') or collection_name,
                    'api_refs': table_meta.get('api_refs') or [],
                    'schema': table_meta.get('schema') or {},
                    'fields': _table_fields(table_meta.get('schema')),
                    'source': table_meta.get('source') or 'table_registry',
                    'items': items,
                    'page': page,
                    'page_size': page_size,
                    'has_next': has_next,
                    'total': total,
                    'query': {
                        'search': search_text,
                        'filters': normalized_filters,
                        'logic': logic,
                        'sort_by': sort_by,
                        'sort_order': sort_order,
                    },
                },
            )
        )
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code='ABT999',
                error_message=Messages.UNEXPECTED,
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


@api_builder_router.websocket('/ws/subscribe/{collection_name}')
async def subscribe_collection(websocket: WebSocket, collection_name: str):
    """
    WebSocket endpoint for real-time collection updates.
    """
    try:
        await realtime_service.connect(websocket, collection_name)
        while True:
            # Keep connection alive; we only send data, don't expect much input
            # But we must await something to detect disconnects
            await websocket.receive_text()
    except WebSocketDisconnect:
        realtime_service.disconnect(websocket, collection_name)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        realtime_service.disconnect(websocket, collection_name)

