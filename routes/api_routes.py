"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from fastapi import APIRouter, Depends, Request
from fastapi_jwt_auth import AuthJWT
import logging
import uuid
import time
from typing import List

from models.response_model import ResponseModel
from services.api_service import ApiService
from utils.auth_util import auth_required
from models.create_api_model import CreateApiModel
from models.update_api_model import UpdateApiModel
from models.api_model_response import ApiModelResponse
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool

api_router = APIRouter() 
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("doorman.gateway")

@api_router.post("",
    description="Add API",
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
                        "message": "API created successfully"
                    }
                }
            }
        }
    }
)
async def create_api(request: Request, api_data: CreateApiModel, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
    logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
    try:
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_apis'):
            logger.warning(f"{request_id} | Permission denied for user: {Authorize.get_jwt_subject()}")
            return process_response(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="API007",
                error_message="You do not have permission to create APIs"
            ).dict(), "rest")
        return process_response(await ApiService.create_api(api_data, request_id), "rest")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@api_router.put("/{api_name}/{api_version}",
    description="Update API",
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
                        "message": "API updated successfully"
                    }
                }
            }
        }
    }
)
async def update_api(api_name: str, api_version: str, request: Request, api_data: UpdateApiModel, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_apis'):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="API008",
                error_message="You do not have permission to update APIs"
            ).dict(), "rest")
        return process_response(await ApiService.update_api(api_name, api_version, api_data, request_id), "rest")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@api_router.get("/{api_name}/{api_version}",
    description="Get API",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=ApiModelResponse,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "API retrieved successfully"
                    }
                }
            }
        }
    }
)
async def get_api_by_name_version(api_name: str, api_version: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await ApiService.get_api_by_name_version(api_name, api_version, request_id), "rest")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")
    
@api_router.delete("/{api_name}/{api_version}",
    description="Delete API",
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
                        "message": "API deleted successfully"
                    }
                }
            }
        }
    }
)
async def delete_api(api_name: str, api_version: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await ApiService.delete_api(api_name, api_version, request_id), "rest")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@api_router.get("/all",
    description="Get all APIs",
    dependencies=[
        Depends(auth_required) 
    ],
    response_model=List[ApiModelResponse]
)
async def get_all_apis(request: Request, Authorize: AuthJWT = Depends(), page: int = 1, page_size: int = 10):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await ApiService.get_apis(page, page_size, request_id), "rest")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")