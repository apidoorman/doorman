"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from functools import wraps
from fastapi import HTTPException, Depends, Request
from fastapi_jwt_auth import AuthJWT

from services.user_service import UserService

def whitelist_check():
    def decorator(f):
        @wraps(f)
        async def decorated_function(*args, request: Request, Authorize: AuthJWT = Depends(), **kwargs):
            try:
                Authorize.jwt_required()
                username = Authorize.get_jwt_subject()
                user = await UserService.get_user_by_username_helper(username)
                client_ip = request.client.host
                if user.get('whitelist') and client_ip not in user.get('whitelist'):
                    raise HTTPException(status_code=403, detail="User is not whitelisted")
                return await f(*args, request=request, Authorize=Authorize, **kwargs)
            except HTTPException as e:
                raise e
            except Exception as e:
                raise HTTPException(status_code=401, detail="Could not validate whitelist")
        return decorated_function
    return decorator