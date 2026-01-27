"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import logging
import time
import uuid

from fastapi import APIRouter, Request, HTTPException

from models.create_role_model import CreateRoleModel
from models.response_model import ResponseModel
from models.role_model_response import RoleModelResponse
from models.update_role_model import UpdateRoleModel
from services.role_service import RoleService
from utils.auth_util import auth_required
from utils.constants import Defaults, ErrorCodes, Headers, Messages, Roles
from utils.response_util import respond_rest
from utils.role_util import is_admin_role, is_admin_user, platform_role_required_bool

role_router = APIRouter()

logger = logging.getLogger('doorman.gateway')

"""
Add role

Request:
{}
Response:
{}
"""


@role_router.post(
    '',
    description='Add role',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {'application/json': {'example': {'message': 'Role created successfully'}}},
        }
    },
)
async def create_role(api_data: CreateRoleModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, Roles.MANAGE_ROLES):
            logger.error(f'User does not have permission to create roles')
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ROLE009',
                    error_message='You do not have permission to create roles',
                )
            )
        try:
            incoming_is_admin = bool(
                getattr(api_data, 'platform_admin', False)
            ) or api_data.role_name.strip().lower() in ('admin', 'platform admin')
        except Exception:
            incoming_is_admin = False
        if incoming_is_admin:
            if not await is_admin_user(username):
                return respond_rest(
                    ResponseModel(
                        status_code=403,
                        response_headers={Headers.REQUEST_ID: request_id},
                        error_code='ROLE013',
                        error_message='Only admin may create the admin role',
                    )
                )
        return respond_rest(await RoleService.create_role(api_data, request_id))
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code=ErrorCodes.UNEXPECTED,
                error_message=Messages.UNEXPECTED,
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


"""
Update role

Request:
{}
Response:
{}
"""


@role_router.put(
    '/{role_name}',
    description='Update role',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {'application/json': {'example': {'message': 'Role updated successfully'}}},
        }
    },
)
async def update_role(role_name: str, api_data: UpdateRoleModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        # DEBUG: Log the incoming data
        logger.info(f'DEBUG: Received model data: {api_data.dict()}')

        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, Roles.MANAGE_ROLES):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ROLE010',
                    error_message='You do not have permission to update roles',
                )
            )
        target_is_admin = await is_admin_role(role_name)
        if target_is_admin and not await is_admin_user(username):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ROLE014',
                    error_message='Only admin may modify the admin role',
                )
            )
        try:
            if getattr(api_data, 'platform_admin', None) is not None and not await is_admin_user(
                username
            ):
                return respond_rest(
                    ResponseModel(
                        status_code=403,
                        response_headers={Headers.REQUEST_ID: request_id},
                        error_code='ROLE015',
                        error_message='Only admin may change admin designation',
                    )
                )
        except Exception:
            pass
        return respond_rest(await RoleService.update_role(role_name, api_data, request_id))
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code=ErrorCodes.UNEXPECTED,
                error_message=Messages.UNEXPECTED,
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


"""
Delete role

Request:
{}
Response:
{}
"""


@role_router.delete(
    '/{role_name}',
    description='Delete role',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {'application/json': {'example': {'message': 'Role deleted successfully'}}},
        }
    },
)
async def delete_role(role_name: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, Roles.MANAGE_ROLES):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ROLE011',
                    error_message='You do not have permission to delete roles',
                )
            )
        target_is_admin = await is_admin_role(role_name)
        if target_is_admin and not await is_admin_user(username):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='ROLE016',
                    error_message='Only admin may delete the admin role',
                )
            )
        return respond_rest(await RoleService.delete_role(role_name, request_id))
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code=ErrorCodes.UNEXPECTED,
                error_message=Messages.UNEXPECTED,
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


"""
Endpoint

Request:
{}
Response:
{}
"""


@role_router.get('/all', description='Get all roles', response_model=list[RoleModelResponse])
async def get_roles(
    request: Request, page: int = Defaults.PAGE, page_size: int = Defaults.PAGE_SIZE
):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        data = await RoleService.get_roles(page, page_size, request_id)
        try:
            if data.get('status_code') == 200 and isinstance(data.get('response'), dict):
                rls = data['response'].get('roles') or []
                if not await is_admin_user(username):
                    filtered = []
                    for r in rls:
                        rn = (r.get('role_name') or '').strip()
                        if await is_admin_role(rn):
                            continue
                        if 'platform_admin' in r:
                            r = dict(r)
                            r.pop('platform_admin', None)
                        filtered.append(r)
                    data = dict(data)
                    data['response'] = {'roles': filtered}
        except Exception:
            pass
        return respond_rest(data)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code=ErrorCodes.UNEXPECTED,
                error_message=Messages.UNEXPECTED,
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


"""
Endpoint

Request:
{}
Response:
{}
"""


@role_router.get('/{role_name}', description='Get role', response_model=RoleModelResponse)
async def get_role(role_name: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        if await is_admin_role(role_name) and not await is_admin_user(username):
            return respond_rest(
                ResponseModel(
                    status_code=404,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_message='Role not found',
                )
            )
        data = await RoleService.get_role(role_name, request_id)
        try:
            if data.get('status_code') == 200 and not await is_admin_user(username):
                role = data.get('response') or {}
                if isinstance(role, dict) and 'platform_admin' in role:
                    role = dict(role)
                    role.pop('platform_admin', None)
                    data = dict(data)
                    data['response'] = role
        except Exception:
            pass
        return respond_rest(data)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code=ErrorCodes.UNEXPECTED,
                error_message=Messages.UNEXPECTED,
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


@role_router.get(
    '', description='Get all roles (base path)', response_model=list[RoleModelResponse]
)
async def get_roles_base(
    request: Request, page: int = Defaults.PAGE, page_size: int = Defaults.PAGE_SIZE
):
    """Convenience alias for GET /platform/role/all to support clients/tests
    that expect listing at the base collection path.
    """
    return await get_roles(request, page, page_size)
