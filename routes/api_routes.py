"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from models.update_api_model import UpdateApiModel
from services.api_service import ApiService
from utils.auth_util import auth_required
from models.api_model import ApiModel
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool

import uuid
import time
import logging

api_router = APIRouter() 

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

"""
Create API *platform endpoint.
"""
@api_router.post("",
    dependencies=[
        Depends(auth_required)
    ])
async def create_api(api_data: ApiModel, Authorize: AuthJWT = Depends()):
    try:
        request_id = str(uuid.uuid4())
        start_time = time.time() * 1000
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_apis'):
            return JSONResponse(content={"error": "You do not have permission to create APIs"}, status_code=403)
        return process_response(await ApiService.create_api(api_data))
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(request_id + " | Total time: " + str(end_time - start_time) + " ms")
    
"""
Update API *platform endpoint.
"""
@api_router.put("/{api_name}/{api_version}",
    dependencies=[
        Depends(auth_required)
    ])
async def create_api(api_name: str, api_version: str, api_data: UpdateApiModel, Authorize: AuthJWT = Depends()):
    try:
        request_id = str(uuid.uuid4())
        start_time = time.time() * 1000
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_apis'):
            return JSONResponse(content={"error": "You do not have permission to update APIs"}, status_code=403)
        return process_response(await ApiService.update_api(api_name, api_version, api_data))
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(request_id + " | Total time: " + str(end_time - start_time) + " ms")

"""
Get API *platform endpoint.
"""
@api_router.get("/{api_name}/{api_version}",
    dependencies=[
        Depends(auth_required)
    ])
async def get_api_by_name_version(api_name: str, api_version: str):
    try:
        request_id = str(uuid.uuid4())
        start_time = time.time() * 1000
        return process_response(await ApiService.get_api_by_name_version(api_name, api_version))
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(request_id + " | Total time: " + str(end_time - start_time) + " ms")
    
"""
Delete API *platform endpoint.
"""
@api_router.delete("/{api_name}/{api_version}",
    dependencies=[
        Depends(auth_required)
    ])
async def get_api_by_name_version(api_name: str, api_version: str):
    try:
        request_id = str(uuid.uuid4())
        start_time = time.time() * 1000
        return process_response(await ApiService.delete_api(api_name, api_version))
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(request_id + " | Total time: " + str(end_time - start_time) + " ms")

"""
Get All Accessable APIs *platform endpoint.
"""
@api_router.get("/all",
    dependencies=[
        Depends(auth_required)
    ])
async def get_all_apis(page: int = 1, page_size: int = 10):
    try:
        request_id = str(uuid.uuid4())
        start_time = time.time() * 1000
        return process_response(await ApiService.get_apis(page, page_size))
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(request_id + " | Total time: " + str(end_time - start_time) + " ms")