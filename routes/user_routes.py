"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from services.user_service import UserService
from utils.auth_util import auth_required
from utils.role_util import platform_role_required_bool
from models.create_user_model import CreateUserModel
from models.update_user_model import UpdateUserModel
from models.update_password_model import UpdatePasswordModel

user_router = APIRouter()

"""
Create user *platform endpoint.
Request:
{
    "username": "<string>",
    "email": "<string>",
    "password": "<string>"
    "role": "<string>"
    "groups": ["<string>"],
    "rate_limit": "<int>",
    "rate_limit_duration": "<int>",
    "throttle": "<int>",
    "throttle_duration": "<int>"
}
Response:
{
    "message": "User created successfully",
    "user_details" {
        "user_id": "<string>",
        "email": "<string>"
    }
}
"""
@user_router.post("",
    dependencies=[
        Depends(auth_required)
    ])
async def create_user(user_data: CreateUserModel, Authorize: AuthJWT = Depends()):
    try:
        await UserService.create_user(user_data)
        return JSONResponse(content={"message": "User created successfully"}, status_code=201)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

"""
Update user *platform endpoint.
Request:
{
    "email": "<string>",
    "role": "<string>",
    "groups": ["<string>"]
}
Response:
{
    "message": "User updated successfully"
}
"""
@user_router.put("/{username}",
    dependencies=[
        Depends(auth_required)
    ])
async def update_user(username: str, api_data: UpdateUserModel, Authorize: AuthJWT = Depends()):
    try:
        if not Authorize.get_jwt_subject() == username or not await platform_role_required_bool(('admin', 'dev'), Authorize.get_jwt_subject()):
            raise HTTPException(status_code=403, detail="Can only update your own information")
        await UserService.update_user(username, api_data)
        return JSONResponse(content={"message": "User updated successfully"}, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

"""
Update user *platform endpoint.
Request:
{
    "current_password": "<string>",
    "new_password": "<string>"
}
Response:
{
    "message": "Password updated successfully"
}
"""
@user_router.put("/{username}/update-password",
    dependencies=[
        Depends(auth_required)
    ])
async def update_user_password(username: str, api_data: UpdatePasswordModel, Authorize: AuthJWT = Depends()):
    try:
        if not Authorize.get_jwt_subject() == username or not await platform_role_required_bool(('admin', 'dev'), Authorize.get_jwt_subject()):
            raise HTTPException(status_code=403, detail="Can only update your own password")
        await UserService.update_password(username, api_data)
        return JSONResponse(content={"message": "Password updated successfully"}, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

"""
Get user by username *platform endpoint.
Request:
{
}
Response:
{
    "username": "<string>",
    "email": "<string>",
    "password": "<string>"
    "role": "<string>"
    "groups": ["<string>"]
}
"""
@user_router.get("/{username}",
    dependencies=[
        Depends(auth_required)
    ])
async def get_user_by_username(username: str):
    try:
        user = await UserService.get_user_by_username(username)
        return JSONResponse(content=user, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

"""
Get user by email *platform endpoint.
Request:
{
}
Response:
{
    "username": "<string>",
    "email": "<string>",
    "password": "<string>"
    "role": "<string>"
    "groups": ["<string>"]
}
"""
@user_router.get("/email/{email}",
    dependencies=[
        Depends(auth_required)
    ])
async def get_user_by_email(email: str):
    try:
        user = await UserService.get_user_by_email(email)
        return JSONResponse(content=user, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))