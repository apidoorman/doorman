"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from models.response_model import ResponseModel
from models.routing_model import RoutingModel
from models.update_routing_model import UpdateRoutingModel
from utils.database import db
from services.cache import pygate_cache
from pymongo.errors import DuplicateKeyError

import uuid
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

class RoutingService:
    routing_collection = db.routings

    @staticmethod
    async def create_routing(data: RoutingModel, request_id):
        """
        Onboard a routing to the platform.
        """
        logger.info(request_id + " | Creating routing: " + data.routing_name)
        logger.info(request_id + " | Routing data: " + str(data))
        data.client_key = str(uuid.uuid4()) if not data.client_key else data.client_key
        if pygate_cache.get_cache('client_routing_cache', data.client_key):
            logger.error(request_id + " | Routing creation failed with code ROUT001")
            return ResponseModel(
                status_code=400,
                error_code='ROUT001',
                error_message='Routing already exists'
            ).dict()
        routing_dict = data.dict()
        try:
            insert_result = RoutingService.routing_collection.insert_one(routing_dict)
            if not insert_result.acknowledged:
                logger.error(request_id + " | Routing creation failed with code ROUT002")
                return ResponseModel(
                    status_code=400,
                    error_code='ROUT002',
                    error_message='Database error: Unable to insert routing'
                ).dict()
            routing_dict['_id'] = str(insert_result.inserted_id)
            pygate_cache.set_cache('client_routing_cache', data.client_key, routing_dict)
            logger.info(request_id + " | Routing creation successful")
            return ResponseModel(
                status_code=201,
                message='Routing created successfully'
            ).dict()
        except DuplicateKeyError as e:
            logger.error(request_id + " | Routing creation failed with code ROUT001")
            return ResponseModel(
                status_code=400,
                error_code='ROUT001',
                error_message='Routing already exists'
            ).dict()
        
    @staticmethod
    async def update_routing(client_key, data: UpdateRoutingModel, request_id):
        """
        Update a routing.
        """
        logger.info(request_id + " | Updating: " + client_key)
        if data.client_key and data.client_key != client_key:
            logger.error(request_id + " | Role update failed with code ROLE005")
            return ResponseModel(
                status_code=400,
                error_code='ROUT005',
                error_message='Routing name cannot be changed'
            ).dict()
        routing = pygate_cache.get_cache('client_routing_cache', client_key)
        if not routing:
            routing = RoutingService.routing_collection.find_one({
                'client_key': client_key
            })
            if not routing:
                logger.error(request_id + " | Routing update failed with code ROUT004")
                return ResponseModel(
                    status_code=400,
                    error_code='ROUT004',
                    error_message='Routing does not exist'
                ).dict()
        else:
            pygate_cache.delete_cache('client_routing_cache', client_key)
        not_null_data = {k: v for k, v in data.dict().items() if v is not None}
        if not_null_data:
            update_result = RoutingService.routing_collection.update_one({'client_key': client_key}, {'$set': not_null_data})
            if not update_result.acknowledged or update_result.modified_count == 0:
                logger.error(request_id + " | Routing update failed with code ROUT006")
                return ResponseModel(
                    status_code=400,
                    error_code='ROUT006',
                    error_message='Database error: Unable to update routing'
                ).dict()
            logger.info(request_id + " | Routing update successful")
            return ResponseModel(
                status_code=200,
                message='Routing updated successfully'
            ).dict()
        else:
            logger.error(request_id + " | Routing update failed with code ROUT007")
            return ResponseModel(
                status_code=400,
                error_code='ROUT007',
                error_message='No data to update'
            ).dict()
        
    @staticmethod
    async def delete_routing(client_key, request_id):
        """
        Delete a routing.
        """
        logger.info(request_id + " | Deleting: " + client_key)
        routing = pygate_cache.get_cache('client_routing_cache', client_key)
        if not routing:
            routing = RoutingService.routing_collection.find_one({
                'client_key': client_key
            })
            if not routing:
                logger.error(request_id + " | Routing deletion failed with code ROUT004")
                return ResponseModel(
                    status_code=400,
                    error_code='ROUT004',
                    error_message='Routing does not exist'
                ).dict()
        else:
            pygate_cache.delete_cache('client_routing_cache', client_key)
        delete_result = RoutingService.routing_collection.delete_one({'client_key': client_key})
        if not delete_result.acknowledged or delete_result.deleted_count == 0:
            logger.error(request_id + " | Routing deletion failed with code ROUT008")
            return ResponseModel(
                status_code=400,
                error_code='ROUT008',
                error_message='Database error: Unable to delete routing'
            ).dict()
        logger.info(request_id + " | Routing deletion successful")
        return ResponseModel(
            status_code=200,
            message='Routing deleted successfully'
        ).dict()
    
    @staticmethod
    async def get_routing(client_key, request_id):
        """
        Get a routing.
        """
        logger.info(request_id + " | Getting: " + client_key)
        routing = pygate_cache.get_cache('client_routing_cache', client_key)
        if not routing:
            routing = RoutingService.routing_collection.find_one({
                'client_key': client_key
            })
            if not routing:
                logger.error(request_id + " | Routing retrieval failed with code ROUT004")
                return ResponseModel(
                    status_code=400,
                    error_code='ROUT004',
                    error_message='Routing does not exist'
                ).dict()
        logger.info(request_id + " | Routing retrieval successful")
        return ResponseModel(
            status_code=200,
            message='Routing retrieved successfully',
            data=routing
        ).dict()
    
    @staticmethod
    async def get_routings(page=1, page_size=10, request_id=None):
        """
        Get all routings.
        """
        logger.info(request_id + " | Getting routings: Page=" + str(page) + " Page Size=" + str(page_size))
        skip = (page - 1) * page_size
        cursor = RoutingService.routing_collection.find().sort('client_key', 1).skip(skip).limit(page_size)
        routings = cursor.to_list(length=None)
        if not routings:
            logger.error(request_id + " | Routing retrieval failed with code ROUT002")
            return ResponseModel(
                status_code=404,
                error_code='ROUT002',
                error_message='No routings found'
            ).dict()
        for route in routings:
            if route.get('_id'): del route['_id']
        logger.info(request_id + " | Routing retrieval successful")
        return ResponseModel(
            status_code=200,
            response={'routings': routings}
        ).dict()