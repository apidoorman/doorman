"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from services.group_service import GroupService
from utils.auth_util import auth_required
from models.group_model import GroupModel
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool

group_router = APIRouter()

"""
Create group *platform endpoint.
Request:
{
    "group_name": "<string>",
    "group_description": "<string>",
    "api_access": ["<string>"]
}
Response:
{
    "message": "Group created successfully"
}
"""
@group_router.post("",
    dependencies=[
        Depends(auth_required)
    ])
async def create_group(api_data: GroupModel, Authorize: AuthJWT = Depends()):
    try:
        if not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_groups'):
            return JSONResponse(content={"error": "You do not have permission to create groups"}, status_code=403)
        return process_response(await GroupService.create_group(api_data))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


"""
Get groups *platform endpoint.
Request:
{
}
Response:
{
    "groups": [
        {
            "group_name": "<string>",
            "group_description": "<string>",
            "api_access": ["<string>"]
        }
    ]
}
"""
@group_router.get("/all",
    dependencies=[
        Depends(auth_required)
    ])
async def get_groups(page: int = 1, page_size: int = 10):
    try:
        return process_response(await GroupService.get_groups(page, page_size))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


"""
Get group *platform endpoint.
Request:
{
}
Response:
{
    {
        "group_name": "<string>",
        "group_description": "<string>",
        "api_access": ["<string>"]
    }
    ]
}
"""
@group_router.get("/{group_name}",
    dependencies=[
        Depends(auth_required)
    ])
async def get_group(group_name: str):
    try:
        return process_response(await GroupService.get_group(group_name))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))