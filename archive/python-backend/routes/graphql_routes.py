"""
GraphQL Management Routes

Routes for schema introspection caching and type summaries.
"""
import logging
import time
import uuid
from fastapi import APIRouter, Request

from utils import api_util
from utils.auth_util import auth_required
from utils.constants import Roles
from utils.doorman_cache_util import doorman_cache
from utils.graphql_util import (
    fetch_introspection_schema,
    extract_types_from_schema,
    get_operation_type,
    has_subscription_support,
)
from utils.response_util import respond_rest
from utils.role_util import platform_role_required_bool

graphql_routes_router = APIRouter()
logger = logging.getLogger('doorman.gateway')

# Cache TTL for GraphQL schemas (1 hour)
SCHEMA_CACHE_TTL = 3600


"""
Get cached GraphQL schema for an API

Request:
{}
Response:
{}
"""


@graphql_routes_router.get('/platform/api/{api_name}/{api_version}/graphql/schema')
async def get_graphql_schema(api_name: str, api_version: str, request: Request):
    """
    Get cached GraphQL schema for an API.
    
    Returns cached schema if available, otherwise fetches via introspection.
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
        cache_key = f'graphql_schema:{api_path}'
        cached = doorman_cache.get_cache('graphql_schema_cache', cache_key)
        if cached:
            return respond_rest(
                None, None,
                {
                    'schema': cached,
                    'cached': True,
                    'operation_types': get_operation_type(cached),
                    'has_subscriptions': has_subscription_support(cached),
                },
                request_id, 200, start_time
            )
        
        # Fetch from upstream
        servers = api.get('api_servers', [])
        if not servers:
            return respond_rest('GQL001', 'No upstream servers configured', None, None, 404, start_time)
        
        schema_url = api.get('api_graphql_schema_url') or '/graphql'
        url = servers[0].rstrip('/') + '/' + schema_url.lstrip('/')
        
        schema = await fetch_introspection_schema(url)
        if not schema:
            return respond_rest('GQL002', 'Failed to fetch schema from upstream', None, None, 502, start_time)
        
        # Cache the schema
        doorman_cache.set_cache('graphql_schema_cache', cache_key, schema, ttl=SCHEMA_CACHE_TTL)
        
        return respond_rest(
            None, None,
            {
                'schema': schema,
                'cached': False,
                'operation_types': get_operation_type(schema),
                'has_subscriptions': has_subscription_support(schema),
            },
            request_id, 200, start_time
        )
        
    except Exception as e:
        logger.error(f'Error getting GraphQL schema: {e}', exc_info=True)
        return respond_rest('GQL999', str(e), None, None, 500, start_time)


"""
Force refresh GraphQL schema from upstream

Request:
{}
Response:
{}
"""


@graphql_routes_router.post('/platform/api/{api_name}/{api_version}/graphql/schema/refresh')
async def refresh_graphql_schema(api_name: str, api_version: str, request: Request):
    """
    Force refresh GraphQL schema from upstream.
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
        
        servers = api.get('api_servers', [])
        if not servers:
            return respond_rest('GQL001', 'No upstream servers configured', None, None, 404, start_time)
        
        schema_url = api.get('api_graphql_schema_url') or '/graphql'
        url = servers[0].rstrip('/') + '/' + schema_url.lstrip('/')
        
        schema = await fetch_introspection_schema(url)
        if not schema:
            return respond_rest('GQL002', 'Failed to fetch schema', None, None, 502, start_time)
        
        # Update cache
        cache_key = f'graphql_schema:{api_path}'
        doorman_cache.set_cache('graphql_schema_cache', cache_key, schema, ttl=SCHEMA_CACHE_TTL)
        
        types = extract_types_from_schema(schema)
        
        return respond_rest(
            None, None,
            {
                'message': 'Schema refreshed successfully',
                'types_count': len(types),
                'has_subscriptions': has_subscription_support(schema),
            },
            request_id, 200, start_time
        )
        
    except Exception as e:
        logger.error(f'Error refreshing GraphQL schema: {e}', exc_info=True)
        return respond_rest('GQL999', str(e), None, None, 500, start_time)


"""
Get schema types summary

Request:
{}
Response:
{}
"""


@graphql_routes_router.get('/platform/api/{api_name}/{api_version}/graphql/types')
async def get_graphql_types(api_name: str, api_version: str, request: Request):
    """
    Get summary of types from cached GraphQL schema.
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
        
        # Get from cache
        cache_key = f'graphql_schema:{api_path}'
        schema = doorman_cache.get_cache('graphql_schema_cache', cache_key)
        
        if not schema:
            return respond_rest('GQL003', 'Schema not cached. Call GET schema first.', None, None, 404, start_time)
        
        types = extract_types_from_schema(schema)
        
        return respond_rest(
            None, None,
            {
                'types': types,
                'types_count': len(types),
            },
            request_id, 200, start_time
        )
        
    except Exception as e:
        logger.error(f'Error getting GraphQL types: {e}', exc_info=True)
        return respond_rest('GQL999', str(e), None, None, 500, start_time)
