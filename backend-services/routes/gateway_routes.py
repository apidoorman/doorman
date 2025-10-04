"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

# External imports
from fastapi import APIRouter, HTTPException, Request, Depends
import uuid
import time
import logging
import json
import re
from datetime import datetime

# Internal imports
from models.response_model import ResponseModel
from utils import api_util
from utils.doorman_cache_util import doorman_cache
from utils.limit_throttle_util import limit_and_throttle
from utils.bandwidth_util import enforce_pre_request_limit
from utils.auth_util import auth_required
from utils.group_util import group_required
from utils.response_util import process_response
from utils.role_util import platform_role_required_bool
from utils.subscription_util import subscription_required
from utils.health_check_util import check_mongodb, check_redis, get_memory_usage, get_active_connections, get_uptime
from services.gateway_service import GatewayService
from utils.validation_util import validation_util
from utils.audit_util import audit
from utils.ip_policy_util import enforce_api_ip_policy

gateway_router = APIRouter()

logger = logging.getLogger('doorman.gateway')

"""
Endpoint

Request:
{}
Response:
{}
"""

@gateway_router.api_route('/status', methods=['GET'],
    description='Check if the gateway is online and healthy',
    response_model=ResponseModel)

async def status():
    """Check if the gateway is online and healthy"""
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        mongodb_status = await check_mongodb()
        redis_status = await check_redis()
        memory_usage = get_memory_usage()
        active_connections = get_active_connections()
        uptime = get_uptime()
        return ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            response={
                'status': 'online',
                'mongodb': mongodb_status,
                'redis': redis_status,
                'memory_usage': memory_usage,
                'active_connections': active_connections,
                'uptime': uptime
            }
        ).dict()
    except Exception as e:
        logger.error(f'{request_id} | Status check failed: {str(e)}')
        return ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='GTW006',
            error_message='Internal server error'
        ).dict()
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Status check time {end_time - start_time}ms')

"""
Clear all caches

Request:
{}
Response:
{}
"""

"""
Clear all caches

Request:
{}
Response:
{}
"""

@gateway_router.api_route('/caches', methods=['DELETE'],
    description='Clear all caches',
    response_model=ResponseModel,
    dependencies=[
        Depends(auth_required)
    ],
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {
                    'example': {
                        'message': 'All caches cleared'
                    }
                }
            }
        }
    }
)

async def clear_all_caches(request: Request):
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        if not await platform_role_required_bool(username, 'manage_gateway'):
            return process_response(ResponseModel(
                status_code=403,
                error_code='GTW008',
                error_message='You do not have permission to clear caches'
            ).dict(), 'rest')
        doorman_cache.clear_all_caches()
        try:
            from utils.limit_throttle_util import reset_counters as _reset_rate
            _reset_rate()
        except Exception:
            pass
        audit(request, actor=username, action='gateway.clear_caches', target='all', status='success', details=None)
        return process_response(ResponseModel(
            status_code=200,
            message='All caches cleared'
            ).dict(), 'rest')
    except Exception as e:
        return process_response(ResponseModel(
            status_code=500,
            error_code='GTW999',
            error_message='An unexpected error occurred'
            ).dict(), 'rest')

"""
Endpoint

Request:
{}
Response:
{}
"""

"""
REST gateway endpoint

Request:
{}
Response:
{}
"""

@gateway_router.api_route('/rest/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'],
    description='REST gateway endpoint',
    response_model=ResponseModel,
    include_in_schema=False)
async def gateway(request: Request, path: str):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:

        parts = [p for p in (path or '').split('/') if p]
        api_public = False
        api_auth_required = True
        resolved_api = None
        if len(parts) >= 2 and parts[1].startswith('v') and parts[1][1:].isdigit():
            api_key = doorman_cache.get_cache('api_id_cache', f'/{parts[0]}/{parts[1]}')
            resolved_api = await api_util.get_api(api_key, f'/{parts[0]}/{parts[1]}')
            if resolved_api:
                try:
                    enforce_api_ip_policy(request, resolved_api)
                except HTTPException as e:
                    return process_response(ResponseModel(status_code=e.status_code, error_code=e.detail, error_message='IP restricted').dict(), 'rest')
                endpoint_uri = '/' + '/'.join(parts[2:]) if len(parts) > 2 else '/'
                try:
                    endpoints = await api_util.get_api_endpoints(resolved_api.get('api_id'))
                    import re as _re
                    regex_pattern = _re.compile(r'\{[^/]+\}')
                    composite = request.method + endpoint_uri
                    if not any(_re.fullmatch(regex_pattern.sub(r'([^/]+)', ep), composite) for ep in (endpoints or [])):
                        return process_response(ResponseModel(
                            status_code=404,
                            response_headers={'request_id': request_id},
                            error_code='GTW003',
                            error_message='Endpoint does not exist for the requested API'
                        ).dict(), 'rest')
                except Exception:
                    pass
            api_public = bool(resolved_api.get('api_public')) if resolved_api else False
            api_auth_required = bool(resolved_api.get('api_auth_required')) if resolved_api and resolved_api.get('api_auth_required') is not None else True
        username = None
        if not api_public:
            if api_auth_required:
                await subscription_required(request)
                await group_required(request)
                await limit_and_throttle(request)
                payload = await auth_required(request)
                username = payload.get('sub')
                await enforce_pre_request_limit(request, username)
            else:

                pass
        logger.info(f"{request_id} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S:%f')[:-3]}ms")
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        return process_response(await GatewayService.rest_gateway(username, request, request_id, start_time, path), 'rest')
    except HTTPException as e:
        return process_response(ResponseModel(
            status_code=e.status_code,
            response_headers={
                'request_id': request_id
            },
            error_code=e.detail,
            error_message=e.detail
        ).dict(), 'rest')
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                'request_id': request_id
            },
            error_code='GTW999',
            error_message='An unexpected error occurred'
            ).dict(), 'rest')
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')

