"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

import logging
from fastapi import HTTPException, Request
from utils.doorman_cache_util import doorman_cache
from services.user_service import UserService
from utils.database import api_collection
from utils.auth_util import auth_required

logger = logging.getLogger("doorman.gateway")

async def group_required(request: Request = None, full_path: str = None, user_to_subscribe = None):
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        if not full_path and request:
            full_path = request.url.path
        elif not full_path:
            raise HTTPException(status_code=400, detail="No path provided")
        prefix = ""
        postfix = ""
        if full_path.startswith("/api/rest/"):
            prefix = "/api/rest/"
        elif full_path.startswith("/api/soap/"):
            prefix = "/api/soap/"
        elif full_path.startswith("/api/graphql/"):
            prefix = "/api/graphql/"
            if request:
                postfix = '/' + request.headers.get('X-API-Version', 'v0')
        elif full_path.startswith("/api/grpc/"):
            prefix = "/api/grpc/"
            if request:
                postfix = '/' + request.headers.get('X-API-Version', 'v0')
        path = full_path[len(prefix):] if full_path.startswith(prefix) else full_path
        api_and_version = '/'.join(path.split('/')[:2]) + postfix
        if not api_and_version or '/' not in api_and_version:
            raise HTTPException(status_code=404, detail="Invalid API path format")
        api_name, api_version = api_and_version.split('/')
        if user_to_subscribe:
            user = await UserService.get_user_by_username_helper(user_to_subscribe)
        else:
            user = await UserService.get_user_by_username_helper(username)
        api = doorman_cache.get_cache('api_cache', api_and_version) or api_collection.find_one({'api_name': api_name, 'api_version': api_version})
        if not api:
            raise HTTPException(status_code=404, detail="API not found")
        if not set(user.get('groups') or []).intersection(api.get('api_allowed_groups') or []):
            raise HTTPException(status_code=401, detail="You do not have the correct group for this")
    except HTTPException as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return payload