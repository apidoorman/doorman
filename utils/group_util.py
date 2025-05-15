"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

import logging
from fastapi import HTTPException, Depends, Request
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import MissingTokenError
from utils.doorman_cache_util import doorman_cache
from services.user_service import UserService
from utils.database import api_collection

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("doorman.gateway")

async def group_required(request: Request = None, Authorize: AuthJWT = Depends(), full_path: str = None, user_to_subscribe = None):
    try:
        username = Authorize.get_jwt_subject()
        if not full_path: full_path = request.url.path
        if full_path.startswith("/api/rest/"):
            prefix = "/api/rest/"
        elif full_path.startswith("/api/soap/"):
            prefix = "/api/soap/"
        elif full_path.startswith("/api/grpc/"):
            prefix = "/api/grpc/"
        else:
            prefix = ""
        if full_path.startswith(prefix):
            path = full_path[len(prefix):]
        else:
            path = full_path
        api_and_version = '/'.join(path.split('/')[:2])
        if user_to_subscribe:
            user = await UserService.get_user_by_username_helper(user_to_subscribe)
        else:
            user = await UserService.get_user_by_username_helper(username)
        api = doorman_cache.get_cache('api_cache', api_and_version) or api_collection.find_one({'api_name': api_and_version.split('/')[0], 'api_version': api_and_version.split('/')[1]})
        if not api:
            raise HTTPException(status_code=404, detail="API not found")
        if not set(user.get('groups') or []).intersection(api.get('api_allowed_groups') or []):
            raise HTTPException(status_code=401, detail="You do not have the correct group for this")
    except MissingTokenError:
        raise HTTPException(status_code=401, detail="Missing token")
    except HTTPException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return Authorize