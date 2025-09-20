"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

from fastapi import APIRouter, HTTPException, Depends, Request

from models.response_model import ResponseModel
from services.subscription_service import SubscriptionService
from utils.auth_util import auth_required
from models.subscribe_model import SubscribeModel
from utils.group_util import group_required
from utils.response_util import respond_rest

import uuid
import time
import logging

subscription_router = APIRouter()

logger = logging.getLogger("doorman.gateway")

@subscription_router.post("/subscribe",
    description="Subscribe to API",
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Subscription created successfully"
                    }
                }
            }
        }
    }
)
async def subscribe_api(api_data: SubscribeModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await group_required(request, api_data.api_name + '/' + api_data.api_version, api_data.username):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="SUB007",
                error_message="You do not have the correct group access"
            ))
        return respond_rest(await SubscriptionService.subscribe(api_data, request_id))
    except HTTPException as e:
        return respond_rest(ResponseModel(
            status_code=e.status_code,
            response_headers={
                "request_id": request_id
            },
            error_code="GEN001",
            error_message=e.detail
        ))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ))
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@subscription_router.post("/unsubscribe",
    description="Unsubscribe from API",
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Subscription deleted successfully"
                    }
                }
            }
        }
    }
)
async def unsubscribe_api(api_data: SubscribeModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await group_required(request, api_data.api_name + '/' + api_data.api_version, api_data.username):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="SUB008",
                error_message="You do not have the correct group access"
            ))
        return respond_rest(await SubscriptionService.unsubscribe(api_data, request_id))
    except HTTPException as e:
        return respond_rest(ResponseModel(
            status_code=e.status_code,
            response_headers={
                "request_id": request_id
            },
            error_code="GEN002",
            error_message=e.detail
        ))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ))
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@subscription_router.get("/subscriptions",
    description="Get current user's subscriptions",
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "apis": [
                            "customer/v1",
                            "orders/v1"
                        ]
                    }
                }
            }
        }
    }
)
async def subscriptions_for_current_user(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return respond_rest(await SubscriptionService.get_user_subscriptions(username, request_id))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ))
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@subscription_router.get("/subscriptions/{user_id}",
    description="Get user's subscriptions",
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "apis": [
                            "customer/v1",
                            "orders/v1"
                        ]
                    }
                }
            }
        }
    }
)
async def subscriptions_for_user_by_id(user_id: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return respond_rest(await SubscriptionService.get_user_subscriptions(user_id, request_id))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ))
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")
