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
        if pygate_cache.get_cache('api_cache', f"{data.api_name}/{data.api_version}") or ApiService.api_collection.find_one({'api_name': data.api_name, 'api_version': data.api_version}):
            raise ValueError("API already exists for the requested name and version")
        data.api_path = f"/{data.get('api_name')}/{data.get('api_version')}"
        data.api_id = str(uuid.uuid4())
        api = ApiService.api_collection.insert_one(data)
        pygate_cache.set_cache('api_cache', f"{data.api_name}/{data.api_version}", api)
        pygate_cache.set_cache('api_id_cache', data.api_path, data.api_id)

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_api_by_name_version(api_name, api_version):
        """
        Get an API by name and version.
        """
        api = pygate_cache.get_cache('api_cache', f"{api_name}/{api_version}") or ApiService.api_collection.find_one({'api_name': api_name, 'api_version': api_version})
        if not api:
            raise ValueError("API does not exist for the requested name and version")
        if '_id' in api:
            del api['_id']
        return api

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_apis():
        """
        Get all APIs that a user has access to.
        """
        return list(ApiService.api_collection.find())