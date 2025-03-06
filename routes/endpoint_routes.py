"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from services.endpoint_service import EndpointService
from utils.whitelist_util import whitelist_check
from utils.role_util import role_required

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
@whitelist_check()
@role_required(("admin", "dev", "platform"))
async def create_endpoint(request: Request, Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()
    try:
        endpoint_data = await request.json()
        EndpointService.create_endpoint(endpoint_data)
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
@whitelist_check()
@role_required(("admin", "dev", "platform"))
async def get_endpoints_by_name_version(request: Request, api_name: str, api_version: str, Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()
    try:
        endpoints = EndpointService.get_endpoints_by_name_version(api_name, api_version)
        for endpoint in endpoints:
            endpoint.pop('_id', None)
        return JSONResponse(content={"endpoints": endpoints}, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))