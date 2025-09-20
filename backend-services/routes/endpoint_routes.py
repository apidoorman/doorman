"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

from typing import List
from fastapi import APIRouter, Depends, Request

from models.create_endpoint_validation_model import CreateEndpointValidationModel
from models.endpoint_model_response import EndpointModelResponse
from models.endpoint_validation_model_response import EndpointValidationModelResponse
from models.response_model import ResponseModel
from models.update_endpoint_model import UpdateEndpointModel
from models.update_endpoint_validation_model import UpdateEndpointValidationModel
from services.endpoint_service import EndpointService
from utils.auth_util import auth_required
from models.create_endpoint_model import CreateEndpointModel
from utils.response_util import respond_rest, process_response
from utils.role_util import platform_role_required_bool

import uuid
import time
import logging

endpoint_router = APIRouter()

logger = logging.getLogger("doorman.gateway")

@endpoint_router.post("",
    description="Add endpoint",
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
async def create_endpoint(endpoint_data: CreateEndpointModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_endpoints'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="END010",
                error_message="You do not have permission to create endpoints"
            ))
        return respond_rest(await EndpointService.create_endpoint(endpoint_data, request_id))
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
async def update_endpoint(endpoint_method: str, api_name: str, api_version: str, endpoint_uri: str, endpoint_data: UpdateEndpointModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_endpoints'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="END011",
                error_message="You do not have permission to update endpoints"
            ))
        return respond_rest(await EndpointService.update_endpoint(endpoint_method, api_name, api_version, '/' + endpoint_uri, endpoint_data, request_id))
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
async def delete_endpoint(endpoint_method: str, api_name: str, api_version: str, endpoint_uri: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_endpoints'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="END012",
                error_message="You do not have permission to delete endpoints"
            ))
        return respond_rest(await EndpointService.delete_endpoint(endpoint_method, api_name, api_version, '/' + endpoint_uri, request_id))
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
    response_model=EndpointModelResponse
)
async def get_endpoint(endpoint_method: str, api_name: str, api_version: str, endpoint_uri: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return respond_rest(await EndpointService.get_endpoint(endpoint_method, api_name, api_version, '/' + endpoint_uri, request_id))
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
    response_model=List[EndpointModelResponse]
)
async def get_endpoints_by_name_version(api_name: str, api_version: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return respond_rest(await EndpointService.get_endpoints_by_name_version(api_name, api_version, request_id))
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

@endpoint_router.post("/endpoint/validation",
    description="Create a new endpoint validation",
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Endpoint validation created successfully"
                    }
                }
            }
        }
    }
)
async def create_endpoint_validation(endpoint_validation_data: CreateEndpointValidationModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_endpoints'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="END013",
                error_message="You do not have permission to create endpoint validations"
            ))
        return respond_rest(await EndpointService.create_endpoint_validation(endpoint_validation_data, request_id))
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

@endpoint_router.put("/endpoint/validation/{endpoint_id}",
    description="Update an endpoint validation by endpoint ID",
    response_model=ResponseModel
)
async def update_endpoint_validation(endpoint_id: str, endpoint_validation_data: UpdateEndpointValidationModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_endpoints'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="END014",
                error_message="You do not have permission to update endpoint validations"
            ))
        return respond_rest(await EndpointService.update_endpoint_validation(endpoint_id, endpoint_validation_data, request_id))
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

@endpoint_router.delete("/endpoint/validation/{endpoint_id}",
    description="Delete an endpoint validation by endpoint ID",
    response_model=ResponseModel
)
async def delete_endpoint_validation(endpoint_id: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_endpoints'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="END015",
                error_message="You do not have permission to delete endpoint validations"
            ))
        return respond_rest(await EndpointService.delete_endpoint_validation(endpoint_id, request_id))
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

@endpoint_router.get("/endpoint/validation/{endpoint_id}",
    description="Get an endpoint validation by endpoint ID",
    response_model=EndpointValidationModelResponse
)
async def get_endpoint_validation(endpoint_id: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return respond_rest(await EndpointService.get_endpoint_validation(endpoint_id, request_id))
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

# Normalized aliases for endpoint validation (without leading /endpoint segment)
@endpoint_router.post("/validation",
    description="Create a new endpoint validation (alias)",
    response_model=ResponseModel)
async def create_endpoint_validation_alias(endpoint_validation_data: CreateEndpointValidationModel, request: Request):
    return await create_endpoint_validation(endpoint_validation_data, request)

@endpoint_router.put("/validation/{endpoint_id}",
    description="Update endpoint validation by endpoint ID (alias)",
    response_model=ResponseModel)
async def update_endpoint_validation_alias(endpoint_id: str, endpoint_validation_data: UpdateEndpointValidationModel, request: Request):
    return await update_endpoint_validation(endpoint_id, endpoint_validation_data, request)

@endpoint_router.delete("/validation/{endpoint_id}",
    description="Delete endpoint validation by endpoint ID (alias)",
    response_model=ResponseModel)
async def delete_endpoint_validation_alias(endpoint_id: str, request: Request):
    return await delete_endpoint_validation(endpoint_id, request)

@endpoint_router.get("/validation/{endpoint_id}",
    description="Get endpoint validation by endpoint ID (alias)",
    response_model=EndpointValidationModelResponse)
async def get_endpoint_validation_alias(endpoint_id: str, request: Request):
    return await get_endpoint_validation(endpoint_id, request)
