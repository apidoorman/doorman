"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from services.group_service import GroupService
from utils.auth_util import auth_required
from utils.whitelist_util import whitelist_check
from utils.role_util import role_required
from models.group_model import GroupModel

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
async def create_group(api_data: GroupModel):
    try:
        auth_required()
        whitelist_check()
        role_required(("admin", "dev", "platform"))
        await GroupService.create_group(api_data)
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
@group_router.get("/all")
async def get_groups(page: int = 1, page_size: int = 10):
    try:
        auth_required()
        whitelist_check()
        role_required(("admin", "dev", "platform"))
        groups = await GroupService.get_groups(page, page_size)
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
async def get_group(group_name: str):
    try:
        auth_required()
        whitelist_check()
        role_required(("admin", "dev", "platform"))
        group = await GroupService.get_group(group_name)
        return JSONResponse(content=group, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))