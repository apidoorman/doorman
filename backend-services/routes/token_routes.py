"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from typing import List
from fastapi import APIRouter, Depends, Request

from models.response_model import ResponseModel
from models.user_tokens_model import UserTokenModel
from models.token_model import TokenModel
from services.token_service import TokenService
from utils.auth_util import auth_required
from utils.response_util import respond_rest, process_response

import uuid
import time
import logging

from utils.role_util import platform_role_required_bool

token_router = APIRouter()

logger = logging.getLogger("doorman.gateway")

@token_router.post("",
    description="Create a token",
    response_model=ResponseModel,
    responses={
        201: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Token created successfully"
                    }
                }
            }
        }
    }
)
async def create_token(token_data: TokenModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_tokens'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code="TKN001",
                    error_message="You do not have permission to manage tokens",
                ))
        return respond_rest(await TokenService.create_token(token_data, request_id))
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

@token_router.put("/{api_token_group}",
    description="Update a token",
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Token created successfully"
                    }
                }
            }
        }
    }
)
async def update_token(api_token_group:str, token_data: TokenModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_tokens'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code="TKN001",
                    error_message="You do not have permission to manage tokens",
                ))
        return respond_rest(await TokenService.update_token(api_token_group, token_data, request_id))
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

@token_router.delete("/{api_token_group}",
    description="Delete a token",
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Token created successfully"
                    }
                }
            }
        }
    }
)
async def delete_token(api_token_group:str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_tokens'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code="TKN001",
                    error_message="You do not have permission to manage tokens",
                ))
        return respond_rest(await TokenService.delete_token(api_token_group, request_id))
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

@token_router.post("/{username}",
    description="Add tokens for a user",
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Tokens added successfully"
                    }
                }
            }
        }
    }
)
async def add_user_tokens(username: str, token_data: UserTokenModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_tokens'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code="TKN001",
                    error_message="You do not have permission to manage tokens",
                ))
        return respond_rest(await TokenService.add_tokens(username, token_data, request_id))
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

@token_router.get("/all",
    description="Get all user tokens",
    response_model=List[UserTokenModel]
)
async def get_roles(request: Request, page: int = 1, page_size: int = 10):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_tokens'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code="TKN002",
                    error_message="Unable to retrieve tokens for all user",
                ))
        return respond_rest(await TokenService.get_all_tokens(page, page_size, request_id))
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

@token_router.get("/{username}",
    description="Get tokens for a user",
    response_model=UserTokenModel
)
async def get_tokens(username: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        if not payload.get("sub") == username and not await platform_role_required_bool(payload.get("sub"), 'manage_tokens'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code="TKN003",
                    error_message="Unable to retrieve tokens for user",
                ))
        return respond_rest(await TokenService.get_user_tokens(username, request_id))
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
