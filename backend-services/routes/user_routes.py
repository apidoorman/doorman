"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

# External imports
from typing import List
from fastapi import APIRouter, Request, HTTPException
import uuid
import time
import logging

# Internal imports
from models.response_model import ResponseModel
from models.user_model_response import UserModelResponse
from services.user_service import UserService
from utils.auth_util import auth_required
from utils.response_util import respond_rest, process_response
from utils.role_util import platform_role_required_bool, is_admin_user, is_admin_role
from utils.constants import ErrorCodes, Messages, Defaults, Roles, Headers
from utils.database import role_collection
from models.create_user_model import CreateUserModel
from models.update_user_model import UpdateUserModel
from models.update_password_model import UpdatePasswordModel

user_router = APIRouter()

logger = logging.getLogger('doorman.gateway')

async def _safe_is_admin_user(username: str) -> bool:
    try:
        return await is_admin_user(username)
    except Exception:
        return False

async def _safe_is_admin_role(role: str) -> bool:
    try:
        return await is_admin_role(role)
    except Exception:
        return False

"""
Add user

Request:
{}
Response:
{}
"""

@user_router.post('',
    description='Add user',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'message': 'User created successfully'
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
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, Roles.MANAGE_USERS):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code='USR006',
                    error_message='Can only update your own information'
                ))
        if user_data.role and await _safe_is_admin_role(user_data.role):
            if not await _safe_is_admin_user(username):
                return respond_rest(
                    ResponseModel(
                        status_code=403,
                        error_code='USR015',
                        error_message='Only admin may create users with the admin role'
                    ))
        return respond_rest(await UserService.create_user(user_data, request_id))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                Headers.REQUEST_ID: request_id
            },
            error_code=ErrorCodes.UNEXPECTED,
            error_message=Messages.UNEXPECTED
            ).dict(), 'rest')
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Update user

Request:
{}
Response:
{}
"""

@user_router.put('/{username}',
    description='Update user',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'message': 'User updated successfully'
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
        auth_username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not auth_username == username and not await platform_role_required_bool(auth_username, Roles.MANAGE_USERS):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code='USR006',
                    error_message='Can only update your own information'
                ))
        if await _safe_is_admin_user(username) and not await _safe_is_admin_user(auth_username):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code='USR012',
                    error_message='Only admin may modify admin users'
                ))
        new_role = api_data.role
        if new_role is not None:
            target_is_admin = await _safe_is_admin_user(username)
            new_is_admin = await _safe_is_admin_role(new_role)
            if (target_is_admin or new_is_admin) and not await _safe_is_admin_user(auth_username):
                return respond_rest(
                    ResponseModel(
                        status_code=403,
                        error_code='USR013',
                        error_message='Only admin may change admin role assignments'
                    ))
        return respond_rest(await UserService.update_user(username, api_data, request_id))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                Headers.REQUEST_ID: request_id
            },
            error_code=ErrorCodes.UNEXPECTED,
            error_message=Messages.UNEXPECTED
            ).dict(), 'rest')
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Delete user

Request:
{}
Response:
{}
"""

@user_router.delete('/{username}',
    description='Delete user',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'message': 'User deleted successfully'
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
        auth_username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not auth_username == username and not await platform_role_required_bool(auth_username, Roles.MANAGE_USERS):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code='USR007',
                    error_message='Can only delete your own account'
                ))
        if await _safe_is_admin_user(username) and not await _safe_is_admin_user(auth_username):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code='USR014',
                    error_message='Only admin may delete admin users'
                ))
        return respond_rest(await UserService.delete_user(username, request_id))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                Headers.REQUEST_ID: request_id
            },
            error_code=ErrorCodes.UNEXPECTED,
            error_message=Messages.UNEXPECTED
            ).dict(), 'rest')
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Update user password

