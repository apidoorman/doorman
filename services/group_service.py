"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from models.response_model import ResponseModel
from utils.database import db
from utils.cache import cache_manager
from services.cache import pygate_cache
from models.group_model import GroupModel
from pymongo.errors import DuplicateKeyError

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

class GroupService:
    group_collection = db.groups

    @staticmethod
    async def create_group(data: GroupModel):
        """
        Onboard a group to the platform.
        """
        if pygate_cache.get_cache('group_cache', data.group_name):
            return ResponseModel(
                status_code=400,
                error_code='GRP001',
                error_message='Group already exists'
            ).dict()
        group_dict = data.dict()
        try:
            insert_result = GroupService.group_collection.insert_one(group_dict)
            if not insert_result.acknowledged:
                    return ResponseModel(
                        status_code=400,
                        error_code='GRP002',
                        error_message='Database error: Unable to insert group'
                    ).dict()
            group_dict['_id'] = str(insert_result.inserted_id)
            pygate_cache.set_cache('group_cache', data.group_name, group_dict)
            return ResponseModel(
                status_code=201,
                message='Group created successfully'
            ).dict()
        except DuplicateKeyError as e:
            return ResponseModel(
                status_code=400,
                error_code='GRP001',
                error_message='Group already exists'
            ).dict()

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
    async def get_groups(page=1, page_size=10):
        """
        Get all groups.
        """
        skip = (page - 1) * page_size
        cursor = GroupService.group_collection.find().sort('group_name', 1).skip(skip).limit(page_size)
        groups = cursor.to_list(length=None)
        if not groups:
            return ResponseModel(
                status_code=404,
                error_code='GRP002',
                error_message='No groups found'
            ).dict()
        for group in groups:
            if group.get('_id'): del group['_id']
        return ResponseModel(
            status_code=200,
            response={'groups': groups}
        ).dict()

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_group(group_name):
        """
        Get a group by name.
        """
        group = pygate_cache.get_cache('group_cache', group_name)
        if not group:
            group = GroupService.group_collection.find_one({'group_name': group_name})
            if not group:
                return ResponseModel(
                    status_code=404,
                    error_code='GRP003',
                    error_message='Group does not exist'
                ).dict()
            if group.get('_id'): del group['_id']
            pygate_cache.set_cache('group_cache', group_name, group)
        if group.get('_id'): del group['_id']
        return ResponseModel(
            status_code=200,
            response=group
        ).dict()