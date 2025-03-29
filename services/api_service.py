"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

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
            raise ValueError("API already exists for the requested name and version")

        data.api_path = f"/{data.api_name}/{data.api_version}"
        data.api_id = str(uuid.uuid4())

        api_dict = data.dict()
        insert_result = ApiService.api_collection.insert_one(api_dict)

        if not insert_result.acknowledged:
            raise ValueError("Database error: Unable to insert endpoint")
        
        api_dict['_id'] = str(insert_result.inserted_id)
        pygate_cache.set_cache('api_cache', data.api_id, api_dict)
        pygate_cache.set_cache('api_id_cache', data.api_path, data.api_id)

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
                raise ValueError("API does not exist for the requested name and version")
            if api.get('_id'): del api['_id']
            pygate_cache.set_cache('api_cache', f"{api_name}/{api_version}", api)
        if not api:
            raise ValueError("API does not exist for the requested name and version")
        if '_id' in api:
            del api['_id']
        return api

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_apis(page, page_size):
        """
        Get all APIs that a user has access to with pagination.
        """
        skip = (page - 1) * page_size
        cursor = ApiService.api_collection.find().sort('api_name', 1).skip(skip).limit(page_size)
        apis = cursor.to_list(length=None)
        for api in apis:
            if api.get('_id'): del api['_id']
        if not apis:
            raise ValueError("No APIs found")
        return apis