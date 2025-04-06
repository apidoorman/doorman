"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT
from slowapi.errors import RateLimitExceeded

from services.rate_limit_service import rate_limit
from utils.auth_util import auth_required
from utils.group_util import group_required
from utils.response_util import process_response
from utils.subscription_util import subscription_required
from services.gateway_service import GatewayService
from models.request_model import RequestModel

import uuid
import time
import logging

gateway_router = APIRouter()

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

@gateway_router.api_route(
    "/rest/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    dependencies=[
        Depends(auth_required),
        Depends(subscription_required),
        Depends(group_required)
    ]
)
async def rest_gateway(path: str, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
    logger.info(f"{request_id} | Endpoint: {str(request.url.path)}")
    try:
        await rate_limit(Authorize, request)
        request_model = RequestModel(
            method=request.method,
            path=path,
            headers=dict(request.headers),
            body=await request.json() if request.method in ["POST", "PUT", "PATCH"] else None,
            query_params=dict(request.query_params),
            identity=Authorize.get_jwt_subject()
        )
        return process_response(await GatewayService.rest_gateway(request_model, request_id))
    except RateLimitExceeded as e:
        return JSONResponse(content={"error": "Rate limit exceeded"}, status_code=429)
    except ValueError:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")
