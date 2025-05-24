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