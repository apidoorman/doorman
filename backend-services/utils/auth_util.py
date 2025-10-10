"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

# External imports
from datetime import datetime, timedelta

try:

    from datetime import UTC
except Exception:
    from datetime import timezone as _timezone
    UTC = _timezone.utc
import os
import uuid
from fastapi import HTTPException, Request
from jose import jwt, JWTError

from utils.auth_blacklist import is_user_revoked, is_jti_revoked
from utils.database import user_collection, role_collection
from utils.doorman_cache_util import doorman_cache

import logging

logger = logging.getLogger('doorman.gateway')

SECRET_KEY = os.getenv('JWT_SECRET_KEY')
ALGORITHM = 'HS256'

def is_jwt_configured() -> bool:
    """Return True if a JWT secret key is configured."""
    return bool(os.getenv('JWT_SECRET_KEY'))

def _read_int_env(name: str, default: int) -> int:
    try:
        raw = os.getenv(name)
        if raw is None:
            return default
        val = int(str(raw).strip())
        if val <= 0:
            logger.warning(f'{name} must be > 0; using default {default}')
            return default
        return val
    except Exception:
        logger.warning(f'Invalid value for {name}; using default {default}')
        return default

def _normalize_unit(unit: str) -> str:
    u = (unit or '').strip().lower()
    mapping = {
        's': 'seconds', 'sec': 'seconds', 'second': 'seconds', 'seconds': 'seconds',
        'm': 'minutes', 'min': 'minutes', 'minute': 'minutes', 'minutes': 'minutes',
        'h': 'hours', 'hr': 'hours', 'hour': 'hours', 'hours': 'hours',
        'd': 'days', 'day': 'days', 'days': 'days',
        'w': 'weeks', 'wk': 'weeks', 'week': 'weeks', 'weeks': 'weeks',
    }
    return mapping.get(u, 'minutes')

def _expiry_from_env(value_key: str, unit_key: str, default_value: int, default_unit: str) -> timedelta:
    value = _read_int_env(value_key, default_value)
    unit = _normalize_unit(os.getenv(unit_key, default_unit))
    try:

        return timedelta(**{unit: value})
    except Exception:
        logger.warning(
            f"Unsupported time unit '{unit}' for {unit_key}; using default {default_value} {default_unit}"
        )
        return timedelta(**{_normalize_unit(default_unit): default_value})

async def validate_csrf_double_submit(header_token: str, cookie_token: str) -> bool:
    try:
        if not header_token or not cookie_token:
            return False
        return header_token == cookie_token
    except Exception:
        return False

async def auth_required(request: Request) -> dict:
    """Validate JWT token and CSRF for HTTPS

    Returns:
        dict: JWT payload containing 'sub' (username), 'jti', and 'accesses'
    """
    token = request.cookies.get('access_token_cookie')
    if not token:
        raise HTTPException(status_code=401, detail='Unauthorized')

    https_enabled = os.getenv('HTTPS_ENABLED', 'false').lower() == 'true' or os.getenv('HTTPS_ONLY', 'false').lower() == 'true'
    if https_enabled:
        csrf_header = request.headers.get('X-CSRF-Token')
        csrf_cookie = request.cookies.get('csrf_token')
        if not await validate_csrf_double_submit(csrf_header, csrf_cookie):
            raise HTTPException(status_code=401, detail='Invalid CSRF token')
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            options={'verify_signature': True}
        )
        username = payload.get('sub')
        jti = payload.get('jti')
        if not username or not jti:
            raise HTTPException(status_code=401, detail='Invalid token')
        if is_user_revoked(username) or is_jti_revoked(username, jti):
            raise HTTPException(status_code=401, detail='Token has been revoked')
        user = doorman_cache.get_cache('user_cache', username)
        if not user:
            user = user_collection.find_one({'username': username})
            if not user:
                raise HTTPException(status_code=404, detail='User not found')
            if user.get('_id'): del user['_id']
            if user.get('password'): del user['password']
            doorman_cache.set_cache('user_cache', username, user)
        if not user:
            raise HTTPException(status_code=404, detail='User not found')
        if user.get('active') is False:
            logger.error(f'Unauthorized access: User {username} is inactive')
            raise HTTPException(status_code=401, detail='User is inactive')
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail='Unauthorized')
    except Exception as e:
        logger.error(f'Unexpected error in auth_required: {str(e)}')
        raise HTTPException(status_code=401, detail='Unauthorized')

def create_access_token(data: dict, refresh: bool = False) -> str:
    """Create a JWT access token with user permissions.

    Args:
        data: Dictionary containing at least 'sub' (username)
        refresh: If True, create refresh token with longer expiry

    Returns:
        str: Encoded JWT token
    """
    to_encode = data.copy()

    if refresh:
        expire = _expiry_from_env('AUTH_REFRESH_EXPIRE_TIME', 'AUTH_REFRESH_EXPIRE_FREQ', 7, 'days')
    else:
        expire = _expiry_from_env('AUTH_EXPIRE_TIME', 'AUTH_EXPIRE_TIME_FREQ', 30, 'minutes')

    username = data.get('sub')
    if not username:
        logger.error('No username provided for token creation')
        raise ValueError('Username is required for token creation')

    user = doorman_cache.get_cache('user_cache', username)
    if not user:
        user = user_collection.find_one({'username': username})
        if user:
            if user.get('_id'): del user['_id']
            if user.get('password'): del user['password']
            doorman_cache.set_cache('user_cache', username, user)

    if not user:
        logger.error(f'User not found: {username}')
        raise ValueError(f'User {username} not found')

    role_name = user.get('role')
    role = None
    if role_name:
        role = doorman_cache.get_cache('role_cache', role_name)
        if not role:
            role = role_collection.find_one({'role_name': role_name})
            if role:
                if role.get('_id'): del role['_id']
                doorman_cache.set_cache('role_cache', role_name, role)

    accesses = {
        'ui_access': True,
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
        'exp': datetime.now(UTC) + expire,
        'jti': str(uuid.uuid4()),
        'accesses': accesses
    })

    logger.info(f'Creating token for user {username} with accesses: {accesses}')
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
