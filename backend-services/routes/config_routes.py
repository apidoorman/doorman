"""
Routes to export and import platform configuration (APIs, Endpoints, Roles, Groups, Routings).
"""

import copy
import logging
import time
import uuid
from typing import Any

from datetime import datetime
from fastapi import APIRouter, Request, HTTPException

from models.response_model import ResponseModel
from utils.audit_util import audit
from utils.auth_util import auth_required
from utils.database import (
    api_collection,
    endpoint_collection,
    group_collection,
    role_collection,
    routing_collection,
    routing_collection,
)
from utils.database_async import async_database
from utils.doorman_cache_util import doorman_cache
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool

config_router = APIRouter()
logger = logging.getLogger('doorman.gateway')


def _strip_id(doc: dict[str, Any]) -> dict[str, Any]:
    d = dict(doc)
    d.pop('_id', None)
    return d


def _export_all() -> dict[str, Any]:
    # PyMongo cursors are synchronous; convert to lists directly
    apis = [_strip_id(a) for a in list(api_collection.find())]
    endpoints = [_strip_id(e) for e in list(endpoint_collection.find())]
    roles = [_strip_id(r) for r in list(role_collection.find())]
    groups = [_strip_id(g) for g in list(group_collection.find())]
    routings = [_strip_id(r) for r in list(routing_collection.find())]
    return {
        'apis': apis,
        'endpoints': endpoints,
        'roles': roles,
        'groups': groups,
        'routings': routings,
        'groups': groups,
        'routings': routings,
    }


async def _create_snapshot(actor: str):
    """Create a snapshot of current configuration"""
    data = _export_all()
    snapshot = {
        'snapshot_id': str(uuid.uuid4()),
        'timestamp': datetime.now(),
        'created_by': actor,
        'data': data,
    }
    # Some environments (MEM) may not expose a config_snapshots collection. Treat as best-effort.
    coll = getattr(async_database.db, 'config_snapshots', None)
    if coll is None:
        try:
            logger.debug('config_snapshots not available in current DB; skipping snapshot create')
        except Exception:
            pass
        return None
    await coll.insert_one(snapshot)
    return snapshot['snapshot_id']


async def _restore_snapshot(snapshot_id: str = None):
    """Restore configuration from snapshot (latest if id not provided)"""
    coll = getattr(async_database.db, 'config_snapshots', None)
    if coll is None:
        raise ValueError('Snapshot storage not available')
    if snapshot_id:
        snapshot = await coll.find_one({'snapshot_id': snapshot_id})
    else:
        # Get latest
        cursor = coll.find().sort('timestamp', -1).limit(1)
        snapshot = await cursor.to_list(length=1)
        snapshot = snapshot[0] if snapshot else None

    if not snapshot:
        raise ValueError('No snapshot found')

    data = snapshot['data']
    
    # Restore logic: wipe and insert (simplified for implementation plan)
    # In prod, transactions would be better
    
    # APIs
    api_collection.delete_many({})
    if data['apis']:
        api_collection.insert_many(data['apis'])
        
    # Endpoints
    endpoint_collection.delete_many({})
    if data['endpoints']:
        endpoint_collection.insert_many(data['endpoints'])
        
    # Roles
    role_collection.delete_many({})
    if data['roles']:
        role_collection.insert_many(data['roles'])
        
    # Groups
    group_collection.delete_many({})
    if data['groups']:
        group_collection.insert_many(data['groups'])
        
    # Routings
    routing_collection.delete_many({})
    if data['routings']:
        routing_collection.insert_many(data['routings'])
        
    doorman_cache.clear_all_caches()
    return snapshot['timestamp']


"""
Endpoint

Request:
{}
Response:
{}
"""


@config_router.get(
    '/config/export/all',
    description='Export all platform configuration (APIs, Endpoints, Roles, Groups, Routings)',
    response_model=ResponseModel,
)
async def export_all(request: Request):
    request_id = str(uuid.uuid4())
    start = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        if not await platform_role_required_bool(username, 'manage_gateway'):
            return process_response(
                ResponseModel(
                    status_code=403, error_code='CFG001', error_message='Insufficient permissions'
                ).dict(),
                'rest',
            )
        data = _export_all()
        audit(
            request,
            actor=username,
            action='config.export_all',
            target='all',
            status='success',
            details={'counts': {k: len(v) for k, v in data.items()}},
            request_id=request_id,
        )
        return process_response(
            ResponseModel(
                status_code=200, response_headers={'request_id': request_id}, response=data
            ).dict(),
            'rest',
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f'{request_id} | export_all error: {e}')
        return process_response(
            ResponseModel(
                status_code=500, error_code='GTW999', error_message='An unexpected error occurred'
            ).dict(),
            'rest',
        )
    finally:
        logger.info(f'{request_id} | export_all took {time.time() * 1000 - start:.2f}ms')


