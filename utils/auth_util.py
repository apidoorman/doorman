"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from datetime import datetime, timedelta
import uuid
from fastapi import HTTPException, Depends
from fastapi_jwt_auth import AuthJWT

from utils.auth_blacklist import jwt_blacklist
from utils.database import user_collection
from utils.doorman_cache_util import doorman_cache

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("doorman.gateway")

async def auth_required(Authorize: AuthJWT = Depends()):
    try:
        Authorize.jwt_required()
        username = Authorize.get_jwt_subject()
        jti = Authorize.get_raw_jwt()["jti"]
        if username in jwt_blacklist:
            timed_heap = jwt_blacklist[username]
            for _, token_jti in timed_heap.heap:
                if token_jti == jti:
                    raise HTTPException(
                        status_code=401,
                        detail="Token has been revoked"
                    )
        user = doorman_cache.get_cache('user_cache', username)
        if not user:
            user = user_collection.find_one({'username': username})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            if user.get('_id'): del user['_id']
            if user.get('password'): del user['password']
            doorman_cache.set_cache('user_cache', username, user)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.get("active") is False:
            logger.error(f"Unauthorized access: User {username} is inactive")
            raise HTTPException(status_code=401, detail="User is inactive")
    except Exception as e:
        logger.error(f"Unauthorized access: {str(e)}")
        raise HTTPException(status_code=401, detail="Unauthorized")
    return Authorize

def create_access_token(data: dict, Authorize: AuthJWT, refresh: bool = False):
    to_encode = data.copy()
    expire = timedelta(minutes=30) if not refresh else timedelta(days=7)
    to_encode.update({"exp": datetime.utcnow() + expire, "jti": str(uuid.uuid4())})
    encoded_jwt = Authorize.create_access_token(subject=data["sub"], expires_time=expire, user_claims={"role": data.get("role")})
    return encoded_jwt