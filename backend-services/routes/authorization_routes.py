"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

# External imports
from fastapi import APIRouter, Request, Depends, HTTPException, Response
from jose import JWTError
import uuid
import time
import logging
import os

# Internal imports
from models.response_model import ResponseModel
from services.user_service import UserService
from utils.response_util import respond_rest
from utils.auth_util import auth_required, create_access_token
from utils.auth_blacklist import TimedHeap, jwt_blacklist, revoke_all_for_user, unrevoke_all_for_user, is_user_revoked, add_revoked_jti
from utils.role_util import platform_role_required_bool
from utils.role_util import is_admin_user
from models.update_user_model import UpdateUserModel
from utils.limit_throttle_util import limit_by_ip

authorization_router = APIRouter()

logger = logging.getLogger('doorman.gateway')

"""
Create authorization token

Request:
{}
Response:
{}
"""

@authorization_router.post('/authorization',
    description='Create authorization token',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'access_token': '******************'
                    }
                }
            }
        }
    }
)

async def authorization(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        # IP-based rate limiting to prevent brute force attacks (5 attempts per 5 minutes)
        # Can be overridden via environment variables for testing
        login_limit = int(os.getenv('LOGIN_IP_RATE_LIMIT', '5'))
        login_window = int(os.getenv('LOGIN_IP_RATE_WINDOW', '300'))
        rate_limit_info = await limit_by_ip(request, limit=login_limit, window=login_window)

        logger.info(f'{request_id} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        # Parse JSON body safely; invalid JSON should not 500
        try:
            data = await request.json()
        except Exception:
            return respond_rest(ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='AUTH004',
                error_message='Invalid JSON payload'
            ))
        email = data.get('email')
        password = data.get('password')
        if not email or not password:
            return respond_rest(ResponseModel(
                status_code=400,
                response_headers={
                    'request_id': request_id
                },
                error_code='AUTH001',
                error_message='Missing email or password'
            ))
        user = await UserService.check_password_return_user(email, password)
        if not user:
            return respond_rest(ResponseModel(
                status_code=400,
                response_headers={
                    'request_id': request_id
                },
                error_code='AUTH002',
                error_message='Invalid email or password'
            ))
        if not user['active']:
            return respond_rest(ResponseModel(
                status_code=400,
                response_headers={
                    'request_id': request_id
                },
                error_code='AUTH007',
                error_message='User is not active'
            ))
        access_token = create_access_token({'sub': user['username'], 'role': user['role']}, False)

        logger.info(f"Login successful for user: {user['username']}")

        response = respond_rest(ResponseModel(
            status_code=200,
            response_headers={
                'request_id': request_id
            },
            response={'access_token': access_token}
        ))

        # Add rate limit headers
        if rate_limit_info:
            response.headers['X-RateLimit-Limit'] = str(rate_limit_info['limit'])
            response.headers['X-RateLimit-Remaining'] = str(rate_limit_info['remaining'])
            response.headers['X-RateLimit-Reset'] = str(rate_limit_info['reset'])

        response.delete_cookie('access_token_cookie')

        import uuid as _uuid
        csrf_token = str(_uuid.uuid4())

        _secure_env = os.getenv('COOKIE_SECURE')
        if _secure_env is not None:
            _secure = str(_secure_env).lower() == 'true'
        else:
            _secure = os.getenv('HTTPS_ENABLED', 'false').lower() == 'true' or os.getenv('HTTPS_ONLY', 'false').lower() == 'true'
        _domain = os.getenv('COOKIE_DOMAIN', None)
        _samesite = (os.getenv('COOKIE_SAMESITE', 'Strict') or 'Strict').strip().lower()
        if _samesite not in ('strict', 'lax', 'none'):
            _samesite = 'strict'
        host = request.url.hostname or (request.client.host if request.client else None)

        if _domain and host and (host == _domain or host.endswith('.' + _domain)):
            safe_domain = _domain
        else:
            safe_domain = None

        # Cookie Duplication Strategy:
        # Cookies are set twice for maximum compatibility across deployment configurations:
        # 1. WITH domain attribute (if COOKIE_DOMAIN is set and matches request host)
        #    - Enables subdomain sharing (e.g., *.example.com)
        #    - Required for SSO and multi-subdomain setups
        # 2. WITHOUT domain attribute
        #    - Exact domain match only (no subdomain sharing)
        #    - Ensures cookies work even if domain validation fails
        #
        # Configuration:
        # - COOKIE_DOMAIN: Base domain for subdomain sharing (e.g., "example.com")
        # - For SSO: Set to SSO provider's domain scope
        # - For reverse proxy: Set to base domain (not subdomain like "api.example.com")
        # - Leave unset for single-domain deployments
        #
        # Impact: Doubles cookie size; consider for large JWTs behind proxies

        # Set CSRF token with domain attribute (for subdomain sharing)
        response.set_cookie(
            key='csrf_token',
            value=csrf_token,
            httponly=False,
            secure=_secure,
            samesite=_samesite,
            path='/',
            domain=safe_domain,
            max_age=1800
        )

        # Set CSRF token without domain attribute (exact domain only)
        response.set_cookie(
            key='csrf_token',
            value=csrf_token,
            httponly=False,
            secure=_secure,
            samesite=_samesite,
            path='/',
            max_age=1800
        )

        # Set access token with domain attribute (for subdomain sharing)
        response.set_cookie(
            key='access_token_cookie',
            value=access_token,
            httponly=True,
            secure=_secure,
            samesite=_samesite,
            path='/',
            domain=safe_domain,
            max_age=1800
        )

        # Set access token without domain attribute (exact domain only)
        response.set_cookie(
            key='access_token_cookie',
            value=access_token,
            httponly=True,
            secure=_secure,
            samesite=_samesite,
            path='/',
            max_age=1800
        )
        return response
    except HTTPException as e:
        # Preserve IP rate limit semantics (429 + Retry-After headers)
        if getattr(e, 'status_code', None) == 429:
            headers = getattr(e, 'headers', {}) or {}
            detail = e.detail if isinstance(e.detail, dict) else {}
            return respond_rest(ResponseModel(
                status_code=429,
                response_headers={
                    'request_id': request_id,
                    **headers
                },
                error_code=str(detail.get('error_code') or 'IP_RATE_LIMIT'),
                error_message=str(detail.get('message') or 'Too many requests')
            ))
        # Default mapping for auth failures
        return respond_rest(ResponseModel(
            status_code=401,
            response_headers={
                'request_id': request_id
            },
            error_code='AUTH003',
            error_message='Unable to validate credentials'
            ))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={
                'request_id': request_id
            },
            error_code='GTW999',
            error_message='An unexpected error occurred'
            ))
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

