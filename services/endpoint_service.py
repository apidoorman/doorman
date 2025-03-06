"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from utils.database import db
from utils.cache import cache_manager
from services.cache import pygate_cache
import uuid

class EndpointService:
    endpoint_collection = db.endpoints

    @staticmethod
    async def create_endpoint(data):
        """
        Create an endpoint for an API.
        """
        if pygate_cache.get_cache('endpoint_cache', f"{data.get('api_name')}/{data.get('api_version')}/{data.get('endpoint_uri')}") or EndpointService.endpoint_collection.find_one({
            'api_name': data.get('api_name'),
            'api_version': data.get('api_version'),
            'endpoint_uri': data.get('endpoint_uri')
        }):
            raise ValueError("Endpoint already exists for the requested API")
        
        data['endpoint_id'] = str(uuid.uuid4())
        endpoint = EndpointService.endpoint_collection.insert_one(data)
        pygate_cache.set_cache('endpoint_cache', f"{data.get('api_name')}/{data.get('api_version')}/{data.get('endpoint_uri')}", endpoint)

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_endpoint(api_name, api_version, endpoint_uri):
        """
        Get an endpoint by API name, version and URI.
        """
        endpoint = pygate_cache.get_cache('endpoint_cache', f"{api_name}/{api_version}/{endpoint_uri}") or EndpointService.endpoint_collection.find_one({
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_uri': endpoint_uri
        })
        if not endpoint:
            raise ValueError("Endpoint does not exist")
        if '_id' in endpoint:
            del endpoint['_id']
        return endpoint