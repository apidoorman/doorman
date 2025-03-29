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
from services.api_service import ApiService

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

async def group_required(request: Request, Authorize: AuthJWT = Depends(), full_path: str = None):
    try:
        Authorize.jwt_required()
        username = Authorize.get_jwt_subject()
        if not full_path: full_path = request.url.path
        prefix = "/api/rest/"
        if full_path.startswith(prefix):
            path = full_path[len(prefix):]
        else:
            path = full_path
        api_and_version = '/'.join(path.split('/')[:2])
        logger.info(f"API and version: {api_and_version}")
        user = await UserService.get_user_by_username(username)
        api = pygate_cache.get_cache('api_cache', api_and_version) or ApiService.api_collection.find_one({'api_name': api_and_version.split('/')[0], 'api_version': api_and_version.split('/')[1]})
        if not set(user.get('groups', [])).intersection(api.get('api_allowed_groups', [])):
            raise HTTPException(status_code=403, detail="You do not have the correct group for this")
    except MissingTokenError:
        raise HTTPException(status_code=401, detail="Missing token")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    return Authorize