"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from typing import List
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from models.response_model import ResponseModel
from models.role_model_response import RoleModelResponse
from models.update_role_model import UpdateRoleModel
from services.role_service import RoleService
from utils.auth_util import auth_required
from models.create_role_model import CreateRoleModel
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool

import uuid
import time
import logging

role_router = APIRouter()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

@role_router.post("",
    description="Add role",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Role created successfully"
                    }
                }
            }
        }
    }
)
async def create_role(api_data: CreateRoleModel, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_roles'):
            logger.error(f"{request_id} | User does not have permission to create roles")
            return JSONResponse(content={"error": "You do not have permission to create roles"}, status_code=403)
        #if api_data.manage_gateway and not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_gateway'):
            #logger.error(f"{request_id} | User does not have permission to create a gateway manager role")
            #return JSONResponse(content={"error": "You do not have permission to create a gateway manager role"}, status_code=403)
        return process_response(await RoleService.create_role(api_data, request_id))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")
    
@role_router.put("/{role_name}",
    description="Update role",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Role updated successfully"
                    }
                }
            }
        }
    }
)
async def update_role(role_name: str, api_data: UpdateRoleModel, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_roles'):
            return JSONResponse(content={"error": "You do not have permission to update roles"}, status_code=403)
        return process_response(await RoleService.update_role(role_name, api_data, request_id))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@role_router.delete("/{role_name}",
    description="Delete role",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Role deleted successfully"
                    }
                }
            }
        }
    }
)
async def delete_role(role_name: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_roles'):
            return JSONResponse(content={"error": "You do not have permission to delete roles"}, status_code=403)
        return process_response(await RoleService.delete_role(role_name, request_id))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@role_router.get("/all",
    description="Get all roles",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=List[RoleModelResponse]
)
async def get_roles(request: Request, Authorize: AuthJWT = Depends(), page: int = 1, page_size: int = 10):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await RoleService.get_roles(page, page_size, request_id))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@role_router.get("/{role_name}",
    description="Get role",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=RoleModelResponse
)
async def get_role(role_name: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await RoleService.get_role(role_name, request_id))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")