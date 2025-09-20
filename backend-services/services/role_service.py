"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

from models.response_model import ResponseModel
from models.update_role_model import UpdateRoleModel
from utils.database import role_collection
from utils.cache_manager_util import cache_manager
from utils.doorman_cache_util import doorman_cache
from models.create_role_model import CreateRoleModel
from pymongo.errors import DuplicateKeyError
import logging

logger = logging.getLogger("doorman.gateway")

class RoleService:

    @staticmethod
    async def create_role(data: CreateRoleModel, request_id):
        """
        Onboard a role to the platform.
        """
        logger.info(request_id + " | Creating role: " + data.role_name)
        if doorman_cache.get_cache('role_cache', data.role_name):
            logger.error(request_id + " | Role creation failed with code ROLE001")
            return ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code='ROLE001',
                error_message='Role already exists'
            ).dict()
        role_dict = data.dict()
        try:
            insert_result = role_collection.insert_one(role_dict)
            if not insert_result.acknowledged:
                logger.error(request_id + " | Role creation failed with code ROLE002")
                return ResponseModel(
                    status_code=400,
                    error_code='ROLE002',
                    error_message='Unable to insert role'
                ).dict()
            role_dict['_id'] = str(insert_result.inserted_id)
            doorman_cache.set_cache('role_cache', data.role_name, role_dict)
            logger.info(request_id + " | Role creation successful")
            return ResponseModel(
                status_code=201,
                message='Role created successfully'
            ).dict()
        except DuplicateKeyError as e:
            logger.error(request_id + " | Role creation failed with code ROLE001")
            return ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code='ROLE001',
                error_message='Role already exists'
            ).dict()
        
    @staticmethod
    async def update_role(role_name, data: UpdateRoleModel, request_id):
        """
        Update a role.
        """
        logger.info(request_id + " | Updating: " + role_name)
        if data.role_name and data.role_name != role_name:
            logger.error(request_id + " | Role update failed with code ROLE005")
            return ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code='ROLE005',
                error_message='Role name cannot be changed'
            ).dict()
        role = doorman_cache.get_cache('role_cache', role_name)
        if not role:
            role = role_collection.find_one({
                'role_name': role_name
            })
            if not role:
                logger.error(request_id + " | Role update failed with code ROLE004")
                return ResponseModel(
                    status_code=400,
                    error_code='ROLE004',
                    error_message='Role does not exist'
                ).dict()
        else:
            doorman_cache.delete_cache('role_cache', role_name)
        not_null_data = {k: v for k, v in data.dict().items() if v is not None}
        if not_null_data:
            update_result = role_collection.update_one({'role_name': role_name}, {'$set': not_null_data})
            if not update_result.acknowledged or update_result.modified_count == 0:
                # In some backends (memory), modified_count may be 0 when values are identical.
                # Check if the role now reflects the requested values before failing.
                current = role_collection.find_one({'role_name': role_name}) or {}
                is_applied = all(current.get(k) == v for k, v in not_null_data.items())
                if not is_applied:
                    logger.error(request_id + " | Role update failed with code ROLE006")
                    return ResponseModel(
                        status_code=400,
                        error_code='ROLE006',
                        error_message='Unable to update role'
                    ).dict()
            # Fetch the updated role to return to clients that expect the object
            updated_role = role_collection.find_one({'role_name': role_name}) or {}
            if updated_role.get('_id'): del updated_role['_id']
            doorman_cache.set_cache('role_cache', role_name, updated_role)
            logger.info(request_id + " | Role update successful")
            return ResponseModel(
                status_code=200,
                response=updated_role,
                message='Role updated successfully'
            ).dict()
        else:
            logger.error(request_id + " | Role update failed with code ROLE007")
            return ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code='ROLE007',
                error_message='No data to update'
            ).dict()
        
    @staticmethod
    async def delete_role(role_name, request_id):
        """
        Delete a role.
        """
        logger.info(request_id + " | Deleting role: " + role_name)
        role = doorman_cache.get_cache('role_cache', role_name)
        if not role:
            role = role_collection.find_one({'role_name': role_name})
            if not role:
                logger.error(request_id + " | Role deletion failed with code ROLE004")
                return ResponseModel(
                    status_code=400,
                    error_code='ROLE004',
                    error_message='Role does not exist'
                ).dict()
        else:
            doorman_cache.delete_cache('role_cache', role_name)
        delete_result = role_collection.delete_one({'role_name': role_name})
        if not delete_result.acknowledged:
            logger.error(request_id + " | Role deletion failed with code ROLE008")
            return ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code='ROLE008',
                error_message='Unable to delete role'
            ).dict()
        logger.info(request_id + " | Role Deletion Successful")
        return ResponseModel(
            status_code=200,
            response_headers={
                "request_id": request_id
            },
            message='Role deleted successfully'
        ).dict()


    @staticmethod
    async def role_exists(data):
        """
        Check if a role exists.
        """
        if doorman_cache.get_cache('role_cache', data.get('role_name')) or role_collection.find_one({'role_name': data.get('role_name')}):
            return True
        return False

    @staticmethod
    async def get_roles(page=1, page_size=10, request_id=None):
        """
        Get all roles.
        """
        logger.info(request_id + " | Getting roles: Page=" + str(page) + " Page Size=" + str(page_size))
        skip = (page - 1) * page_size
        cursor = role_collection.find().sort('role_name', 1).skip(skip).limit(page_size)
        roles = cursor.to_list(length=None)
        for role in roles:
            if role.get('_id'): del role['_id']
        logger.info(request_id + " | Roles retrieval successful")
        return ResponseModel(
            status_code=200,
            response={'roles': roles}
        ).dict()

    @staticmethod
    async def get_role(role_name, request_id):
        """
        Get a role by name.
        """
        logger.info(request_id + " | Getting role: " + role_name)
        role = doorman_cache.get_cache('role_cache', role_name)
        if not role:
            role = role_collection.find_one({'role_name': role_name})
            if not role:
                logger.error(request_id + " | Role retrieval failed with code ROLE004")
                return ResponseModel(
                    status_code=404,
                    error_code='ROLE004',
                    error_message='Role does not exist'
                ).dict()
            if role.get('_id'): del role['_id']
            doorman_cache.set_cache('role_cache', role_name, role)
        if role.get('_id'): del role['_id']
        logger.info(request_id + " | Role retrieval successful")
        return ResponseModel(
            status_code=200,
            response=role
        ).dict()