# Admin endpoints for revoking tokens and disabling/enabling users
"""
Endpoint

Request:
{}
Response:
{}
"""

@authorization_router.post('/authorization/admin/revoke/{username}',
    description='Revoke all active tokens for a user (admin)',
    response_model=ResponseModel)

async def admin_revoke_user_tokens(username: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        admin_user = payload.get('sub')
        logger.info(f'{request_id} | Username: {admin_user} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(admin_user, 'manage_auth'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='AUTH900',
                error_message='You do not have permission to manage auth'
            ))

        try:
            if await is_admin_user(username) and not await is_admin_user(admin_user):
                return respond_rest(ResponseModel(
                    status_code=404,
                    response_headers={'request_id': request_id},
                    error_message='User not found'
                ))
        except Exception as e:
            logger.error(f'{request_id} | Admin check failed: {str(e)}', exc_info=True)
            # Continue anyway - permission check failure shouldn't block operation
        revoke_all_for_user(username)
        return respond_rest(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            message=f'All tokens revoked for {username}'
        ))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='GTW999',
            error_message='An unexpected error occurred'
        ))
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Endpoint

Request:
{}
Response:
{}
"""

@authorization_router.post('/authorization/admin/unrevoke/{username}',
    description='Clear token revocation for a user (admin)',
    response_model=ResponseModel)

async def admin_unrevoke_user_tokens(username: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        admin_user = payload.get('sub')
        logger.info(f'{request_id} | Username: {admin_user} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(admin_user, 'manage_auth'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='AUTH900',
                error_message='You do not have permission to manage auth'
            ))

        try:
            if await is_admin_user(username) and not await is_admin_user(admin_user):
                return respond_rest(ResponseModel(
                    status_code=404,
                    response_headers={'request_id': request_id},
                    error_message='User not found'
                ))
        except Exception as e:
            logger.error(f'{request_id} | Admin check failed: {str(e)}', exc_info=True)
            # Continue anyway - permission check failure shouldn't block operation
        unrevoke_all_for_user(username)
        return respond_rest(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            message=f'Token revocation cleared for {username}'
        ))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='GTW999',
            error_message='An unexpected error occurred'
        ))
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Endpoint

Request:
{}
Response:
{}
"""

