from utils.pygate_cache_util import pygate_cache
from utils.database import api_collection, endpoint_collection

async def get_api(api_key, api_name_version):
    api = pygate_cache.get_cache('api_cache', api_key) if api_key else None
    if not api:
        api = api_collection.find_one({'api_path': api_name_version})
        if not api:
            return None
        api.pop('_id', None)
        pygate_cache.set_cache('api_cache', api_key, api)
    return api

async def get_api_endpoints(api_id):
    endpoints = pygate_cache.get_cache('api_endpoint_cache', api_id)
    if not endpoints:
        endpoints_cursor = endpoint_collection.find({'api_id': api_id})
        endpoints_list = list(endpoints_cursor)
        if not endpoints_list:
            return None
        endpoints = [
            f"{endpoint.get('endpoint_method')}{endpoint.get('endpoint_uri')}"
            for endpoint in endpoints_list
        ]
        pygate_cache.set_cache('api_endpoint_cache', api_id, endpoints)
    return endpoints