"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

# External imports
from typing import List
from fastapi import APIRouter, Depends, Request
import uuid
import time
import logging

# Internal imports
from models.response_model import ResponseModel
from models.user_credits_model import UserCreditModel
from models.credit_model import CreditModel
from services.credit_service import CreditService
from utils.auth_util import auth_required
from utils.response_util import respond_rest, process_response
from utils.role_util import platform_role_required_bool
from utils.audit_util import audit

credit_router = APIRouter()

logger = logging.getLogger('doorman.gateway')

"""
Endpoint

Request:
{}
Response:
{}
"""


@credit_router.get('/defs',
    description='List credit definitions',
    response_model=ResponseModel,
    responses={
        200: {'description': 'Successful Response'}
    }
)

async def list_credit_definitions(request: Request, page: int = 1, page_size: int = 50):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, 'manage_credits'):
            return respond_rest(ResponseModel(
                status_code=403,
                error_code='CRD002',
                error_message='Unable to retrieve credits'
            ))
        return respond_rest(await CreditService.list_credit_defs(page, page_size, request_id))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='GTW999',
            error_message='An unexpected error occurred'
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


@credit_router.get('/defs/{api_credit_group}',
    description='Get a credit definition',
    response_model=ResponseModel,
)

async def get_credit_definition(api_credit_group: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, 'manage_credits'):
            return respond_rest(ResponseModel(
                status_code=403,
                error_code='CRD002',
                error_message='Unable to retrieve credits'
            ))
        return respond_rest(await CreditService.get_credit_def(api_credit_group, request_id))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='GTW999',
            error_message='An unexpected error occurred'
        ).dict(), 'rest')
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Create a credit definition

Request:
{}
Response:
{}
"""


@credit_router.post('',
    description='Create a credit definition',
    response_model=ResponseModel,
    responses={
        201: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'message': 'Credit definition created successfully'
                    }
                }
            }
        }
    }
)

async def create_credit(credit_data: CreditModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, 'manage_credits'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code='CRD001',
                    error_message='You do not have permission to manage credits',
                ))
        result = await CreditService.create_credit(credit_data, request_id)
        audit(request, actor=username, action='credit_def.create', target=credit_data.api_credit_group, status=result.get('status_code'), details=None, request_id=request_id)
        return respond_rest(result)
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                'request_id': request_id
            },
            error_code='GTW999',
            error_message='An unexpected error occurred'
            ).dict(), 'rest')
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Update a credit definition

Request:
{}
Response:
{}
"""


@credit_router.put('/{api_credit_group}',
    description='Update a credit definition',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'message': 'Credit definition updated successfully'
                    }
                }
            }
        }
    }
)

async def update_credit(api_credit_group:str, credit_data: CreditModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, 'manage_credits'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code='CRD001',
                    error_message='You do not have permission to manage credits',
                ))
        result = await CreditService.update_credit(api_credit_group, credit_data, request_id)
        audit(request, actor=username, action='credit_def.update', target=api_credit_group, status=result.get('status_code'), details=None, request_id=request_id)
        return respond_rest(result)
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                'request_id': request_id
            },
            error_code='GTW999',
            error_message='An unexpected error occurred'
            ).dict(), 'rest')
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Delete a credit definition

Request:
{}
Response:
{}
"""


@credit_router.delete('/{api_credit_group}',
    description='Delete a credit definition',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'message': 'Credit definition deleted successfully'
                    }
                }
            }
        }
    }
)

async def delete_credit(api_credit_group:str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, 'manage_credits'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code='CRD001',
                    error_message='You do not have permission to manage credits',
                ))
        result = await CreditService.delete_credit(api_credit_group, request_id)
        audit(request, actor=username, action='credit_def.delete', target=api_credit_group, status=result.get('status_code'), details=None, request_id=request_id)
        return respond_rest(result)
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                'request_id': request_id
            },
            error_code='GTW999',
            error_message='An unexpected error occurred'
            ).dict(), 'rest')
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Add credits for a user

Request:
{}
Response:
{}
"""


@credit_router.post('/{username}',
    description='Add credits for a user',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'message': 'Credits saved successfully'
                    }
                }
            }
        }
    }
)

async def add_user_credits(username: str, credit_data: UserCreditModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, 'manage_credits'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code='CRD001',
                    error_message='You do not have permission to manage credits',
                ))
        result = await CreditService.add_credits(username, credit_data, request_id)
        audit(request, actor=username, action='user_credits.save', target=username, status=result.get('status_code'), details={'groups': list((credit_data.users_credits or {}).keys())}, request_id=request_id)
        return respond_rest(result)
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                'request_id': request_id
            },
            error_code='GTW999',
            error_message='An unexpected error occurred'
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


@credit_router.get('/all',
    description='Get all user credits',
    response_model=List[UserCreditModel]
)

async def get_all_users_credits(request: Request, page: int = 1, page_size: int = 10, search: str = ''):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, 'manage_credits'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code='CRD002',
                    error_message='Unable to retrieve credits for all users',
                ))
        return respond_rest(await CreditService.get_all_credits(page, page_size, request_id, search=search))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                'request_id': request_id
            },
            error_code='GTW999',
            error_message='An unexpected error occurred'
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


@credit_router.get('/{username}',
    description='Get credits for a user',
    response_model=UserCreditModel
)

async def get_credits(username: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        if not payload.get('sub') == username and not await platform_role_required_bool(payload.get('sub'), 'manage_credits'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code='CRD003',
                    error_message='Unable to retrieve credits for user',
                ))
        return respond_rest(await CreditService.get_user_credits(username, request_id))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={
                'request_id': request_id
            },
            error_code='GTW999',
            error_message='An unexpected error occurred'
            ))
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')
