"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from models.update_group_model import UpdateGroupModel
from services.group_service import GroupService
from utils.auth_util import auth_required
from models.create_group_model import CreateGroupModel
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool

import uuid
import time
import logging

group_router = APIRouter()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

@group_router.post("",
    description="Add group",
    dependencies=[
        Depends(auth_required)
    ])
async def create_group(api_data: CreateGroupModel, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_groups'):
            return JSONResponse(content={"error": "You do not have permission to create groups"}, status_code=403)
        return process_response(await GroupService.create_group(api_data, request_id))
    except ValueError as e:
        logger.error(f"{request_id} | Error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@group_router.put("/{group_name}",
    description="Update group",
    dependencies=[
        Depends(auth_required)
    ])
async def update_group(group_name: str, api_data: UpdateGroupModel, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_groups'):
            return JSONResponse(content={"error": "You do not have permission to update groups"}, status_code=403)
        return process_response(await GroupService.update_group(group_name, api_data, request_id))
    except ValueError as e:
        logger.error(f"{request_id} | Error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@group_router.delete("/{group_name}",
    description="Delete group",
    dependencies=[
        Depends(auth_required)
    ])
async def delete_group(group_name: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_groups'):
            return JSONResponse(content={"error": "You do not have permission to delete groups"}, status_code=403)
        return process_response(await GroupService.delete_group(group_name, request_id))
    except ValueError as e:
        logger.error(f"{request_id} | Error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@group_router.get("/all",
    description="Get all groups",
    dependencies=[
        Depends(auth_required)
    ])
async def get_groups(request: Request, Authorize: AuthJWT = Depends(), page: int = 1, page_size: int = 10):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await GroupService.get_groups(page, page_size, request_id))
    except ValueError as e:
        logger.error(f"{request_id} | Error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")


@group_router.get("/{group_name}",
    description="Get group",
    dependencies=[
        Depends(auth_required)
    ])
async def get_group(group_name: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await GroupService.get_group(group_name, request_id))
    except ValueError as e:
        logger.error(f"{request_id} | Error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")