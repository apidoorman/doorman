"""
OpenAPI Auto-Discovery Routes

Routes for fetching, caching, and importing OpenAPI/Swagger specs from upstream servers.
"""

import logging
import time
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Request, HTTPException

from models.response_model import ResponseModel
from services.endpoint_service import EndpointService
from utils import api_util
from utils.auth_util import auth_required
from utils.constants import Roles
from utils.doorman_cache_util import doorman_cache
from utils.response_util import respond_rest
from utils.role_util import platform_role_required_bool

openapi_router = APIRouter()
logger = logging.getLogger('doorman.gateway')

# Cache TTL for OpenAPI specs (1 hour default)
OPENAPI_CACHE_TTL = 3600


async def _fetch_upstream_openapi(base_url: str, openapi_path: str) -> dict | None:
    """
    Fetch OpenAPI spec from upstream server.
    
    Args:
        base_url: Base URL of the upstream server
        openapi_path: Path to the OpenAPI spec (e.g., /openapi.json)
        
    Returns:
        Parsed OpenAPI spec or None if failed
    """
    try:
        url = base_url.rstrip('/') + '/' + openapi_path.lstrip('/')
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return response.json()
            logger.warning(f'Failed to fetch OpenAPI from {url}: {response.status_code}')
            return None
    except Exception as e:
        logger.error(f'Error fetching OpenAPI spec: {e}')
        return None


def _parse_openapi_endpoints(spec: dict) -> list[dict]:
    """
    Parse endpoints from OpenAPI spec.
    
    Args:
        spec: OpenAPI spec dictionary
        
    Returns:
        List of endpoint definitions
    """
    endpoints = []
    paths = spec.get('paths', {})
    
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
            
        for method, details in methods.items():
            method_upper = method.upper()
            if method_upper not in ('GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'):
                continue
                
            endpoint = {
                'endpoint_uri': path,
                'endpoint_method': method_upper,
                'endpoint_description': details.get('summary') or details.get('description', ''),
                'endpoint_tags': details.get('tags', []),
                'endpoint_parameters': [],
                'endpoint_request_body': None,
                'endpoint_responses': {},
            }
            
            # Parse parameters
            for param in details.get('parameters', []):
                endpoint['endpoint_parameters'].append({
                    'name': param.get('name'),
                    'in': param.get('in'),  # query, path, header
                    'required': param.get('required', False),
                    'type': param.get('schema', {}).get('type', 'string'),
                })
            
            # Parse request body (OpenAPI 3.x)
            if 'requestBody' in details:
                content = details['requestBody'].get('content', {})
                for media_type, media_details in content.items():
                    endpoint['endpoint_request_body'] = {
                        'content_type': media_type,
                        'schema': media_details.get('schema', {}),
                    }
                    break
            
            # Parse responses
            for status, resp_details in details.get('responses', {}).items():
                endpoint['endpoint_responses'][status] = {
                    'description': resp_details.get('description', ''),
                }
            
            endpoints.append(endpoint)
    
    return endpoints


"""
Get cached OpenAPI spec for an API

Request:
{}
Response:
{}
"""


