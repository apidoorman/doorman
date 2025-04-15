"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT
from slowapi.errors import RateLimitExceeded

from utils.pygate_cache_util import pygate_cache
from utils.limit_throttle_util import limit_and_throttle
from utils.auth_util import auth_required
from utils.group_util import group_required
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool
from utils.subscription_util import subscription_required
from services.gateway_service import GatewayService
from models.request_model import RequestModel

import uuid
import time
import logging

gateway_router = APIRouter()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

@gateway_router.api_route("/status/rest", methods=["GET"],
    description="Check if the REST gateway is online",
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Gateway is online"
                    }
                }
            }
        }
    }
)
async def rest_gateway_status():
    return JSONResponse(content={"message": "Gateway is online"}, status_code=200)

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
            return JSONResponse(content={"error": "You do not have permission to create roles"}, status_code=403)
        pygate_cache.clear_all_caches()
        return JSONResponse(content={"message": "All caches cleared"}, status_code=200)
    except Exception as e:
        logger.error(f"Error clearing caches: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)

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
        request_model = RequestModel(
            method=request.method,
            path=path,
            headers=dict(request.headers),
            body=await request.json() if request.method in ["POST", "PUT", "PATCH"] else None,
            query_params=dict(request.query_params),
            identity=Authorize.get_jwt_subject()
        )
        return process_response(await GatewayService.rest_gateway(request_model, request_id, start_time))
    except RateLimitExceeded as e:
        return JSONResponse(content={"error": "Rate limit exceeded"}, status_code=429)
    except ValueError:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")
