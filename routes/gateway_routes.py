"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from utils.subscription_util import subscription_required
from utils.whitelist_util import whitelist_check
from services.gateway_service import GatewayService
from models.request_model import RequestModel

gateway_router = APIRouter()

@gateway_router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
@whitelist_check()
@subscription_required()
async def rest_gateway(path: str, request: Request, Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()

    request_model = RequestModel(
        method=request.method,
        path=path,
        headers=dict(request.headers),
        body=await request.json() if request.method in ["POST", "PUT", "PATCH"] else None,
        query_params=dict(request.query_params),
        identity=Authorize.get_jwt_subject()
    )
    
    response = GatewayService.rest_gateway(request_model)
    return JSONResponse(content=response)