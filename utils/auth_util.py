"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from functools import wraps
from fastapi import HTTPException, Depends
from fastapi_jwt_auth import AuthJWT

from utils.auth_blacklist import jwt_blacklist

def auth_required():
    def decorator(func):
        @wraps(func)
        async def decorated_function(*args, Authorize: AuthJWT = Depends(), **kwargs):
            try:
                Authorize.jwt_required()

                jwt_subject = Authorize.get_jwt_subject()
                jwt_id = Authorize.get_raw_jwt()['jti']

                if jwt_subject in jwt_blacklist and jwt_id in jwt_blacklist[jwt_subject]:
                    raise HTTPException(
                        status_code=401,
                        detail="Token has been revoked"
                    )
                return await func(*args, Authorize=Authorize, **kwargs)
            except HTTPException as e:
                raise e
            except Exception as e:
                raise HTTPException(
                    status_code=401,
                    detail="Could not validate credentials"
                )
        return decorated_function
    return decorator