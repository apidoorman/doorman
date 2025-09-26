"""
Routes to export and import platform configuration (APIs, Endpoints, Roles, Groups, Routings).
"""

from fastapi import APIRouter, Request
from typing import Any, Dict, List, Optional
import uuid
import time
import logging
import copy

from models.response_model import ResponseModel
from utils.response_util import process_response
from utils.auth_util import auth_required
from utils.role_util import platform_role_required_bool
from utils.doorman_cache_util import doorman_cache
from utils.database import (
    api_collection,
    endpoint_collection,
    group_collection,
    role_collection,
    routing_collection,
)

config_router = APIRouter()
logger = logging.getLogger("doorman.gateway")


def _strip_id(doc: Dict[str, Any]) -> Dict[str, Any]:
    d = dict(doc)
    d.pop("_id", None)
    return d


def _export_all() -> Dict[str, Any]:
    apis = [_strip_id(a) for a in api_collection.find().to_list(length=None)]
    endpoints = [_strip_id(e) for e in endpoint_collection.find().to_list(length=None)]
    roles = [_strip_id(r) for r in role_collection.find().to_list(length=None)]
    groups = [_strip_id(g) for g in group_collection.find().to_list(length=None)]
    routings = [_strip_id(r) for r in routing_collection.find().to_list(length=None)]
    return {
        "apis": apis,
        "endpoints": endpoints,
        "roles": roles,
        "groups": groups,
        "routings": routings,
    }


@config_router.get("/config/export/all",
    description="Export all platform configuration (APIs, Endpoints, Roles, Groups, Routings)",
    response_model=ResponseModel,
)
async def export_all(request: Request):
    request_id = str(uuid.uuid4())
    start = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        if not await platform_role_required_bool(username, 'manage_gateway'):
            return process_response(ResponseModel(status_code=403, error_code="CFG001", error_message="Insufficient permissions").dict(), "rest")
        data = _export_all()
        return process_response(ResponseModel(status_code=200, response_headers={"request_id": request_id}, response=data).dict(), "rest")
    except Exception as e:
        logger.error(f"{request_id} | export_all error: {e}")
        return process_response(ResponseModel(status_code=500, error_code="GTW999", error_message="An unexpected error occurred").dict(), "rest")
    finally:
        logger.info(f"{request_id} | export_all took {time.time()*1000 - start:.2f}ms")


@config_router.get("/config/export/apis",
    description="Export APIs (optionally a single API with its endpoints)",
    response_model=ResponseModel)
async def export_apis(request: Request, api_name: Optional[str] = None, api_version: Optional[str] = None):
    request_id = str(uuid.uuid4())
    start = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        if not await platform_role_required_bool(username, 'manage_apis'):
            return process_response(ResponseModel(status_code=403, error_code="CFG002", error_message="Insufficient permissions").dict(), "rest")
        if api_name and api_version:
            api = api_collection.find_one({"api_name": api_name, "api_version": api_version})
            if not api:
                return process_response(ResponseModel(status_code=404, error_code="CFG404", error_message="API not found").dict(), "rest")
            aid = api.get('api_id')
            eps = endpoint_collection.find({"api_name": api_name, "api_version": api_version}).to_list(length=None)
            return process_response(ResponseModel(status_code=200, response={
                "api": _strip_id(api),
                "endpoints": [_strip_id(e) for e in eps]
            }).dict(), "rest")
        apis = [_strip_id(a) for a in api_collection.find().to_list(length=None)]
        return process_response(ResponseModel(status_code=200, response={"apis": apis}).dict(), "rest")
    except Exception as e:
        logger.error(f"{request_id} | export_apis error: {e}")
        return process_response(ResponseModel(status_code=500, error_code="GTW999", error_message="An unexpected error occurred").dict(), "rest")
    finally:
        logger.info(f"{request_id} | export_apis took {time.time()*1000 - start:.2f}ms")


