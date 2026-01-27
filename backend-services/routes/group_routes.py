"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import logging
import time
import uuid

from fastapi import APIRouter, Request, HTTPException

from models.create_group_model import CreateGroupModel
from models.group_model_response import GroupModelResponse
from models.response_model import ResponseModel
from models.update_group_model import UpdateGroupModel
from services.group_service import GroupService
from utils.auth_util import auth_required
from utils.constants import Defaults, ErrorCodes, Headers, Messages, Roles
from utils.response_util import process_response, respond_rest
from utils.role_util import platform_role_required_bool

group_router = APIRouter()

logger = logging.getLogger('doorman.gateway')

"""
Add group

Request:
{}
Response:
{}
"""


@group_router.post(
    '',
    description='Add group',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {'application/json': {'example': {'message': 'Group created successfully'}}},
        }
    },
)
async def create_group(api_data: CreateGroupModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, Roles.MANAGE_GROUPS):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='GRP008',
                    error_message='You do not have permission to create groups',
                )
            )
        return respond_rest(await GroupService.create_group(api_data, request_id))
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
Update group

Request:
{}
Response:
{}
"""


@group_router.put(
    '/{group_name}',
    description='Update group',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {'application/json': {'example': {'message': 'Group updated successfully'}}},
        }
    },
)
async def update_group(group_name: str, api_data: UpdateGroupModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, Roles.MANAGE_GROUPS):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='GRP009',
                    error_message='You do not have permission to update groups',
                )
            )
        return respond_rest(await GroupService.update_group(group_name, api_data, request_id))
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
Delete group

Request:
{}
Response:
{}
"""


@group_router.delete(
    '/{group_name}',
    description='Delete group',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {'application/json': {'example': {'message': 'Group deleted successfully'}}},
        }
    },
)
async def delete_group(group_name: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, Roles.MANAGE_GROUPS):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='GRP010',
                    error_message='You do not have permission to delete groups',
                )
            )
        return respond_rest(await GroupService.delete_group(group_name, request_id))
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


@group_router.get('/all', description='Get all groups', response_model=list[GroupModelResponse])
async def get_groups(
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
        return respond_rest(await GroupService.get_groups(page, page_size, request_id))
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return process_response(
            ResponseModel(
                status_code=500,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code=ErrorCodes.UNEXPECTED,
                error_message=Messages.UNEXPECTED,
            ).dict(),
            'rest',
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


@group_router.get('/{group_name}', description='Get group', response_model=GroupModelResponse)
async def get_group(group_name: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        return respond_rest(await GroupService.get_group(group_name, request_id))
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return process_response(
            ResponseModel(
                status_code=500,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code=ErrorCodes.UNEXPECTED,
                error_message=Messages.UNEXPECTED,
            ).dict(),
            'rest',
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')
