"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from functools import wraps
from fastapi import HTTPException, Depends
from fastapi_jwt_auth import AuthJWT

def role_required(allowed_roles):
    def decorator(func):
        @wraps(func)
        async def decorated_function(*args, Authorize: AuthJWT = Depends(), **kwargs):
            try:
                Authorize.jwt_required('cookies')
                claims = Authorize.get_raw_jwt()
                user_role = claims.get('role')
                if not user_role or user_role not in allowed_roles:
                    raise HTTPException(
                        status_code=403,
                        detail="You do not have permission to access this resource"
                    )
                return await func(*args, Authorize=Authorize, **kwargs)
            except HTTPException as e:
                raise e
            except Exception as e:
                raise HTTPException(
                    status_code=401,
                    detail="Could not validate role credentials"
                )
        return decorated_function
    return decorator