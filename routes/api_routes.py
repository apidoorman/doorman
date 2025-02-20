"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

# External imports
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

# Internal imports
from services.api_service import ApiService
from utils.auth_util import auth_required
from utils.whitelist_util import whitelist_check
from utils.role_util import role_required

api_router = APIRouter()

# Start role based endpoints

"""
Create API *platform endpoint.
Request:
{
    "api_name": "<string>",
    "api_version": "<string>",
    "api_description": "<string>",
    "api_servers": ["<string>"]
}
Response:
{
    "message": "API created successfully"
}
"""
@api_router.post("")
@whitelist_check()
@role_required(("admin", "dev", "platform"))
async def create_api(request: Request, Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()
    try:
        api_data = await request.json()
        ApiService.create_api(api_data)
        return JSONResponse(content={'message': 'API created successfully'}, status_code=201)
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

"""
Get API *platform endpoint.
Request:
{
}
Response:
{
    "api_name": "<string>",
    "api_version": "<string>",
    "api_description": "<string>",
    "api_path": "<string>"
}
"""
@api_router.get("/{api_name}/{api_version}")
@whitelist_check()
@role_required(("admin", "dev", "platform"))
async def get_api_by_name_version(request: Request, api_name: str, api_version: str, Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()
    try:
        api = ApiService.get_api_by_name_version(api_name, api_version)
        del api['_id']
        return JSONResponse(content=api, status_code=200)
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

"""
Get All Accessable APIs *platform endpoint.
Request:
{
}
Response:
{
    "api_name": "<string>",
    "api_version": "<string>",
    "api_description": "<string>",
    "api_path": "<string>"
}
"""
@api_router.get("/all")
@auth_required()
@whitelist_check()
@role_required(("admin", "dev", "platform"))
async def get_all_apis(request: Request, Authorize: AuthJWT = Depends()):
    try:
        apis = await ApiService.get_apis()
        for api in apis:
            del api['_id']
        return JSONResponse(content=apis, status_code=200)
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)
    
# End role based endpoints