"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from models.response_model import ResponseModel
from models.update_role_model import UpdateRoleModel
from utils.database import db
from utils.cache import cache_manager
from services.cache import pygate_cache
from models.role_model import RoleModel
from pymongo.errors import DuplicateKeyError
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

class RoleService:
    role_collection = db.roles

    @staticmethod
    async def create_role(data: RoleModel):
        """
        Onboard a role to the platform.
        """
        if pygate_cache.get_cache('role_cache', data.role_name):
            return ResponseModel(
                status_code=400,
                error_code='ROLE001',
                error_message='Role already exists'
            ).dict()
        role_dict = data.dict()
        try:
            insert_result = RoleService.role_collection.insert_one(role_dict)
            if not insert_result.acknowledged:
                    return ResponseModel(
                        status_code=400,
                        error_code='ROLE002',
                        error_message='Database error: Unable to insert role'
                    ).dict()
            role_dict['_id'] = str(insert_result.inserted_id)
            pygate_cache.set_cache('role_cache', data.role_name, role_dict)
            return ResponseModel(
                status_code=201,
                message='Role created successfully'
            ).dict()
        except DuplicateKeyError as e:
            return ResponseModel(
                status_code=400,
                error_code='GRP001',
                error_message='Role already exists'
            ).dict()
        
    @staticmethod
    async def update_role(role_name, data: UpdateRoleModel):
        """
        Update a role.
        """
        if data.role_name and data.role_name != role_name:
            return ResponseModel(
                status_code=400,
                error_code='ROLE005',
                error_message='Role name cannot be changed'
            ).dict()
        role = pygate_cache.get_cache('role_cache', role_name)
        if not role:
            role = RoleService.role_collection.find_one({
                'role_name': role_name
            })
            if not role:
                return ResponseModel(
                    status_code=400,
                    error_code='ROLE004',
                    error_message='Role does not exist'
                ).dict()
        else:
            pygate_cache.delete_cache('role_cache', role_name)
        not_null_data = {k: v for k, v in data.dict().items() if v is not None}
        if not_null_data:
            update_result = RoleService.role_collection.update_one({'role_name': role_name}, {'$set': not_null_data})
            if not update_result.acknowledged or update_result.modified_count == 0:
                return ResponseModel(
                    status_code=400,
                    error_code='ROLE006',
                    error_message='Database error: Unable to update role'
                ).dict()
            return ResponseModel(
                status_code=200,
                message='Role updated successfully'
            ).dict()
        else:
            return ResponseModel(
                status_code=400,
                error_code='ROLE007',
                error_message='No data to update'
            ).dict()
        
    @staticmethod
    async def delete_role(role_name):
        """
        Delete a role.
        """
        role = pygate_cache.get_cache('role_cache', role_name)
        if not role:
            role = RoleService.role_collection.find_one({'role_name': role_name})
            if not role:
                return ResponseModel(
                    status_code=400,
                    error_code='ROLE004',
                    error_message='Role does not exist'
                ).dict()
        else:
            pygate_cache.delete_cache('role_cache', role_name)
        delete_result = RoleService.role_collection.delete_one({'role_name': role_name})
        if not delete_result.acknowledged:
            return ResponseModel(
                status_code=400,
                error_code='ROLE008',
                error_message='Database error: Unable to delete role'
            ).dict()
        return ResponseModel(
            status_code=200,
            message='Role deleted successfully'
        ).dict()


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
    async def get_roles(page=1, page_size=10):
        """
        Get all roles.
        """
        skip = (page - 1) * page_size
        cursor = RoleService.role_collection.find().sort('role_name', 1).skip(skip).limit(page_size)
        roles = cursor.to_list(length=None)
        if not roles:
            return ResponseModel(
                status_code=404,
                error_code='ROLE003',
                error_message='No roles found'
            ).dict()
        for role in roles:
            if role.get('_id'): del role['_id']
        return ResponseModel(
            status_code=200,
            response={'roles': roles}
        ).dict()

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_role(role_name):
        """
        Get a role by name.
        """
        role = pygate_cache.get_cache('role_cache', role_name)
        if not role:
            role = RoleService.role_collection.find_one({'role_name': role_name})
            if not role:
                return ResponseModel(
                    status_code=404,
                    error_code='ROLE004',
                    error_message='Role does not exist'
                ).dict()
            if role.get('_id'): del role['_id']
            pygate_cache.set_cache('role_cache', role_name, role)
        if role.get('_id'): del role['_id']
        return ResponseModel(
            status_code=200,
            response=role
        ).dict()