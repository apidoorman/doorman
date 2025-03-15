"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from utils.database import db
from utils.cache import cache_manager
from services.cache import pygate_cache
from models.endpoint_model import EndpointModel

import uuid

class EndpointService:
    endpoint_collection = db.endpoints
    apis_collection = db.apis

    @staticmethod
    async def create_endpoint(data: EndpointModel):
        """
        Create an endpoint for an API.
        """
        cache_key = f"/{data.api_name}/{data.api_version}/{data.endpoint_uri}".replace("//", "/")

        if pygate_cache.get_cache('endpoint_cache', cache_key) or EndpointService.endpoint_collection.find_one({
            'api_name': data.api_name,
            'api_version': data.api_version,
            'endpoint_uri': data.endpoint_uri
        }):
            raise ValueError("Endpoint already exists for the requested API")

        data.api_id = pygate_cache.get_cache('api_id_cache', data.api_name + '/' + data.api_version)

        if not data.api_id:
            api = EndpointService.apis_collection.find_one({"api_name": data.api_name, "api_version": data.api_version})
            if not api:
                raise ValueError("API does not exist")
            data.api_id = api.get('api_id')
            pygate_cache.set_cache('api_id_cache', f"{data.api_name}/{data.api_version}", data.api_id)

        data.endpoint_id = str(uuid.uuid4())

        endpoint_dict = data.dict()
        insert_result = EndpointService.endpoint_collection.insert_one(endpoint_dict)

        if not insert_result.acknowledged:
            raise ValueError("Database error: Unable to insert endpoint")

        endpoint_dict['_id'] = str(insert_result.inserted_id)
        pygate_cache.set_cache('endpoint_cache', cache_key, endpoint_dict)
        api_endpoints = pygate_cache.get_cache('api_endpoint_cache', data.api_id) or list()
        api_endpoints.append(endpoint_dict.get('endpoint_method') + endpoint_dict.get('endpoint_uri'))
        pygate_cache.set_cache('api_endpoint_cache', data.api_id, api_endpoints)

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