"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from models.update_group_model import UpdateGroupModel
from services.group_service import GroupService
from utils.auth_util import auth_required
from models.group_model import GroupModel
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool

import uuid
import time
import logging

group_router = APIRouter()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

"""
Create group *platform endpoint.
"""
@group_router.post("",
    dependencies=[
        Depends(auth_required)
    ])
async def create_group(api_data: GroupModel, Authorize: AuthJWT = Depends()):
    try:
        request_id = str(uuid.uuid4())
        start_time = time.time() * 1000
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_groups'):
            return JSONResponse(content={"error": "You do not have permission to create groups"}, status_code=403)
        return process_response(await GroupService.create_group(api_data))
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(request_id + " | Total time: " + str(end_time - start_time) + " ms")

"""
Update group *platform endpoint.
"""
@group_router.put("/{group_name}",
    dependencies=[
        Depends(auth_required)
    ])
async def update_group(group_name: str, api_data: UpdateGroupModel, Authorize: AuthJWT = Depends()):
    try:
        request_id = str(uuid.uuid4())
        start_time = time.time() * 1000
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_groups'):
            return JSONResponse(content={"error": "You do not have permission to update groups"}, status_code=403)
        return process_response(await GroupService.update_group(group_name, api_data))
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(request_id + " | Total time: " + str(end_time - start_time) + " ms")

"""
Delete group *platform endpoint.
"""
@group_router.delete("/{group_name}",
    dependencies=[
        Depends(auth_required)
    ])
async def delete_group(group_name: str, Authorize: AuthJWT = Depends()):
    try:
        request_id = str(uuid.uuid4())
        start_time = time.time() * 1000
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_groups'):
            return JSONResponse(content={"error": "You do not have permission to delete groups"}, status_code=403)
        return process_response(await GroupService.delete_group(group_name))
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(request_id + " | Total time: " + str(end_time - start_time) + " ms")

"""
Get groups *platform endpoint.
"""
@group_router.get("/all",
    dependencies=[
        Depends(auth_required)
    ])
async def get_groups(page: int = 1, page_size: int = 10):
    try:
        request_id = str(uuid.uuid4())
        start_time = time.time() * 1000
        return process_response(await GroupService.get_groups(page, page_size))
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(request_id + " | Total time: " + str(end_time - start_time) + " ms")


"""
Get group *platform endpoint.
"""
@group_router.get("/{group_name}",
    dependencies=[
        Depends(auth_required)
    ])
async def get_group(group_name: str):
    try:
        request_id = str(uuid.uuid4())
        start_time = time.time() * 1000
        return process_response(await GroupService.get_group(group_name))
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(request_id + " | Total time: " + str(end_time - start_time) + " ms")