"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from utils.auth_util import auth_required
from utils.subscription_util import subscription_required
from utils.whitelist_util import whitelist_check
from services.gateway_service import GatewayService
from models.request_model import RequestModel

gateway_router = APIRouter()

@gateway_router.api_route("/rest/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def rest_gateway(path: str, request: Request, Authorize: AuthJWT = Depends()):
    try:
        auth_required()
        whitelist_check()
        subscription_required()

        request_model = RequestModel(
            method=request.method,
            path=path,
            headers=dict(request.headers),
            body=await request.json() if request.method in ["POST", "PUT", "PATCH"] else None,
            query_params=dict(request.query_params),
            identity=Authorize.get_jwt_subject()
        )

        return await GatewayService.rest_gateway(request_model)
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)