@openapi_router.get('/platform/api/{api_name}/{api_version}/openapi')
async def get_openapi_spec(api_name: str, api_version: str, request: Request):
    """
    Get OpenAPI spec for an API.
    
    Returns cached spec if available, otherwise fetches from upstream.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    
    try:
        payload = await auth_required(request)
        if not payload:
            return respond_rest('AUTHN001', 'Not authenticated', None, None, 401, start_time)

        username = payload.get('sub')
        if not await platform_role_required_bool(username, Roles.MANAGE_APIS):
            return respond_rest('AUTHZ001', 'Not authorized', None, None, 403, start_time)
        
        api_path = f'{api_name}/{api_version}'
        api = await api_util.get_api(None, api_path)
        if not api:
            return respond_rest('API001', 'API not found', None, None, 404, start_time)
        
        # Check cache first
        cache_key = f'openapi:{api_path}'
        cached = doorman_cache.get_cache('openapi_cache', cache_key)
        if cached:
            return respond_rest(None, None, cached, request_id, 200, start_time)
        
        # Fetch from upstream if configured
        openapi_url = api.get('api_openapi_url')
        if not openapi_url:
            return respond_rest(
                'OPENAPI001', 
                'No OpenAPI URL configured for this API', 
                None, None, 404, start_time
            )
        
        servers = api.get('api_servers', [])
        if not servers:
            return respond_rest(
                'OPENAPI002', 
                'No upstream servers configured', 
                None, None, 404, start_time
            )
        
        # Try each server until one succeeds
        spec = None
        for server in servers:
            spec = await _fetch_upstream_openapi(server, openapi_url)
            if spec:
                break
        
        if not spec:
            return respond_rest(
                'OPENAPI003', 
                'Failed to fetch OpenAPI spec from upstream', 
                None, None, 502, start_time
            )
        
        # Cache the spec
        doorman_cache.set_cache('openapi_cache', cache_key, spec, ttl=OPENAPI_CACHE_TTL)
        
        return respond_rest(None, None, spec, request_id, 200, start_time)
        
    except Exception as e:
        logger.error(f'Error getting OpenAPI spec: {e}', exc_info=True)
        return respond_rest('OPENAPI999', str(e), None, None, 500, start_time)


"""
Force refresh OpenAPI spec from upstream

Request:
{}
Response:
{}
"""


@openapi_router.post('/platform/api/{api_name}/{api_version}/openapi/refresh')
async def refresh_openapi_spec(api_name: str, api_version: str, request: Request):
    """
    Force refresh OpenAPI spec from upstream.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    
    try:
        payload = await auth_required(request)
        if not payload:
            return respond_rest('AUTHN001', 'Not authenticated', None, None, 401, start_time)

        username = payload.get('sub')
        if not await platform_role_required_bool(username, Roles.MANAGE_APIS):
            return respond_rest('AUTHZ001', 'Not authorized', None, None, 403, start_time)
        
        api_path = f'{api_name}/{api_version}'
        api = await api_util.get_api(None, api_path)
        if not api:
            return respond_rest('API001', 'API not found', None, None, 404, start_time)
        
        openapi_url = api.get('api_openapi_url')
        if not openapi_url:
            return respond_rest(
                'OPENAPI001', 
                'No OpenAPI URL configured', 
                None, None, 404, start_time
            )
        
        servers = api.get('api_servers', [])
        if not servers:
            return respond_rest(
                'OPENAPI002', 
                'No upstream servers configured', 
                None, None, 404, start_time
            )
        
        # Fetch fresh spec
        spec = None
        for server in servers:
            spec = await _fetch_upstream_openapi(server, openapi_url)
            if spec:
                break
        
        if not spec:
            return respond_rest(
                'OPENAPI003', 
                'Failed to fetch OpenAPI spec', 
                None, None, 502, start_time
            )
        
        # Update cache
        cache_key = f'openapi:{api_path}'
        doorman_cache.set_cache('openapi_cache', cache_key, spec, ttl=OPENAPI_CACHE_TTL)
        
        return respond_rest(
            None, None, 
            {'message': 'OpenAPI spec refreshed successfully', 'endpoints_found': len(spec.get('paths', {}))},
            request_id, 200, start_time
        )
        
    except Exception as e:
        logger.error(f'Error refreshing OpenAPI spec: {e}', exc_info=True)
        return respond_rest('OPENAPI999', str(e), None, None, 500, start_time)


"""
Import endpoints from OpenAPI spec

Request:
{}
Response:
{}
"""


