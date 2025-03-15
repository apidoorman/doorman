"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from services.endpoint_service import EndpointService
from utils.auth_util import auth_required
from utils.whitelist_util import whitelist_check
from utils.role_util import role_required
from models.endpoint_model import EndpointModel

endpoint_router = APIRouter()

"""
Create endpoint *platform endpoint.
Request:
{
    "api_name": "<string>",
    "api_version": "<string>",
    "endpoint_method": "<string>",
    "endpoint_uri": "<string>"
}
Response:
{
    "message": "Endpoint created successfully"
}
"""
@endpoint_router.post("")
async def create_endpoint(endpoint_data: EndpointModel, Authorize: AuthJWT = Depends()):
    try:
        auth_required()
        whitelist_check()
        role_required(("admin", "dev", "platform"))
        await EndpointService.create_endpoint(endpoint_data)
        return JSONResponse(content={'message': 'Endpoint created successfully'}, status_code=201)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


"""
Get endpoints *platform endpoint.
Request:
{
}
Response:
{
    "api_name": "<string>",
    "api_version": "<string>",
    "endpoints": [
        {
            "endpoint_method": "<string>",
            "endpoint_uri": "<string>"
        }
    ]
}
"""
@endpoint_router.get("/api/{api_name}/{api_version}")
async def get_endpoints_by_name_version(api_name: str, api_version: str, Authorize: AuthJWT = Depends()):
    try:
        auth_required()
        whitelist_check()
        role_required(("admin", "dev", "platform"))
        endpoints = await EndpointService.get_endpoints_by_name_version(api_name, api_version)
        return JSONResponse(content={"endpoints": endpoints}, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))