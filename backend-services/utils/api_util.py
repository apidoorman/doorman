# External imports
from typing import Optional, Dict

# Internal imports
from utils.doorman_cache_util import doorman_cache
from utils.database import api_collection, endpoint_collection

async def get_api(api_key, api_name_version):
    api = doorman_cache.get_cache('api_cache', api_key) if api_key else None
    if not api:
        api_name, api_version = api_name_version.lstrip('/').split('/')
        api = api_collection.find_one({'api_name': api_name, 'api_version': api_version})
        if not api:
            return None
        api.pop('_id', None)
        doorman_cache.set_cache('api_cache', api_key, api)
        doorman_cache.set_cache('api_id_cache', api_name_version, api_key)
    return api

async def get_api_endpoints(api_id):
    endpoints = doorman_cache.get_cache('api_endpoint_cache', api_id)
    if not endpoints:
        endpoints_cursor = endpoint_collection.find({'api_id': api_id})
        endpoints_list = list(endpoints_cursor)
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
    doc = endpoint_collection.find_one({
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