Request:
{}
Response:
{}
"""

@user_router.put('/{username}/update-password',
    description='Update user password',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'message': 'Password updated successfully'
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
        auth_username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not auth_username == username and not await platform_role_required_bool(auth_username, Roles.MANAGE_USERS):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={
                    Headers.REQUEST_ID: request_id
                },
                error_code='USR006',
                error_message='Can only update your own password'
            ))
        return respond_rest(await UserService.update_password(username, api_data, request_id))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                Headers.REQUEST_ID: request_id
            },
            error_code=ErrorCodes.UNEXPECTED,
            error_message=Messages.UNEXPECTED
            ).dict(), 'rest')
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Endpoint

Request:
{}
Response:
{}
"""

@user_router.get('/me',
    description='Get user by username',
    response_model=UserModelResponse
    )

async def get_user_by_username(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        auth_username = payload.get('sub')
        logger.info(f'{request_id} | Username: {auth_username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        return respond_rest(await UserService.get_user_by_username(auth_username, request_id))
    except HTTPException as e:
        return respond_rest(ResponseModel(
            status_code=e.status_code,
            response_headers={
                Headers.REQUEST_ID: request_id
            },
            error_code=ErrorCodes.HTTP_EXCEPTION,
            error_message=e.detail
            ))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={
                Headers.REQUEST_ID: request_id
            },
            error_code=ErrorCodes.UNEXPECTED,
            error_message=Messages.UNEXPECTED
            ))
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Endpoint

Request:
{}
Response:
{}
"""

@user_router.get('/all',
    description='Get all users',
    response_model=List[UserModelResponse]
)

async def get_all_users(request: Request, page: int = Defaults.PAGE, page_size: int = Defaults.PAGE_SIZE):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        data = await UserService.get_all_users(page, page_size, request_id)
        if data.get('status_code') == 200 and isinstance(data.get('response'), dict) and not await _safe_is_admin_user(username):
            users = data['response'].get('users') or []
            filtered = []
            for u in users:
                if await _safe_is_admin_role(u.get('role')):
                    continue
                filtered.append(u)
            data = dict(data)
            data['response'] = {'users': filtered}
        return process_response(data, 'rest')
    except HTTPException as e:
        return process_response(ResponseModel(
            status_code=e.status_code,
            response_headers={
                Headers.REQUEST_ID: request_id
            },
            error_code=ErrorCodes.HTTP_EXCEPTION,
            error_message=e.detail
            ).dict(), 'rest')
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                Headers.REQUEST_ID: request_id
            },
            error_code=ErrorCodes.UNEXPECTED,
            error_message=Messages.UNEXPECTED
            ).dict(), 'rest')
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Endpoint

Request:
{}
Response:
{}
"""

@user_router.get('/{username}',
    description='Get user by username',
    response_model=UserModelResponse
)

async def get_user_by_username(username: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        auth_username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not auth_username == username and not await platform_role_required_bool(auth_username, 'manage_users'):
            return process_response(
                ResponseModel(
                    status_code=403,
                    error_code='USR008',
                    error_message='Unable to retrieve information for user',
                ).dict(), 'rest')
        if not await _safe_is_admin_user(auth_username) and await _safe_is_admin_user(username):
            return process_response(ResponseModel(
                status_code=404,
                response_headers={Headers.REQUEST_ID: request_id},
                error_message='User not found'
            ).dict(), 'rest')
        return process_response(await UserService.get_user_by_username(username, request_id), 'rest')
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                Headers.REQUEST_ID: request_id
            },
            error_code=ErrorCodes.UNEXPECTED,
            error_message=Messages.UNEXPECTED
            ).dict(), 'rest')
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Endpoint

Request:
{}
Response:
{}
"""

@user_router.get('/email/{email}',
    description='Get user by email',
    response_model=List[UserModelResponse]
)

async def get_user_by_email(email: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        data = await UserService.get_user_by_email(username, email, request_id)
        if data.get('status_code') == 200 and isinstance(data.get('response'), dict) and not await _safe_is_admin_user(username):
            u = data.get('response')
            if await _safe_is_admin_role(u.get('role')):
                return process_response(ResponseModel(
                    status_code=404,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_message='User not found'
                ).dict(), 'rest')
        return process_response(data, 'rest')
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                Headers.REQUEST_ID: request_id
            },
            error_code=ErrorCodes.UNEXPECTED,
            error_message=Messages.UNEXPECTED
            ).dict(), 'rest')
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')
