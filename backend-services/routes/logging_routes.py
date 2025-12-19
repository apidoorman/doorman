"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import io
import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from models.response_model import ResponseModel
from services.logging_service import LoggingService
from utils.auth_util import auth_required
from utils.constants import ErrorCodes, Headers, Messages, Roles
from utils.response_util import process_response, respond_rest
from utils.role_util import platform_role_required_bool

logging_router = APIRouter()

logger = logging.getLogger('doorman.logging')

"""
Get logs with filtering

Request:
{}
Response:
{}
"""


@logging_router.get(
    '/logs',
    description='Get logs with filtering',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'logs': [
                            {
                                'timestamp': '2024-01-01T12:00:00',
                                'level': 'INFO',
                                'message': 'Request processed',
                                'source': 'doorman.gateway',
                                'user': 'john_doe',
                                'api': 'customer',
                                'endpoint': '/api/customer/v1/users',
                                'method': 'GET',
                                'status_code': 200,
                                'response_time': '150.5',
                                'ip_address': '192.168.1.1',
                                'protocol': 'HTTP/1.1',
                                'request_id': '123e4567-e89b-12d3-a456-426614174000',
                            }
                        ],
                        'total': 100,
                        'has_more': False,
                    }
                }
            },
        }
    },
)
async def get_logs(
    request: Request,
    start_date: str | None = Query(None, description='Start date (YYYY-MM-DD)'),
    end_date: str | None = Query(None, description='End date (YYYY-MM-DD)'),
    start_time: str | None = Query(None, description='Start time (HH:MM)'),
    end_time: str | None = Query(None, description='End time (HH:MM)'),
    user: str | None = Query(None, description='Filter by user'),
    api: str | None = Query(None, description='Filter by API'),
    endpoint: str | None = Query(None, description='Filter by endpoint'),
    request_id: str | None = Query(None, description='Filter by request ID'),
    method: str | None = Query(None, description='Filter by HTTP method'),
    ip_address: str | None = Query(None, description='Filter by IP address'),
    min_response_time: str | None = Query(None, description='Minimum response time (ms)'),
    max_response_time: str | None = Query(None, description='Maximum response time (ms)'),
    level: str | None = Query(None, description='Filter by log level'),
    limit: int = Query(100, description='Number of logs to return', ge=1, le=1000),
    offset: int = Query(0, description='Number of logs to skip', ge=0),
):
    request_id_param = str(uuid.uuid4())
    start_time_param = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')

        logger.info(
            f'{request_id_param} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id_param} | Endpoint: {request.method} {str(request.url.path)}')

        if not await platform_role_required_bool(username, Roles.VIEW_LOGS):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id_param},
                    error_code='LOG001',
                    error_message='You do not have permission to view logs',
                )
            )

        logging_service = LoggingService()
        result = await logging_service.get_logs(
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            user=user,
            api=api,
            endpoint=endpoint,
            request_id=request_id,
            method=method,
            ip_address=ip_address,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            level=level,
            limit=limit,
            offset=offset,
            request_id_param=request_id_param,
        )

        return respond_rest(
            ResponseModel(
                status_code=200, response_headers={'request_id': request_id_param}, response=result
            )
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.critical(f'{request_id_param} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={Headers.REQUEST_ID: request_id_param},
                error_code=ErrorCodes.UNEXPECTED,
                error_message=Messages.UNEXPECTED,
            )
        )
    finally:
        end_time_param = time.time() * 1000
        logger.info(f'{request_id_param} | Total time: {str(end_time_param - start_time_param)}ms')


"""
Endpoint

Request:
{}
Response:
{}
"""


