"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from typing import List
from fastapi import APIRouter, Depends, Request
from fastapi_jwt_auth import AuthJWT

from models.response_model import ResponseModel
from models.user_tokens_model import UserTokenModel
from models.token_model import TokenModel
from utils.auth_util import auth_required
from utils.response_util import process_response\

import uuid
import time
import logging

from utils.role_util import platform_role_required_bool

token_router = APIRouter()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

@token_router.post("",
    description="Create a token",
    dependencies=[
        Depends(auth_required)
    ],
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
async def create_token(token_data: TokenModel, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_tokens'):
            return process_response(
                ResponseModel(
                    status_code=403,
                    error_code="TKN001",
                    error_message="You do not have permission to manage tokens",
                ).dict()
            )
        return process_response(await TokenService.create_token(token_data, request_id))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict())
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@token_router.post("/{username}",
    description="Add tokens",
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
                        "message": "Tokens added successfully"
                    }
                }
            }
        }
    }
)
async def add_user_tokens(token_data: TokenModel, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_tokens'):
            return process_response(
                ResponseModel(
                    status_code=403,
                    error_code="TKN001",
                    error_message="You do not have permission to manage tokens",
                ).dict()
            )
        return process_response(await TokenService.add_tokens(token_data, request_id))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict())
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@token_router.get("/all",
    description="Get all user tokens",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=List[UserTokenModel]
)
async def get_roles(request: Request, Authorize: AuthJWT = Depends(), page: int = 1, page_size: int = 10):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_tokens'):
            return process_response(
                ResponseModel(
                    status_code=403,
                    error_code="TKN002",
                    error_message="Unable to retrieve tokens for all user",
                ).dict()
            )
        return process_response(await TokenService.get_all_tokens(page, page_size, request_id))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict())
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@token_router.get("/{username}",
    description="Get tokens for a user",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=UserTokenModel
)
async def get_tokens(username: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not Authorize.get_jwt_subject == username and not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_tokens'):
            return process_response(
                ResponseModel(
                    status_code=403,
                    error_code="TKN003",
                    error_message="Unable to retrieve tokens for user",
                ).dict()
            )
        return process_response(await TokenService.get_user_tokens(username, request_id))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict())
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")