@openapi_router.post('/platform/api/{api_name}/{api_version}/openapi/import')
async def import_openapi_endpoints(api_name: str, api_version: str, request: Request):
    """
    Import endpoints from upstream OpenAPI spec.
    
    Creates endpoints in Doorman based on the OpenAPI spec.
    Existing endpoints are not modified.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    
    try:
        payload = await auth_required(request)
        if not payload:
            return respond_rest('AUTHN001', 'Not authenticated', None, None, 401, start_time)
        
        username = payload.get('sub')
        if not await platform_role_required_bool(username, Roles.MANAGE_ENDPOINTS):
            return respond_rest('AUTHZ001', 'Not authorized', None, None, 403, start_time)
        
        api_path = f'{api_name}/{api_version}'
        api = await api_util.get_api(None, api_path)
        if not api:
            return respond_rest('API001', 'API not found', None, None, 404, start_time)
        
        api_id = api.get('api_id')
        
        # Get spec from cache or fetch
        cache_key = f'openapi:{api_path}'
        spec = doorman_cache.get_cache('openapi_cache', cache_key)
        
        if not spec:
            openapi_url = api.get('api_openapi_url')
            if openapi_url:
                servers = api.get('api_servers', [])
                for server in servers:
                    spec = await _fetch_upstream_openapi(server, openapi_url)
                    if spec:
                        doorman_cache.set_cache('openapi_cache', cache_key, spec, ttl=OPENAPI_CACHE_TTL)
                        break
        
        if not spec:
            return respond_rest(
                'OPENAPI003', 
                'No OpenAPI spec available', 
                None, None, 404, start_time
            )
        
        # Parse endpoints
        parsed = _parse_openapi_endpoints(spec)
        
        # Get existing endpoints
        existing = await api_util.get_api_endpoints(api_id)
        existing_set = set(existing) if existing else set()
        
        # Import new endpoints
        endpoint_service = EndpointService()
        imported = 0
        skipped = 0
        
        for ep in parsed:
            composite = f"{ep['endpoint_method']}/{ep['endpoint_uri'].lstrip('/')}"
            if composite in existing_set:
                skipped += 1
                continue
            
            try:
                endpoint_data = {
                    'api_id': api_id,
                    'endpoint_uri': ep['endpoint_uri'],
                    'endpoint_method': ep['endpoint_method'],
                    'endpoint_description': ep['endpoint_description'][:127] if ep['endpoint_description'] else '',
                }
                await endpoint_service.create_endpoint(endpoint_data)
                imported += 1
            except Exception as ce:
                logger.warning(f'Failed to create endpoint {composite}: {ce}')
        
        return respond_rest(
            None, None,
            {
                'message': 'OpenAPI import completed',
                'endpoints_found': len(parsed),
                'endpoints_imported': imported,
                'endpoints_skipped': skipped,
            },
            request_id, 200, start_time
        )
        
    except Exception as e:
        logger.error(f'Error importing OpenAPI endpoints: {e}', exc_info=True)
        return respond_rest('OPENAPI999', str(e), None, None, 500, start_time)


"""
Parse endpoints from provided OpenAPI spec (does not import)

Request:
{}
Response:
{}
"""


@openapi_router.post('/platform/openapi/parse')
async def parse_openapi_spec(request: Request):
    """
    Parse an OpenAPI spec without importing.
    
    Useful for previewing what would be imported.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    
    try:
        payload = await auth_required(request)
        if not payload:
            return respond_rest('AUTHN001', 'Not authenticated', None, None, 401, start_time)

        username = payload.get('sub')
        if not await platform_role_required_bool(username, Roles.MANAGE_APIS):
            return respond_rest('AUTHZ001', 'Not authorized', None, None, 403, start_time)
        
        body = await request.json()
        if not isinstance(body, dict):
            return respond_rest('OPENAPI004', 'Invalid OpenAPI spec', None, None, 400, start_time)
        
        endpoints = _parse_openapi_endpoints(body)
        
        return respond_rest(
            None, None,
            {
                'title': body.get('info', {}).get('title', 'Unknown'),
                'version': body.get('info', {}).get('version', 'Unknown'),
                'endpoints_count': len(endpoints),
                'endpoints': endpoints,
            },
            request_id, 200, start_time
        )
        
    except Exception as e:
        logger.error(f'Error parsing OpenAPI spec: {e}', exc_info=True)
        return respond_rest('OPENAPI999', str(e), None, None, 500, start_time)
