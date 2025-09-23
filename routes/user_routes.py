"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from services.user_service import UserService
from utils.auth_util import auth_required
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool
from models.create_user_model import CreateUserModel
from models.update_user_model import UpdateUserModel
from models.update_password_model import UpdatePasswordModel

user_router = APIRouter()

"""
Create user *platform endpoint.
"""
@user_router.post("",
    dependencies=[
        Depends(auth_required)
    ])
async def create_user(user_data: CreateUserModel, Authorize: AuthJWT = Depends()):
    try:
        return process_response(await UserService.create_user(user_data))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

"""
Update user *platform endpoint.
"""
@user_router.put("/{username}",
    dependencies=[
        Depends(auth_required)
    ])
async def update_user(username: str, api_data: UpdateUserModel, Authorize: AuthJWT = Depends()):
    try:
        if not Authorize.get_jwt_subject() == username or not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_users'):
            raise HTTPException(status_code=403, detail="Can only update your own information")
        return process_response(await UserService.update_user(username, api_data))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
"""
Delete user *platform endpoint.
"""
@user_router.delete("/{username}",
    dependencies=[
        Depends(auth_required)
    ])
async def delete_user(username: str, Authorize: AuthJWT = Depends()):
    try:
        if not Authorize.get_jwt_subject() == username or not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_users'):
            raise HTTPException(status_code=403, detail="Can only delete your own account")
        return process_response(await UserService.delete_user(username))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

"""
Update user *platform endpoint.
"""
@user_router.put("/{username}/update-password",
    dependencies=[
        Depends(auth_required)
    ])
async def update_user_password(username: str, api_data: UpdatePasswordModel, Authorize: AuthJWT = Depends()):
    try:
        if not Authorize.get_jwt_subject() == username or not await platform_role_required_bool(Authorize.get_jwt_subject(), 'manage_users'):
            raise HTTPException(status_code=403, detail="Can only update your own password")
        return process_response(await UserService.update_password(username, api_data))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

"""
Get user by username *platform endpoint.
"""
@user_router.get("/{username}",
    dependencies=[
        Depends(auth_required)
    ])
async def get_user_by_username(username: str):
    try:
        return process_response(await UserService.get_user_by_username(username))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

"""
Get user by email *platform endpoint.
"""
@user_router.get("/email/{email}",
    dependencies=[
        Depends(auth_required)
    ])
async def get_user_by_email(email: str):
    try:
        return process_response(await UserService.get_user_by_email(email))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))