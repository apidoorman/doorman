"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from models.response_model import ResponseModel
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
            return ResponseModel(
                status_code=400,
                error_code='END001',
                error_message='Endpoint already exists for the requested API name, version and URI'
            ).dict()

        data.api_id = pygate_cache.get_cache('api_id_cache', data.api_name + '/' + data.api_version)

        if not data.api_id:
            api = EndpointService.apis_collection.find_one({"api_name": data.api_name, "api_version": data.api_version})
            if not api:
                return ResponseModel(
                    status_code=400,
                    error_code='END002',
                    error_message='API does not exist for the requested name and version'
                ).dict()
            data.api_id = api.get('api_id')
            pygate_cache.set_cache('api_id_cache', f"{data.api_name}/{data.api_version}", data.api_id)
        data.endpoint_id = str(uuid.uuid4())
        endpoint_dict = data.dict()
        insert_result = EndpointService.endpoint_collection.insert_one(endpoint_dict)
        if not insert_result.acknowledged:
            return ResponseModel(
                status_code=400,
                error_code='END003',
                error_message='Database error: Unable to insert endpoint'
            ).dict()
        endpoint_dict['_id'] = str(insert_result.inserted_id)
        pygate_cache.set_cache('endpoint_cache', cache_key, endpoint_dict)
        api_endpoints = pygate_cache.get_cache('api_endpoint_cache', data.api_id) or list()
        api_endpoints.append(endpoint_dict.get('endpoint_method') + endpoint_dict.get('endpoint_uri'))
        pygate_cache.set_cache('api_endpoint_cache', data.api_id, api_endpoints)
        return ResponseModel(
            status_code=201,
            message='Endpoint created successfully'
        ).dict()

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_endpoint(api_name, api_version, endpoint_uri):
        """
        Get an endpoint by API name, version and URI.
        """
        endpoint = pygate_cache.get_cache('endpoint_cache', f"{api_name}/{api_version}/{endpoint_uri}")
        if not endpoint:
            endpoint = EndpointService.endpoint_collection.find_one({
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_uri': endpoint_uri
        })
            if not endpoint:
                return ResponseModel(
                    status_code=400,
                    error_code='END004',
                    error_message='Endpoint does not exist for the requested API name, version and URI'
                ).dict()
            if endpoint.get('_id'): del endpoint['_id']
            pygate_cache.set_cache('endpoint_cache', f"{api_name}/{api_version}/{endpoint_uri}", endpoint)
        if not endpoint:
            return ResponseModel(
                status_code=400,
                error_code='END004',
                error_message='Endpoint does not exist for the requested API name, version and URI'
            ).dict()
        if '_id' in endpoint:
            del endpoint['_id']
        return ResponseModel(
            status_code=200,
            response=endpoint
        ).dict()
    
    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_endpoints_by_name_version(api_name, api_version):
        """
        Get all endpoints by API name and version.
        """
        cursor = EndpointService.endpoint_collection.find({
            'api_name': api_name,
            'api_version': api_version
        })
        endpoints = cursor.to_list(length=None)
        for endpoint in endpoints:
            if '_id' in endpoint: del endpoint['_id']
        if not endpoints:
            return ResponseModel(
                status_code=400,
                error_code='END005',
                error_message='No endpoints found for the requested API name and version'
            ).dict()
        return ResponseModel(
            status_code=200,
            response={'endpoints': endpoints}
        ).dict()