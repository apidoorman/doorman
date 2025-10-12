"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

# External imports
from pymongo.errors import PyMongoError
import logging
from typing import Optional

# Internal imports
from models.response_model import ResponseModel
from models.credit_model import CreditModel
from models.user_credits_model import UserCreditModel
from utils.database_async import credit_def_collection, user_credit_collection
from utils.async_db import db_find_one, db_insert_one, db_update_one, db_delete_one, db_find_list
from utils.encryption_util import encrypt_value, decrypt_value
from utils.doorman_cache_util import doorman_cache
from utils.paging_util import validate_page_params
from utils.constants import ErrorCodes, Messages

logger = logging.getLogger('doorman.gateway')

class CreditService:

    @staticmethod
    def _validate_credit_data(data: CreditModel) -> Optional[ResponseModel]:
        """Validate credit definition data before creation or update."""
        if not data.api_credit_group:
            return ResponseModel(
                status_code=400,
                error_code='CRD009',
                error_message='Credit group name is required'
            )
        if not data.api_key or not data.api_key_header:
            return ResponseModel(
                status_code=400,
                error_code='CRD010',
                error_message='API key and header are required'
            )
        return None

    @staticmethod
    async def create_credit(data: CreditModel, request_id):
        """Create a credit definition."""
        logger.info(request_id + ' | Creating credit definition')
        validation_error = CreditService._validate_credit_data(data)
        if validation_error:
            logger.error(request_id + f' | Credit creation failed with code {validation_error.error_code}')
            return validation_error.dict()
        try:
            if doorman_cache.get_cache('credit_def_cache', data.api_credit_group) or await db_find_one(credit_def_collection, {'api_credit_group': data.api_credit_group}):
                logger.error(request_id + ' | Credit creation failed with code CRD001')
                return ResponseModel(
                    status_code=400,
                    error_code='CRD001',
                    error_message='Credit group already exists'
                ).dict()
            credit_data = data.dict()
            if credit_data.get('api_key') is not None:
                credit_data['api_key'] = encrypt_value(credit_data['api_key'])
            if credit_data.get('api_key_new') is not None:
                credit_data['api_key_new'] = encrypt_value(credit_data['api_key_new'])
            insert_result = await db_insert_one(credit_def_collection, credit_data)
            if not insert_result.acknowledged:
                logger.error(request_id + ' | Credit creation failed with code CRD002')
                return ResponseModel(
                    status_code=400,
                    error_code='CRD002',
                    error_message='Unable to insert credit definition'
                ).dict()
            credit_data['_id'] = str(insert_result.inserted_id)
            doorman_cache.set_cache('credit_def_cache', data.api_credit_group, credit_data)
            logger.info(request_id + ' | Credit creation successful')
            return ResponseModel(
                status_code=201,
                response_headers={'request_id': request_id},
                message='Credit definition created successfully'
            ).dict()
        except PyMongoError as e:
            logger.error(request_id + f' | Credit creation failed with database error: {str(e)}')
            return ResponseModel(
                status_code=500,
                error_code='CRD011',
                error_message='Database error occurred while creating credit definition'
            ).dict()

    @staticmethod
    async def update_credit(api_credit_group: str, data: CreditModel, request_id):
        """Update a credit definition."""
        logger.info(request_id + ' | Updating credit definition')
        validation_error = CreditService._validate_credit_data(data)
        if validation_error:
            logger.error(request_id + f' | Credit update failed with code {validation_error.error_code}')
            return validation_error.dict()
        try:
            if data.api_credit_group and data.api_credit_group != api_credit_group:
                logger.error(request_id + ' | Credit update failed with code CRD003')
                return ResponseModel(
                    status_code=400,
                    error_code='CRD003',
                    error_message='Credit group name cannot be updated'
                ).dict()
            doc = doorman_cache.get_cache('credit_def_cache', api_credit_group)
            if not doc:
                doc = await db_find_one(credit_def_collection, {'api_credit_group': api_credit_group})
                if not doc:
                    logger.error(request_id + ' | Credit update failed with code CRD004')
                    return ResponseModel(
                        status_code=400,
                        error_code='CRD004',
                        error_message='Credit definition does not exist for the requested group'
                    ).dict()
            else:
                doorman_cache.delete_cache('credit_def_cache', api_credit_group)
            not_null = {k: v for k, v in data.dict().items() if v is not None}
            if 'api_key' in not_null:
                not_null['api_key'] = encrypt_value(not_null['api_key'])
            if 'api_key_new' in not_null:
                not_null['api_key_new'] = encrypt_value(not_null['api_key_new'])
            if not_null:
                update_result = await db_update_one(credit_def_collection, {'api_credit_group': api_credit_group}, {'$set': not_null})
                if not update_result.acknowledged or update_result.modified_count == 0:
                    logger.error(request_id + ' | Credit update failed with code CRD005')
                    return ResponseModel(
                        status_code=400,
                        error_code='CRD005',
                        error_message='Unable to update credit definition'
                    ).dict()
                logger.info(request_id + ' | Credit update successful')
                return ResponseModel(status_code=200, message='Credit definition updated successfully').dict()
            else:
                logger.error(request_id + ' | Credit update failed with code CRD006')
                return ResponseModel(status_code=400, error_code='CRD006', error_message='No data to update').dict()
        except PyMongoError as e:
            logger.error(request_id + f' | Credit update failed with database error: {str(e)}')
            return ResponseModel(status_code=500, error_code='CRD012', error_message='Database error occurred while updating credit definition').dict()

    @staticmethod
    async def delete_credit(api_credit_group: str, request_id):
        """Delete a credit definition."""
        logger.info(request_id + ' | Deleting credit definition')
        try:
            doc = doorman_cache.get_cache('credit_def_cache', api_credit_group)
            if not doc:
                doc = await db_find_one(credit_def_collection, {'api_credit_group': api_credit_group})
                if not doc:
                    logger.error(request_id + ' | Credit deletion failed with code CRD007')
                    return ResponseModel(status_code=400, error_code='CRD007', error_message='Credit definition does not exist for the requested group').dict()
            else:
                doorman_cache.delete_cache('credit_def_cache', api_credit_group)
            delete_result = await db_delete_one(credit_def_collection, {'api_credit_group': api_credit_group})
            if not delete_result.acknowledged or delete_result.deleted_count == 0:
                logger.error(request_id + ' | Credit deletion failed with code CRD008')
                return ResponseModel(status_code=400, error_code='CRD008', error_message='Unable to delete credit definition').dict()
            logger.info(request_id + ' | Credit deletion successful')
            return ResponseModel(status_code=200, message='Credit definition deleted successfully').dict()
        except PyMongoError as e:
            logger.error(request_id + f' | Credit deletion failed with database error: {str(e)}')
            return ResponseModel(status_code=500, error_code='CRD013', error_message='Database error occurred while deleting credit definition').dict()

    @staticmethod
    async def list_credit_defs(page: int, page_size: int, request_id):
        """List credit definitions (masked), paginated."""
        logger.info(request_id + ' | Listing credit definitions')
        try:
            try:
                page, page_size = validate_page_params(page, page_size)
            except Exception as e:
                return ResponseModel(
                    status_code=400,
                    error_code=ErrorCodes.PAGE_SIZE,
                    error_message=(Messages.PAGE_TOO_LARGE if 'page_size' in str(e) else Messages.INVALID_PAGING)
                ).dict()
            all_defs = await db_find_list(credit_def_collection, {})
            all_defs.sort(key=lambda d: d.get('api_credit_group'))
            start = max((page - 1), 0) * page_size if page and page_size else 0
            end = start + page_size if page and page_size else None
            items = []
            for doc in all_defs[start:end]:
                if doc.get('_id'):
                    del doc['_id']
                items.append({
                    'api_credit_group': doc.get('api_credit_group'),
                    'api_key_header': doc.get('api_key_header'),
                    'api_key_present': bool(doc.get('api_key')),
                    'credit_tiers': doc.get('credit_tiers', []),
                })
            return ResponseModel(status_code=200, response={'items': items}).dict()
        except PyMongoError as e:
            logger.error(request_id + f' | Credit list failed with database error: {str(e)}')
            return ResponseModel(status_code=500, error_code='CRD020', error_message='Database error occurred while listing credit definitions').dict()

    @staticmethod
    async def get_credit_def(api_credit_group: str, request_id):
        """Get a single credit definition (masked)."""
        logger.info(request_id + ' | Getting credit definition')
        try:
            doc = credit_def_collection.find_one({'api_credit_group': api_credit_group})
            if not doc:
                return ResponseModel(status_code=404, error_code='CRD021', error_message='Credit definition not found').dict()
            if doc.get('_id'):
                del doc['_id']
            masked = {
                'api_credit_group': doc.get('api_credit_group'),
                'api_key_header': doc.get('api_key_header'),
                'api_key_present': bool(doc.get('api_key')),
                'credit_tiers': doc.get('credit_tiers', []),
            }
            return ResponseModel(status_code=200, response=masked).dict()
        except PyMongoError as e:
            logger.error(request_id + f' | Credit fetch failed with database error: {str(e)}')
            return ResponseModel(status_code=500, error_code='CRD022', error_message='Database error occurred while retrieving credit definition').dict()

    @staticmethod
    async def add_credits(username: str, data: UserCreditModel, request_id):
        """Add or update a user's credit balances for one or more groups."""
        logger.info(request_id + f' | Adding credits for user: {username}')
        try:
            if data.username and data.username != username:
                return ResponseModel(status_code=400, error_code='CRD014', error_message='Username in body does not match path').dict()
            doc = user_credit_collection.find_one({'username': username})
            users_credits = data.users_credits or {}
            secured = {}
            for group, info in users_credits.items():
                info = dict(info or {})
                if 'user_api_key' in info and info['user_api_key'] is not None:
                    info['user_api_key'] = encrypt_value(info['user_api_key'])
                secured[group] = info
            payload = {'username': username, 'users_credits': secured}
            if doc:
                user_credit_collection.update_one({'username': username}, {'$set': {'users_credits': secured}})
            else:
                user_credit_collection.insert_one(payload)
            return ResponseModel(status_code=200, message='Credits saved successfully').dict()
        except PyMongoError as e:
            logger.error(request_id + f' | Add credits failed with database error: {str(e)}')
            return ResponseModel(status_code=500, error_code='CRD015', error_message='Database error occurred while saving user credits').dict()

    @staticmethod
    async def get_all_credits(page: int, page_size: int, request_id, search: str = ''):
        logger.info(request_id + " | Getting all users' credits")
        try:
            try:
                page, page_size = validate_page_params(page, page_size)
            except Exception as e:
                return ResponseModel(
                    status_code=400,
                    error_code=ErrorCodes.PAGE_SIZE,
                    error_message=(Messages.PAGE_TOO_LARGE if 'page_size' in str(e) else Messages.INVALID_PAGING)
                ).dict()

            cursor = user_credit_collection.find().sort('username', 1)
            all_items = cursor.to_list(length=None)
            term = (search or '').strip().lower()
            if term:
                filtered = []
                for it in all_items:
                    uname = str(it.get('username', '')).lower()
                    groups = list((it.get('users_credits') or {}).keys())
                    if uname.find(term) != -1 or any(term in str(g).lower() for g in groups):
                        filtered.append(it)
                items_src = filtered
            else:
                items_src = all_items

            start = max((page - 1), 0) * page_size
            end = start + page_size if page_size else None
            items = items_src[start:end]
            for it in items:
                if it.get('_id'):
                    del it['_id']
                uc = it.get('users_credits') or {}
                for g, info in uc.items():
                    if isinstance(info, dict) and 'user_api_key' in info:
                        dec = decrypt_value(info.get('user_api_key'))
                        if dec is not None:
                            info['user_api_key'] = dec
            return ResponseModel(status_code=200, response={'user_credits': items}).dict()
        except PyMongoError as e:
            logger.error(request_id + f' | Get all credits failed with database error: {str(e)}')
            return ResponseModel(status_code=500, error_code='CRD016', error_message='Database error occurred while retrieving credits').dict()

    @staticmethod
    async def get_user_credits(username: str, request_id):
        logger.info(request_id + f' | Getting credits for user: {username}')
        try:
            doc = user_credit_collection.find_one({'username': username})
            if not doc:
                return ResponseModel(status_code=404, error_code='CRD017', error_message='User credits not found').dict()
            if doc.get('_id'):
                del doc['_id']
            uc = doc.get('users_credits') or {}
            for g, info in uc.items():
                if isinstance(info, dict) and 'user_api_key' in info:
                    dec = decrypt_value(info.get('user_api_key'))
                    if dec is not None:
                        info['user_api_key'] = dec
            return ResponseModel(status_code=200, response=doc).dict()
        except PyMongoError as e:
            logger.error(request_id + f' | Get user credits failed with database error: {str(e)}')
            return ResponseModel(status_code=500, error_code='CRD018', error_message='Database error occurred while retrieving user credits').dict()