@config_router.get("/config/export/roles", description="Export Roles", response_model=ResponseModel)
async def export_roles(request: Request, role_name: Optional[str] = None):
    request_id = str(uuid.uuid4())
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        if not await platform_role_required_bool(username, 'manage_roles'):
            return process_response(ResponseModel(status_code=403, error_code="CFG003", error_message="Insufficient permissions").dict(), "rest")
        if role_name:
            role = role_collection.find_one({"role_name": role_name})
            if not role:
                return process_response(ResponseModel(status_code=404, error_code="CFG404", error_message="Role not found").dict(), "rest")
            return process_response(ResponseModel(status_code=200, response={"role": _strip_id(role)}).dict(), "rest")
        roles = [_strip_id(r) for r in role_collection.find().to_list(length=None)]
        return process_response(ResponseModel(status_code=200, response={"roles": roles}).dict(), "rest")
    except Exception as e:
        logger.error(f"{request_id} | export_roles error: {e}")
        return process_response(ResponseModel(status_code=500, error_code="GTW999", error_message="An unexpected error occurred").dict(), "rest")


@config_router.get("/config/export/groups", description="Export Groups", response_model=ResponseModel)
async def export_groups(request: Request, group_name: Optional[str] = None):
    request_id = str(uuid.uuid4())
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        if not await platform_role_required_bool(username, 'manage_groups'):
            return process_response(ResponseModel(status_code=403, error_code="CFG004", error_message="Insufficient permissions").dict(), "rest")
        if group_name:
            group = group_collection.find_one({"group_name": group_name})
            if not group:
                return process_response(ResponseModel(status_code=404, error_code="CFG404", error_message="Group not found").dict(), "rest")
            return process_response(ResponseModel(status_code=200, response={"group": _strip_id(group)}).dict(), "rest")
        groups = [_strip_id(g) for g in group_collection.find().to_list(length=None)]
        return process_response(ResponseModel(status_code=200, response={"groups": groups}).dict(), "rest")
    except Exception as e:
        logger.error(f"{request_id} | export_groups error: {e}")
        return process_response(ResponseModel(status_code=500, error_code="GTW999", error_message="An unexpected error occurred").dict(), "rest")


@config_router.get("/config/export/routings", description="Export Routings", response_model=ResponseModel)
async def export_routings(request: Request, client_key: Optional[str] = None):
    request_id = str(uuid.uuid4())
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        if not await platform_role_required_bool(username, 'manage_routings'):
            return process_response(ResponseModel(status_code=403, error_code="CFG005", error_message="Insufficient permissions").dict(), "rest")
        if client_key:
            routing = routing_collection.find_one({"client_key": client_key})
            if not routing:
                return process_response(ResponseModel(status_code=404, error_code="CFG404", error_message="Routing not found").dict(), "rest")
            return process_response(ResponseModel(status_code=200, response={"routing": _strip_id(routing)}).dict(), "rest")
        routings = [_strip_id(r) for r in routing_collection.find().to_list(length=None)]
        return process_response(ResponseModel(status_code=200, response={"routings": routings}).dict(), "rest")
    except Exception as e:
        logger.error(f"{request_id} | export_routings error: {e}")
        return process_response(ResponseModel(status_code=500, error_code="GTW999", error_message="An unexpected error occurred").dict(), "rest")


@config_router.get("/config/export/endpoints",
    description="Export endpoints (optionally filter by api_name/api_version)",
    response_model=ResponseModel)
async def export_endpoints(request: Request, api_name: Optional[str] = None, api_version: Optional[str] = None):
    request_id = str(uuid.uuid4())
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        # Reuse manage_endpoints permission for endpoint export
        if not await platform_role_required_bool(username, 'manage_endpoints'):
            return process_response(ResponseModel(status_code=403, error_code="CFG007", error_message="Insufficient permissions").dict(), "rest")
        query = {}
        if api_name:
            query['api_name'] = api_name
        if api_version:
            query['api_version'] = api_version
        eps = [_strip_id(e) for e in endpoint_collection.find(query).to_list(length=None)]
        return process_response(ResponseModel(status_code=200, response={"endpoints": eps}).dict(), "rest")
    except Exception as e:
        logger.error(f"{request_id} | export_endpoints error: {e}")
        return process_response(ResponseModel(status_code=500, error_code="GTW999", error_message="An unexpected error occurred").dict(), "rest")


