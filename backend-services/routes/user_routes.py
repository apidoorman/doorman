"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

from http.client import HTTPException
from typing import List
from fastapi import APIRouter, Request

from models.response_model import ResponseModel
from models.user_model_response import UserModelResponse
from services.user_service import UserService
from utils.auth_util import auth_required
from utils.response_util import respond_rest, process_response
from utils.role_util import platform_role_required_bool, is_admin_user, is_admin_role
from utils.database import role_collection
from models.create_user_model import CreateUserModel
from models.update_user_model import UpdateUserModel
from models.update_password_model import UpdatePasswordModel

import uuid
import time
import logging

user_router = APIRouter()

logger = logging.getLogger("doorman.gateway")

@user_router.post("",
    description="Add user",
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
async def create_user(user_data: CreateUserModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_users'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code="USR006",
                    error_message="Can only update your own information"
                ))
        # Only admin may create a user with the admin role
        try:
            if user_data.role and await is_admin_role(user_data.role):
                if not await is_admin_user(username):
                    return respond_rest(
                        ResponseModel(
                            status_code=403,
                            error_code="USR015",
                            error_message="Only admin may create users with the admin role"
                        ))
        except Exception:
            pass
        return respond_rest(await UserService.create_user(user_data, request_id))
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

@user_router.put("/{username}",
    description="Update user",
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
async def update_user(username: str, api_data: UpdateUserModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        auth_username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not auth_username == username and not await platform_role_required_bool(auth_username, 'manage_users'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code="USR006",
                    error_message="Can only update your own information"
                ))
        # If target user is an admin user, only admin may edit
        try:
            if await is_admin_user(username) and not await is_admin_user(auth_username):
                return respond_rest(
                    ResponseModel(
                        status_code=403,
                        error_code="USR012",
                        error_message="Only admin may modify admin users"
                    ))
        except Exception:
            pass
        # If changing role to or from admin, only admin may do so
        try:
            new_role = api_data.role
            if new_role is not None:
                target_is_admin = await is_admin_user(username)
                new_is_admin = await is_admin_role(new_role)
                if (target_is_admin or new_is_admin) and not await is_admin_user(auth_username):
                    return respond_rest(
                        ResponseModel(
                            status_code=403,
                            error_code="USR013",
                            error_message="Only admin may change admin role assignments"
                        ))
        except Exception:
            pass
        return respond_rest(await UserService.update_user(username, api_data, request_id))
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
    
@user_router.delete("/{username}",
    description="Delete user",
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
async def delete_user(username: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        auth_username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not auth_username == username and not await platform_role_required_bool(auth_username, 'manage_users'):
            return respond_rest(
                ResponseModel(
                    status_code=403, 
                    error_code="USR007",
                    error_message="Can only delete your own account"
                ))
        # Only admin may delete admin users
        try:
            if await is_admin_user(username) and not await is_admin_user(auth_username):
                return respond_rest(
                    ResponseModel(
                        status_code=403,
                        error_code="USR014",
                        error_message="Only admin may delete admin users"
                    ))
        except Exception:
            pass
        return respond_rest(await UserService.delete_user(username, request_id))
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

@user_router.put("/{username}/update-password",
    description="Update user password",
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
async def update_user_password(username: str, api_data: UpdatePasswordModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        auth_username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not auth_username == username and not await platform_role_required_bool(auth_username, 'manage_users'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={
                    "request_id": request_id
                },
                error_code="USR006",
                error_message="Can only update your own password"
            ))
        return respond_rest(await UserService.update_password(username, api_data, request_id))
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

@user_router.get("/me",
    description="Get user by username",
    response_model=UserModelResponse
    )
async def get_user_by_username(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        auth_username = payload.get("sub")
        logger.info(f"{request_id} | Username: {auth_username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return respond_rest(await UserService.get_user_by_username(auth_username, request_id))
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


@user_router.get("/all",
    description="Get all users",
    response_model=List[UserModelResponse]
)
async def get_all_users(request: Request, page: int = 1, page_size: int = 10):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        data = await UserService.get_all_users(page, page_size, request_id)
        try:
            if data.get('status_code') == 200 and isinstance(data.get('response'), dict) and not await is_admin_user(username):
                users = data['response'].get('users') or []
                filtered = []
                for u in users:
                    try:
                        if await is_admin_role(u.get('role')):
                            continue
                    except Exception:
                        pass
                    filtered.append(u)
                data = dict(data)
                data['response'] = {'users': filtered}
        except Exception:
            pass
        return process_response(data, "rest")
    except HTTPException as e:
        return process_response(ResponseModel(
            status_code=e.status_code,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW998",
            error_message=e.detail
            ).dict(), "rest")
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

@user_router.get("/{username}",
    description="Get user by username",
    response_model=UserModelResponse
)
async def get_user_by_username(username: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        auth_username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not auth_username == username and not await platform_role_required_bool(auth_username, 'manage_users'):
            return process_response(
                ResponseModel(
                    status_code=403,
                    error_code="USR008",
                    error_message="Unable to retrieve information for user",
                ).dict(), "rest")
        # Hide admin users from non-admin viewers
        try:
            if not await is_admin_user(auth_username) and await is_admin_user(username):
                return process_response(ResponseModel(
                    status_code=404,
                    response_headers={"request_id": request_id},
                    error_message="User not found"
                ).dict(), "rest")
        except Exception:
            pass
        return process_response(await UserService.get_user_by_username(username, request_id), "rest")
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

@user_router.get("/email/{email}",
    description="Get user by email",
    response_model=List[UserModelResponse]
)
async def get_user_by_email(email: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        data = await UserService.get_user_by_email(username, email, request_id)
        try:
            if data.get('status_code') == 200 and isinstance(data.get('response'), dict) and not await is_admin_user(username):
                u = data.get('response')
                if await is_admin_role(u.get('role')):
                    return process_response(ResponseModel(
                        status_code=404,
                        response_headers={"request_id": request_id},
                        error_message="User not found"
                    ).dict(), "rest")
        except Exception:
            pass
        return process_response(data, "rest")
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
