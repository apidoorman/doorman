"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from services.role_service import RoleService
from utils.auth_util import auth_required
from models.role_model import RoleModel
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool

role_router = APIRouter()

"""
Create API *platform endpoint.
"""
@role_router.post("",
    dependencies=[
        Depends(auth_required)
    ])
async def create_role(api_data: RoleModel, Authorize: AuthJWT = Depends()):
    try:
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_roles'):
            return JSONResponse(content={"error": "You do not have permission to create roles"}, status_code=403)
        return process_response(await RoleService.create_role(api_data))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


"""
Create API *platform endpoint.
"""
@role_router.get("/all",
    dependencies=[
        Depends(auth_required)
    ])
async def get_roles(page: int = 1, page_size: int = 10):
    try:
        return process_response(await RoleService.get_roles(page, page_size))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


"""
Create API *platform endpoint.
"""
@role_router.get("/{role_name}",
    dependencies=[
        Depends(auth_required)
    ])
async def get_role(role_name: str):
    try:
        return process_response(await RoleService.get_role(role_name))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))