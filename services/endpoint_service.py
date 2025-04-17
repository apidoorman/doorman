"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from models.response_model import ResponseModel
from models.update_endpoint_model import UpdateEndpointModel
from utils.database import endpoint_collection, api_collection
from utils.cache_manager_util import cache_manager
from utils.pygate_cache_util import pygate_cache
from models.create_endpoint_model import CreateEndpointModel

import uuid
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

class EndpointService:

    @staticmethod
    async def create_endpoint(data: CreateEndpointModel, request_id):
        """
        Create an endpoint for an API.
        """
        logger.info(request_id + " | Creating endpoint: " + data.api_name + " " + data.api_version + " " + data.endpoint_uri)
        cache_key = f"/{data.endpoint_method}/{data.api_name}/{data.api_version}/{data.endpoint_uri}".replace("//", "/")
        if pygate_cache.get_cache('endpoint_cache', cache_key) or endpoint_collection.find_one({
            'api_name': data.api_name,
            'api_version': data.api_version,
            'endpoint_uri': data.endpoint_uri
        }):
            logger.error(request_id + " | Endpoint creation failed with code END001")
            return ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code='END001',
                error_message='Endpoint already exists for the requested API name, version and URI'
            ).dict()
        data.api_id = pygate_cache.get_cache('api_id_cache', data.api_name + data.api_version)
        if not data.api_id:
            api = api_collection.find_one({"api_name": data.api_name, "api_version": data.api_version})
            if not api:
                logger.error(request_id + " | Endpoint creation failed with code END002")
                return ResponseModel(
                    status_code=400,
                    error_code='END002',
                    error_message='API does not exist for the requested name and version'
                ).dict()
            data.api_id = api.get('api_id')
            pygate_cache.set_cache('api_id_cache', f"{data.api_name}/{data.api_version}", data.api_id)
        data.endpoint_id = str(uuid.uuid4())
        endpoint_dict = data.dict()
        insert_result = endpoint_collection.insert_one(endpoint_dict)
        if not insert_result.acknowledged:
            logger.error(request_id + " | Endpoint creation failed with code END003")
            return ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code='END003',
                error_message='Unable to insert endpoint'
            ).dict()
        endpoint_dict['_id'] = str(insert_result.inserted_id)
        pygate_cache.set_cache('endpoint_cache', cache_key, endpoint_dict)
        api_endpoints = pygate_cache.get_cache('api_endpoint_cache', data.api_id) or list()
        api_endpoints.append(endpoint_dict.get('endpoint_method') + endpoint_dict.get('endpoint_uri'))
        pygate_cache.set_cache('api_endpoint_cache', data.api_id, api_endpoints)
        logger.info(request_id + " | Endpoint creation successful")
        return ResponseModel(
            status_code=201,
            response_headers={
                "request_id": request_id
            },
            message='Endpoint created successfully'
        ).dict()
    
    @staticmethod
    async def update_endpoint(endpoint_method, api_name, api_version, endpoint_uri, data: UpdateEndpointModel, request_id):
        logger.info(request_id + " | Updating endpoint: " + api_name + " " + api_version + " " + endpoint_uri)
        cache_key = f"/{endpoint_method}/{api_name}/{api_version}/{endpoint_uri}".replace("//", "/")
        endpoint = pygate_cache.get_cache('endpoint_cache', cache_key)
        if not endpoint:
            endpoint = endpoint_collection.find_one({
                'api_name': api_name,
                'api_version': api_version,
                'endpoint_uri': endpoint_uri,
                'endpoint_method': endpoint_method
            })
            logger.error(request_id + " | Endpoint update failed with code END008")
            if not endpoint:
                return ResponseModel(
                    status_code=400,
                    error_code='END008',
                    error_message='Endpoint does not exist for the requested API name, version and URI'
                ).dict()
        else:
            pygate_cache.delete_cache('endpoint_cache', cache_key)
        if (data.endpoint_method and data.endpoint_method != endpoint.get('endpoint_method')) or (data.api_name and data.api_name != endpoint.get('api_name')) or (data.api_version and data.api_version != endpoint.get('api_version')) or (data.endpoint_uri and data.endpoint_uri != endpoint.get('endpoint_uri')):
            logger.error(request_id + " | Endpoint update failed with code END006")
            return ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code='END006',
                error_message='API method, name, version and URI cannot be updated'
            ).dict()
        not_null_data = {k: v for k, v in data.dict().items() if v is not None}
        if not_null_data:
            update_result = endpoint_collection.update_one({
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
                logger.error(request_id + " | Endpoint update failed with code END003")
                return ResponseModel(
                    status_code=400,
                    error_code='END003',
                    error_message='Unable to update endpoint'
                ).dict()
            logger.info(request_id + " | Endpoint update successful")
            return ResponseModel(
                status_code=200,
                message='Endpoint updated successfully'
                ).dict()
        else:
            logger.error(request_id + " | Endpoint update failed with code END007")
            return ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code='END007',
                error_message='No data to update'
            ).dict()
        
    @staticmethod
    async def delete_endpoint(endpoint_method, api_name, api_version, endpoint_uri, request_id):
        """
        Delete an endpoint for an API.
        """
        logger.info(request_id + " | Deleting: " + api_name + " " + api_version + " " + endpoint_uri)
        cache_key = f"/{endpoint_method}/{api_name}/{api_version}/{endpoint_uri}".replace("//", "/")
        endpoint = pygate_cache.get_cache('endpoint_cache', cache_key)
        if not endpoint:
            endpoint = endpoint_collection.find_one({
                'api_name': api_name,
                'api_version': api_version,
                'endpoint_uri': endpoint_uri,
                'endpoint_method': endpoint_method
            })
            if not endpoint:
                logger.error(request_id + " | Endpoint deletion failed with code END004")
                return ResponseModel(
                    status_code=400,
                    error_code='END004',
                    error_message='Endpoint does not exist for the requested API name, version and URI'
                ).dict()
        delete_result = endpoint_collection.delete_one({
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_uri': endpoint_uri,
            'endpoint_method': endpoint_method
        })
        if not delete_result.acknowledged:
            logger.error(request_id + " | Endpoint deletion failed with code END009")
            return ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code='END009',
                error_message='Unable to delete endpoint'
            ).dict()
        pygate_cache.delete_cache('endpoint_cache', cache_key)
        logger.info(request_id + " | Endpoint deletion successful")
        return ResponseModel(
            status_code=200,
            response_headers={
                "request_id": request_id
            },
            message='Endpoint deleted successfully'
        ).dict()

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_endpoint(endpoint_method, api_name, api_version, endpoint_uri, request_id):
        """
        Get an endpoint by API name, version and URI.
        """
        logger.info(request_id + " | Getting: " + api_name + " " + api_version + " " + endpoint_uri)
        endpoint = pygate_cache.get_cache('endpoint_cache', f"{api_name}/{api_version}/{endpoint_uri}")
        if not endpoint:
            endpoint = endpoint_collection.find_one({
            'api_name': api_name,
            'api_version': api_version,
            'endpoint_uri': endpoint_uri,
            'endpoint_method': endpoint_method
            })
            if not endpoint:
                logger.error(request_id + " | Endpoint retrieval failed with code END004")
                return ResponseModel(
                    status_code=400,
                    error_code='END004',
                    error_message='Endpoint does not exist for the requested API name, version and URI'
                ).dict()
            if endpoint.get('_id'): del endpoint['_id']
            pygate_cache.set_cache('endpoint_cache', f"{api_name}/{api_version}/{endpoint_uri}", endpoint)
        if '_id' in endpoint:
            del endpoint['_id']
        logger.info(request_id + " | Endpoint retrieval successful")
        return ResponseModel(
            status_code=200,
            response=endpoint
        ).dict()
    
    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_endpoints_by_name_version(api_name, api_version, request_id):
        """
        Get all endpoints by API name and version.
        """
        logger.info(request_id + " | Getting: " + api_name + " " + api_version)
        cursor = endpoint_collection.find({
            'api_name': api_name,
            'api_version': api_version
        })
        endpoints = cursor.to_list(length=None)
        for endpoint in endpoints:
            if '_id' in endpoint: del endpoint['_id']
        if not endpoints:
            logger.error(request_id + " | Endpoint retrieval failed with code END005")
            return ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code='END005',
                error_message='No endpoints found for the requested API name and version'
            ).dict()
        logger.info(request_id + " | Endpoint retrieval successful")
        return ResponseModel(
            status_code=200,
            response={'endpoints': endpoints}
        ).dict()