"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from models.update_role_model import UpdateRoleModel
from services.role_service import RoleService
from utils.auth_util import auth_required
from models.role_model import RoleModel
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool

import uuid
import time
import logging

role_router = APIRouter()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

"""
Create API *platform endpoint.
"""
@role_router.post("",
    dependencies=[
        Depends(auth_required)
    ])
async def create_role(api_data: RoleModel, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_roles'):
            return JSONResponse(content={"error": "You do not have permission to create roles"}, status_code=403)
        return process_response(await RoleService.create_role(api_data, request_id))
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")
    
"""
Update API *platform endpoint.
"""
@role_router.put("/{role_name}",
    dependencies=[
        Depends(auth_required)
    ])
async def update_role(role_name: str, api_data: UpdateRoleModel, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_roles'):
            return JSONResponse(content={"error": "You do not have permission to update roles"}, status_code=403)
        return process_response(await RoleService.update_role(role_name, api_data, request_id))
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

"""
Delete API *platform endpoint.
"""
@role_router.delete("/{role_name}",
    dependencies=[
        Depends(auth_required)
    ])
async def delete_role(role_name: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_roles'):
            return JSONResponse(content={"error": "You do not have permission to delete roles"}, status_code=403)
        return process_response(await RoleService.delete_role(role_name, request_id))
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

"""
Create API *platform endpoint.
"""
@role_router.get("/all",
    dependencies=[
        Depends(auth_required)
    ])
async def get_roles(request: Request, Authorize: AuthJWT = Depends(), page: int = 1, page_size: int = 10):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {str(request.url.path)}")
        return process_response(await RoleService.get_roles(page, page_size, request_id))
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

"""
Create API *platform endpoint.
"""
@role_router.get("/{role_name}",
    dependencies=[
        Depends(auth_required)
    ])
async def get_role(role_name: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {str(request.url.path)}")
        return process_response(await RoleService.get_role(role_name, request_id))
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")