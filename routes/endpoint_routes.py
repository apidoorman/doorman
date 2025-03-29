"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from services.endpoint_service import EndpointService
from utils.auth_util import auth_required
from models.endpoint_model import EndpointModel
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool

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
@endpoint_router.post("",
    dependencies=[
        Depends(auth_required)
    ])
async def create_endpoint(endpoint_data: EndpointModel, Authorize: AuthJWT = Depends()):
    try:
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_endpoints'):
            return JSONResponse(content={"error": "You do not have permission to create endpoints"}, status_code=403)
        return process_response(await EndpointService.create_endpoint(endpoint_data))
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
@endpoint_router.get("/api/{api_name}/{api_version}",
    dependencies=[
        Depends(auth_required)
    ])
async def get_endpoints_by_name_version(api_name: str, api_version: str, Authorize: AuthJWT = Depends()):
    try:
        return process_response(await EndpointService.get_endpoints_by_name_version(api_name, api_version))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))