"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi.responses import JSONResponse
from models.response_model import ResponseModel
from models.update_api_model import UpdateApiModel
from utils.database import db
from utils.cache import cache_manager
from services.cache import pygate_cache
from models.api_model import ApiModel

import uuid

class ApiService:
    api_collection = db.apis

    @staticmethod
    async def create_api(data: ApiModel):
        """
        Onboard an API to the platform.
        """
        cache_key = f"{data.api_name}/{data.api_version}"
        if pygate_cache.get_cache('api_cache', cache_key) or ApiService.api_collection.find_one({'api_name': data.api_name, 'api_version': data.api_version}):
            return ResponseModel(
                status_code=400, 
                error_code='API001',
                error_message='API already exists for the requested name and version'
                ).dict()
        data.api_path = f"/{data.api_name}/{data.api_version}"
        data.api_id = str(uuid.uuid4())
        api_dict = data.dict()
        insert_result = ApiService.api_collection.insert_one(api_dict)
        if not insert_result.acknowledged:
            return ResponseModel(
                status_code=400, 
                error_code='API002', 
                error_message='Database error: Unable to insert endpoint'
                ).dict()
        api_dict['_id'] = str(insert_result.inserted_id)
        pygate_cache.set_cache('api_cache', data.api_id, api_dict)
        pygate_cache.set_cache('api_id_cache', data.api_path, data.api_id)
        return ResponseModel(
            status_code=201,
            message='API created successfully'
            ).dict()
    
    @staticmethod
    async def update_api(api_name, api_version, data: UpdateApiModel):
        """
        Update an API on the platform.
        """
        if data.api_name and data.api_name != api_name or data.api_version and data.api_version != api_version:
            return ResponseModel(
                status_code=400, 
                error_code='API005', 
                error_message='API name and version cannot be updated'
                ).dict()
        api = pygate_cache.get_cache('api_cache', f"{api_name}/{api_version}")
        if not api:
            api = ApiService.api_collection.find_one({'api_name': api_name, 'api_version': api_version})
            if not api:
                return ResponseModel(
                    status_code=400, 
                    error_code='API003', 
                    error_message='API does not exist for the requested name and version'
                    ).dict()
        else:
            pygate_cache.delete_cache('api_cache', pygate_cache.get_cache('api_id_cache', f"/{api_name}/{api_version}"))
            pygate_cache.delete_cache('api_id_cache', f"/{api_name}/{api_version}")
        not_null_data = {k: v for k, v in data.dict().items() if v is not None}
        if not_null_data:
            update_result = ApiService.api_collection.update_one(
                {'api_name': api_name, 'api_version': api_version},
                {'$set': not_null_data}
            )
            if not update_result.acknowledged or update_result.modified_count == 0:
                return ResponseModel(
                    status_code=400, 
                    error_code='API002', 
                    error_message='Database error: Unable to update endpoint or no changes were made'
                    ).dict()
            return ResponseModel(
                status_code=200,
                message='API updated successfully'
                ).dict()
        else:
            return ResponseModel(
                status_code=400, 
                error_code='API006', 
                error_message='No data to update'
                ).dict()
        
    @staticmethod
    async def delete_api(api_name, api_version):
        """
        Delete an API from the platform.
        """
        api = pygate_cache.get_cache('api_cache', f"{api_name}/{api_version}")
        if not api:
            api = ApiService.api_collection.find_one({'api_name': api_name, 'api_version': api_version})
            if not api:
                return ResponseModel(
                    status_code=400, 
                    error_code='API003', 
                    error_message='API does not exist for the requested name and version'
                    ).dict()
        delete_result = ApiService.api_collection.delete_one({'api_name': api_name, 'api_version': api_version})
        if not delete_result.acknowledged:
            return ResponseModel(
                status_code=400, 
                error_code='API002', 
                error_message='Database error: Unable to delete endpoint'
                ).dict()
        pygate_cache.delete_cache('api_cache', pygate_cache.get_cache('api_id_cache', f"/{api_name}/{api_version}"))
        pygate_cache.delete_cache('api_id_cache', f"/{api_name}/{api_version}")
        return ResponseModel(
            status_code=200,
            message='API deleted successfully'
            ).dict()

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_api_by_name_version(api_name, api_version):
        """
        Get an API by name and version.
        """
        api = pygate_cache.get_cache('api_cache', f"{api_name}/{api_version}")
        if not api:
            api = ApiService.api_collection.find_one({'api_name': api_name, 'api_version': api_version})
            if not api:
                return ResponseModel(
                    status_code=400, 
                    error_code='API003', 
                    error_message='API does not exist for the requested name and version'
                    ).dict()
            if api.get('_id'): del api['_id']
            pygate_cache.set_cache('api_cache', f"{api_name}/{api_version}", api)
        if '_id' in api:
            del api['_id']
        return ResponseModel(
            status_code=200, 
            response=api
            ).dict()

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_apis(page, page_size):
        """
        Get all APIs that a user has access to with pagination.
        """
        skip = (page - 1) * page_size
        cursor = ApiService.api_collection.find().sort('api_name', 1).skip(skip).limit(page_size)
        apis = cursor.to_list(length=None)
        if not apis:
            return ResponseModel(
                status_code=400, 
                error_code='API004', 
                error_message='No APIs found'
                ).dict()
        for api in apis:
            if api.get('_id'): del api['_id']
        return ResponseModel(
            status_code=200, 
            response={'apis': apis}
            ).dict()