"""
Endpoint

Request:
{}
Response:
{}
"""


@config_router.get(
    '/config/export/apis',
    description='Export APIs (optionally a single API with its endpoints)',
    response_model=ResponseModel,
)
async def export_apis(
    request: Request, api_name: str | None = None, api_version: str | None = None
):
    request_id = str(uuid.uuid4())
    start = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        if not await platform_role_required_bool(username, 'manage_apis'):
            return process_response(
                ResponseModel(
                    status_code=403, error_code='CFG002', error_message='Insufficient permissions'
                ).dict(),
                'rest',
            )
        if api_name and api_version:
            api = api_collection.find_one({'api_name': api_name, 'api_version': api_version})
            if not api:
                return process_response(
                    ResponseModel(
                        status_code=404, error_code='CFG404', error_message='API not found'
                    ).dict(),
                    'rest',
                )
            api.get('api_id')
            eps = list(
                endpoint_collection.find({'api_name': api_name, 'api_version': api_version})
            )
            audit(
                request,
                actor=username,
                action='config.export_api',
                target=f'{api_name}/{api_version}',
                status='success',
                details={'endpoints': len(eps)},
                request_id=request_id,
            )
            return process_response(
                ResponseModel(
                    status_code=200,
                    response={'api': _strip_id(api), 'endpoints': [_strip_id(e) for e in eps]},
                ).dict(),
                'rest',
            )
        apis = [_strip_id(a) for a in list(api_collection.find())]
        audit(
            request,
            actor=username,
            action='config.export_apis',
            target='list',
            status='success',
            details={'count': len(apis)},
            request_id=request_id,
        )
        return process_response(
            ResponseModel(status_code=200, response={'apis': apis}).dict(), 'rest'
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f'{request_id} | export_apis error: {e}')
        return process_response(
            ResponseModel(
                status_code=500, error_code='GTW999', error_message='An unexpected error occurred'
            ).dict(),
            'rest',
        )
    finally:
        logger.info(f'{request_id} | export_apis took {time.time() * 1000 - start:.2f}ms')


"""
Endpoint

Request:
{}
Response:
{}
"""


@config_router.get('/config/export/roles', description='Export Roles', response_model=ResponseModel)
async def export_roles(request: Request, role_name: str | None = None):
    request_id = str(uuid.uuid4())
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        if not await platform_role_required_bool(username, 'manage_roles'):
            return process_response(
                ResponseModel(
                    status_code=403, error_code='CFG003', error_message='Insufficient permissions'
                ).dict(),
                'rest',
            )
        if role_name:
            role = role_collection.find_one({'role_name': role_name})
            if not role:
                return process_response(
                    ResponseModel(
                        status_code=404, error_code='CFG404', error_message='Role not found'
                    ).dict(),
                    'rest',
                )
            audit(
                request,
                actor=username,
                action='config.export_role',
                target=role_name,
                status='success',
                details=None,
                request_id=request_id,
            )
            return process_response(
                ResponseModel(status_code=200, response={'role': _strip_id(role)}).dict(), 'rest'
            )
        roles = [_strip_id(r) for r in list(role_collection.find())]
        audit(
            request,
            actor=username,
            action='config.export_roles',
            target='list',
            status='success',
            details={'count': len(roles)},
            request_id=request_id,
        )
        return process_response(
            ResponseModel(status_code=200, response={'roles': roles}).dict(), 'rest'
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f'{request_id} | export_roles error: {e}')
        return process_response(
            ResponseModel(
                status_code=500, error_code='GTW999', error_message='An unexpected error occurred'
            ).dict(),
            'rest',
        )


"""
Endpoint

Request:
{}
Response:
{}
"""


@config_router.get(
    '/config/export/groups', description='Export Groups', response_model=ResponseModel
)
async def export_groups(request: Request, group_name: str | None = None):
    request_id = str(uuid.uuid4())
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        if not await platform_role_required_bool(username, 'manage_groups'):
            return process_response(
                ResponseModel(
                    status_code=403, error_code='CFG004', error_message='Insufficient permissions'
                ).dict(),
                'rest',
            )
        if group_name:
            group = group_collection.find_one({'group_name': group_name})
            if not group:
                return process_response(
                    ResponseModel(
                        status_code=404, error_code='CFG404', error_message='Group not found'
                    ).dict(),
                    'rest',
                )
            audit(
                request,
                actor=username,
                action='config.export_group',
                target=group_name,
                status='success',
                details=None,
                request_id=request_id,
            )
            return process_response(
                ResponseModel(status_code=200, response={'group': _strip_id(group)}).dict(), 'rest'
            )
        groups = [_strip_id(g) for g in list(group_collection.find())]
        audit(
            request,
            actor=username,
            action='config.export_groups',
            target='list',
            status='success',
            details={'count': len(groups)},
            request_id=request_id,
        )
        return process_response(
            ResponseModel(status_code=200, response={'groups': groups}).dict(), 'rest'
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f'{request_id} | export_groups error: {e}')
        return process_response(
            ResponseModel(
                status_code=500, error_code='GTW999', error_message='An unexpected error occurred'
            ).dict(),
            'rest',
        )


