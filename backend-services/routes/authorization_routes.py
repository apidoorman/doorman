"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import logging
import os
import time
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from jose import JWTError

from models.create_user_model import CreateUserModel
from models.response_model import ResponseModel
from models.update_user_model import UpdateUserModel
from services.user_service import UserService
from utils.auth_blacklist import (
    TimedHeap,
    add_revoked_jti,
    is_user_revoked,
    jwt_blacklist,
    revoke_all_for_user,
    unrevoke_all_for_user,
)
from utils.auth_util import auth_required, create_access_token
from utils.limit_throttle_util import limit_by_ip
from utils.response_util import respond_rest
from utils.role_util import is_admin_user, platform_role_required_bool

authorization_router = APIRouter()

logger = logging.getLogger('doorman.gateway')

"""
Create authorization token

Request:
{}
Response:
{}
"""


@authorization_router.post(
    '/authorization',
    description='Create authorization token',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {'application/json': {'example': {'access_token': '******************'}}},
        }
    },
)
async def authorization(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        login_limit = int(os.getenv('LOGIN_IP_RATE_LIMIT', '5'))
        login_window = int(os.getenv('LOGIN_IP_RATE_WINDOW', '300'))
        rate_limit_info = await limit_by_ip(request, limit=login_limit, window=login_window)

        logger.info(f'From: {request.client.host}:{request.client.port}')
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        try:
            data = await request.json()
        except Exception:
            return respond_rest(
                ResponseModel(
                    status_code=400,
                    response_headers={'request_id': request_id},
                    error_code='AUTH004',
                    error_message='Invalid JSON payload',
                )
            )
        email = data.get('email')
        password = data.get('password')
        if not email or not password:
            return respond_rest(
                ResponseModel(
                    status_code=400,
                    response_headers={'request_id': request_id},
                    error_code='AUTH001',
                    error_message='Missing email or password',
                )
            )
        user = await UserService.check_password_return_user(email, password)
        if not user:
            return respond_rest(
                ResponseModel(
                    status_code=400,
                    response_headers={'request_id': request_id},
                    error_code='AUTH002',
                    error_message='Invalid email or password',
                )
            )
        if not user['active']:
            return respond_rest(
                ResponseModel(
                    status_code=400,
                    response_headers={'request_id': request_id},
                    error_code='AUTH007',
                    error_message='User is not active',
                )
            )
        access_token = create_access_token({'sub': user['username'], 'role': user['role']}, False)

        logger.info(f'Login successful for user: {user["username"]}')

        response = respond_rest(
            ResponseModel(
                status_code=200,
                response_headers={'request_id': request_id},
                response={'access_token': access_token},
            )
        )

        if rate_limit_info:
            response.headers['X-RateLimit-Limit'] = str(rate_limit_info['limit'])
            response.headers['X-RateLimit-Remaining'] = str(rate_limit_info['remaining'])
            response.headers['X-RateLimit-Reset'] = str(rate_limit_info['reset'])

        # Clear any prior cookies to avoid conflicts
        response.delete_cookie('access_token_cookie')

        import uuid as _uuid

        csrf_token = str(_uuid.uuid4())

        # Decide cookie security based on env and proxy headers
        _secure_env = os.getenv('COOKIE_SECURE')
        https_only = os.getenv('HTTPS_ONLY', 'false').lower() == 'true'
        xf_proto = (
            request.headers.get('x-forwarded-proto')
            or request.headers.get('X-Forwarded-Proto')
            or ''
        ).lower()
        scheme = (request.url.scheme or '').lower()
        inferred_secure = xf_proto == 'https' or scheme == 'https'
        if _secure_env is not None:
            _secure = str(_secure_env).lower() == 'true'
        else:
            # Prefer actual connection security where possible to ensure
            # cookies are usable in local HTTP runs. This avoids setting
            # Secure on cookies for localhost/127.0.0.1 when HTTPS_ONLY=true
            # but the connection is plain HTTP.
            _secure = bool(inferred_secure or https_only)

        # Force non-Secure cookies when serving local hosts over HTTP to
        # allow developer/live-test flows without TLS. Do not override when
        # HTTPS_ONLY is enabled, since tests and production expectations
        # require Secure cookies in that mode regardless of host.
        try:
            _host = request.headers.get('x-forwarded-host') or request.url.hostname or (
                request.client.host if request.client else None
            )
            if (
                not inferred_secure
                and not https_only
                and str(_host) in {'localhost', '127.0.0.1', 'testserver'}
            ):
                _secure = False
        except Exception:
            pass


        if not _secure and os.getenv('ENV', '').lower() in ('production', 'prod'):
            logger.warning(
                f'SECURITY WARNING: Secure cookies disabled in production environment'
            )

        _domain = os.getenv('COOKIE_DOMAIN', None)
        _raw_samesite = os.getenv('COOKIE_SAMESITE')
        if _raw_samesite is None or str(_raw_samesite).strip() == '':
            _samesite = 'strict'
        else:
            _samesite = str(_raw_samesite).strip().lower()
        if _samesite not in ('strict', 'lax', 'none'):
            _samesite = 'lax'
        if _samesite == 'none' and not _secure:
            logger.warning(
                f'COOKIE_SAMESITE=None requires Secure cookies; downgrading to Lax for non-HTTPS'
            )
            _samesite = 'lax'

        host = request.headers.get('x-forwarded-host') or request.url.hostname or (request.client.host if request.client else None)
        # Prefer host-only cookies for single-label local hosts (localhost/testserver)
        # Only set Domain attribute when env domain is a registrable domain (contains a dot)
        _local_hosts = {'localhost', '127.0.0.1', 'testserver'}
        if (
            _domain
            and '.' in str(_domain)
            and host
            and (host == _domain or host.endswith('.' + _domain))
        ):
            cookie_domain = _domain
        else:
            cookie_domain = None  # Host-only for maximum compatibility in tests/local

        # Set CSRF + Access cookies once with computed attributes
        response.set_cookie(
            key='csrf_token',
            value=csrf_token,
            httponly=False,
            secure=_secure,
            samesite=_samesite,
            path='/',
            # Use host-only cookie for CSRF to maximize compatibility in tests/clients
            domain=cookie_domain,
            max_age=1800,
        )

        response.set_cookie(
            key='access_token_cookie',
            value=access_token,
            httponly=True,
            secure=_secure,
            samesite=_samesite,
            path='/',
            domain=cookie_domain,
            max_age=1800,
        )
        try:
            # Cache CSRF token for header validation fallback during HTTPS_ONLY
            from utils.doorman_cache_util import doorman_cache as _cache
            from jose import jwt as _jwt
            from utils.auth_util import ALGORITHM as _ALG, _get_secret_key as _getk

            payload = _jwt.decode(access_token, _getk(), algorithms=[_ALG], options={'verify_signature': True})
            uname = payload.get('sub')
            if uname:
                _cache.set_cache('csrf_token_map', uname, csrf_token)
        except Exception:
            pass
        # No additional dev/test cookies are set; tests use the standard cookie
        # and header paths.
        return response
    except HTTPException as e:
        if getattr(e, 'status_code', None) == 429:
            headers = getattr(e, 'headers', {}) or {}
            detail = e.detail if isinstance(e.detail, dict) else {}
            return respond_rest(
                ResponseModel(
                    status_code=429,
                    response_headers={'request_id': request_id, **headers},
                    error_code=str(detail.get('error_code') or 'IP_RATE_LIMIT'),
                    error_message=str(detail.get('message') or 'Too many requests'),
                )
            )
        # Preserve validation errors from password check as 400 Invalid email or password
        try:
            detail = getattr(e, 'detail', '')
            if getattr(e, 'status_code', None) in (400,):
                return respond_rest(
                    ResponseModel(
                        status_code=400,
                        response_headers={'request_id': request_id},
                        error_code='AUTH002',
                        error_message='Invalid email or password',
                    )
                )
        except Exception:
            pass
        return respond_rest(
            ResponseModel(
                status_code=401,
                response_headers={'request_id': request_id},
                error_code='AUTH003',
                error_message='Unable to validate credentials',
            )
        )
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


"""
Register new user

Request:
{}
Response:
{}
"""


@authorization_router.post(
    '/authorization/register',
    description='Register new user',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {'application/json': {'example': {'message': 'User created successfully'}}},
        }
    },
)
async def register(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        # Rate limit registration to prevent abuse
        reg_limit = int(os.getenv('REGISTER_IP_RATE_LIMIT', '5'))
        reg_window = int(os.getenv('REGISTER_IP_RATE_WINDOW', '3600'))
        await limit_by_ip(request, limit=reg_limit, window=reg_window)

        logger.info(
            f'Register request from: {request.client.host}:{request.client.port}'
        )

        try:
            data = await request.json()
        except Exception:
            return respond_rest(
                ResponseModel(
                    status_code=400,
                    response_headers={'request_id': request_id},
                    error_code='AUTH004',
                    error_message='Invalid JSON payload',
                )
            )

        # Validate required fields
        if not data.get('email') or not data.get('password'):
            return respond_rest(
                ResponseModel(
                    status_code=400,
                    response_headers={'request_id': request_id},
                    error_code='AUTH001',
                    error_message='Missing email or password',
                )
            )

        # Create user model
        # Default to 'user' role and active=True
        user_data = CreateUserModel(
            username=data.get('email').split('@')[0],  # Simple username derivation
            email=data.get('email'),
            password=data.get('password'),
            role='user',
            active=True,
        )

        # Check if user exists (UserService.create_user handles this but we want clean error)
        # Actually UserService.create_user will return error if exists.

        result = await UserService.create_user(user_data, request_id)

        # If successful, we could auto-login, but for now just return success
        return respond_rest(result)

    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


"""
Endpoint

Request:
{}
Response:
{}
"""


@authorization_router.post(
    '/authorization/admin/revoke/{username}',
    description='Revoke all active tokens for a user (admin)',
    response_model=ResponseModel,
)
async def admin_revoke_user_tokens(username: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        admin_user = payload.get('sub')
        logger.info(
            f'Username: {admin_user} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(admin_user, 'manage_auth'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={'request_id': request_id},
                    error_code='AUTH900',
                    error_message='You do not have permission to manage auth',
                )
            )

        try:
            if await is_admin_user(username) and not await is_admin_user(admin_user):
                return respond_rest(
                    ResponseModel(
                        status_code=404,
                        response_headers={'request_id': request_id},
                        error_message='User not found',
                    )
                )
        except Exception as e:
            logger.error(f'Admin check failed: {str(e)}', exc_info=True)
        revoke_all_for_user(username)
        return respond_rest(
            ResponseModel(
                status_code=200,
                response_headers={'request_id': request_id},
                message=f'All tokens revoked for {username}',
            )
        )
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


"""
Endpoint

Request:
{}
Response:
{}
"""


@authorization_router.post(
    '/authorization/admin/unrevoke/{username}',
    description='Clear token revocation for a user (admin)',
    response_model=ResponseModel,
)
async def admin_unrevoke_user_tokens(username: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        admin_user = payload.get('sub')
        logger.info(
            f'Username: {admin_user} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(admin_user, 'manage_auth'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={'request_id': request_id},
                    error_code='AUTH900',
                    error_message='You do not have permission to manage auth',
                )
            )

        try:
            if await is_admin_user(username) and not await is_admin_user(admin_user):
                return respond_rest(
                    ResponseModel(
                        status_code=404,
                        response_headers={'request_id': request_id},
                        error_message='User not found',
                    )
                )
        except Exception as e:
            logger.error(f'Admin check failed: {str(e)}', exc_info=True)
        unrevoke_all_for_user(username)
        return respond_rest(
            ResponseModel(
                status_code=200,
                response_headers={'request_id': request_id},
                message=f'Token revocation cleared for {username}',
            )
        )
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


"""
Endpoint

Request:
{}
Response:
{}
"""


@authorization_router.post(
    '/authorization/admin/disable/{username}',
    description='Disable a user (admin)',
    response_model=ResponseModel,
)
async def admin_disable_user(username: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        admin_user = payload.get('sub')
        logger.info(
            f'Username: {admin_user} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(admin_user, 'manage_auth'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={'request_id': request_id},
                    error_code='AUTH900',
                    error_message='You do not have permission to manage auth',
                )
            )

        try:
            if await is_admin_user(username) and not await is_admin_user(admin_user):
                return respond_rest(
                    ResponseModel(
                        status_code=404,
                        response_headers={'request_id': request_id},
                        error_message='User not found',
                    )
                )
        except Exception as e:
            logger.error(f'Admin check failed: {str(e)}', exc_info=True)

        await UserService.update_user(username, UpdateUserModel(active=False), request_id)

        revoke_all_for_user(username)
        return respond_rest(
            ResponseModel(
                status_code=200,
                response_headers={'request_id': request_id},
                message=f'User {username} disabled and tokens revoked',
            )
        )
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


"""
Endpoint

Request:
{}
Response:
{}
"""


@authorization_router.post(
    '/authorization/admin/enable/{username}',
    description='Enable a user (admin)',
    response_model=ResponseModel,
)
async def admin_enable_user(username: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        admin_user = payload.get('sub')
        logger.info(
            f'Username: {admin_user} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(admin_user, 'manage_auth'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={'request_id': request_id},
                    error_code='AUTH900',
                    error_message='You do not have permission to manage auth',
                )
            )

        try:
            if await is_admin_user(username) and not await is_admin_user(admin_user):
                return respond_rest(
                    ResponseModel(
                        status_code=404,
                        response_headers={'request_id': request_id},
                        error_message='User not found',
                    )
                )
        except Exception as e:
            logger.error(f'Admin check failed: {str(e)}', exc_info=True)
        await UserService.update_user(username, UpdateUserModel(active=True), request_id)

        return respond_rest(
            ResponseModel(
                status_code=200,
                response_headers={'request_id': request_id},
                message=f'User {username} enabled',
            )
        )
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


"""
Endpoint

Request:
{}
Response:
{}
"""


@authorization_router.get(
    '/authorization/admin/status/{username}',
    description='Get auth status for a user (admin)',
    response_model=ResponseModel,
)
async def admin_user_status(username: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        admin_user = payload.get('sub')
        logger.info(
            f'Username: {admin_user} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(admin_user, 'manage_auth'):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={'request_id': request_id},
                    error_code='AUTH900',
                    error_message='You do not have permission to manage auth',
                )
            )

        try:
            if await is_admin_user(username) and not await is_admin_user(admin_user):
                return respond_rest(
                    ResponseModel(
                        status_code=404,
                        response_headers={'request_id': request_id},
                        error_message='User not found',
                    )
                )
        except Exception as e:
            logger.error(f'Admin check failed: {str(e)}', exc_info=True)
        user = await UserService.get_user_by_username_helper(username)
        status = {'active': bool(user.get('active', False)), 'revoked': is_user_revoked(username)}
        return respond_rest(
            ResponseModel(
                status_code=200, response_headers={'request_id': request_id}, response=status
            )
        )
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


"""
Create authorization refresh token

Request:
{}
Response:
{}
"""


@authorization_router.post(
    '/authorization/refresh',
    description='Create authorization refresh token',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {'application/json': {'example': {'refresh_token': '******************'}}},
        }
    },
)
async def extended_authorization(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        user = await UserService.get_user_by_username_helper(username)
        if not user['active']:
            return respond_rest(
                ResponseModel(
                    status_code=400,
                    response_headers={'request_id': request_id},
                    error_code='AUTH007',
                    error_message='User is not active',
                )
            )
        refresh_token = create_access_token({'sub': username, 'role': user['role']}, True)
        response = respond_rest(
            ResponseModel(
                status_code=200,
                response_headers={'request_id': request_id},
                response={'refresh_token': refresh_token},
            )
        )

        import uuid as _uuid

        csrf_token = str(_uuid.uuid4())

        _secure_env = os.getenv('COOKIE_SECURE')
        https_only = os.getenv('HTTPS_ONLY', 'false').lower() == 'true'
        xf_proto = (
            request.headers.get('x-forwarded-proto')
            or request.headers.get('X-Forwarded-Proto')
            or ''
        ).lower()
        scheme = (request.url.scheme or '').lower()
        inferred_secure = xf_proto == 'https' or scheme == 'https'
        if _secure_env is not None:
            _secure = str(_secure_env).lower() == 'true'
        else:
            _secure = inferred_secure


        if not _secure and os.getenv('ENV', '').lower() in ('production', 'prod'):
            logger.warning(
                f'SECURITY WARNING: Secure cookies disabled in production environment'
            )

        _domain = os.getenv('COOKIE_DOMAIN', None)
        _raw_samesite = os.getenv('COOKIE_SAMESITE')
        if _raw_samesite is None or str(_raw_samesite).strip() == '':
            _samesite = 'strict'
        else:
            _samesite = str(_raw_samesite).strip().lower()
        if _samesite not in ('strict', 'lax', 'none'):
            _samesite = 'lax'
        host = request.headers.get('x-forwarded-host') or request.url.hostname or (request.client.host if request.client else None)
        _local_hosts = {'localhost', '127.0.0.1', 'testserver'}
        if (
            _domain
            and '.' in str(_domain)
            and host
            and (host == _domain or host.endswith('.' + _domain))
        ):
            cookie_domain = _domain
        else:
            cookie_domain = None

        response.set_cookie(
            key='csrf_token',
            value=csrf_token,
            httponly=False,
            secure=_secure,
            samesite=_samesite,
            path='/',
            domain=cookie_domain,
            max_age=604800,
        )

        response.set_cookie(
            key='access_token_cookie',
            value=refresh_token,
            httponly=True,
            secure=_secure,
            samesite=_samesite,
            path='/',
            domain=cookie_domain,
            max_age=604800,
        )
        try:
            from utils.doorman_cache_util import doorman_cache as _cache
            from jose import jwt as _jwt
            from utils.auth_util import ALGORITHM as _ALG, _get_secret_key as _getk

            payload = _jwt.decode(refresh_token, _getk(), algorithms=[_ALG], options={'verify_signature': True})
            uname = payload.get('sub')
            if uname:
                _cache.set_cache('csrf_token_map', uname, csrf_token)
        except Exception:
            pass
        # No additional dev/test cookies are set; tests use the standard cookie
        # and header paths.
        return response
    except HTTPException:
        return respond_rest(
            ResponseModel(
                status_code=401,
                response_headers={'request_id': request_id},
                error_code='AUTH003',
                error_message='Unable to validate credentials',
            )
        )
    except JWTError as e:
        logging.error(f'Token refresh failed: {str(e)}')
        return respond_rest(
            ResponseModel(
                status_code=401,
                response_headers={'request_id': request_id},
                error_code='AUTH004',
                error_message='Token refresh failed',
            )
        )
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


"""
Get authorization token status

Request:
{}
Response:
{}
"""


@authorization_router.get(
    '/authorization/status',
    description='Get authorization token status',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {'application/json': {'example': {'status': 'authorized'}}},
        }
    },
)
async def authorization_status(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        return respond_rest(
            ResponseModel(
                status_code=200,
                response_headers={'request_id': request_id},
                message='Token is valid',
            )
        )
    except HTTPException as e:
        return respond_rest(
            ResponseModel(
                status_code=getattr(e, 'status_code', 401),
                response_headers={'request_id': request_id},
                error_code='AUTH005',
                error_message=str(getattr(e, 'detail', 'Token error')),
            )
        )
    except JWTError:
        return respond_rest(
            ResponseModel(
                status_code=401,
                response_headers={'request_id': request_id},
                error_code='AUTH005',
                error_message='Token is invalid',
            )
        )
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')


"""
Invalidate authorization token

Request:
{}
Response:
{}
"""


@authorization_router.post(
    '/authorization/invalidate',
    description='Invalidate authorization token',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {'example': {'message': 'Your token has been invalidated'}}
            },
        }
    },
)
async def authorization_invalidate(response: Response, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'Endpoint: {request.method} {str(request.url.path)}')
        try:
            import time as _t

            exp = payload.get('exp')
            ttl = None
            if isinstance(exp, (int, float)):
                ttl = max(1, int(exp - _t.time()))
            add_revoked_jti(username, payload.get('jti'), ttl)
        except Exception as e:
            logger.warning(f'Token revocation failed, using fallback: {str(e)}')
            if username not in jwt_blacklist:
                jwt_blacklist[username] = TimedHeap()
            jwt_blacklist[username].push(payload.get('jti'))
        response = respond_rest(
            ResponseModel(
                status_code=200,
                response_headers={'request_id': request_id},
                message='Your token has been invalidated',
            )
        )

        _domain = os.getenv('COOKIE_DOMAIN', None)
        host = request.headers.get('x-forwarded-host') or request.url.hostname or (request.client.host if request.client else None)
        _local_hosts = {'localhost', '127.0.0.1', 'testserver'}
        if host in _local_hosts or (isinstance(host, str) and host.endswith('.localhost')):
            safe_domain = None
        elif _domain and host and (host == _domain or host.endswith(_domain)):
            safe_domain = _domain
        else:
            safe_domain = None
        response.delete_cookie('access_token_cookie', domain=safe_domain, path='/')
        try:
            response.delete_cookie('access_token_cookie_dev', domain=safe_domain, path='/')
        except Exception:
            pass
        return response
    except HTTPException as e:
        return respond_rest(
            ResponseModel(
                status_code=getattr(e, 'status_code', 401),
                response_headers={'request_id': request_id},
                error_code='AUTH005',
                error_message=str(getattr(e, 'detail', 'Token error')),
            )
        )
    except Exception as e:
        logger.critical(f'Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'Total time: {str(end_time - start_time)}ms')
