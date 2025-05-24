"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from fastapi import APIRouter, HTTPException, Request, Depends

from models.response_model import ResponseModel
from utils import api_util
from utils.doorman_cache_util import doorman_cache
from utils.limit_throttle_util import limit_and_throttle
from utils.auth_util import auth_required
from utils.group_util import group_required
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool
from utils.subscription_util import subscription_required
from utils.health_check_util import check_mongodb, check_redis, get_memory_usage, get_active_connections, get_uptime
from services.gateway_service import GatewayService
from utils.validation_util import validation_util

import uuid
import time
import logging
import json
import re
from datetime import datetime

gateway_router = APIRouter()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("doorman.gateway")

@gateway_router.api_route("/status", methods=["GET"],
    description="Check if the gateway is online and healthy",
    response_model=ResponseModel)
async def status():
    """Check if the gateway is online and healthy"""
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        mongodb_status = await check_mongodb()
        redis_status = await check_redis()
        memory_usage = await get_memory_usage()
        active_connections = await get_active_connections()
        uptime = await get_uptime()
        return ResponseModel(
            status_code=200,
            response_headers={"request_id": request_id},
            response={
                "status": "online",
                "mongodb": mongodb_status,
                "redis": redis_status,
                "memory_usage": memory_usage,
                "active_connections": active_connections,
                "uptime": uptime
            }
        ).dict()
    except Exception as e:
        logger.error(f"{request_id} | Status check failed: {str(e)}")
        return ResponseModel(
            status_code=500,
            response_headers={"request_id": request_id},
            error_code="GTW006",
            error_message="Internal server error"
        ).dict()
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Status check time {end_time - start_time}ms")

@gateway_router.api_route("/caches", methods=["DELETE"],
    description="Clear all caches",
    dependencies=[
        Depends(auth_required)
    ],
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "All caches cleared"
                    }
                }
            }
        }
    }
)
async def clear_all_caches(request: Request):
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        if not await platform_role_required_bool(username, 'manage_gateway'):
            return process_response(ResponseModel(
                status_code=403,
                error_code="GTW008",
                error_message="You do not have permission to clear caches"
            ))
        doorman_cache.clear_all_caches()
        return process_response(ResponseModel(
            status_code=200,
            message="All caches cleared"
            ).dict(), "rest")
    except Exception as e:
        return process_response(ResponseModel(
            status_code=500,
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict(), "rest")

@gateway_router.api_route("/rest/{path:path}", methods=["GET", "POST", "PUT", "DELETE"],
    description="REST gateway endpoint",
    response_model=ResponseModel)
async def gateway(request: Request, path: str):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        await subscription_required(request)
        await group_required(request)
        await limit_and_throttle(request)
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S:%f')[:-3]}ms")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await GatewayService.rest_gateway(username, request, request_id, start_time, path), "rest")
    except HTTPException as e:
        return process_response(ResponseModel(
            status_code=e.status_code,
            response_headers={
                "request_id": request_id
            },
            error_code=e.detail,
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

@gateway_router.api_route("/soap/{path:path}", methods=["POST"],
    description="SOAP gateway endpoint",
    response_model=ResponseModel)
async def soap_gateway(request: Request, path: str):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        await subscription_required(request)
        await group_required(request)
        await limit_and_throttle(request)
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S:%f')[:-3]}ms")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(await GatewayService.soap_gateway(username, request, request_id, start_time, path), "soap")
    except HTTPException as e:
        return process_response(ResponseModel(
            status_code=e.status_code,
            response_headers={
                "request_id": request_id
            },
            error_code=e.detail,
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
            ).dict(), "soap")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@gateway_router.api_route("/graphql/{path:path}", methods=["POST"],
    description="GraphQL gateway endpoint",
    response_model=ResponseModel)
async def graphql_gateway(request: Request, path: str):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        if not request.headers.get('X-API-Version'):
            raise HTTPException(status_code=400, detail="X-API-Version header is required")
        await subscription_required(request)
        await group_required(request)
        await limit_and_throttle(request)
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S:%f')[:-3]}ms")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        api_name = re.sub(r"^.*/", "",request.url.path)
        api_key = doorman_cache.get_cache('api_id_cache', api_name + '/' + request.headers.get('X-API-Version', 'v0'))
        api = await api_util.get_api(api_key, api_name + '/' + request.headers.get('X-API-Version', 'v0'))
        if api and api.get('validation_enabled'):
            body = await request.json()
            query = body.get('query')
            variables = body.get('variables', {})
            try:
                await validation_util.validate_graphql_request(api.get('api_id'), query, variables)
            except Exception as e:
                return process_response(ResponseModel(
                    status_code=400,
                    response_headers={"request_id": request_id},
                    error_code="GTW011",
                    error_message=str(e)
                ).dict(), "graphql")
        return process_response(await GatewayService.graphql_gateway(username, request, request_id, start_time, path), "graphql")
    except HTTPException as e:
        return process_response(ResponseModel(
            status_code=e.status_code,
            response_headers={
                "request_id": request_id
            },
            error_code=e.detail,
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
            ).dict(), "graphql")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@gateway_router.api_route("/grpc/{path:path}", methods=["POST"],
    description="gRPC gateway endpoint",
    response_model=ResponseModel)
async def grpc_gateway(request: Request, path: str):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        if not request.headers.get('X-API-Version'):
            raise HTTPException(status_code=400, detail="X-API-Version header is required")
        await subscription_required(request)
        await group_required(request)
        await limit_and_throttle(request)
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S:%f')[:-3]}ms")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        api_name = re.sub(r"^.*/", "",request.url.path)
        api_key = doorman_cache.get_cache('api_id_cache', api_name + '/' + request.headers.get('X-API-Version', 'v0'))
        api = await api_util.get_api(api_key, api_name + '/' + request.headers.get('X-API-Version', 'v0'))
        if api and api.get('validation_enabled'):
            body = await request.json()
            request_data = json.loads(body.get('data', '{}'))
            try:
                await validation_util.validate_grpc_request(api.get('api_id'), request_data)
            except Exception as e:
                return process_response(ResponseModel(
                    status_code=400,
                    response_headers={"request_id": request_id},
                    error_code="GTW011",
                    error_message=str(e)
                ).dict(), "grpc")
        return process_response(await GatewayService.grpc_gateway(username, request, request_id, start_time, path), "grpc")
    except HTTPException as e:
        return process_response(ResponseModel(
            status_code=e.status_code,
            response_headers={
                "request_id": request_id
            },
            error_code=e.detail,
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
            ).dict(), "grpc")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")