"""
Endpoint

Request:
{}
Response:
{}
"""


@config_router.get(
    '/config/export/routings', description='Export Routings', response_model=ResponseModel
)
async def export_routings(request: Request, client_key: str | None = None):
    request_id = str(uuid.uuid4())
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        if not await platform_role_required_bool(username, 'manage_routings'):
            return process_response(
                ResponseModel(
                    status_code=403, error_code='CFG005', error_message='Insufficient permissions'
                ).dict(),
                'rest',
            )
        if client_key:
            routing = routing_collection.find_one({'client_key': client_key})
            if not routing:
                return process_response(
                    ResponseModel(
                        status_code=404, error_code='CFG404', error_message='Routing not found'
                    ).dict(),
                    'rest',
                )
            audit(
                request,
                actor=username,
                action='config.export_routing',
                target=client_key,
                status='success',
                details=None,
                request_id=request_id,
            )
            return process_response(
                ResponseModel(status_code=200, response={'routing': _strip_id(routing)}).dict(),
                'rest',
            )
        routings = [_strip_id(r) for r in list(routing_collection.find())]
        audit(
            request,
            actor=username,
            action='config.export_routings',
            target='list',
            status='success',
            details={'count': len(routings)},
            request_id=request_id,
        )
        return process_response(
            ResponseModel(status_code=200, response={'routings': routings}).dict(), 'rest'
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f'{request_id} | export_routings error: {e}')
        return process_response(
            ResponseModel(
                status_code=500, error_code='GTW999', error_message='An unexpected error occurred'
            ).dict(),
            'rest',
        )


"""
Endpoint

Request:
{}
Response:
{}
"""


@config_router.get(
    '/config/export/endpoints',
    description='Export endpoints (optionally filter by api_name/api_version)',
    response_model=ResponseModel,
)
async def export_endpoints(
    request: Request, api_name: str | None = None, api_version: str | None = None
):
    request_id = str(uuid.uuid4())
    try:
        payload = await auth_required(request)
        username = payload.get('sub')

        if not await platform_role_required_bool(username, 'manage_endpoints'):
            return process_response(
                ResponseModel(
                    status_code=403, error_code='CFG007', error_message='Insufficient permissions'
                ).dict(),
                'rest',
            )
        query = {}
        if api_name:
            query['api_name'] = api_name
        if api_version:
            query['api_version'] = api_version
        eps = [_strip_id(e) for e in list(endpoint_collection.find(query))]
        return process_response(
            ResponseModel(status_code=200, response={'endpoints': eps}).dict(), 'rest'
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f'{request_id} | export_endpoints error: {e}')
        return process_response(
            ResponseModel(
                status_code=500, error_code='GTW999', error_message='An unexpected error occurred'
            ).dict(),
            'rest',
        )


def _upsert_api(doc: dict[str, Any]) -> None:
    api_name = doc.get('api_name')
    api_version = doc.get('api_version')
    if not api_name or not api_version:
        return
    existing = api_collection.find_one({'api_name': api_name, 'api_version': api_version})
    to_set = copy.deepcopy(_strip_id(doc))

    if existing:
        if not to_set.get('api_id'):
            to_set['api_id'] = existing.get('api_id')
    else:
        to_set.setdefault('api_id', str(uuid.uuid4()))
        to_set.setdefault('api_path', f'/{api_name}/{api_version}')
    if existing:
        api_collection.update_one(
            {'api_name': api_name, 'api_version': api_version}, {'$set': to_set}
        )
    else:
        api_collection.insert_one(to_set)


