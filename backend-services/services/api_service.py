"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import uuid
from models.response_model import ResponseModel
from models.update_api_model import UpdateApiModel
from utils.database import api_collection
from utils.cache_manager_util import cache_manager
from utils.doorman_cache_util import doorman_cache
from models.create_api_model import CreateApiModel

import logging

logger = logging.getLogger("doorman.gateway")

class ApiService:

    @staticmethod
    async def create_api(data: CreateApiModel, request_id):
        """
        Onboard an API to the platform.
        """
        logger.info(request_id + " | Creating API: " + data.api_name + " " + data.api_version)
        # Prevent unsafe combination: public API with credits enabled
        try:
            if getattr(data, 'api_public', False) and getattr(data, 'api_credits_enabled', False):
                return ResponseModel(
                    status_code=400,
                    error_code='API013',
                    error_message='Public API cannot have credits enabled'
                ).dict()
        except Exception:
            pass
        cache_key = f"{data.api_name}/{data.api_version}"
        existing = doorman_cache.get_cache('api_cache', cache_key)
        if not existing:
            existing = api_collection.find_one({'api_name': data.api_name, 'api_version': data.api_version})
        if existing:
            # Idempotent create: if already exists, ensure caches are populated and return 200
            try:
                if existing.get('_id'):
                    existing = {k: v for k, v in existing.items() if k != '_id'}
                # Ensure api_id/api_path present for cache keys
                if not existing.get('api_id'):
                    existing['api_id'] = str(uuid.uuid4())
                if not existing.get('api_path'):
                    existing['api_path'] = f"/{existing.get('api_name')}/{existing.get('api_version')}"
                doorman_cache.set_cache('api_cache', cache_key, existing)
                doorman_cache.set_cache('api_id_cache', existing['api_path'], existing['api_id'])
            except Exception:
                pass
            logger.info(request_id + " | API already exists; returning success")
            return ResponseModel(
                status_code=200,
                response_headers={
                    "request_id": request_id
                },
                message='API already exists'
                ).dict()
        data.api_path = f"/{data.api_name}/{data.api_version}"
        data.api_id = str(uuid.uuid4())
        api_dict = data.dict()
        insert_result = api_collection.insert_one(api_dict)
        if not insert_result.acknowledged:
            logger.error(request_id + " | API creation failed with code API002")
            return ResponseModel(
                status_code=400, 
                error_code='API002', 
                error_message='Unable to insert endpoint'
                ).dict()
        api_dict['_id'] = str(insert_result.inserted_id)
        doorman_cache.set_cache('api_cache', data.api_id, api_dict)
        doorman_cache.set_cache('api_id_cache', data.api_path, data.api_id)
        logger.info(request_id + " | API creation successful")
        return ResponseModel(
            status_code=201,
            response_headers={
                "request_id": request_id
            },
            message='API created successfully'
            ).dict()
    
    @staticmethod
    async def update_api(api_name, api_version, data: UpdateApiModel, request_id):
        """
        Update an API on the platform.
        """
        logger.info(request_id + " | Updating API: " + api_name + " " + api_version)
        if data.api_name and data.api_name != api_name or data.api_version and data.api_version != api_version or data.api_path and data.api_path != f"/{api_name}/{api_version}":
            logger.error(request_id + " | API update failed with code API005")
            return ResponseModel(
                status_code=400, 
                error_code='API005', 
                error_message='API name and version cannot be updated'
                ).dict()
        api = doorman_cache.get_cache('api_cache', f"{api_name}/{api_version}")
        if not api:
            api = api_collection.find_one({'api_name': api_name, 'api_version': api_version})
            if not api:
                logger.error(request_id + " | API update failed with code API003")
                return ResponseModel(
                    status_code=400, 
                    error_code='API003', 
                    error_message='API does not exist for the requested name and version'
                    ).dict()
        else:
            doorman_cache.delete_cache('api_cache', doorman_cache.get_cache('api_id_cache', f"/{api_name}/{api_version}"))
            doorman_cache.delete_cache('api_id_cache', f"/{api_name}/{api_version}")
        not_null_data = {k: v for k, v in data.dict().items() if v is not None}
        # Validate unsafe combination on the desired state (existing + updates)
        try:
            desired_public = bool(not_null_data.get('api_public', api.get('api_public')))
            desired_credits = bool(not_null_data.get('api_credits_enabled', api.get('api_credits_enabled')))
            if desired_public and desired_credits:
                return ResponseModel(
                    status_code=400,
                    error_code='API013',
                    error_message='Public API cannot have credits enabled'
                ).dict()
        except Exception:
            pass
        if not_null_data:
            update_result = api_collection.update_one(
                {'api_name': api_name, 'api_version': api_version},
                {'$set': not_null_data}
            )
            if not update_result.acknowledged or update_result.modified_count == 0:
                logger.error(request_id + " | API update failed with code API002")
                return ResponseModel(
                    status_code=400, 
                    error_code='API002', 
                    error_message='Unable to update api'
                    ).dict()
            logger.info(request_id + " | API updated successful")
            return ResponseModel(
                status_code=200,
                message='API updated successfully'
                ).dict()
        else:
            logger.error(request_id + " | API update failed with code API006")
            return ResponseModel(
                status_code=400, 
                error_code='API006', 
                error_message='No data to update'
                ).dict()
        
    @staticmethod
    async def delete_api(api_name, api_version, request_id):
        """
        Delete an API from the platform.
        """
        logger.info(request_id + " | Deleting API: " + api_name + " " + api_version)
        api = doorman_cache.get_cache('api_cache', f"{api_name}/{api_version}")
        if not api:
            api = api_collection.find_one({'api_name': api_name, 'api_version': api_version})
            if not api:
                logger.error(request_id + " | API deletion failed with code API003")
                return ResponseModel(
                    status_code=400, 
                    error_code='API003', 
                    error_message='API does not exist for the requested name and version'
                    ).dict()
        delete_result = api_collection.delete_one({'api_name': api_name, 'api_version': api_version})
        if not delete_result.acknowledged:
            logger.error(request_id + " | API deletion failed with code API002")
            return ResponseModel(
                status_code=400, 
                error_code='API002', 
                error_message='Unable to delete endpoint'
                ).dict()
        doorman_cache.delete_cache('api_cache', doorman_cache.get_cache('api_id_cache', f"/{api_name}/{api_version}"))
        doorman_cache.delete_cache('api_id_cache', f"/{api_name}/{api_version}")
        logger.info(request_id + " | API deletion successful")
        return ResponseModel(
            status_code=200,
            response_headers={
                "request_id": request_id
            },
            message='API deleted successfully'
            ).dict()

    @staticmethod
    async def get_api_by_name_version(api_name, api_version, request_id):
        """
        Get an API by name and version.
        """
        logger.info(request_id + " | Getting API: " + api_name + " " + api_version)
        api = doorman_cache.get_cache('api_cache', f"{api_name}/{api_version}")
        if not api:
            api = api_collection.find_one({'api_name': api_name, 'api_version': api_version})
            if not api:
                logger.error(request_id + " | API retrieval failed with code API003")
                return ResponseModel(
                    status_code=400, 
                    error_code='API003', 
                    error_message='API does not exist for the requested name and version'
                    ).dict()
            if api.get('_id'): del api['_id']
            doorman_cache.set_cache('api_cache', f"{api_name}/{api_version}", api)
        if '_id' in api:
            del api['_id']
        logger.info(request_id + " | API retrieval successful")
        return ResponseModel(
            status_code=200, 
            response=api
            ).dict()

    @staticmethod
    async def get_apis(page, page_size, request_id):
        """
        Get all APIs that a user has access to with pagination.
        """
        logger.info(request_id + " | Getting APIs: Page=" + str(page) + " Page Size=" + str(page_size))
        skip = (page - 1) * page_size
        cursor = api_collection.find().sort('api_name', 1).skip(skip).limit(page_size)
        apis = cursor.to_list(length=None)
        for api in apis:
            if api.get('_id'): del api['_id']
        logger.info(request_id + " | APIs retrieval successful")
        return ResponseModel(
            status_code=200, 
            response={'apis': apis}
            ).dict()
