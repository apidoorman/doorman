"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse

from services.role_service import RoleService
from utils.auth_util import auth_required
from utils.whitelist_util import whitelist_check
from utils.role_util import role_required
from models.role_model import RoleModel

role_router = APIRouter()

"""
Create API *platform endpoint.
Request:
{
    "role_name": "<string>",
    "role_description": "<string>",
    "manage_users": "<boolean>",
    "manage_apis": "<boolean>",
    "manage_endpoints": "<boolean>",
    "manage_groups": "<boolean>",
    "manage_roles": "<boolean>"
}
Response:
{
    "message": "Role created successfully"
}
"""
@role_router.post("")
async def create_role(api_data: RoleModel):
    try:
        auth_required()
        whitelist_check()
        role_required(("admin", "dev", "platform"))
        await RoleService.create_role(api_data)
        return JSONResponse(content={'message': 'Role created successfully'}, status_code=201)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


"""
Create API *platform endpoint.
Request:
{
}
Response:
{
    "roles": [
        {
            "role_name": "<string>",
            "role_description": "<string>",
            "manage_users": "<boolean>",
            "manage_apis": "<boolean>",
            "manage_endpoints": "<boolean>",
            "manage_groups": "<boolean>",
            "manage_roles": "<boolean>"
        }
    ]
}
"""
@role_router.get("/all")
async def get_roles(page: int = 1, page_size: int = 10):
    try:
        auth_required()
        whitelist_check()
        role_required(("admin", "dev", "platform"))
        roles = await RoleService.get_roles(page, page_size)
        return JSONResponse(content=roles, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


"""
Create API *platform endpoint.
Request:
{
}
Response:
{
    {
        "role_name": "<string>",
        "role_description": "<string>",
        "manage_users": "<boolean>",
        "manage_apis": "<boolean>",
        "manage_endpoints": "<boolean>",
        "manage_groups": "<boolean>",
        "manage_roles": "<boolean>"
    }
}
"""
@role_router.get("/{role_name}")
async def get_role(role_name: str):
    try:
        auth_required()
        whitelist_check()
        role_required(("admin", "dev", "platform"))
        role = await RoleService.get_role(role_name)
        return JSONResponse(content=role, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))