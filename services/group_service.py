"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from models.response_model import ResponseModel
from models.update_group_model import UpdateGroupModel
from utils.database import group_collection
from utils.cache_manager_util import cache_manager
from utils.pygate_cache_util import pygate_cache
from models.create_group_model import CreateGroupModel
from pymongo.errors import DuplicateKeyError

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

class GroupService:

    @staticmethod
    async def create_group(data: CreateGroupModel, request_id):
        """
        Onboard a group to the platform.
        """
        logger.info(request_id + " | Creating group: " + data.group_name)
        if pygate_cache.get_cache('group_cache', data.group_name):
            return ResponseModel(
                status_code=400,
                error_code='GRP001',
                error_message='Group already exists'
            ).dict()
        group_dict = data.dict()
        try:
            insert_result = group_collection.insert_one(group_dict)
            if not insert_result.acknowledged:
                logger.error(request_id + " | Group creation failed with code GRP002")
                return ResponseModel(
                    status_code=400,
                    error_code='GRP002',
                    error_message='Unable to insert group'
                ).dict()
            group_dict['_id'] = str(insert_result.inserted_id)
            pygate_cache.set_cache('group_cache', data.group_name, group_dict)
            logger.info(request_id + " | Group creation successful")
            return ResponseModel(
                status_code=201,
                message='Group created successfully'
            ).dict()
        except DuplicateKeyError as e:
            logger.error(request_id + " | Group creation failed with code GRP001")
            return ResponseModel(
                status_code=400,
                error_code='GRP001',
                error_message='Group already exists'
            ).dict()
        
    @staticmethod
    async def update_group(group_name, data: UpdateGroupModel, request_id):
        """
        Update a group.
        """
        logger.info(request_id + " | Updating group: " + group_name)
        if data.group_name and data.group_name != group_name:
            return ResponseModel(
                status_code=400,
                error_code='GRP004',
                error_message='Group name cannot be updated'
            ).dict()
        group = pygate_cache.get_cache('group_cache', group_name)
        if not group:
            group = group_collection.find_one({
                'group_name': group_name
            })
            if not group:
                logger.error(request_id + " | Group update failed with code GRP003")
                return ResponseModel(
                    status_code=400,
                    error_code='GRP003',
                    error_message='Group does not exist'
                ).dict()
        else:
            pygate_cache.delete_cache('group_cache', group_name)
        not_null_data = {k: v for k, v in data.dict().items() if v is not None}
        if not_null_data:
            update_result = group_collection.update_one(
                {'group_name': group_name},
                {'$set': not_null_data}
            )
            if not update_result.acknowledged or update_result.modified_count == 0:
                logger.error(request_id + " | Group update failed with code GRP002")
                return ResponseModel(
                    status_code=400,
                    error_code='GRP005',
                    error_message='Unable to update group'
                ).dict()
            logger.info(request_id + " | Group updated successful")
            return ResponseModel(
                status_code=200,
                message='Group updated successfully'
                ).dict()
        else:
            logger.error(request_id + " | Group update failed with code GRP006")
            return ResponseModel(
                status_code=400,
                error_code='GRP006',
                error_message='No data to update'
            ).dict()
        
    @staticmethod
    async def delete_group(group_name, request_id):
        """
        Delete a group.
        """
        logger.info(request_id + " | Deleting group: " + group_name)
        group = pygate_cache.get_cache('group_cache', group_name)
        if not group:
            group = group_collection.find_one({
                'group_name': group_name
            })
            if not group:
                logger.error(request_id + " | Group deletion failed with code GRP003")
                return ResponseModel(
                    status_code=400,
                    error_code='GRP003',
                    error_message='Group does not exist'
                ).dict()
        delete_result = group_collection.delete_one({'group_name': group_name})
        if not delete_result.acknowledged:
            logger.error(request_id + " | Group deletion failed with code GRP002")
            return ResponseModel(
                status_code=400,
                error_code='GRP007',
                error_message='Unable to delete group'
            ).dict()
        pygate_cache.delete_cache('group_cache', group_name)
        logger.info(request_id + " | Group deletion successful")
        return ResponseModel(
            status_code=200,
            message='Group deleted successfully'
        ).dict()

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def group_exists(data):
        """
        Check if a group exists.
        """
        if pygate_cache.get_cache('group_cache', data.get('group_name')) or group_collection.find_one({'group_name': data.get('group_name')}):
            return True
        return False

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_groups(page=1, page_size=10, request_id=None):
        """
        Get all groups.
        """
        logger.info(request_id + " | Getting groups: Page=" + str(page) + " Page Size=" + str(page_size))
        skip = (page - 1) * page_size
        cursor = group_collection.find().sort('group_name', 1).skip(skip).limit(page_size)
        groups = cursor.to_list(length=None)
        if not groups:
            logger.error(request_id + " | Groups retrieval failed with code GRP002")
            return ResponseModel(
                status_code=404,
                error_code='GRP002',
                error_message='No groups found'
            ).dict()
        for group in groups:
            if group.get('_id'): del group['_id']
        logger.info(request_id + " | Groups retrieval successful")
        return ResponseModel(
            status_code=200,
            response={'groups': groups}
        ).dict()

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_group(group_name, request_id):
        """
        Get a group by name.
        """
        logger.info(request_id + " | Getting group: " + group_name)
        group = pygate_cache.get_cache('group_cache', group_name)
        if not group:
            group = group_collection.find_one({'group_name': group_name})
            if not group:
                logger.error(request_id + " | Group retrieval failed with code GRP003")
                return ResponseModel(
                    status_code=404,
                    error_code='GRP003',
                    error_message='Group does not exist'
                ).dict()
            if group.get('_id'): del group['_id']
            pygate_cache.set_cache('group_cache', group_name, group)
        if group.get('_id'): del group['_id']
        logger.info(request_id + " | Group retrieval successful")
        return ResponseModel(
            status_code=200,
            response=group
        ).dict()