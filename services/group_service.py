"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

# Internal imports
from utils.database import db
from utils.cache import cache_manager
from services.cache import pygate_cache

class GroupService:
    group_collection = db.group

    @staticmethod
    async def create_group(data):
        """
        Onboard a group to the platform.
        """
        if pygate_cache.get_cache('group_cache', data.get('group_name')) or GroupService.group_collection.find_one({'group_name': data.get('group_name')}):
            raise ValueError("Group already exists")
        group = GroupService.group_collection.insert_one(data)
        pygate_cache.set_cache('group_cache', data.get('group_name'), group)

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def group_exists(data):
        """
        Check if a group exists.
        """
        if pygate_cache.get_cache('group_cache', data.get('group_name')) or GroupService.group_collection.find_one({'group_name': data.get('group_name')}):
            return True
        return False

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_groups():
        """
        Get all groups.
        """
        return GroupService.group_collection.find_all()

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_group(group_name):
        """
        Get a group by name.
        """
        group = pygate_cache.get_cache('group_cache', group_name) or GroupService.group_collection.find_one({'group_name': group_name})
        if not group:
            raise ValueError("Group not found")
        return group