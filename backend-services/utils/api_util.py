from utils.async_db import db_find_list, db_find_one
from utils.database_async import api_collection, endpoint_collection
from utils.doorman_cache_util import doorman_cache


async def get_api(api_key: str | None, api_name_version: str) -> dict | None:
    """Get API document by key or name/version.

    Args:
        api_key: API key for cache lookup (optional)
        api_name_version: API path like '/myapi/v1'

    Returns:
        Optional[Dict]: API document or None if not found
    """
    # Prefer id-based cache when available; fall back to name/version mapping
    api = doorman_cache.get_cache('api_cache', api_key) if api_key else None
    if not api:
        api_name, api_version = api_name_version.lstrip('/').split('/')
        api = await db_find_one(api_collection, {'api_name': api_name, 'api_version': api_version})
        if not api:
            return None
        api.pop('_id', None)
        # Populate caches consistently: id and name/version
        api_id = api.get('api_id')
        if api_id:
            doorman_cache.set_cache('api_cache', api_id, api)
            doorman_cache.set_cache('api_id_cache', api_name_version, api_id)
        # Also map by name/version for direct lookups
        doorman_cache.set_cache('api_cache', f'{api_name}/{api_version}', api)
    return api


async def get_api_endpoints(api_id: str) -> list | None:
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
        endpoints = []
        for endpoint in endpoints_list:
            # Use client_uri if available for routing matching
            uri = endpoint.get('client_uri') or endpoint.get('endpoint_uri')
            endpoints.append(f'{endpoint.get("endpoint_method")}{uri}')
        doorman_cache.set_cache('api_endpoint_cache', api_id, endpoints)
    return endpoints


async def get_endpoint(api: dict, method: str, routing_uri: str) -> dict | None:
    """Return the endpoint document for a given API, method, and URI.
    
    Args:
        api: API document
        method: HTTP method
        routing_uri: The URI requested by the client (matches client_uri or endpoint_uri)

    Uses the same cache key pattern as EndpointService to avoid duplicate queries.
    """
    api_name = api.get('api_name')
    api_version = api.get('api_version')
    cache_key = f'/{method}/{api_name}/{api_version}/{routing_uri}'.replace('//', '/')
    endpoint = doorman_cache.get_cache('endpoint_cache', cache_key)
    if endpoint:
        return endpoint
    
    # Search for either client_uri or endpoint_uri matching the request
    doc = await db_find_one(
        endpoint_collection,
        {
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_method': method,
            '$or': [
                {'client_uri': routing_uri},
                {'endpoint_uri': routing_uri}
            ]
        },
    )
    if not doc:
        return None
    doc.pop('_id', None)
    doorman_cache.set_cache('endpoint_cache', cache_key, doc)
    return doc