@authorization_router.post('/authorization/admin/disable/{username}',
    description='Disable a user (admin)',
    response_model=ResponseModel)

async def admin_disable_user(username: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        admin_user = payload.get('sub')
        logger.info(f'{request_id} | Username: {admin_user} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(admin_user, 'manage_auth'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='AUTH900',
                error_message='You do not have permission to manage auth'
            ))

        try:
            if await is_admin_user(username) and not await is_admin_user(admin_user):
                return respond_rest(ResponseModel(
                    status_code=404,
                    response_headers={'request_id': request_id},
                    error_message='User not found'
                ))
        except Exception as e:
            logger.error(f'{request_id} | Admin check failed: {str(e)}', exc_info=True)
            # Continue anyway - permission check failure shouldn't block operation

        await UserService.update_user(username, UpdateUserModel(active=False), request_id)

        revoke_all_for_user(username)
        return respond_rest(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            message=f'User {username} disabled and tokens revoked'
        ))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='GTW999',
            error_message='An unexpected error occurred'
        ))
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Endpoint

Request:
{}
Response:
{}
"""

@authorization_router.post('/authorization/admin/enable/{username}',
    description='Enable a user (admin)',
    response_model=ResponseModel)

async def admin_enable_user(username: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        admin_user = payload.get('sub')
        logger.info(f'{request_id} | Username: {admin_user} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(admin_user, 'manage_auth'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='AUTH900',
                error_message='You do not have permission to manage auth'
            ))

        try:
            if await is_admin_user(username) and not await is_admin_user(admin_user):
                return respond_rest(ResponseModel(
                    status_code=404,
                    response_headers={'request_id': request_id},
                    error_message='User not found'
                ))
        except Exception as e:
            logger.error(f'{request_id} | Admin check failed: {str(e)}', exc_info=True)
            # Continue anyway - permission check failure shouldn't block operation
        await UserService.update_user(username, UpdateUserModel(active=True), request_id)

        return respond_rest(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            message=f'User {username} enabled'
        ))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='GTW999',
            error_message='An unexpected error occurred'
        ))
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Endpoint

Request:
{}
Response:
{}
"""

@authorization_router.get('/authorization/admin/status/{username}',
    description='Get auth status for a user (admin)',
    response_model=ResponseModel)

async def admin_user_status(username: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        admin_user = payload.get('sub')
        logger.info(f'{request_id} | Username: {admin_user} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(admin_user, 'manage_auth'):
            return respond_rest(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='AUTH900',
                error_message='You do not have permission to manage auth'
            ))

        try:
            if await is_admin_user(username) and not await is_admin_user(admin_user):
                return respond_rest(ResponseModel(
                    status_code=404,
                    response_headers={'request_id': request_id},
                    error_message='User not found'
                ))
        except Exception as e:
            logger.error(f'{request_id} | Admin check failed: {str(e)}', exc_info=True)
            # Continue anyway - permission check failure shouldn't block operation
        user = await UserService.get_user_by_username_helper(username)
        status = {
            'active': bool(user.get('active', False)),
            'revoked': is_user_revoked(username)
        }
        return respond_rest(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            response=status
        ))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='GTW999',
            error_message='An unexpected error occurred'
        ))
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Create authorization refresh token

