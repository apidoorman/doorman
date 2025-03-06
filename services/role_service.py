"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from utils.database import db
from utils.cache import cache_manager
from services.cache import pygate_cache

class RoleService:
    role_collection = db.roles

    @staticmethod
    async def create_role(data):
        """
        Onboard a role to the platform.
        """
        if pygate_cache.get_cache('role_cache', data.get('role_name')) or RoleService.role_collection.find_one({'role_name': data.get('role_name')}):
            raise ValueError("Role already exists")
        role = RoleService.role_collection.insert_one(data)
        pygate_cache.set_cache('role_cache', data.get('role_name'), role)

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def role_exists(data):
        """
        Check if a role exists.
        """
        if pygate_cache.get_cache('role_cache', data.get('role_name')) or RoleService.role_collection.find_one({'role_name': data.get('role_name')}):
            return True
        return False

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_roles():
        """
        Get all roles.
        """
        return RoleService.role_collection.find_all()

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_role(role_name):
        """
        Get a role by name.
        """
        role = pygate_cache.get_cache('role_cache', role_name) or RoleService.role_collection.find_one({'role_name': role_name})
        if not role:
            raise ValueError("Role not found")
        return role