def _upsert_endpoint(doc: dict[str, Any]) -> None:
    api_name = doc.get('api_name')
    api_version = doc.get('api_version')
    method = doc.get('endpoint_method')
    uri = doc.get('endpoint_uri')
    if not (api_name and api_version and method and uri):
        return

    api_doc = api_collection.find_one({'api_name': api_name, 'api_version': api_version})
    to_set = copy.deepcopy(_strip_id(doc))
    if api_doc:
        to_set['api_id'] = api_doc.get('api_id')
    to_set.setdefault('endpoint_id', str(uuid.uuid4()))
    existing = endpoint_collection.find_one(
        {
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': method,
            'endpoint_uri': uri,
        }
    )
    if existing:
        endpoint_collection.update_one(
            {
                'api_name': api_name,
                'api_version': api_version,
                'endpoint_method': method,
                'endpoint_uri': uri,
            },
            {'$set': to_set},
        )
    else:
        endpoint_collection.insert_one(to_set)


def _upsert_role(doc: dict[str, Any]) -> None:
    name = doc.get('role_name')
    if not name:
        return
    to_set = copy.deepcopy(_strip_id(doc))
    existing = role_collection.find_one({'role_name': name})
    if existing:
        role_collection.update_one({'role_name': name}, {'$set': to_set})
    else:
        role_collection.insert_one(to_set)


def _upsert_group(doc: dict[str, Any]) -> None:
    name = doc.get('group_name')
    if not name:
        return
    to_set = copy.deepcopy(_strip_id(doc))
    existing = group_collection.find_one({'group_name': name})
    if existing:
        group_collection.update_one({'group_name': name}, {'$set': to_set})
    else:
        group_collection.insert_one(to_set)


def _upsert_routing(doc: dict[str, Any]) -> None:
    key = doc.get('client_key')
    if not key:
        return
    to_set = copy.deepcopy(_strip_id(doc))
    existing = routing_collection.find_one({'client_key': key})
    if existing:
        routing_collection.update_one({'client_key': key}, {'$set': to_set})
    else:
        routing_collection.insert_one(to_set)


"""
Endpoint

Request:
{}
Response:
{}
"""


@config_router.post(
    '/config/import',
    description='Import platform configuration (any subset of apis, endpoints, roles, groups, routings)',
    response_model=ResponseModel,
)
async def import_all(request: Request, body: dict[str, Any]):
    request_id = str(uuid.uuid4())
    start = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')

        if not await platform_role_required_bool(username, 'manage_gateway'):
            return process_response(
                ResponseModel(
                    status_code=403, error_code='CFG006', error_message='Insufficient permissions'
                ).dict(),
                'rest',
            )

        # Create snapshot before import
        await _create_snapshot(username)
        
        counts = {'apis': 0, 'endpoints': 0, 'roles': 0, 'groups': 0, 'routings': 0}
        for api in body.get('apis', []) or []:
            _upsert_api(api)
            counts['apis'] += 1
        for ep in body.get('endpoints', []) or []:
            _upsert_endpoint(ep)
            counts['endpoints'] += 1
        for r in body.get('roles', []) or []:
            _upsert_role(r)
            counts['roles'] += 1
        for g in body.get('groups', []) or []:
            _upsert_group(g)
            counts['groups'] += 1
        for rt in body.get('routings', []) or []:
            _upsert_routing(rt)
            counts['routings'] += 1

        try:
            doorman_cache.clear_all_caches()
        except Exception:
            pass
        audit(
            request,
            actor=username,
            action='config.import',
            target='bulk',
            status='success',
            details={'imported': counts},
            request_id=request_id,
        )
        return process_response(
            ResponseModel(status_code=200, response={'imported': counts}).dict(), 'rest'
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f'{request_id} | import_all error: {e}')
        return process_response(
            ResponseModel(
                status_code=500, error_code='GTW999', error_message='An unexpected error occurred'
            ).dict(),
            'rest',
        )
    finally:
        logger.info(f'{request_id} | import_all took {time.time() * 1000 - start:.2f}ms')


@config_router.post(
    '/config/rollback',
    description='Rollback configuration to latest snapshot',
    response_model=ResponseModel,
)
async def rollback_config(request: Request):
    """
    Rollback to the most recent configuration snapshot.
    """
    request_id = str(uuid.uuid4())
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        
        if not await platform_role_required_bool(username, 'manage_gateway'):
             raise HTTPException(status_code=403, detail='Insufficient permissions')

        ts = await _restore_snapshot()
        
        audit(
            request,
            actor=username,
            action='config.rollback',
            target='latest',
            status='success',
            details={'restored_to': str(ts)},
            request_id=request_id,
        )
        
        return process_response(
            ResponseModel(status_code=200, message=f'Configuration rolled back to {ts}').dict(),
            'rest'
        )
    except ValueError as e:
        return process_response(
            ResponseModel(status_code=404, error_code='CFG404', error_message=str(e)).dict(),
            'rest'
        )
    except Exception as e:
        logger.error(f'{request_id} | rollback error: {e}')
        raise HTTPException(status_code=500, detail='Rollback failed')
