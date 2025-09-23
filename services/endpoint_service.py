"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from models.response_model import ResponseModel
from models.update_endpoint_model import UpdateEndpointModel
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
        cache_key = f"/{data.endpoint_method}/{data.api_name}/{data.api_version}/{data.endpoint_uri}".replace("//", "/")

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

        data.api_id = pygate_cache.get_cache('api_id_cache', data.api_name + data.api_version)

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
    async def update_endpoint(endpoint_method, api_name, api_version, endpoint_uri, data: UpdateEndpointModel):
        if data.endpoint_method and data.endpoint_method != endpoint_method or data.api_name and data.api_name != api_name or data.api_version and data.api_version != api_version or data.endpoint_uri and data.endpoint_uri != endpoint_uri:
            return ResponseModel(
                status_code=400,
                error_code='END006',
                error_message='API method, name, version and URI cannot be updated'
            ).dict()
        cache_key = f"/{endpoint_method}/{api_name}/{api_version}/{endpoint_uri}".replace("//", "/")
        endpoint = pygate_cache.get_cache('endpoint_cache', cache_key)
        if not endpoint:
            endpoint = EndpointService.endpoint_collection.find_one({
                'api_name': api_name,
                'api_version': api_version,
                'endpoint_uri': endpoint_uri,
                'endpoint_method': endpoint_method
            })
            if not endpoint:
                return ResponseModel(
                    status_code=400,
                    error_code='END004',
                    error_message='Endpoint does not exist for the requested API name, version and URI'
                ).dict()
        else:
            pygate_cache.delete_cache('endpoint_cache', cache_key)
        not_null_data = {k: v for k, v in data.dict().items() if v is not None}
        if not_null_data:
            update_result = EndpointService.endpoint_collection.update_one({
                    'api_name': api_name,
                    'api_version': api_version,
                    'endpoint_uri': endpoint_uri,
                    'endpoint_method': endpoint_method
                },
                {   
                    '$set': not_null_data
                }
            )
            if not update_result.acknowledged or update_result.modified_count == 0:
                return ResponseModel(
                    status_code=400,
                    error_code='END003',
                    error_message='Database error: Unable to update endpoint'
                ).dict()
            return ResponseModel(
                status_code=200,
                message='Endpoint updated successfully'
                ).dict()
        else:
            return ResponseModel(
                status_code=400,
                error_code='END007',
                error_message='No data to update'
            ).dict()
        
    @staticmethod
    async def delete_endpoint(endpoint_method, api_name, api_version, endpoint_uri):
        """
        Delete an endpoint for an API.
        """
        cache_key = f"/{endpoint_method}/{api_name}/{api_version}/{endpoint_uri}".replace("//", "/")
        endpoint = pygate_cache.get_cache('endpoint_cache', cache_key)
        if not endpoint:
            endpoint = EndpointService.endpoint_collection.find_one({
                'api_name': api_name,
                'api_version': api_version,
                'endpoint_uri': endpoint_uri,
                'endpoint_method': endpoint_method
            })
            if not endpoint:
                return ResponseModel(
                    status_code=400,
                    error_code='END004',
                    error_message='Endpoint does not exist for the requested API name, version and URI'
                ).dict()
        delete_result = EndpointService.endpoint_collection.delete_one({
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_uri': endpoint_uri,
            'endpoint_method': endpoint_method
        })
        if not delete_result.acknowledged:
            return ResponseModel(
                status_code=400,
                error_code='END003',
                error_message='Database error: Unable to delete endpoint'
            ).dict()
        pygate_cache.delete_cache('endpoint_cache', cache_key)
        return ResponseModel(
            status_code=200,
            message='Endpoint deleted successfully'
        ).dict()

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_endpoint(endpoint_method, api_name, api_version, endpoint_uri):
        """
        Get an endpoint by API name, version and URI.
        """
        endpoint = pygate_cache.get_cache('endpoint_cache', f"{api_name}/{api_version}/{endpoint_uri}")
        if not endpoint:
            endpoint = EndpointService.endpoint_collection.find_one({
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_uri': endpoint_uri,
            'endpoint_method': endpoint_method
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