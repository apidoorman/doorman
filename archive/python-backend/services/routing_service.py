"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

import logging
import uuid

from pymongo.errors import DuplicateKeyError

from models.create_routing_model import CreateRoutingModel
from models.response_model import ResponseModel
from models.update_routing_model import UpdateRoutingModel
from utils.constants import ErrorCodes, Messages
from utils.database import routing_collection
from utils.doorman_cache_util import doorman_cache
from utils.paging_util import validate_page_params

logger = logging.getLogger('doorman.gateway')


class RoutingService:
    @staticmethod
    async def create_routing(data: CreateRoutingModel, request_id):
        """
        Onboard a routing to the platform.
        """
        logger.info(request_id + ' | Creating routing: ' + data.routing_name)
        data.client_key = str(uuid.uuid4()) if not data.client_key else data.client_key
        if doorman_cache.get_cache('client_routing_cache', data.client_key):
            logger.error(request_id + ' | Routing creation failed with code RTG001')
            return ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='RTG001',
                error_message='Routing already exists',
            ).dict()
        routing_dict = data.dict()
        try:
            insert_result = routing_collection.insert_one(routing_dict)
            if not insert_result.acknowledged:
                logger.error(request_id + ' | Routing creation failed with code RTG002')
                return ResponseModel(
                    status_code=400, error_code='RTG002', error_message='Unable to insert routing'
                ).dict()
            routing_dict['_id'] = str(insert_result.inserted_id)
            doorman_cache.set_cache('client_routing_cache', data.client_key, routing_dict)
            logger.info(request_id + ' | Routing creation successful')
            return ResponseModel(
                status_code=201, message='Routing created successfully with key: ' + data.client_key
            ).dict()
        except DuplicateKeyError:
            logger.error(request_id + ' | Routing creation failed with code RTG001')
            return ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='RTG001',
                error_message='Routing already exists',
            ).dict()

    @staticmethod
    async def update_routing(client_key, data: UpdateRoutingModel, request_id):
        """
        Update a routing.
        """
        logger.info(request_id + ' | Updating: ' + client_key)
        if data.client_key and data.client_key != client_key:
            logger.error(request_id + ' | Role update failed with code ROLE005')
            return ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='RTG005',
                error_message='Routing key cannot be changed',
            ).dict()
        routing = doorman_cache.get_cache('client_routing_cache', client_key)
        if not routing:
            routing = routing_collection.find_one({'client_key': client_key})
            if not routing:
                logger.error(request_id + ' | Routing update failed with code RTG004')
                return ResponseModel(
                    status_code=400, error_code='RTG004', error_message='Routing does not exist'
                ).dict()
        else:
            doorman_cache.delete_cache('client_routing_cache', client_key)
        not_null_data = {k: v for k, v in data.dict().items() if v is not None}
        if not_null_data:
            update_result = routing_collection.update_one(
                {'client_key': client_key}, {'$set': not_null_data}
            )
            if not update_result.acknowledged or update_result.modified_count == 0:
                logger.error(request_id + ' | Routing update failed with code RTG006')
                return ResponseModel(
                    status_code=400, error_code='RTG006', error_message='Unable to update routing'
                ).dict()
            logger.info(request_id + ' | Routing update successful')
            return ResponseModel(status_code=200, message='Routing updated successfully').dict()
        else:
            logger.error(request_id + ' | Routing update failed with code RTG007')
            return ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='RTG007',
                error_message='No data to update',
            ).dict()

    @staticmethod
    async def delete_routing(client_key, request_id):
        """
        Delete a routing.
        """
        logger.info(request_id + ' | Deleting: ' + client_key)
        routing = doorman_cache.get_cache('client_routing_cache', client_key)
        if not routing:
            routing = routing_collection.find_one({'client_key': client_key})
            if not routing:
                logger.error(request_id + ' | Routing deletion failed with code RTG004')
                return ResponseModel(
                    status_code=400, error_code='RTG004', error_message='Routing does not exist'
                ).dict()
        else:
            doorman_cache.delete_cache('client_routing_cache', client_key)
        delete_result = routing_collection.delete_one({'client_key': client_key})
        if not delete_result.acknowledged or delete_result.deleted_count == 0:
            logger.error(request_id + ' | Routing deletion failed with code RTG008')
            return ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='RTG008',
                error_message='Unable to delete routing',
            ).dict()
        logger.info(request_id + ' | Routing deletion successful')
        return ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            message='Routing deleted successfully',
        ).dict()

    @staticmethod
    async def get_routing(client_key, request_id):
        """
        Get a routing.
        """
        logger.info(request_id + ' | Getting: ' + client_key)
        routing = doorman_cache.get_cache('client_routing_cache', client_key)
        if not routing:
            routing = routing_collection.find_one({'client_key': client_key})
            if not routing:
                logger.error(request_id + ' | Routing retrieval failed with code RTG004')
                return ResponseModel(
                    status_code=400, error_code='RTG004', error_message='Routing does not exist'
                ).dict()
        logger.info(request_id + ' | Routing retrieval successful')
        if routing.get('_id'):
            del routing['_id']
        return ResponseModel(status_code=200, response=routing).dict()

    @staticmethod
    async def get_routings(page=1, page_size=10, request_id=None):
        """
        Get all routings.
        """
        logger.info(
            request_id + ' | Getting routings: Page=' + str(page) + ' Page Size=' + str(page_size)
        )
        try:
            page, page_size = validate_page_params(page, page_size)
        except Exception as e:
            return ResponseModel(
                status_code=400,
                error_code=ErrorCodes.PAGE_SIZE,
                error_message=(
                    Messages.PAGE_TOO_LARGE if 'page_size' in str(e) else Messages.INVALID_PAGING
                ),
            ).dict()
        skip = (page - 1) * page_size
        try:
            from utils.async_db import db_find_paginated, db_count
            docs = await db_find_paginated(
                routing_collection, {}, skip=skip, limit=page_size, sort=[('client_key', 1)]
            )
            try:
                extra = await db_find_paginated(
                    routing_collection, {}, skip=skip, limit=page_size + 1, sort=[('client_key', 1)]
                )
                has_next = len(extra) > page_size
            except Exception:
                has_next = False
            try:
                total = await db_count(routing_collection, {})
            except Exception:
                total = None
        except Exception:
            cursor = routing_collection.find().sort('client_key', 1).skip(skip).limit(page_size)
            docs = await cursor.to_list(length=None)
            has_next = len(docs) >= page_size
            try:
                total = await routing_collection.count_documents({})
            except Exception:
                total = None
        routings = docs
        for route in routings:
            if route.get('_id'):
                del route['_id']
        logger.info(request_id + ' | Routing retrieval successful')
        return ResponseModel(
            status_code=200,
            response={
                'routings': routings,
                'page': page,
                'page_size': page_size,
                'has_next': has_next,
                **({'total': total} if total is not None else {}),
            },
        ).dict()
