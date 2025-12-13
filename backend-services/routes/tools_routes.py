"""
Tools and diagnostics routes (e.g., CORS checker).
"""

import logging
import os
import time
import uuid
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from models.response_model import ResponseModel
from utils import chaos_util
from utils.auth_util import auth_required
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool

tools_router = APIRouter()
logger = logging.getLogger('doorman.gateway')


class CorsCheckRequest(BaseModel):
    origin: str = Field(..., description='Origin to evaluate, e.g., https://localhost:3000')
    method: str = Field(..., description='Intended request method, e.g., GET/POST/PUT')
    request_headers: list[str] | None = Field(
        default=None, description='Requested headers from Access-Control-Request-Headers'
    )
    with_credentials: bool | None = Field(
        default=None,
        description='Whether credentials will be sent; defaults to ALLOW_CREDENTIALS env if omitted',
    )


def _compute_cors_config() -> dict[str, Any]:
    origins_env = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000')

    if not (origins_env or '').strip():
        origins_env = 'http://localhost:3000'
    origins = [o.strip() for o in origins_env.split(',') if o.strip()]
    credentials = os.getenv('ALLOW_CREDENTIALS', 'true').lower() == 'true'
    methods_env = os.getenv('ALLOW_METHODS', 'GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD')
    if not (methods_env or '').strip():
        methods_env = 'GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD'
    methods = [m.strip().upper() for m in methods_env.split(',') if m.strip()]
    if any(m == '*' for m in methods):
        methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
    if 'OPTIONS' not in methods:
        methods.append('OPTIONS')
    headers_env = os.getenv('ALLOW_HEADERS', '*')
    if not (headers_env or '').strip():
        headers_env = '*'
    raw_headers = [h.strip() for h in headers_env.split(',') if h.strip()]

    if any(h == '*' for h in raw_headers):
        headers = ['Accept', 'Content-Type', 'X-CSRF-Token', 'Authorization']
    else:
        headers = raw_headers

    cors_strict = os.getenv('CORS_STRICT', 'false').lower() == 'true'
    if credentials and any(o == '*' for o in origins):
        safe_origins = ['http://localhost', 'http://localhost:3000']
    elif cors_strict:
        safe = [o for o in origins if o != '*']
        safe_origins = safe if safe else ['http://localhost', 'http://localhost:3000']
    else:
        safe_origins = origins
    return {
        'origins': origins,
        'safe_origins': safe_origins,
        'credentials': credentials,
        'methods': methods,
        'headers': headers,
        'cors_strict': cors_strict,
    }


"""
Endpoint

Request:
{}
Response:
{}
"""


@tools_router.post(
    '/cors/check',
    description='Simulate CORS preflight/actual decisions against current gateway config',
    response_model=ResponseModel,
)
async def cors_check(request: Request, body: CorsCheckRequest):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, 'manage_security'):
            return process_response(
                ResponseModel(
                    status_code=403,
                    response_headers={'request_id': request_id},
                    error_code='TLS001',
                    error_message='You do not have permission to use tools',
                ).dict(),
                'rest',
            )

        cfg = _compute_cors_config()
        origin = (body.origin or '').strip()
        method = (body.method or '').strip().upper()
        requested_headers = [h.strip() for h in (body.request_headers or []) if h.strip()]
        with_credentials = (
            cfg['credentials'] if body.with_credentials is None else bool(body.with_credentials)
        )

        origin_allowed = origin in cfg['safe_origins'] or (
            not cfg['cors_strict'] and '*' in cfg['origins']
        )
        method_allowed = method in cfg['methods']

        allowed_headers_lower = {h.lower() for h in cfg['headers']}
        requested_lower = [h.lower() for h in requested_headers]
        headers_not_allowed = [
            h for h in requested_headers if h.lower() not in allowed_headers_lower
        ]
        headers_allowed = len(headers_not_allowed) == 0

        preflight_allowed = origin_allowed and method_allowed and headers_allowed

        preflight_headers = {
            'Access-Control-Allow-Origin': origin if origin_allowed else None,
            'Access-Control-Allow-Methods': ', '.join(cfg['methods']),
            'Access-Control-Allow-Headers': ', '.join(cfg['headers'])
            if requested_headers
            else ', '.join(cfg['headers']),
            'Access-Control-Allow-Credentials': 'true'
            if with_credentials and cfg['credentials']
            else 'false',
            'Vary': 'Origin',
        }

        actual_allowed = origin_allowed
        actual_headers = {
            'Access-Control-Allow-Origin': origin if origin_allowed else None,
            'Access-Control-Allow-Credentials': 'true'
            if with_credentials and cfg['credentials']
            else 'false',
            'Vary': 'Origin',
        }

        notes: list[str] = []
        if cfg['credentials'] and ('*' in cfg['origins']) and not cfg['cors_strict']:
            notes.append(
                'Wildcard origins with credentials can be rejected by browsers; prefer explicit origins or set CORS_STRICT=true.'
            )
        if any(h == '*' for h in os.getenv('ALLOW_HEADERS', '*').split(',')):
            notes.append(
                "ALLOW_HEADERS='*' replaced with a conservative default set to satisfy credentialed requests."
            )
        if not origin_allowed:
            notes.append('Origin is not allowed based on current configuration.')
        if not method_allowed:
            notes.append('Requested method is not in ALLOW_METHODS.')
        if not headers_allowed and headers_not_allowed:
            notes.append(
                f'Some requested headers are not allowed: {", ".join(headers_not_allowed)}'
            )

        response_payload = {
            'config': {
                'allowed_origins': cfg['origins'],
                'effective_allowed_origins': cfg['safe_origins'],
                'allow_credentials': cfg['credentials'],
                'allow_methods': cfg['methods'],
                'allow_headers': cfg['headers'],
                'cors_strict': cfg['cors_strict'],
            },
            'input': {
                'origin': origin,
                'method': method,
                'request_headers': requested_headers,
                'request_headers_normalized': requested_lower,
                'with_credentials': with_credentials,
            },
            'preflight': {
                'allowed': preflight_allowed,
                'allow_origin': origin_allowed,
                'method_allowed': method_allowed,
                'headers_allowed': headers_allowed,
                'not_allowed_headers': headers_not_allowed,
                'response_headers': preflight_headers,
            },
            'actual': {'allowed': actual_allowed, 'response_headers': actual_headers},
            'notes': notes,
        }

        return process_response(
            ResponseModel(
                status_code=200,
                response_headers={'request_id': request_id},
                response=response_payload,
            ).dict(),
            'rest',
        )

    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='TLS999',
                error_message='An unexpected error occurred',
            ).dict(),
            'rest',
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')


