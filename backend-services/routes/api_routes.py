"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Request, Response

from models.api_model_response import ApiModelResponse
from models.create_api_model import CreateApiModel
from models.response_model import ResponseModel
from models.update_api_model import UpdateApiModel
from services.api_service import ApiService
from utils.audit_util import audit
from utils.auth_util import auth_required
from utils.constants import ErrorCodes, Headers, Messages, Roles
from utils.response_util import process_response, respond_rest
from utils.role_util import platform_role_required_bool

api_router = APIRouter()
logger = logging.getLogger('doorman.gateway')

"""
Add API

Request:
{}
Response:
{}
"""


@api_router.post(
    '',
    description='Add API',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {'application/json': {'example': {'message': 'API created successfully'}}},
        }
    },
)
async def create_api(request: Request, api_data: CreateApiModel) -> Response:
    payload = await auth_required(request)
    username = payload.get('sub')
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    logger.info(
        f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
    )
    logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
    try:
        if not await platform_role_required_bool(username, Roles.MANAGE_APIS):
            logger.warning(f'{request_id} | Permission denied for user: {username}')
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='API007',
                    error_message='You do not have permission to create APIs',
                )
            )
        result = await ApiService.create_api(api_data, request_id)
        audit(
            request,
            actor=username,
            action='api.create',
            target=f'{api_data.api_name}/{api_data.api_version}',
            status=result.get('status_code'),
            details={'message': result.get('message')},
            request_id=request_id,
        )
        return respond_rest(result)
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
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
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')


"""
Update API

Request:
{}
Response:
{}
"""


@api_router.put(
    '/{api_name}/{api_version}',
    description='Update API',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {'application/json': {'example': {'message': 'API updated successfully'}}},
        }
    },
)
async def update_api(
    api_name: str, api_version: str, request: Request, api_data: UpdateApiModel
) -> Response:
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, Roles.MANAGE_APIS):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='API008',
                    error_message='You do not have permission to update APIs',
                )
            )
        result = await ApiService.update_api(api_name, api_version, api_data, request_id)
        audit(
            request,
            actor=username,
            action='api.update',
            target=f'{api_name}/{api_version}',
            status=result.get('status_code'),
            details={'message': result.get('message')},
            request_id=request_id,
        )
        return respond_rest(result)
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
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
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')


"""
Get API

Request:
{}
Response:
{}
"""


@api_router.get(
    '/{api_name}/{api_version}',
    description='Get API',
    response_model=ApiModelResponse,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {'application/json': {'example': {'message': 'API retrieved successfully'}}},
        }
    },
)
async def get_api_by_name_version(api_name: str, api_version: str, request: Request) -> Response:
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        return respond_rest(
            await ApiService.get_api_by_name_version(api_name, api_version, request_id)
        )
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
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
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')


"""
Delete API

Request:
{}
Response:
{}
"""


@api_router.delete(
    '/{api_name}/{api_version}',
    description='Delete API',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {'application/json': {'example': {'message': 'API deleted successfully'}}},
        }
    },
)
async def delete_api(api_name: str, api_version: str, request: Request) -> Response:
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        result = await ApiService.delete_api(api_name, api_version, request_id)
        audit(
            request,
            actor=username,
            action='api.delete',
            target=f'{api_name}/{api_version}',
            status=result.get('status_code'),
            details={'message': result.get('message')},
            request_id=request_id,
        )
        return respond_rest(result)
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            ).dict(),
            'rest',
        )
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


@api_router.get('/all', description='Get all APIs', response_model=list[ApiModelResponse])
async def get_all_apis(page: int, page_size: int, request: Request) -> Response:
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        return respond_rest(await ApiService.get_apis(page, page_size, request_id))
    except HTTPException as e:
        # Surface 401/403 properly for tests that probe unauthorized access
        return respond_rest(
            ResponseModel(
                status_code=e.status_code,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code='API_AUTH',
                error_message=e.detail,
            )
        )
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
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
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')


@api_router.get('', description='Get all APIs (base path)', response_model=list[ApiModelResponse])
async def get_all_apis_base(page: int, page_size: int, request: Request) -> Response:
    """Convenience alias for GET /platform/api/all to support tests and clients
    that expect listing at the base collection path.
    """
    # Explicitly forward through the same auth/error handling as get_all_apis
    request_id = str(uuid.uuid4())
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        return respond_rest(await ApiService.get_apis(page, page_size, request_id))
    except HTTPException as e:
        return respond_rest(
            ResponseModel(
                status_code=e.status_code,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code='API_AUTH',
                error_message=e.detail,
            )
        )
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(
            ResponseModel(
                status_code=500,
                response_headers={Headers.REQUEST_ID: request_id},
                error_code=ErrorCodes.UNEXPECTED,
                error_message=Messages.UNEXPECTED,
            ).dict(),
            'rest',
        )
