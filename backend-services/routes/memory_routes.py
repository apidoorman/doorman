"""
Routes for dumping and restoring in-memory database state.
"""

# External imports
from fastapi import APIRouter, Request
from typing import Optional
from pydantic import BaseModel
import os
import uuid
import time
import logging

# Internal imports
from utils.response_util import process_response
from models.response_model import ResponseModel
from utils.auth_util import auth_required
from utils.role_util import platform_role_required_bool
from utils.database import database
from utils.memory_dump_util import dump_memory_to_file, restore_memory_from_file

memory_router = APIRouter()
logger = logging.getLogger('doorman.gateway')

class DumpRequest(BaseModel):
    path: Optional[str] = None

"""
Endpoint

Request:
{}
Response:
{}
"""

@memory_router.post('/memory/dump',
    description='Dump in-memory database to an encrypted file',
    response_model=ResponseModel,
)

async def memory_dump(request: Request, body: Optional[DumpRequest] = None):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')

        if not await platform_role_required_bool(username, 'manage_security'):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='SEC003',
                error_message='You do not have permission to perform memory dump'
            ).dict(), 'rest')

        if not database.memory_only:
            return process_response(ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='MEM001',
                error_message='Memory dump available only in memory-only mode'
            ).dict(), 'rest')

        if not os.getenv('MEM_ENCRYPTION_KEY'):
            return process_response(ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='MEM002',
                error_message='MEM_ENCRYPTION_KEY is not configured'
            ).dict(), 'rest')

        path = None
        if body and body.path:
            path = body.path
        dump_path = dump_memory_to_file(path)
        return process_response(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            message='Memory dump created successfully',
            response={'response': {'path': dump_path}}
        ).dict(), 'rest')
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

class RestoreRequest(BaseModel):
    path: Optional[str] = None

"""
Endpoint

Request:
{}
Response:
{}
"""

@memory_router.post('/memory/restore',
    description='Restore in-memory database from an encrypted file',
    response_model=ResponseModel,
)

async def memory_restore(request: Request, body: Optional[RestoreRequest] = None):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')

        if not await platform_role_required_bool(username, 'manage_security'):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='SEC004',
                error_message='You do not have permission to perform memory restore'
            ).dict(), 'rest')

        if not database.memory_only:
            return process_response(ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='MEM001',
                error_message='Memory restore available only in memory-only mode'
            ).dict(), 'rest')

        if not os.getenv('MEM_ENCRYPTION_KEY'):
            return process_response(ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='MEM002',
                error_message='MEM_ENCRYPTION_KEY is not configured'
            ).dict(), 'rest')

        path = None
        if body and body.path:
            path = body.path
        info = restore_memory_from_file(path)
        return process_response(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            message='Memory restore completed',
            response={'response': info}
        ).dict(), 'rest')
    except FileNotFoundError as e:
        return process_response(ResponseModel(
            status_code=404,
            response_headers={'request_id': request_id},
            error_code='MEM003',
            error_message=str(e)
        ).dict(), 'rest')
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