"""
gRPC environment check

Request:
{}
Response:
{}
"""


@tools_router.get(
    '/grpc/check',
    description='Report gRPC/grpc-tools availability and reflection flag',
    response_model=ResponseModel,
)
async def grpc_env_check(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, 'manage_security'):
            return process_response(
                ResponseModel(
                    status_code=403,
                    response_headers={'request_id': request_id},
                    error_code='TLS001',
                    error_message='You do not have permission to use tools',
                ).dict(),
                'rest',
            )
        available = {'grpc': False, 'grpc_tools_protoc': False}
        details: dict[str, str] = {}
        import importlib

        try:
            importlib.import_module('grpc')
            available['grpc'] = True
        except Exception as e:
            details['grpc_error'] = f'{type(e).__name__}: {str(e)}'
        try:
            importlib.import_module('grpc_tools.protoc')
            available['grpc_tools_protoc'] = True
        except Exception as e:
            details['grpc_tools_protoc_error'] = f'{type(e).__name__}: {str(e)}'

        reflection_enabled = (
            os.getenv('DOORMAN_ENABLE_GRPC_REFLECTION', '').lower() in ('1', 'true', 'yes', 'on')
        )
        notes = []
        if not available['grpc']:
            notes.append('grpcio not available. Install with: pip install grpcio')
        if not available['grpc_tools_protoc']:
            notes.append('grpcio-tools not available. Install with: pip install grpcio-tools')
        if not reflection_enabled:
            notes.append('Reflection is disabled by default. Enable with DOORMAN_ENABLE_GRPC_REFLECTION=true')

        payload = {
            'available': available,
            'reflection_enabled': reflection_enabled,
            'notes': notes,
            'details': details,
        }
        return process_response(
            ResponseModel(
                status_code=200,
                response_headers={'request_id': request_id},
                response=payload,
            ).dict(),
            'rest',
        )
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='TLS999',
                error_message='An unexpected error occurred',
            ).dict(),
            'rest',
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')


class ChaosToggleRequest(BaseModel):
    backend: str = Field(..., description='Backend to toggle (redis|mongo)')
    enabled: bool = Field(..., description='Enable or disable outage simulation')
    duration_ms: int | None = Field(
        default=None, description='Optional duration for outage before auto-disable'
    )


@tools_router.post(
    '/chaos/toggle',
    description='Toggle simulated backend outages (redis|mongo)',
    response_model=ResponseModel,
)
async def chaos_toggle(request: Request, body: ChaosToggleRequest):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        if not await platform_role_required_bool(username, 'manage_gateway'):
            return process_response(
                ResponseModel(
                    status_code=403,
                    response_headers={'request_id': request_id},
                    error_code='TLS001',
                    error_message='You do not have permission to use tools',
                ).dict(),
                'rest',
            )
        backend = (body.backend or '').strip().lower()
        if backend not in ('redis', 'mongo'):
            return process_response(
                ResponseModel(
                    status_code=400,
                    response_headers={'request_id': request_id},
                    error_code='TLS002',
                    error_message='backend must be redis or mongo',
                ).dict(),
                'rest',
            )
        if body.duration_ms and int(body.duration_ms) > 0:
            chaos_util.enable_for(backend, int(body.duration_ms))
        else:
            chaos_util.enable(backend, bool(body.enabled))
        return process_response(
            ResponseModel(
                status_code=200,
                response_headers={'request_id': request_id},
                response={'backend': backend, 'enabled': chaos_util.should_fail(backend)},
            ).dict(),
            'rest',
        )
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='TLS999',
                error_message='An unexpected error occurred',
            ).dict(),
            'rest',
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')


@tools_router.get(
    '/chaos/stats', description='Get chaos simulation stats', response_model=ResponseModel
)
async def chaos_stats(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        if not await platform_role_required_bool(username, 'manage_gateway'):
            return process_response(
                ResponseModel(
                    status_code=403,
                    response_headers={'request_id': request_id},
                    error_code='TLS001',
                    error_message='You do not have permission to use tools',
                ).dict(),
                'rest',
            )
        return process_response(
            ResponseModel(
                status_code=200,
                response_headers={'request_id': request_id},
                response=chaos_util.stats(),
            ).dict(),
            'rest',
        )
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='TLS999',
                error_message='An unexpected error occurred',
            ).dict(),
            'rest',
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')
