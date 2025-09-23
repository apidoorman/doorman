"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from datetime import datetime, timedelta
try:
    # Python 3.11+
    from datetime import UTC  # type: ignore
except Exception:  # Python <3.11 fallback
    from datetime import timezone as _timezone  # type: ignore
    UTC = _timezone.utc  # type: ignore
import os
import uuid
from fastapi import HTTPException, Request
from jose import jwt, JWTError

from utils.auth_blacklist import jwt_blacklist, is_user_revoked
from utils.database import user_collection, role_collection
from utils.doorman_cache_util import doorman_cache

import logging

logger = logging.getLogger("doorman.gateway")

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

def is_jwt_configured() -> bool:
    """Return True if a JWT secret key is configured."""
    return bool(os.getenv("JWT_SECRET_KEY"))

async def validate_csrf_double_submit(header_token: str, cookie_token: str) -> bool:
    try:
        if not header_token or not cookie_token:
            return False
        return header_token == cookie_token
    except Exception:
        return False

async def auth_required(request: Request):
    """Validate JWT token and CSRF for HTTPS"""
    token = request.cookies.get("access_token_cookie")
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    # Enforce CSRF on HTTPS deployments; support both env flags for consistency
    https_enabled = os.getenv("HTTPS_ENABLED", "false").lower() == "true" or os.getenv("HTTPS_ONLY", "false").lower() == "true"
    if https_enabled:
        csrf_header = request.headers.get("X-CSRF-Token")
        csrf_cookie = request.cookies.get("csrf_token")
        if not await validate_csrf_double_submit(csrf_header, csrf_cookie):
            raise HTTPException(status_code=401, detail="Invalid CSRF token")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        jti = payload.get("jti")
        if not username or not jti:
            raise HTTPException(status_code=401, detail="Invalid token")
        if is_user_revoked(username):
            raise HTTPException(status_code=401, detail="Token has been revoked")
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
    
    username = data.get("sub")
    if not username:
        logger.error("No username provided for token creation")
        raise ValueError("Username is required for token creation")
    
    user = doorman_cache.get_cache('user_cache', username)
    if not user:
        user = user_collection.find_one({'username': username})
        if user:
            if user.get('_id'): del user['_id']
            if user.get('password'): del user['password']
            doorman_cache.set_cache('user_cache', username, user)
    
    if not user:
        logger.error(f"User not found: {username}")
        raise ValueError(f"User {username} not found")
    
    role_name = user.get("role")
    role = None
    if role_name:
        role = doorman_cache.get_cache('role_cache', role_name)
        if not role:
            role = role_collection.find_one({'role_name': role_name})
            if role:
                if role.get('_id'): del role['_id']
                doorman_cache.set_cache('role_cache', role_name, role)
    
    # Create accesses object with defaults
    accesses = {
        "ui_access": True,
        'manage_users': role.get('manage_users', False) if role else False,
        'manage_apis': role.get('manage_apis', False) if role else False,
        'manage_endpoints': role.get('manage_endpoints', False) if role else False,
        'manage_groups': role.get('manage_groups', False) if role else False,
        'manage_roles': role.get('manage_roles', False) if role else False,
        'manage_routings': role.get('manage_routings', False) if role else False,
        'manage_gateway': role.get('manage_gateway', False) if role else False,
        'manage_subscriptions': role.get('manage_subscriptions', False) if role else False,
        'manage_security': role.get('manage_security', False) if role else False,
        'export_logs': role.get('export_logs', False) if role else False,
        'view_logs': role.get('view_logs', False) if role else False,
    }
    
    to_encode.update({
        "exp": datetime.now(UTC) + expire,
        "jti": str(uuid.uuid4()),
        "accesses": accesses
    })
    
    logger.info(f"Creating token for user {username} with accesses: {accesses}")
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
