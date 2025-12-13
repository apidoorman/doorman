"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import logging
import time
import uuid

from fastapi import APIRouter, Request, HTTPException

from models.create_vault_entry_model import CreateVaultEntryModel
from models.response_model import ResponseModel
from models.update_vault_entry_model import UpdateVaultEntryModel
from services.vault_service import VaultService
from utils.auth_util import auth_required
from utils.constants import ErrorCodes, Headers, Messages
from utils.response_util import process_response, respond_rest

vault_router = APIRouter()

logger = logging.getLogger('doorman.gateway')


@vault_router.post(
    '',
    description='Create a new vault entry',
    response_model=ResponseModel,
    responses={
        201: {
            'description': 'Vault entry created successfully',
            'content': {
                'application/json': {
                    'example': {
                        'message': 'Vault entry created successfully',
                        'data': {'key_name': 'api_key_production'},
                    }
                }
            },
        }
    },
)
async def create_vault_entry(entry_data: CreateVaultEntryModel, request: Request):
    """
    Create a new encrypted vault entry for the authenticated user.
    The value will be encrypted using the user's email, username, and VAULT_KEY.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')

        return respond_rest(await VaultService.create_vault_entry(username, entry_data, request_id))
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
            )
        )
    finally:
        elapsed = time.time() * 1000 - start_time
        logger.info(f'{request_id} | Total time: {elapsed:.2f}ms')


@vault_router.get(
    '',
    description='List all vault entries for the authenticated user',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'data': {
                            'entries': [
                                {
                                    'key_name': 'api_key_production',
                                    'username': 'john_doe',
                                    'description': 'Production API key',
                                    'created_at': '2024-11-22T10:15:30Z',
                                    'updated_at': '2024-11-22T10:15:30Z',
                                }
                            ],
                            'count': 1,
                        }
                    }
                }
            },
        }
    },
)
async def list_vault_entries(request: Request):
    """
    List all vault entries for the authenticated user.
    Values are never returned for security reasons.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')

        return respond_rest(await VaultService.list_vault_entries(username, request_id))
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
            )
        )
    finally:
        elapsed = time.time() * 1000 - start_time
        logger.info(f'{request_id} | Total time: {elapsed:.2f}ms')


@vault_router.get(
    '/{key_name}',
    description='Get a specific vault entry by key name',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'data': {
                            'key_name': 'api_key_production',
                            'username': 'john_doe',
                            'description': 'Production API key',
                            'created_at': '2024-11-22T10:15:30Z',
                            'updated_at': '2024-11-22T10:15:30Z',
                        }
                    }
                }
            },
        }
    },
)
async def get_vault_entry(key_name: str, request: Request):
    """
    Get a specific vault entry by key name.
    The value is never returned for security reasons.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')

        return respond_rest(await VaultService.get_vault_entry(username, key_name, request_id))
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
            )
        )
    finally:
        elapsed = time.time() * 1000 - start_time
        logger.info(f'{request_id} | Total time: {elapsed:.2f}ms')


@vault_router.put(
    '/{key_name}',
    description='Update a vault entry (description only)',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Vault entry updated successfully',
            'content': {
                'application/json': {'example': {'message': 'Vault entry updated successfully'}}
            },
        }
    },
)
async def update_vault_entry(key_name: str, update_data: UpdateVaultEntryModel, request: Request):
    """
    Update a vault entry. Only the description can be updated.
    The encrypted value cannot be modified - delete and recreate if needed.
    """
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
            await VaultService.update_vault_entry(username, key_name, update_data, request_id)
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
            )
        )
    finally:
        elapsed = time.time() * 1000 - start_time
        logger.info(f'{request_id} | Total time: {elapsed:.2f}ms')


@vault_router.delete(
    '/{key_name}',
    description='Delete a vault entry',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Vault entry deleted successfully',
            'content': {
                'application/json': {'example': {'message': 'Vault entry deleted successfully'}}
            },
        }
    },
)
async def delete_vault_entry(key_name: str, request: Request):
    """
    Delete a vault entry permanently.
    This action cannot be undone.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')

        return respond_rest(await VaultService.delete_vault_entry(username, key_name, request_id))
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
            )
        )
    finally:
        elapsed = time.time() * 1000 - start_time
        logger.info(f'{request_id} | Total time: {elapsed:.2f}ms')
