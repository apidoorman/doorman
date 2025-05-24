"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from datetime import datetime, timedelta, UTC
import os
import uuid
from fastapi import HTTPException, Request
from jose import jwt, JWTError

from utils.auth_blacklist import jwt_blacklist
from utils.database import user_collection
from utils.doorman_cache_util import doorman_cache

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("doorman.gateway")

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

async def validate_csrf_token(csrf_token: str, auth_token: str) -> bool:
    try:
        csrf_payload = jwt.decode(csrf_token, SECRET_KEY, algorithms=[ALGORITHM])
        auth_payload = jwt.decode(auth_token, SECRET_KEY, algorithms=[ALGORITHM])
        return csrf_payload.get("sub") == auth_payload.get("sub")
    except:
        return False

async def auth_required(request: Request):
    """Validate JWT token and CSRF for HTTPS"""
    token = request.cookies.get("access_token_cookie")
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if os.getenv("HTTPS_ENABLED", "false").lower() == "true":
        csrf_token = request.headers.get("X-CSRF-Token")
        if not csrf_token:
            raise HTTPException(status_code=401, detail="Unauthorized")
        if not await validate_csrf_token(csrf_token, token):
            raise HTTPException(status_code=401, detail="Invalid CSRF token")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        jti = payload.get("jti")
        if not username or not jti:
            raise HTTPException(status_code=401, detail="Invalid token")
        if username in jwt_blacklist:
            timed_heap = jwt_blacklist[username]
            for _, token_jti in timed_heap.heap:
                if token_jti == jti:
                    raise HTTPException(status_code=401, detail="Token has been revoked")
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
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Unauthorized")
    except Exception as e:
        logger.error(f"Unexpected error in auth_required: {str(e)}")
        raise HTTPException(status_code=401, detail="Unauthorized")

def create_access_token(data: dict, refresh: bool = False):
    to_encode = data.copy()
    expire = timedelta(minutes=30) if not refresh else timedelta(days=7)
    to_encode.update({"exp": datetime.now(UTC) + expire, "jti": str(uuid.uuid4())})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt