"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from services.group_service import GroupService
from utils.whitelist_util import whitelist_check
from utils.role_util import role_required

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
@group_router.post("")
@whitelist_check()
@role_required(("admin", "dev", "platform"))
async def create_group(request: Request, Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()
    try:
        api_data = await request.json()
        GroupService.create_group(api_data)
        return JSONResponse(content={'message': 'Group created successfully'}, status_code=201)
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
@group_router.get("")
@whitelist_check()
@role_required(("admin", "dev", "platform"))
async def get_groups(request: Request, Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()
    try:
        groups = GroupService.get_groups()
        for group in groups:
            group.pop('_id', None)
        return JSONResponse(content=groups, status_code=200)
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
@group_router.get("/{group_name}")
@whitelist_check()
@role_required(("admin", "dev", "platform"))
async def get_group(request: Request, group_name: str, Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()
    try:
        group = GroupService.get_group(group_name)
        group.pop('_id', None)
        return JSONResponse(content=group, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))