# External imports
from typing import Optional, Dict

# Internal imports
from utils.doorman_cache_util import doorman_cache
from utils.database_async import api_collection, endpoint_collection
from utils.async_db import db_find_one, db_find_list

async def get_api(api_key: Optional[str], api_name_version: str) -> Optional[Dict]:
    """Get API document by key or name/version.

    Args:
        api_key: API key for cache lookup (optional)
        api_name_version: API path like '/myapi/v1'

    Returns:
        Optional[Dict]: API document or None if not found
    """
    api = doorman_cache.get_cache('api_cache', api_key) if api_key else None
    if not api:
        api_name, api_version = api_name_version.lstrip('/').split('/')
        api = await db_find_one(api_collection, {'api_name': api_name, 'api_version': api_version})
        if not api:
            return None
        api.pop('_id', None)
        doorman_cache.set_cache('api_cache', api_key, api)
        doorman_cache.set_cache('api_id_cache', api_name_version, api_key)
    return api

async def get_api_endpoints(api_id: str) -> Optional[list]:
    """Get list of endpoints for an API.

    Args:
        api_id: API identifier

    Returns:
        Optional[list]: List of endpoint strings (METHOD + URI) or None
    """
    endpoints = doorman_cache.get_cache('api_endpoint_cache', api_id)
    if not endpoints:
        endpoints_list = await db_find_list(endpoint_collection, {'api_id': api_id})
        if not endpoints_list:
            return None
        endpoints = [
            f"{endpoint.get('endpoint_method')}{endpoint.get('endpoint_uri')}"
            for endpoint in endpoints_list
        ]
        doorman_cache.set_cache('api_endpoint_cache', api_id, endpoints)
    return endpoints

async def get_endpoint(api: Dict, method: str, endpoint_uri: str) -> Optional[Dict]:
    """Return the endpoint document for a given API, method, and uri.

    Uses the same cache key pattern as EndpointService to avoid duplicate queries.
    """
    api_name = api.get('api_name')
    api_version = api.get('api_version')
    cache_key = f'/{method}/{api_name}/{api_version}/{endpoint_uri}'.replace('//', '/')
    endpoint = doorman_cache.get_cache('endpoint_cache', cache_key)
    if endpoint:
        return endpoint
    doc = await db_find_one(endpoint_collection, {
        'api_name': api_name,
        'api_version': api_version,
        'endpoint_uri': endpoint_uri,
        'endpoint_method': method
    })
    if not doc:
        return None
    doc.pop('_id', None)
    doorman_cache.set_cache('endpoint_cache', cache_key, doc)
    return doc
