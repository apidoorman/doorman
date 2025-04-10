"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from models.update_endpoint_model import UpdateEndpointModel
from services.endpoint_service import EndpointService
from utils.auth_util import auth_required
from models.create_endpoint_model import CreateEndpointModel
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool

import uuid
import time
import logging

endpoint_router = APIRouter()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

@endpoint_router.post("",
    description="Add endpoint",
    dependencies=[
        Depends(auth_required)
    ])
async def create_endpoint(endpoint_data: CreateEndpointModel, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_endpoints'):
            return JSONResponse(content={"error": "You do not have permission to create endpoints"}, status_code=403)
        return process_response(await EndpointService.create_endpoint(endpoint_data, request_id))
    except ValueError as e:
        logger.error(f"{request_id} | Error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@endpoint_router.put("/{endpoint_method}/{api_name}/{api_version}/{endpoint_uri}",
    description="Update endpoint",
    dependencies=[
        Depends(auth_required)
    ])
async def update_endpoint(endpoint_method: str, api_name: str, api_version: str, endpoint_uri: str, endpoint_data: UpdateEndpointModel, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_endpoints'):
            return JSONResponse(content={"error": "You do not have permission to update endpoints"}, status_code=403)
        return process_response(await EndpointService.update_endpoint(endpoint_method, api_name, api_version, '/' + endpoint_uri, endpoint_data, request_id))
    except ValueError as e:
        logger.error(f"{request_id} | Error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@endpoint_router.delete("/{endpoint_method}/{api_name}/{api_version}/{endpoint_uri}",
    description="Delete endpoint",
    dependencies=[
        Depends(auth_required)
    ])
async def delete_endpoint(endpoint_method: str, api_name: str, api_version: str, endpoint_uri: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_endpoints'):
            return JSONResponse(content={"error": "You do not have permission to delete endpoints"}, status_code=403)
        return process_response(await EndpointService.delete_endpoint(endpoint_method, api_name, api_version, '/' + endpoint_uri, request_id))
    except ValueError as e:
        logger.error(f"{request_id} | Error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")
    
@endpoint_router.get("/{api_name}/{api_version}/{endpoint_uri}",
    dependencies=[
        Depends(auth_required)
    ])
async def get_endpoint(api_name: str, api_version: str, endpoint_uri: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await EndpointService.get_endpoint(request.method, api_name, api_version, '/' + endpoint_uri, request_id))
    except ValueError as e:
        logger.error(f"{request_id} | Error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@endpoint_router.get("/{api_name}/{api_version}",
    description="Get all endpoints for an API",
    dependencies=[
        Depends(auth_required)
    ])
async def get_endpoints_by_name_version(api_name: str, api_version: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await EndpointService.get_endpoints_by_name_version(api_name, api_version, request_id))
    except ValueError as e:
        logger.error(f"{request_id} | Error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")