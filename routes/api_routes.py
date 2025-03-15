"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from services.api_service import ApiService
from utils.auth_util import auth_required
from utils.whitelist_util import whitelist_check
from utils.role_util import role_required
from models.api_model import ApiModel

api_router = APIRouter() 

"""
Create API *platform endpoint.
Request:
{
    "api_name": "<string>",
    "api_version": "<string>",
    "api_description": "<string>",
    "api_servers": ["<string>"],
    "api_type": "<string>"
}
Response:
{
    "message": "API created successfully"
}
"""
@api_router.post("")
async def create_api(api_data: ApiModel):
    try:
        auth_required()
        whitelist_check()
        role_required(("admin", "dev", "platform"))
        await ApiService.create_api(api_data)
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
async def get_api_by_name_version(api_name: str, api_version: str):
    try:
        auth_required()
        whitelist_check()
        role_required(("admin", "dev", "platform"))
        api = await ApiService.get_api_by_name_version(api_name, api_version)
        if api.get('_id'): del api['_id']
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
async def get_all_apis(page: int = 1, page_size: int = 10):
    try:
        auth_required()
        whitelist_check()
        role_required(("admin", "dev", "platform"))
        apis = await ApiService.get_apis(page, page_size)
        return JSONResponse(content=apis, status_code=200)
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)