def _upsert_api(doc: Dict[str, Any]) -> None:
    api_name = doc.get('api_name')
    api_version = doc.get('api_version')
    if not api_name or not api_version:
        return
    existing = api_collection.find_one({"api_name": api_name, "api_version": api_version})
    to_set = copy.deepcopy(_strip_id(doc))
    # Ensure identifiers
    if existing:
        if not to_set.get('api_id'):
            to_set['api_id'] = existing.get('api_id')
    else:
        to_set.setdefault('api_id', str(uuid.uuid4()))
        to_set.setdefault('api_path', f"/{api_name}/{api_version}")
    if existing:
        api_collection.update_one({"api_name": api_name, "api_version": api_version}, {"$set": to_set})
    else:
        api_collection.insert_one(to_set)


def _upsert_endpoint(doc: Dict[str, Any]) -> None:
    api_name = doc.get('api_name')
    api_version = doc.get('api_version')
    method = doc.get('endpoint_method')
    uri = doc.get('endpoint_uri')
    if not (api_name and api_version and method and uri):
        return
    # Ensure endpoint_id and api_id
    api_doc = api_collection.find_one({"api_name": api_name, "api_version": api_version})
    to_set = copy.deepcopy(_strip_id(doc))
    if api_doc:
        to_set['api_id'] = api_doc.get('api_id')
    to_set.setdefault('endpoint_id', str(uuid.uuid4()))
    existing = endpoint_collection.find_one({
        'api_name': api_name,
        'api_version': api_version,
        'endpoint_method': method,
        'endpoint_uri': uri,
    })
    if existing:
        endpoint_collection.update_one({
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': method,
            'endpoint_uri': uri,
        }, {"$set": to_set})
    else:
        endpoint_collection.insert_one(to_set)


def _upsert_role(doc: Dict[str, Any]) -> None:
    name = doc.get('role_name')
    if not name:
        return
    to_set = copy.deepcopy(_strip_id(doc))
    existing = role_collection.find_one({'role_name': name})
    if existing:
        role_collection.update_one({'role_name': name}, {"$set": to_set})
    else:
        role_collection.insert_one(to_set)


def _upsert_group(doc: Dict[str, Any]) -> None:
    name = doc.get('group_name')
    if not name:
        return
    to_set = copy.deepcopy(_strip_id(doc))
    existing = group_collection.find_one({'group_name': name})
    if existing:
        group_collection.update_one({'group_name': name}, {"$set": to_set})
    else:
        group_collection.insert_one(to_set)


def _upsert_routing(doc: Dict[str, Any]) -> None:
    key = doc.get('client_key')
    if not key:
        return
    to_set = copy.deepcopy(_strip_id(doc))
    existing = routing_collection.find_one({'client_key': key})
    if existing:
        routing_collection.update_one({'client_key': key}, {"$set": to_set})
    else:
        routing_collection.insert_one(to_set)


@config_router.post("/config/import",
    description="Import platform configuration (any subset of apis, endpoints, roles, groups, routings)",
    response_model=ResponseModel)
async def import_all(request: Request, body: Dict[str, Any]):
    request_id = str(uuid.uuid4())
    start = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        # Require broad gateway permission for bulk import
        if not await platform_role_required_bool(username, 'manage_gateway'):
            return process_response(ResponseModel(status_code=403, error_code="CFG006", error_message="Insufficient permissions").dict(), "rest")
        counts = {"apis": 0, "endpoints": 0, "roles": 0, "groups": 0, "routings": 0}
        for api in body.get('apis', []) or []:
            _upsert_api(api); counts['apis'] += 1
        for ep in body.get('endpoints', []) or []:
            _upsert_endpoint(ep); counts['endpoints'] += 1
        for r in body.get('roles', []) or []:
            _upsert_role(r); counts['roles'] += 1
        for g in body.get('groups', []) or []:
            _upsert_group(g); counts['groups'] += 1
        for rt in body.get('routings', []) or []:
            _upsert_routing(rt); counts['routings'] += 1
        # Invalidate caches so changes take immediate effect
        try:
            doorman_cache.clear_all_caches()
        except Exception:
            pass
        return process_response(ResponseModel(status_code=200, response={"imported": counts}).dict(), "rest")
    except Exception as e:
        logger.error(f"{request_id} | import_all error: {e}")
        return process_response(ResponseModel(status_code=500, error_code="GTW999", error_message="An unexpected error occurred").dict(), "rest")
    finally:
        logger.info(f"{request_id} | import_all took {time.time()*1000 - start:.2f}ms")

