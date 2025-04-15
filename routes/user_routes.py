"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from typing import List
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from models.response_model import ResponseModel
from models.user_model_response import UserModelResponse
from services.user_service import UserService
from utils.auth_util import auth_required
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool
from models.create_user_model import CreateUserModel
from models.update_user_model import UpdateUserModel
from models.update_password_model import UpdatePasswordModel

import uuid
import time
import logging

user_router = APIRouter()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

@user_router.post("",
    description="Add user",
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
                        "message": "User created successfully"
                    }
                }
            }
        }
    }
)
async def create_user(user_data: CreateUserModel, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_users'):
            return process_response(
                ResponseModel(
                    status_code=403,
                    error_code="ACCS002",
                    error_message="Can only update your own information"
                ).dict()
            )
        return process_response(await UserService.create_user(user_data, request_id))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@user_router.put("/{username}",
    description="Update user",
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
                        "message": "User updated successfully"
                    }
                }
            }
        }
    }
)
async def update_user(username: str, api_data: UpdateUserModel, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not Authorize.get_jwt_subject() == username and not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_users'):
            return process_response(
                ResponseModel(
                    status_code=403,
                    error_code="ACCS002",
                    error_message="Can only update your own information"
                ).dict()
            )
        return process_response(await UserService.update_user(username, api_data, request_id))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")
    
@user_router.delete("/{username}",
    description="Delete user",
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
                        "message": "User deleted successfully"
                    }
                }
            }
        }
    }
)
async def delete_user(username: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not Authorize.get_jwt_subject() == username and not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_users'):
            return process_response(
                ResponseModel(
                    status_code=403, 
                    error_code="ACCS001",
                    error_message="Can only delete your own account"
                ).dict()
            )
        return process_response(await UserService.delete_user(username, request_id))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@user_router.put("/{username}/update-password",
    description="Update user password",
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
                        "message": "Password updated successfully"
                    }
                }
            }
        }
    }
)
async def update_user_password(username: str, api_data: UpdatePasswordModel, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not Authorize.get_jwt_subject() == username and not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_users'):
            raise HTTPException(status_code=400, detail="Can only update your own password")
        return process_response(await UserService.update_password(username, api_data, request_id))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@user_router.get("/{username}",
    description="Get user by username",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=UserModelResponse
)
async def get_user_by_username(username: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await UserService.get_user_by_username(username, request_id))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@user_router.get("/email/{email}",
    description="Get user by email",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=List[UserModelResponse]
)
async def get_user_by_email(email: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await UserService.get_user_by_email(email, request_id))
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")