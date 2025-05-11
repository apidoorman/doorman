"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from fastapi import APIRouter, Request, Depends
from fastapi_jwt_auth import AuthJWT
from slowapi.errors import RateLimitExceeded

from models.response_model import ResponseModel
from utils.doorman_cache_util import doorman_cache
from utils.limit_throttle_util import limit_and_throttle
from utils.auth_util import auth_required
from utils.group_util import group_required
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool
from utils.subscription_util import subscription_required
from utils.health_check_util import check_mongodb, check_redis, get_memory_usage, get_active_connections, get_uptime
from services.gateway_service import GatewayService
from models.request_model import RequestModel

import uuid
import time
import logging
import json

gateway_router = APIRouter()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("doorman.gateway")

@gateway_router.api_route("/status", methods=["GET"],
    description="Check if the gateway is online and all dependencies are healthy",
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "version": "0.0.1",
                        "dependencies": {
                            "mongodb": "connected",
                            "redis": "connected",
                            "cache": "operational"
                        },
                        "metrics": {
                            "memory_usage": "45%",
                            "active_connections": 10,
                            "uptime": "2h 15m"
                        }
                    }
                }
            }
        },
        503: {
            "description": "Service Unavailable",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "version": "0.0.1",
                        "dependencies": {
                            "mongodb": "disconnected",
                            "redis": "connected",
                            "cache": "operational"
                        },
                        "metrics": {
                            "memory_usage": "45%",
                            "active_connections": 10,
                            "uptime": "2h 15m"
                        }
                    }
                }
            }
        }
    }
)
async def rest_gateway_status():
    try:
        mongodb_status = "connected" if await check_mongodb() else "disconnected"
        redis_status = "connected" if await check_redis() else "disconnected"
        metrics = {
            "memory_usage": get_memory_usage(),
            "active_connections": get_active_connections(),
            "uptime": get_uptime()
        }
        status = "healthy" if mongodb_status == "connected" and redis_status == "connected" else "unhealthy"
        response = {
            "status": status,
            "version": "0.0.1",
            "dependencies": {
                "mongodb": mongodb_status,
                "redis": redis_status,
                "cache": "operational" if doorman_cache.is_operational() else "degraded"
            },
            "metrics": metrics
        }
        return process_response(ResponseModel(
            status_code=200 if status == "healthy" else 503,
            response=response
        ).dict(), "rest")
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return process_response(ResponseModel(
            status_code=503,
            error_code="HLT001",
            error_message="Health check failed"
        ).dict(), "rest")
    
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
async def clear_all_caches(Authorize: AuthJWT = Depends()):
    try:
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_gateway'):
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

@gateway_router.api_route(
    "/rest/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    description="REST API gateway",
    dependencies=[
        Depends(auth_required),
        Depends(subscription_required)
    ],
    include_in_schema=False
)
async def rest_gateway(path: str, request: Request, Authorize: AuthJWT = Depends()):
    await group_required(request, Authorize, path)
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    logger.info(f"{request_id} | Time: {time.strftime('%Y-%m-%d %H:%M:%S')}:{int(time.time() * 1000) % 1000}ms")
    logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
    logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
    try:
        await limit_and_throttle(Authorize, request)
        content_type = request.headers.get("Content-Type", "")
        if "application/json" in content_type:
            body = await request.json()
        elif "application/xml" in content_type or "text/xml" in content_type:
            body = (await request.body()).decode("utf-8")
        else:
            try:
                body = await request.json()
            except Exception:
                body = None
        request_model = RequestModel(
            method=request.method,
            path=path,
            headers=dict(request.headers),
            body=body,
            query_params=dict(request.query_params),
            identity=Authorize.get_jwt_subject()
        )
        return process_response(await GatewayService.rest_gateway(Authorize, request_model, request_id, start_time), "rest")
    except RateLimitExceeded as e:
        return process_response(ResponseModel(
            status_code=429,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW009",
            error_message="Rate limit exceeded"
            ).dict(), "rest")
    except ValueError:
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

@gateway_router.api_route(
    "/soap/{path:path}",
    methods=["POST"],
    description="SOAP API gateway",
    dependencies=[
        Depends(auth_required),
        Depends(subscription_required)
    ],
    include_in_schema=False
)
async def soap_gateway(path: str, request: Request, Authorize: AuthJWT = Depends()):
    await group_required(request, Authorize, path)
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    logger.info(f"{request_id} | Time: {time.strftime('%Y-%m-%d %H:%M:%S')}:{int(time.time() * 1000) % 1000}ms")
    logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
    logger.info(f"{request_id} | Endpoint: POST {path}")
    try:
        await limit_and_throttle(Authorize, request)
        response_payload = await GatewayService.soap_gateway(path, Authorize, request, request_id, start_time)
        return process_response(response_payload, "soap")
    except RateLimitExceeded:
        return process_response(ResponseModel(
            status_code=429,
            response_headers={"request_id": request_id},
            error_code="GTW009",
            error_message="Rate limit exceeded"
        ).dict(), "soap")
    except ValueError:
        return process_response(ResponseModel(
            status_code=500,
            response_headers={"request_id": request_id},
            error_code="GTW999",
            error_message="An unexpected error occurred"
        ).dict(), "soap")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@gateway_router.api_route(
    "/graphql/{api_name}",
    methods=["POST"],
    description="GraphQL API gateway",
    dependencies=[
        Depends(auth_required),
        Depends(subscription_required)
    ],
    include_in_schema=False
)
async def graphql_gateway(api_name: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    logger.info(f"{request_id} | Time: {time.strftime('%Y-%m-%d %H:%M:%S')}:{int(time.time() * 1000) % 1000}ms")
    logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
    logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
    try:
        await limit_and_throttle(Authorize, request)
        body = await request.json()
        if not isinstance(body, dict) or 'query' not in body:
            return process_response(ResponseModel(
                status_code=400,
                response_headers={"request_id": request_id},
                error_code="GTW011",
                error_message="Invalid GraphQL request: missing query"
            ).dict(), "graphql")
        api_version = request.headers.get('X-API-Version', 'v1')
        api_name_version = f'{api_name}/{api_version}'
        await group_required(request, Authorize, api_name_version)
        try:
            request_model = RequestModel(
                method=request.method,
                path=f"{api_name}",
                headers=dict(request.headers),
                body=json.dumps(body),
                query_params=dict(request.query_params),
                identity=Authorize.get_jwt_subject()
            )
        except Exception as e:
            logger.error(f"{request_id} | Failed to create request model: {str(e)}")
            return process_response(ResponseModel(
                status_code=500,
                response_headers={"request_id": request_id},
                error_code="GTW014",
                error_message="Failed to process request"
            ).dict(), "graphql")
        return process_response(await GatewayService.graphql_gateway(Authorize, request_model, request_id, start_time), "graphql")
    except RateLimitExceeded as e:
        return process_response(ResponseModel(
            status_code=429,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW009",
            error_message="Rate limit exceeded"
            ).dict(), "graphql")
    except ValueError:
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