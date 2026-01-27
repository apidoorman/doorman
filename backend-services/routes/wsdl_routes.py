"""
WSDL Management Routes

Routes for fetching, caching, and importing WSDL specs from upstream SOAP services.
"""

import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Request

from services.endpoint_service import EndpointService
from utils import api_util
from utils.auth_util import auth_required
from utils.doorman_cache_util import doorman_cache
from utils.response_util import respond_rest
from utils.role_util import platform_role_required_bool
from utils.wsdl_util import fetch_wsdl, parse_wsdl, validate_wsdl_content

wsdl_router = APIRouter()
logger = logging.getLogger('doorman.gateway')

# Cache TTL for WSDL specs (1 hour default)
WSDL_CACHE_TTL = 3600


"""
Get cached WSDL for an API

Request:
{}
Response:
{}
"""


@wsdl_router.get('/platform/api/{api_name}/{api_version}/wsdl')
async def get_wsdl(api_name: str, api_version: str, request: Request):
    """
    Get WSDL for an API.
    
    Returns cached WSDL if available, otherwise fetches from upstream.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    
    try:
        payload = await auth_required(request)
        if not payload:
            return respond_rest('AUTHN001', 'Not authenticated', None, None, 401, start_time)
        
        if not await platform_role_required_bool(request, 'manage_api'):
            return respond_rest('AUTHZ001', 'Not authorized', None, None, 403, start_time)
        
        api_path = f'{api_name}/{api_version}'
        api = await api_util.get_api(None, api_path)
        if not api:
            return respond_rest('API001', 'API not found', None, None, 404, start_time)
        
        # Check cache first
        cache_key = f'wsdl:{api_path}'
        cached = doorman_cache.get_cache('wsdl_cache', cache_key)
        if cached:
            return respond_rest(None, None, {'wsdl': cached, 'cached': True}, request_id, 200, start_time)
        
        # Fetch from upstream if configured
        wsdl_url = api.get('api_wsdl_url')
        if not wsdl_url:
            return respond_rest(
                'WSDL001', 
                'No WSDL URL configured for this API', 
                None, None, 404, start_time
            )
        
        # If wsdl_url is a relative path, combine with server
        if wsdl_url.startswith('/'):
            servers = api.get('api_servers', [])
            if not servers:
                return respond_rest(
                    'WSDL002', 
                    'No upstream servers configured', 
                    None, None, 404, start_time
                )
            wsdl_url = servers[0].rstrip('/') + wsdl_url
        
        wsdl_content = await fetch_wsdl(wsdl_url)
        
        if not wsdl_content:
            return respond_rest(
                'WSDL003', 
                'Failed to fetch WSDL from upstream', 
                None, None, 502, start_time
            )
        
        # Validate
        is_valid, error = validate_wsdl_content(wsdl_content)
        if not is_valid:
            return respond_rest('WSDL004', f'Invalid WSDL: {error}', None, None, 400, start_time)
        
        # Cache the WSDL
        doorman_cache.set_cache('wsdl_cache', cache_key, wsdl_content, ttl=WSDL_CACHE_TTL)
        
        return respond_rest(None, None, {'wsdl': wsdl_content, 'cached': False}, request_id, 200, start_time)
        
    except Exception as e:
        logger.error(f'Error getting WSDL: {e}', exc_info=True)
        return respond_rest('WSDL999', str(e), None, None, 500, start_time)


"""
Force refresh WSDL from upstream

Request:
{}
Response:
{}
"""


@wsdl_router.post('/platform/api/{api_name}/{api_version}/wsdl/refresh')
async def refresh_wsdl(api_name: str, api_version: str, request: Request):
    """
    Force refresh WSDL from upstream.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    
    try:
        payload = await auth_required(request)
        if not payload:
            return respond_rest('AUTHN001', 'Not authenticated', None, None, 401, start_time)
        
        if not await platform_role_required_bool(request, 'manage_api'):
            return respond_rest('AUTHZ001', 'Not authorized', None, None, 403, start_time)
        
        api_path = f'{api_name}/{api_version}'
        api = await api_util.get_api(None, api_path)
        if not api:
            return respond_rest('API001', 'API not found', None, None, 404, start_time)
        
        wsdl_url = api.get('api_wsdl_url')
        if not wsdl_url:
            return respond_rest('WSDL001', 'No WSDL URL configured', None, None, 404, start_time)
        
        # Build full URL if relative
        if wsdl_url.startswith('/'):
            servers = api.get('api_servers', [])
            if servers:
                wsdl_url = servers[0].rstrip('/') + wsdl_url
        
        # Fetch fresh WSDL
        wsdl_content = await fetch_wsdl(wsdl_url)
        
        if not wsdl_content:
            return respond_rest('WSDL003', 'Failed to fetch WSDL', None, None, 502, start_time)
        
        # Validate
        is_valid, error = validate_wsdl_content(wsdl_content)
        if not is_valid:
            return respond_rest('WSDL004', f'Invalid WSDL: {error}', None, None, 400, start_time)
        
        # Parse to get operation count
        parsed = parse_wsdl(wsdl_content)
        
        # Update cache
        cache_key = f'wsdl:{api_path}'
        doorman_cache.set_cache('wsdl_cache', cache_key, wsdl_content, ttl=WSDL_CACHE_TTL)
        
        return respond_rest(
            None, None, 
            {
                'message': 'WSDL refreshed successfully',
                'service_name': parsed.get('service_name', ''),
                'operations_found': len(parsed.get('operations', [])),
            },
            request_id, 200, start_time
        )
        
    except Exception as e:
        logger.error(f'Error refreshing WSDL: {e}', exc_info=True)
        return respond_rest('WSDL999', str(e), None, None, 500, start_time)


