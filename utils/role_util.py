"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

import logging
from fastapi import HTTPException, Depends, Request
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import MissingTokenError
from services.cache import pygate_cache
from services.user_service import UserService

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

async def platform_role_required_bool(roles, username):
    try:
        user = await UserService.get_user_by_username(username)
        if user.get('role') not in roles:
            raise HTTPException(status_code=403, detail="You do not have the correct role for this")
        return True
    except MissingTokenError:
        raise HTTPException(status_code=401, detail="Missing token")
    except HTTPException as e:
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False