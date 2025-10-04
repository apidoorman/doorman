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
from utils.auth_blacklist import TimedHeap, jwt_blacklist, revoke_all_for_user, unrevoke_all_for_user, is_user_revoked
from utils.role_util import platform_role_required_bool
from utils.role_util import is_admin_user
from models.update_user_model import UpdateUserModel

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
        logger.info(f'{request_id} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        data = await request.json()
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
        response.delete_cookie('access_token_cookie')

        import uuid as _uuid
        csrf_token = str(_uuid.uuid4())

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

        response.set_cookie(
            key='csrf_token',
            value=csrf_token,
            httponly=False,
            secure=_secure,
            samesite=_samesite,
            path='/',
            max_age=1800
        )

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
        except Exception:
            pass
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
        except Exception:
            pass
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
        except Exception:
            pass

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
        except Exception:
            pass
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
        except Exception:
            pass
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

        _secure = os.getenv('HTTPS_ENABLED', 'false').lower() == 'true' or os.getenv('HTTPS_ONLY', 'false').lower() == 'true'
        _domain = os.getenv('COOKIE_DOMAIN', None)
        _samesite = (os.getenv('COOKIE_SAMESITE', 'Strict') or 'Strict').strip().lower()
        if _samesite not in ('strict', 'lax', 'none'):
            _samesite = 'strict'
        host = request.url.hostname or (request.client.host if request.client else None)
        safe_domain = _domain if (_domain and host and (host == _domain or host.endswith(_domain))) else None

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