"""
Import endpoints from WSDL

Request:
{}
Response:
{}
"""


@wsdl_router.post('/platform/api/{api_name}/{api_version}/wsdl/import')
async def import_wsdl_operations(api_name: str, api_version: str, request: Request):
    """
    Import operations from WSDL as endpoints.
    
    Creates endpoints in Doorman based on WSDL operations.
    Existing endpoints are not modified.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    
    try:
        payload = await auth_required(request)
        if not payload:
            return respond_rest('AUTHN001', 'Not authenticated', None, None, 401, start_time)
        
        if not await platform_role_required_bool(request, 'manage_endpoint'):
            return respond_rest('AUTHZ001', 'Not authorized', None, None, 403, start_time)
        
        api_path = f'{api_name}/{api_version}'
        api = await api_util.get_api(None, api_path)
        if not api:
            return respond_rest('API001', 'API not found', None, None, 404, start_time)
        
        api_id = api.get('api_id')
        
        # Get WSDL from cache or fetch
        cache_key = f'wsdl:{api_path}'
        wsdl_content = doorman_cache.get_cache('wsdl_cache', cache_key)
        
        if not wsdl_content:
            wsdl_url = api.get('api_wsdl_url')
            if wsdl_url:
                if wsdl_url.startswith('/'):
                    servers = api.get('api_servers', [])
                    if servers:
                        wsdl_url = servers[0].rstrip('/') + wsdl_url
                wsdl_content = await fetch_wsdl(wsdl_url)
                if wsdl_content:
                    doorman_cache.set_cache('wsdl_cache', cache_key, wsdl_content, ttl=WSDL_CACHE_TTL)
        
        if not wsdl_content:
            return respond_rest('WSDL003', 'No WSDL available', None, None, 404, start_time)
        
        # Parse WSDL
        parsed = parse_wsdl(wsdl_content)
        
        # Get existing endpoints
        existing = await api_util.get_api_endpoints(api_id)
        existing_set = set(existing) if existing else set()
        
        # Import new endpoints
        endpoint_service = EndpointService()
        imported = 0
        skipped = 0
        
        for ep in parsed.get('endpoints', []):
            composite = f"POST/{ep['uri'].lstrip('/')}"
            if composite in existing_set:
                skipped += 1
                continue
            
            try:
                endpoint_data = {
                    'api_id': api_id,
                    'endpoint_uri': ep['uri'],
                    'endpoint_method': 'POST',
                    'endpoint_description': ep.get('description', '')[:127],
                    'endpoint_soap_action': ep.get('soap_action', ''),
                }
                await endpoint_service.create_endpoint(endpoint_data)
                imported += 1
            except Exception as ce:
                logger.warning(f'Failed to create endpoint {composite}: {ce}')
        
        return respond_rest(
            None, None,
            {
                'message': 'WSDL import completed',
                'service_name': parsed.get('service_name', ''),
                'operations_found': len(parsed.get('operations', [])),
                'endpoints_imported': imported,
                'endpoints_skipped': skipped,
            },
            request_id, 200, start_time
        )
        
    except Exception as e:
        logger.error(f'Error importing WSDL: {e}', exc_info=True)
        return respond_rest('WSDL999', str(e), None, None, 500, start_time)


"""
Parse WSDL content without importing

Request:
{}
Response:
{}
"""


@wsdl_router.post('/platform/wsdl/parse')
async def parse_wsdl_content(request: Request):
    """
    Parse a WSDL document without importing.
    
    Useful for previewing what would be imported.
    Accepts raw XML in request body.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    
    try:
        payload = await auth_required(request)
        if not payload:
            return respond_rest('AUTHN001', 'Not authenticated', None, None, 401, start_time)
        
        if not await platform_role_required_bool(request, 'manage_api'):
            return respond_rest('AUTHZ001', 'Not authorized', None, None, 403, start_time)
        
        body = await request.body()
        wsdl_content = body.decode('utf-8')
        
        if not wsdl_content.strip():
            return respond_rest('WSDL004', 'Empty WSDL content', None, None, 400, start_time)
        
        # Validate
        is_valid, error = validate_wsdl_content(wsdl_content)
        if not is_valid:
            return respond_rest('WSDL004', f'Invalid WSDL: {error}', None, None, 400, start_time)
        
        # Parse
        parsed = parse_wsdl(wsdl_content)
        
        return respond_rest(
            None, None,
            {
                'service_name': parsed.get('service_name', ''),
                'target_namespace': parsed.get('target_namespace', ''),
                'operations': parsed.get('operations', []),
                'endpoints_count': len(parsed.get('endpoints', [])),
            },
            request_id, 200, start_time
        )
        
    except Exception as e:
        logger.error(f'Error parsing WSDL: {e}', exc_info=True)
        return respond_rest('WSDL999', str(e), None, None, 500, start_time)