@logging_router.get(
    '/logs/files', description='Get list of available log files', response_model=ResponseModel
)
async def get_log_files(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')

        if not await platform_role_required_bool(username, Roles.VIEW_LOGS):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='LOG005',
                    error_message='You do not have permission to view log files',
                )
            )

        logging_service = LoggingService()
        log_files = logging_service.get_available_log_files()

        return respond_rest(
            ResponseModel(
                status_code=200,
                response_headers={'request_id': request_id},
                response={'log_files': log_files, 'count': len(log_files)},
            )
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
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
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')


"""
Get log statistics for dashboard

Request:
{}
Response:
{}
"""


@logging_router.get(
    '/logs/statistics',
    description='Get log statistics for dashboard',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'total_logs': 1000,
                        'error_count': 50,
                        'warning_count': 100,
                        'info_count': 800,
                        'debug_count': 50,
                        'avg_response_time': 150.5,
                        'top_apis': [
                            {'name': 'customer', 'count': 500},
                            {'name': 'orders', 'count': 300},
                        ],
                        'top_users': [
                            {'name': 'john_doe', 'count': 200},
                            {'name': 'jane_smith', 'count': 150},
                        ],
                        'top_endpoints': [
                            {'name': '/api/customer/v1/users', 'count': 100},
                            {'name': '/api/orders/v1/orders', 'count': 80},
                        ],
                    }
                }
            },
        }
    },
)
async def get_log_statistics(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')

        if not await platform_role_required_bool(username, Roles.VIEW_LOGS):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='LOG002',
                    error_message='You do not have permission to view log statistics',
                )
            )

        logging_service = LoggingService()
        statistics = await logging_service.get_log_statistics(request_id)

        return respond_rest(
            ResponseModel(
                status_code=200, response_headers={'request_id': request_id}, response=statistics
            )
        )

    except HTTPException as e:
        raise e
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
Export logs in various formats

Request:
{}
Response:
{}
"""


@logging_router.get(
    '/logs/export',
    description='Export logs in various formats',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'format': 'json',
                        'data': '[{"timestamp": "2024-01-01T12:00:00", "level": "INFO"}]',
                        'filename': 'logs_export_20240101_120000.json',
                    }
                }
            },
        }
    },
)
async def export_logs(
    request: Request,
    format: str = Query('json', description='Export format (json, csv)'),
    start_date: str | None = Query(None, description='Start date (YYYY-MM-DD)'),
    end_date: str | None = Query(None, description='End date (YYYY-MM-DD)'),
    user: str | None = Query(None, description='Filter by user'),
    api: str | None = Query(None, description='Filter by API'),
    endpoint: str | None = Query(None, description='Filter by endpoint'),
    level: str | None = Query(None, description='Filter by log level'),
):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')

        if not await platform_role_required_bool(username, Roles.EXPORT_LOGS):
            return process_response(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='LOG003',
                    error_message='You do not have permission to export logs',
                ).dict(),
                'rest',
            )

        logging_service = LoggingService()

        filters = {}
        if user:
            filters['user'] = user
        if api:
            filters['api'] = api
        if endpoint:
            filters['endpoint'] = endpoint
        if level:
            filters['level'] = level

        export_result = await logging_service.export_logs(
            format=format,
            start_date=start_date,
            end_date=end_date,
            filters=filters,
            request_id=request_id,
        )

        return respond_rest(
            ResponseModel(
                status_code=200,
                response_headers={Headers.REQUEST_ID: request_id},
                response=export_result,
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


"""
Download logs as file

Request:
{}
Response:
{}
"""


@logging_router.get(
    '/logs/download',
    description='Download logs as file',
    include_in_schema=False,
    responses={
        200: {'description': 'File download', 'content': {'application/json': {}, 'text/csv': {}}}
    },
)
async def download_logs(
    request: Request,
    format: str = Query('json', description='Export format (json, csv)'),
    start_date: str | None = Query(None, description='Start date (YYYY-MM-DD)'),
    end_date: str | None = Query(None, description='End date (YYYY-MM-DD)'),
    user: str | None = Query(None, description='Filter by user'),
    api: str | None = Query(None, description='Filter by API'),
    endpoint: str | None = Query(None, description='Filter by endpoint'),
    level: str | None = Query(None, description='Filter by log level'),
):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')

        if not await platform_role_required_bool(username, Roles.EXPORT_LOGS):
            return process_response(
                ResponseModel(
                    status_code=403,
                    response_headers={Headers.REQUEST_ID: request_id},
                    error_code='LOG004',
                    error_message='You do not have permission to download logs',
                ).dict(),
                'rest',
            )

        logging_service = LoggingService()

        filters = {}
        if user:
            filters['user'] = user
        if api:
            filters['api'] = api
        if endpoint:
            filters['endpoint'] = endpoint
        if level:
            filters['level'] = level

        export_result = await logging_service.export_logs(
            format=format,
            start_date=start_date,
            end_date=end_date,
            filters=filters,
            request_id=request_id,
        )

        file_data = export_result['data'].encode('utf-8')
        io.BytesIO(file_data)

        content_type = 'application/json' if format.lower() == 'json' else 'text/csv'

        return StreamingResponse(
            io.BytesIO(file_data),
            media_type=content_type,
            headers={
                'Content-Disposition': f'attachment; filename={export_result["filename"]}',
                Headers.REQUEST_ID: request_id,
            },
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