# Per-method wrappers with unique operation IDs for OpenAPI
@gateway_router.get('/rest/{path:path}', description='REST gateway endpoint (GET)', response_model=ResponseModel, operation_id='rest_get')
async def rest_get(request: Request, path: str):
    return await gateway(request, path)

@gateway_router.post('/rest/{path:path}', description='REST gateway endpoint (POST)', response_model=ResponseModel, operation_id='rest_post')
async def rest_post(request: Request, path: str):
    return await gateway(request, path)

@gateway_router.put('/rest/{path:path}', description='REST gateway endpoint (PUT)', response_model=ResponseModel, operation_id='rest_put')
async def rest_put(request: Request, path: str):
    return await gateway(request, path)

@gateway_router.patch('/rest/{path:path}', description='REST gateway endpoint (PATCH)', response_model=ResponseModel, operation_id='rest_patch')
async def rest_patch(request: Request, path: str):
    return await gateway(request, path)

@gateway_router.delete('/rest/{path:path}', description='REST gateway endpoint (DELETE)', response_model=ResponseModel, operation_id='rest_delete')
async def rest_delete(request: Request, path: str):
    return await gateway(request, path)

"""
Endpoint

Request:
{}
Response:
{}
"""

"""
REST gateway CORS preflight

Request:
{}
Response:
{}
"""

@gateway_router.api_route('/rest/{path:path}', methods=['OPTIONS'],
    description='REST gateway CORS preflight', include_in_schema=False)

async def rest_preflight(request: Request, path: str):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:

        from utils import api_util as _api_util
        from utils.doorman_cache_util import doorman_cache as _cache
        parts = [p for p in (path or '').split('/') if p]
        name_ver = ''
        if len(parts) >= 2 and parts[1].startswith('v') and parts[1][1:].isdigit():
            name_ver = f'/{parts[0]}/{parts[1]}'
        api_key = _cache.get_cache('api_id_cache', name_ver)
        api = await _api_util.get_api(api_key, name_ver)
        if not api:
            from fastapi.responses import Response as StarletteResponse
            return StarletteResponse(status_code=204, headers={'request_id': request_id})
        origin = request.headers.get('origin') or request.headers.get('Origin')
        req_method = request.headers.get('access-control-request-method') or request.headers.get('Access-Control-Request-Method')
        req_headers = request.headers.get('access-control-request-headers') or request.headers.get('Access-Control-Request-Headers')
        ok, headers = GatewayService._compute_api_cors_headers(api, origin, req_method, req_headers)
        headers = {**(headers or {}), 'request_id': request_id}
        from fastapi.responses import Response as StarletteResponse
        return StarletteResponse(status_code=204, headers=headers)
    except Exception:
        from fastapi.responses import Response as StarletteResponse
        return StarletteResponse(status_code=204, headers={'request_id': request_id})
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

"""
SOAP gateway endpoint

Request:
{}
Response:
{}
"""

@gateway_router.api_route('/soap/{path:path}', methods=['POST'],
    description='SOAP gateway endpoint',
    response_model=ResponseModel)

