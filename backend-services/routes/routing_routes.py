"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

from typing import List
from fastapi import APIRouter, Depends, Request

from models.create_routing_model import CreateRoutingModel
from models.response_model import ResponseModel
from models.routing_model_response import RoutingModelResponse
from models.update_routing_model import UpdateRoutingModel
from services.routing_service import RoutingService
from utils.auth_util import auth_required
from utils.response_util import respond_rest, process_response
from utils.role_util import platform_role_required_bool

import uuid
import time
import logging

routing_router = APIRouter()

logger = logging.getLogger("doorman.gateway")

@routing_router.post("",
    description="Add routing",
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Routing created successfully"
                    }
                }
            }
        }
    }
)
async def create_routing(api_data: CreateRoutingModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_routings'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="RTG009",
                error_message="You do not have permission to create routings"
            ))
        return respond_rest(await RoutingService.create_routing(api_data, request_id))
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

@routing_router.put("/{client_key}",
    description="Update routing",
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Routing updated successfully"
                    }
                }
            }
        }
    }
)
async def update_routing(client_key: str, api_data: UpdateRoutingModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_routings'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="RTG010",
                error_message="You do not have permission to update routings"
            ))
        return respond_rest(await RoutingService.update_routing(client_key, api_data, request_id))
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

@routing_router.delete("/{client_key}",
    description="Delete routing",
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Routing deleted successfully"
                    }
                }
            }
        }
    }
)
async def delete_routing(client_key: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_routings'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="RTG011",
                error_message="You do not have permission to delete routings"
            ))
        return respond_rest(await RoutingService.delete_routing(client_key, request_id))
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

@routing_router.get("/all",
    description="Get all routings",
    response_model=List[RoutingModelResponse]
)
async def get_routings(request: Request, page: int = 1, page_size: int = 10):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_routings'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="RTG012",
                error_message="You do not have permission to get routings"
            ))
        return respond_rest(await RoutingService.get_routings(page, page_size, request_id))
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

@routing_router.get("/{client_key}",
    description="Get routing",
    response_model=RoutingModelResponse
)
async def get_routing(client_key: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_routings'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="RTG013",
                error_message="You do not have permission to get routings"
            ))
        return respond_rest(await RoutingService.get_routing(client_key, request_id))
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
