"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from models.response_model import ResponseModel
from models.token_model import TokenModel
from utils.database import token_def_collection
from utils.doorman_cache_util import doorman_cache
from pymongo.errors import PyMongoError

import logging
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("doorman.gateway")

class TokenService:

    @staticmethod
    def _validate_token_data(data: TokenModel) -> Optional[ResponseModel]:
        """Validate token data before creation or update."""
        if not data.api_token_group:
            return ResponseModel(
                status_code=400,
                error_code='TKN009',
                error_message='Token group name is required'
            )
        if not data.token_type:
            return ResponseModel(
                status_code=400,
                error_code='TKN010',
                error_message='Token type is required'
            )
        return None

    @staticmethod
    async def create_token(data: TokenModel, request_id):
        """
        Create a token.
        """
        logger.info(request_id + " | Creating Token: " + data.api_token_group)
        validation_error = TokenService._validate_token_data(data)
        if validation_error:
            logger.error(request_id + f" | Token creation failed with code {validation_error.error_code}")
            return validation_error.dict()
        try:
            if doorman_cache.get_cache('token_def_cache', data.api_token_group) or token_def_collection.find_one({'token_name': data.api_token_group}):
                logger.error(request_id + " | Token creation failed with code TKN001")
                return ResponseModel(
                    status_code=400,
                    error_code='TKN001',
                    error_message='Token group already exists'
                ).dict()
            token_data_dict = data.dict()
            insert_result = token_def_collection.insert_one(token_data_dict)
            if not insert_result.acknowledged:
                logger.error(request_id + " | Token creation failed with code TKN002")
                return ResponseModel(
                    status_code=400, 
                    error_code='TKN002', 
                    error_message='Unable to insert token'
                ).dict()
            token_data_dict['_id'] = str(insert_result.inserted_id)
            doorman_cache.set_cache('token_def_cache', data.api_token_group, token_data_dict)
            logger.info(request_id + " | Token creation successful")
            return ResponseModel(
                status_code=201,
                response_headers={
                    "request_id": request_id
                },
                message='Token created successfully'
            ).dict()
        except PyMongoError as e:
            logger.error(request_id + f" | Token creation failed with database error: {str(e)}")
            return ResponseModel(
                status_code=500,
                error_code='TKN011',
                error_message='Database error occurred while creating token'
            ).dict()
    
    @staticmethod
    async def update_token(api_token_group, data: TokenModel, request_id):
        """
        Update an API on the platform.
        """
        logger.info(request_id + " | Updating token: " + api_token_group)
        validation_error = TokenService._validate_token_data(data)
        if validation_error:
            logger.error(request_id + f" | Token update failed with code {validation_error.error_code}")
            return validation_error.dict()
        try:
            if data.api_token_group and data.api_token_group != api_token_group:
                logger.error(request_id + " | Token update failed with code TKN003")
                return ResponseModel(
                    status_code=400, 
                    error_code='TKN003', 
                    error_message='Token api group name cannot be updated'
                ).dict()
            token = doorman_cache.get_cache('token_def_cache', api_token_group)
            if not token:
                token = token_def_collection.find_one({'api_token_group': api_token_group})
                if not token:
                    logger.error(request_id + " | Token update failed with code TKN004")
                    return ResponseModel(
                        status_code=400, 
                        error_code='TKN004', 
                        error_message='Token does not exist for the request api token group'
                    ).dict()
            else:
                doorman_cache.delete_cache('token_def_cache', api_token_group)
            not_null_data = {k: v for k, v in data.dict().items() if v is not None}
            if not_null_data:
                update_result = token_def_collection.update_one(
                    {'api_token_group': api_token_group},
                    {'$set': not_null_data}
                )
                if not update_result.acknowledged or update_result.modified_count == 0:
                    logger.error(request_id + " | Token update failed with code TKN005")
                    return ResponseModel(
                        status_code=400, 
                        error_code='TKN005', 
                        error_message='Unable to update token'
                    ).dict()
                logger.info(request_id + " | Token updated successful")
                return ResponseModel(
                    status_code=200,
                    message='Token updated successfully'
                ).dict()
            else:
                logger.error(request_id + " | Token update failed with code TKN006")
                return ResponseModel(
                    status_code=400, 
                    error_code='TKN006', 
                    error_message='No data to update'
                ).dict()
        except PyMongoError as e:
            logger.error(request_id + f" | Token update failed with database error: {str(e)}")
            return ResponseModel(
                status_code=500,
                error_code='TKN012',
                error_message='Database error occurred while updating token'
            ).dict()
    
    @staticmethod
    async def delete_token(api_token_group, request_id):
        """
        Delete a token.
        """
        logger.info(request_id + " | Deleting token: " + api_token_group)
        try:
            token = doorman_cache.get_cache('token_def_cache', api_token_group)
            if not token:
                token = token_def_collection.find_one({'api_token_group': api_token_group})
                if not token:
                    logger.error(request_id + " | Token deletion failed with code TKN007")
                    return ResponseModel(
                        status_code=400, 
                        error_code='TKN007', 
                        error_message='Token does not exist for the request api token group'
                    ).dict()
            else:
                doorman_cache.delete_cache('token_def_cache', api_token_group)
            delete_result = token_def_collection.delete_one({'api_token_group': api_token_group})
            if not delete_result.acknowledged or delete_result.deleted_count == 0:
                logger.error(request_id + " | Token deletion failed with code TKN008")
                return ResponseModel(
                    status_code=400, 
                    error_code='TKN008', 
                    error_message='Unable to delete token'
                ).dict()
            logger.info(request_id + " | Token deletion successful")
            return ResponseModel(
                status_code=200,
                message='Token deleted successfully'
            ).dict()
        except PyMongoError as e:
            logger.error(request_id + f" | Token deletion failed with database error: {str(e)}")
            return ResponseModel(
                status_code=500,
                error_code='TKN013',
                error_message='Database error occurred while deleting token'
            ).dict()