async def soap_gateway(request: Request, path: str):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        parts = [p for p in (path or '').split('/') if p]
        api_public = False
        api_auth_required = True
        if len(parts) >= 2 and parts[1].startswith('v') and parts[1][1:].isdigit():
            api_key = doorman_cache.get_cache('api_id_cache', f'/{parts[0]}/{parts[1]}')
            api = await api_util.get_api(api_key, f'/{parts[0]}/{parts[1]}')
            api_public = bool(api.get('api_public')) if api else False
            api_auth_required = bool(api.get('api_auth_required')) if api and api.get('api_auth_required') is not None else True
            if api:
                try:
                    enforce_api_ip_policy(request, api)
                except HTTPException as e:
                    return process_response(ResponseModel(status_code=e.status_code, error_code=e.detail, error_message='IP restricted').dict(), 'soap')
        username = None
        if not api_public:
            if api_auth_required:
                await subscription_required(request)
                await group_required(request)
                await limit_and_throttle(request)
                payload = await auth_required(request)
                username = payload.get('sub')
                await enforce_pre_request_limit(request, username)
            else:
                pass
        logger.info(f"{request_id} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S:%f')[:-3]}ms")
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        return process_response(await GatewayService.soap_gateway(username, request, request_id, start_time, path), 'soap')
    except HTTPException as e:
        return process_response(ResponseModel(
            status_code=e.status_code,
            response_headers={
                'request_id': request_id
            },
            error_code=e.detail,
            error_message=e.detail
        ).dict(), 'rest')
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                'request_id': request_id
            },
            error_code='GTW999',
            error_message='An unexpected error occurred'
            ).dict(), 'soap')
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

"""
SOAP gateway CORS preflight

Request:
{}
Response:
{}
"""

@gateway_router.api_route('/soap/{path:path}', methods=['OPTIONS'],
    description='SOAP gateway CORS preflight', include_in_schema=False)

async def soap_preflight(request: Request, path: str):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        from utils import api_util as _api_util
        from utils.doorman_cache_util import doorman_cache as _cache
        parts = [p for p in (path or '').split('/') if p]
        name_ver = ''
        if len(parts) >= 2 and parts[1].startswith('v') and parts[1][1:].isdigit():
            name_ver = f'/{parts[0]}/{parts[1]}'
        api_key = _cache.get_cache('api_id_cache', name_ver)
        api = await _api_util.get_api(api_key, name_ver)
        if not api:
            from fastapi.responses import Response as StarletteResponse
            return StarletteResponse(status_code=204, headers={'request_id': request_id})
        origin = request.headers.get('origin') or request.headers.get('Origin')
        req_method = request.headers.get('access-control-request-method') or request.headers.get('Access-Control-Request-Method')
        req_headers = request.headers.get('access-control-request-headers') or request.headers.get('Access-Control-Request-Headers')
        ok, headers = GatewayService._compute_api_cors_headers(api, origin, req_method, req_headers)
        headers = {**(headers or {}), 'request_id': request_id}
        from fastapi.responses import Response as StarletteResponse
        return StarletteResponse(status_code=204, headers=headers)
    except Exception:
        from fastapi.responses import Response as StarletteResponse
        return StarletteResponse(status_code=204, headers={'request_id': request_id})
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

"""
GraphQL gateway endpoint

Request:
{}
Response:
{}
"""

@gateway_router.api_route('/graphql/{path:path}', methods=['POST'],
    description='GraphQL gateway endpoint',
    response_model=ResponseModel)

async def graphql_gateway(request: Request, path: str):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        if not request.headers.get('X-API-Version'):
            raise HTTPException(status_code=400, detail='X-API-Version header is required')

        api_name = re.sub(r'^.*/', '',request.url.path)
        api_key = doorman_cache.get_cache('api_id_cache', api_name + '/' + request.headers.get('X-API-Version', 'v0'))
        api = await api_util.get_api(api_key, api_name + '/' + request.headers.get('X-API-Version', 'v0'))
        if api:
            try:
                enforce_api_ip_policy(request, api)
            except HTTPException as e:
                return process_response(ResponseModel(status_code=e.status_code, error_code=e.detail, error_message='IP restricted').dict(), 'graphql')
        api_public = bool(api.get('api_public')) if api else False
        api_auth_required = bool(api.get('api_auth_required')) if api and api.get('api_auth_required') is not None else True
        username = None
        if not api_public:
            if api_auth_required:
                await subscription_required(request)
                await group_required(request)
                await limit_and_throttle(request)
                payload = await auth_required(request)
                username = payload.get('sub')
                await enforce_pre_request_limit(request, username)
            else:
                pass
        logger.info(f"{request_id} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S:%f')[:-3]}ms")
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        api_name = re.sub(r'^.*/', '',request.url.path)
        api_key = doorman_cache.get_cache('api_id_cache', api_name + '/' + request.headers.get('X-API-Version', 'v0'))
        api = await api_util.get_api(api_key, api_name + '/' + request.headers.get('X-API-Version', 'v0'))
        if api and api.get('validation_enabled'):
            body = await request.json()
            query = body.get('query')
            variables = body.get('variables', {})
            try:
                await validation_util.validate_graphql_request(api.get('api_id'), query, variables)
            except Exception as e:
                return process_response(ResponseModel(
                    status_code=400,
                    response_headers={'request_id': request_id},
                    error_code='GTW011',
                    error_message=str(e)
                ).dict(), 'graphql')
        return process_response(await GatewayService.graphql_gateway(username, request, request_id, start_time, path), 'graphql')
    except HTTPException as e:
        return process_response(ResponseModel(
            status_code=e.status_code,
            response_headers={
                'request_id': request_id
            },
            error_code=e.detail,
            error_message=e.detail
        ).dict(), 'rest')
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                'request_id': request_id
            },
            error_code='GTW999',
            error_message='An unexpected error occurred'
            ).dict(), 'graphql')
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

