"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from typing import List
from fastapi import APIRouter, Depends, Request
from fastapi_jwt_auth import AuthJWT

from models.endpoint_model_response import EndpointModelResponse
from models.response_model import ResponseModel
from models.update_endpoint_model import UpdateEndpointModel
from services.endpoint_service import EndpointService
from utils.auth_util import auth_required
from models.create_endpoint_model import CreateEndpointModel
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool

import uuid
import time
import logging

endpoint_router = APIRouter()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

@endpoint_router.post("",
    description="Add endpoint",
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
                        "message": "Endpoint created successfully"
                    }
                }
            }
        }
    }
)
async def create_endpoint(endpoint_data: CreateEndpointModel, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_endpoints'):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="END010",
                error_message="You do not have permission to create endpoints"
            ).dict(), "rest")
        return process_response(await EndpointService.create_endpoint(endpoint_data, request_id), "rest")
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

@endpoint_router.put("/{endpoint_method}/{api_name}/{api_version}/{endpoint_uri}",
    description="Update endpoint",
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
                        "message": "Endpoint updated successfully"
                    }
                }
            }
        }
    }
)
async def update_endpoint(endpoint_method: str, api_name: str, api_version: str, endpoint_uri: str, endpoint_data: UpdateEndpointModel, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_endpoints'):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="END011",
                error_message="You do not have permission to update endpoints"
            ).dict(), "rest")
        return process_response(await EndpointService.update_endpoint(endpoint_method, api_name, api_version, '/' + endpoint_uri, endpoint_data, request_id), "rest")
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

@endpoint_router.delete("/{endpoint_method}/{api_name}/{api_version}/{endpoint_uri}",
    description="Delete endpoint",
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
                        "message": "Endpoint deleted successfully"
                    }
                }
            }
        }
    }
)
async def delete_endpoint(endpoint_method: str, api_name: str, api_version: str, endpoint_uri: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_endpoints'):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="END012",
                error_message="You do not have permission to delete endpoints"
            ))
        return process_response(await EndpointService.delete_endpoint(endpoint_method, api_name, api_version, '/' + endpoint_uri, request_id), "rest")
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
    
@endpoint_router.get("/{endpoint_method}/{api_name}/{api_version}/{endpoint_uri}",
    description="Get endpoint by API name, API version and endpoint uri",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=EndpointModelResponse
)
async def get_endpoint(endpoint_method: str, api_name: str, api_version: str, endpoint_uri: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await EndpointService.get_endpoint(endpoint_method, api_name, api_version, '/' + endpoint_uri, request_id), "rest")
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

@endpoint_router.get("/{api_name}/{api_version}",
    description="Get all endpoints for an API",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=List[EndpointModelResponse]
)
async def get_endpoints_by_name_version(api_name: str, api_version: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await EndpointService.get_endpoints_by_name_version(api_name, api_version, request_id), "rest")
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