Request:
{}
Response:
{}
"""

@authorization_router.post('/authorization/refresh',
    description='Create authorization refresh token',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'refresh_token': '******************'
                    }
                }
            }
        }
    }
)

async def extended_authorization(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        user = await UserService.get_user_by_username_helper(username)
        if not user['active']:
            return respond_rest(ResponseModel(
                status_code=400,
                response_headers={
                    'request_id': request_id
                },
                error_code='AUTH007',
                error_message='User is not active'
            ))
        refresh_token = create_access_token({'sub': username, 'role': user['role']}, True)
        response = respond_rest(ResponseModel(
            status_code=200,
            response_headers={
                'request_id': request_id
            },
            response={'refresh_token': refresh_token}
        ))

        import uuid as _uuid
        csrf_token = str(_uuid.uuid4())

        _secure_env = os.getenv('COOKIE_SECURE')
        if _secure_env is not None:
            _secure = str(_secure_env).lower() == 'true'
        else:
            _secure = os.getenv('HTTPS_ENABLED', 'false').lower() == 'true' or os.getenv('HTTPS_ONLY', 'false').lower() == 'true'
        _domain = os.getenv('COOKIE_DOMAIN', None)
        _samesite = (os.getenv('COOKIE_SAMESITE', 'Strict') or 'Strict').strip().lower()
        if _samesite not in ('strict', 'lax', 'none'):
            _samesite = 'strict'
        host = request.url.hostname or (request.client.host if request.client else None)

        if _domain and host and (host == _domain or host.endswith('.' + _domain)):
            safe_domain = _domain
        else:
            safe_domain = None

        # Cookie Duplication Strategy (see login endpoint for full documentation)
        # Cookies set twice: WITH domain for subdomain sharing, WITHOUT domain for exact match

        # Set CSRF token with domain attribute (for subdomain sharing)
        response.set_cookie(
            key='csrf_token',
            value=csrf_token,
            httponly=False,
            secure=_secure,
            samesite=_samesite,
            path='/',
            domain=safe_domain,
            max_age=604800
        )

        # Set CSRF token without domain attribute (exact domain only)
        response.set_cookie(
            key='csrf_token',
            value=csrf_token,
            httponly=False,
            secure=_secure,
            samesite=_samesite,
            path='/',
            max_age=604800
        )

        # Set refresh token with domain attribute (for subdomain sharing)
        response.set_cookie(
            key='access_token_cookie',
            value=refresh_token,
            httponly=True,
            secure=_secure,
            samesite=_samesite,
            path='/',
            domain=safe_domain,
            max_age=604800
        )

        # Set refresh token without domain attribute (exact domain only)
        response.set_cookie(
            key='access_token_cookie',
            value=refresh_token,
            httponly=True,
            secure=_secure,
            samesite=_samesite,
            path='/',
            max_age=604800
        )
        return response
    except HTTPException as e:
        return respond_rest(ResponseModel(
            status_code=401,
            response_headers={
                'request_id': request_id
            },
            error_code='AUTH003',
            error_message='Unable to validate credentials'
            ))
    except JWTError as e:
        logging.error(f'Token refresh failed: {str(e)}')
        return respond_rest(ResponseModel(
            status_code=401,
            response_headers={
                'request_id': request_id
            },
            error_code='AUTH004',
            error_message='Token refresh failed'
            ))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={
                'request_id': request_id
            },
            error_code='GTW999',
            error_message='An unexpected error occurred'
            ))
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Get authorization token status

Request:
{}
Response:
{}
"""

@authorization_router.get('/authorization/status',
    description='Get authorization token status',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'status': 'authorized'
                    }
                }
            }
        }
    }
)

async def authorization_status(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        return respond_rest(ResponseModel(
            status_code=200,
            response_headers={
                'request_id': request_id
            },
            message='Token is valid'
            ))
    except JWTError:
        return respond_rest(ResponseModel(
            status_code=401,
            response_headers={
                'request_id': request_id
            },
            error_code='AUTH005',
            error_message='Token is invalid'
            ))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={
                'request_id': request_id
            },
            error_code='GTW999',
            error_message='An unexpected error occurred'
            ))
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

"""
Invalidate authorization token

Request:
{}
Response:
{}
"""

@authorization_router.post('/authorization/invalidate',
    description='Invalidate authorization token',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'message': 'Your token has been invalidated'
                    }
                }
            }
        }
    }
)

async def authorization_invalidate(response: Response, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        # Add this token's JTI to durable revocation with TTL until expiry
        try:
            import time as _t
            exp = payload.get('exp')
            ttl = None
            if isinstance(exp, (int, float)):
                ttl = max(1, int(exp - _t.time()))
            add_revoked_jti(username, payload.get('jti'), ttl)
        except Exception as e:
            # Fallback to in-memory TimedHeap (back-compat)
            logger.warning(f'{request_id} | Token revocation failed, using fallback: {str(e)}')
            if username not in jwt_blacklist:
                jwt_blacklist[username] = TimedHeap()
            jwt_blacklist[username].push(payload.get('jti'))
        response = respond_rest(ResponseModel(
            status_code=200,
            response_headers={
                'request_id': request_id
            },
            message='Your token has been invalidated'
            ))

        _domain = os.getenv('COOKIE_DOMAIN', None)
        host = request.url.hostname or (request.client.host if request.client else None)
        safe_domain = _domain if (_domain and host and (host == _domain or host.endswith(_domain))) else None
        response.delete_cookie('access_token_cookie', domain=safe_domain, path='/')
        return response
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={
                'request_id': request_id
            },
            error_code='GTW999',
            error_message='An unexpected error occurred'
            ))
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')