"""
GraphQL gateway CORS preflight

Request:
{}
Response:
{}
"""

@gateway_router.api_route('/graphql/{path:path}', methods=['OPTIONS'],
    description='GraphQL gateway CORS preflight', include_in_schema=False)

async def graphql_preflight(request: Request, path: str):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        from utils import api_util as _api_util
        from utils.doorman_cache_util import doorman_cache as _cache
        api_name = path.replace('graphql/', '')
        api_version = request.headers.get('X-API-Version', 'v1')
        api_path = f'/{api_name}/{api_version}'
        api_key = _cache.get_cache('api_id_cache', api_path)
        api = await _api_util.get_api(api_key, f'{api_name}/{api_version}')
        if not api:
            from fastapi.responses import Response as StarletteResponse
            return StarletteResponse(status_code=204, headers={'request_id': request_id})
        origin = request.headers.get('origin') or request.headers.get('Origin')
        req_method = request.headers.get('access-control-request-method') or request.headers.get('Access-Control-Request-Method')
        req_headers = request.headers.get('access-control-request-headers') or request.headers.get('Access-Control-Request-Headers')
        ok, headers = GatewayService._compute_api_cors_headers(api, origin, req_method, req_headers)
        headers = {**(headers or {}), 'request_id': request_id}
        from fastapi.responses import Response as StarletteResponse
        return StarletteResponse(status_code=204, headers=headers)
    except Exception:
        from fastapi.responses import Response as StarletteResponse
        return StarletteResponse(status_code=204, headers={'request_id': request_id})
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

"""
gRPC gateway endpoint

Request:
{}
Response:
{}
"""

@gateway_router.api_route('/grpc/{path:path}', methods=['POST'],
    description='gRPC gateway endpoint',
    response_model=ResponseModel)

async def grpc_gateway(request: Request, path: str):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        if not request.headers.get('X-API-Version'):
            raise HTTPException(status_code=400, detail='X-API-Version header is required')
        api_name = re.sub(r'^.*/', '', request.url.path)
        api_key = doorman_cache.get_cache('api_id_cache', api_name + '/' + request.headers.get('X-API-Version', 'v0'))
        api = await api_util.get_api(api_key, api_name + '/' + request.headers.get('X-API-Version', 'v0'))
        if api:
            try:
                enforce_api_ip_policy(request, api)
            except HTTPException as e:
                return process_response(ResponseModel(status_code=e.status_code, error_code=e.detail, error_message='IP restricted').dict(), 'grpc')
        api_public = bool(api.get('api_public')) if api else False
        api_auth_required = bool(api.get('api_auth_required')) if api and api.get('api_auth_required') is not None else True
        username = None
        if not api_public:
            if api_auth_required:
                await subscription_required(request)
                await group_required(request)
                await limit_and_throttle(request)
                payload = await auth_required(request)
                username = payload.get('sub')
                await enforce_pre_request_limit(request, username)
            else:
                pass
        logger.info(f"{request_id} | Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S:%f')[:-3]}ms")
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        api_name = re.sub(r'^.*/', '', request.url.path)
        api_key = doorman_cache.get_cache('api_id_cache', api_name + '/' + request.headers.get('X-API-Version', 'v0'))
        api = await api_util.get_api(api_key, api_name + '/' + request.headers.get('X-API-Version', 'v0'))
        if api and api.get('validation_enabled'):
            body = await request.json()
            request_data = json.loads(body.get('data', '{}'))
            try:
                await validation_util.validate_grpc_request(api.get('api_id'), request_data)
            except Exception as e:
                return process_response(ResponseModel(
                    status_code=400,
                    response_headers={'request_id': request_id},
                    error_code='GTW011',
                    error_message=str(e)
                ).dict(), 'grpc')
        return process_response(await GatewayService.grpc_gateway(username, request, request_id, start_time, path), 'grpc')
    except HTTPException as e:
        return process_response(ResponseModel(
            status_code=e.status_code,
            response_headers={
                'request_id': request_id
            },
            error_code=e.detail,
            error_message=e.detail
        ).dict(), 'rest')
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                'request_id': request_id
            },
            error_code='GTW999',
            error_message='An unexpected error occurred'
            ).dict(), 'grpc')
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')
