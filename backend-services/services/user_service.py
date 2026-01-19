"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import logging
import time

from fastapi import HTTPException

from models.create_user_model import CreateUserModel
from models.response_model import ResponseModel
from utils import password_util
from utils.async_db import (
    db_delete_one,
    db_find_list,
    db_find_one,
    db_insert_one,
    db_update_one,
    db_find_paginated,
)
from utils.bandwidth_util import get_current_usage
from utils.constants import ErrorCodes, Messages
from utils.database_async import api_collection, subscriptions_collection, user_collection
from utils.doorman_cache_util import doorman_cache
from utils.paging_util import validate_page_params
from utils.role_util import platform_role_required_bool

logger = logging.getLogger('doorman.gateway')


class UserService:
    @staticmethod
    async def get_user_by_email_with_password_helper(email: str) -> dict:
        """
        Retrieve a user by email.
        """
        user = await db_find_one(user_collection, {'email': email})
        if user.get('_id'):
            del user['_id']
        if not user:
            raise HTTPException(status_code=404, detail='User not found')
        return user

    @staticmethod
    async def get_user_by_username_helper(username: str) -> dict:
        """
        Retrieve a user by username.
        """
        try:
            user = doorman_cache.get_cache('user_cache', username)
            if not user:
                user = await db_find_one(user_collection, {'username': username})
                if not user:
                    raise HTTPException(status_code=404, detail='User not found')
                if user.get('_id'):
                    del user['_id']
                if user.get('password'):
                    del user['password']
                doorman_cache.set_cache('user_cache', username, user)
            if not user:
                raise HTTPException(status_code=404, detail='User not found')
            return user
        except Exception:
            raise HTTPException(status_code=404, detail='User not found')

    @staticmethod
    async def get_user_by_username(username: str, request_id: str) -> dict:
        """
        Retrieve a user by username.
        """
        logger.info(f'{request_id} | Getting user: {username}')
        user = doorman_cache.get_cache('user_cache', username)
        if not user:
            user = await db_find_one(user_collection, {'username': username})
            if not user:
                logger.error(f'{request_id} | User retrieval failed with code USR002')
                return ResponseModel(
                    status_code=404, error_code='USR002', error_message='User not found'
                ).dict()
            if user.get('_id'):
                del user['_id']
            if user.get('password'):
                del user['password']
            doorman_cache.set_cache('user_cache', username, user)
        if not user:
            logger.error(f'{request_id} | User retrieval failed with code USR002')
            return ResponseModel(
                status_code=404,
                response_headers={'request_id': request_id},
                error_code='USR002',
                error_message='User not found',
            ).dict()
        try:
            limit = user.get('bandwidth_limit_bytes')
            enabled = user.get('bandwidth_limit_enabled')
            if (enabled is not False) and limit and int(limit) > 0:
                window = user.get('bandwidth_limit_window') or 'day'
                used = int(get_current_usage(username, window))
                mapping = {
                    'second': 1,
                    'minute': 60,
                    'hour': 3600,
                    'day': 86400,
                    'week': 604800,
                    'month': 2592000,
                }
                sec = mapping.get(str(window).lower().rstrip('s'), 86400)
                now = int(time.time())
                bucket_start = (now // sec) * sec
                resets_at = bucket_start + sec
                user['bandwidth_usage_bytes'] = used
                user['bandwidth_resets_at'] = resets_at
        except Exception:
            pass
        logger.info(f'{request_id} | User retrieval successful')
        return ResponseModel(status_code=200, response=user).dict()

    @staticmethod
    async def get_user_by_email(active_username: str, email: str, request_id: str) -> dict:
        """
        Retrieve a user by email.
        """
        logger.info(f'{request_id} | Getting user by email: {email}')
        user = await db_find_one(user_collection, {'email': email})
        if not user:
            logger.error(f'{request_id} | User retrieval failed with code USR002')
            return ResponseModel(
                status_code=404,
                response_headers={'request_id': request_id},
                error_code='USR002',
                error_message='User not found',
            ).dict()
        if '_id' in user:
            del user['_id']
        if 'password' in user:
            del user['password']
        logger.info(f'{request_id} | User retrieval successful')
        if not active_username == user.get('username') and not await platform_role_required_bool(
            active_username, 'manage_users'
        ):
            logger.error(f'{request_id} | User retrieval failed with code USR008')
            return ResponseModel(
                status_code=403,
                error_code='USR008',
                error_message='Unable to retrieve information for user',
            ).dict()
        return ResponseModel(status_code=200, response=user).dict()

    @staticmethod
    async def create_user(data: CreateUserModel, request_id: str) -> dict:
        """
        Create a new user.
        """
        logger.info(f'{request_id} | Creating user: {data.username}')
        try:
            if data.custom_attributes is not None and len(data.custom_attributes.keys()) > 10:
                logger.error(
                    f'{request_id} | User creation failed with code USR016: Too many custom attributes'
                )
                return ResponseModel(
                    status_code=400,
                    response_headers={'request_id': request_id},
                    error_code='USR016',
                    error_message='Maximum 10 custom attributes allowed. Please replace an existing one.',
                ).dict()
        except Exception:
            logger.error(
                f'{request_id} | User creation failed with code USR016: Invalid custom attributes payload'
            )
            return ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='USR016',
                error_message='Maximum 10 custom attributes allowed. Please replace an existing one.',
            ).dict()
        if await db_find_one(user_collection, {'username': data.username}):
            logger.error(f'{request_id} | User creation failed with code USR001')
            return ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='USR001',
                error_message='Username already exists',
            ).dict()
        if await db_find_one(user_collection, {'email': data.email}):
            logger.error(f'{request_id} | User creation failed with code USR001')
            return ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='USR001',
                error_message='Email already exists',
            ).dict()
        if not password_util.is_secure_password(data.password):
            logger.error(f'{request_id} | User creation failed with code USR005')
            return ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='USR005',
                error_message='Password must include at least 16 characters, one uppercase letter, one lowercase letter, one digit, and one special character',
            ).dict()
        data.password = password_util.hash_password(data.password)
        data_dict = data.dict()
        await db_insert_one(user_collection, data_dict)
        if '_id' in data_dict:
            del data_dict['_id']
        if 'password' in data_dict:
            del data_dict['password']
        doorman_cache.set_cache('user_cache', data.username, data_dict)
        logger.info(f'{request_id} | User creation successful')
        return ResponseModel(
            status_code=201,
            response_headers={'request_id': request_id},
            message='User created successfully',
        ).dict()

    @staticmethod
    async def check_password_return_user(email: str, password: str) -> dict:
        """
        Verify password and return user if valid.
        """
        try:
            try:
                user = await UserService.get_user_by_email_with_password_helper(email)
            except Exception:
                maybe_user = await db_find_one(user_collection, {'username': email})
                if maybe_user:
                    user = maybe_user
                else:
                    raise
            if not password_util.verify_password(password, user.get('password')):
                raise HTTPException(status_code=400, detail='Invalid email or password')
            return user
        except Exception:
            raise HTTPException(status_code=400, detail='Invalid email or password')

    @staticmethod
    async def update_user(username: str, update_data: dict, request_id: str) -> dict:
        """
        Update user information.
        """
        logger.info(f'{request_id} | Updating user: {username}')
        user = doorman_cache.get_cache('user_cache', username)
        if not user:
            user = await db_find_one(user_collection, {'username': username})
            if not user:
                logger.error(f'{request_id} | User update failed with code USR002')
                return ResponseModel(
                    status_code=404, error_code='USR002', error_message='User not found'
                ).dict()
        else:
            doorman_cache.delete_cache('user_cache', username)
        non_null_update_data = {k: v for k, v in update_data.dict().items() if v is not None}
        if 'custom_attributes' in non_null_update_data:
            try:
                if (
                    non_null_update_data['custom_attributes'] is not None
                    and len(non_null_update_data['custom_attributes'].keys()) > 10
                ):
                    logger.error(
                        f'{request_id} | User update failed with code USR016: Too many custom attributes'
                    )
                    return ResponseModel(
                        status_code=400,
                        error_code='USR016',
                        error_message='Maximum 10 custom attributes allowed. Please replace an existing one.',
                    ).dict()
            except Exception:
                logger.error(
                    f'{request_id} | User update failed with code USR016: Invalid custom attributes payload'
                )
                return ResponseModel(
                    status_code=400,
                    error_code='USR016',
                    error_message='Maximum 10 custom attributes allowed. Please replace an existing one.',
                ).dict()
        if non_null_update_data:
            try:
                update_result = await db_update_one(
                    user_collection, {'username': username}, {'$set': non_null_update_data}
                )
                if update_result.modified_count > 0:
                    doorman_cache.delete_cache('user_cache', username)
                if not update_result.acknowledged or update_result.modified_count == 0:
                    logger.error(f'{request_id} | User update failed with code USR003')
                    return ResponseModel(
                        status_code=400, error_code='USR004', error_message='Unable to update user'
                    ).dict()
            except Exception as e:
                doorman_cache.delete_cache('user_cache', username)
                logger.error(
                    f'{request_id} | User update failed with exception: {str(e)}', exc_info=True
                )
                raise
        if non_null_update_data.get('role'):
            await UserService.purge_apis_after_role_change(username, request_id)
        logger.info(f'{request_id} | User update successful')
        return ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            message='User updated successfully',
        ).dict()

    @staticmethod
    async def delete_user(username: str, request_id: str) -> dict:
        """
        Delete a user.
        """
        logger.info(f'{request_id} | Deleting user: {username}')
        user = doorman_cache.get_cache('user_cache', username)
        if not user:
            user = await db_find_one(user_collection, {'username': username})
            if not user:
                logger.error(f'{request_id} | User deletion failed with code USR002')
                return ResponseModel(
                    status_code=404, error_code='USR002', error_message='User not found'
                ).dict()
        delete_result = await db_delete_one(user_collection, {'username': username})
        if not delete_result.acknowledged or delete_result.deleted_count == 0:
            logger.error(f'{request_id} | User deletion failed with code USR003')
            return ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='USR003',
                error_message='Unable to delete user',
            ).dict()
        doorman_cache.delete_cache('user_cache', username)
        doorman_cache.delete_cache('user_subscription_cache', username)
        logger.info(f'{request_id} | User deletion successful')
        return ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            message='User deleted successfully',
        ).dict()

    @staticmethod
    async def update_password(username: str, update_data: dict, request_id: str) -> dict:
        """
        Update user information.
        """
        logger.info(f'{request_id} | Updating password for user: {username}')
        if not password_util.is_secure_password(update_data.new_password):
            logger.error(f'{request_id} | User password update failed with code USR005')
            return ResponseModel(
                status_code=400,
                response_headers={'request_id': request_id},
                error_code='USR005',
                error_message='Password must include at least 16 characters, one uppercase letter, one lowercase letter, one digit, and one special character',
            ).dict()
        hashed_password = password_util.hash_password(update_data.new_password)
        try:
            update_result = await db_update_one(
                user_collection, {'username': username}, {'$set': {'password': hashed_password}}
            )
            if update_result.modified_count > 0:
                doorman_cache.delete_cache('user_cache', username)
        except Exception as e:
            doorman_cache.delete_cache('user_cache', username)
            logger.error(
                f'{request_id} | User password update failed with exception: {str(e)}',
                exc_info=True,
            )
            raise
        user = await db_find_one(user_collection, {'username': username})
        if not user:
            logger.error(f'{request_id} | User password update failed with code USR002')
            return ResponseModel(
                status_code=404,
                response_headers={'request_id': request_id},
                error_code='USR002',
                error_message='User not found',
            ).dict()
        if '_id' in user:
            del user['_id']
        if 'password' in user:
            del user['password']
        doorman_cache.set_cache('user_cache', username, user)
        logger.info(f'{request_id} | User password update successful')
        return ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            message='User updated successfully',
        ).dict()

    @staticmethod
    async def purge_apis_after_role_change(username: str, request_id: str) -> None:
        """
        Remove subscriptions after role change.
        """
        logger.info(f'{request_id} | Purging APIs for user: {username}')
        user_subscriptions = doorman_cache.get_cache(
            'user_subscription_cache', username
        ) or await db_find_one(subscriptions_collection, {'username': username})
        if user_subscriptions:
            for subscription in user_subscriptions.get('apis'):
                api_name, api_version = subscription.split('/')
                user = doorman_cache.get_cache('user_cache', username) or await db_find_one(
                    user_collection, {'username': username}
                )
                api = doorman_cache.get_cache(
                    'api_cache', f'{api_name}/{api_version}'
                ) or await db_find_one(
                    api_collection, {'api_name': api_name, 'api_version': api_version}
                )
                if api and api.get('role') and user.get('role') not in api.get('role'):
                    user_subscriptions['apis'].remove(subscription)
            try:
                update_result = await db_update_one(
                    subscriptions_collection,
                    {'username': username},
                    {'$set': {'apis': user_subscriptions.get('apis', [])}},
                )
                if update_result.modified_count > 0:
                    doorman_cache.delete_cache('user_subscription_cache', username)
                    doorman_cache.set_cache('user_subscription_cache', username, user_subscriptions)
            except Exception as e:
                doorman_cache.delete_cache('user_subscription_cache', username)
                logger.error(
                    f'{request_id} | Subscription update failed with exception: {str(e)}',
                    exc_info=True,
                )
                raise
        logger.info(f'{request_id} | Purge successful')

    @staticmethod
    async def get_all_users(page: int, page_size: int, request_id: str) -> dict:
        """
        Get all users.
        """
        logger.info(f'{request_id} | Getting all users: Page={page} Page Size={page_size}')
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
        docs = await db_find_paginated(
            user_collection, {}, skip=skip, limit=page_size, sort=[('username', 1)]
        )
        # Compute metadata
        has_next = False
        try:
            # Fetch one extra to detect next page without a separate query
            extra = await db_find_paginated(
                user_collection, {}, skip=skip, limit=page_size + 1, sort=[('username', 1)]
            )
            has_next = len(extra) > page_size
        except Exception:
            pass
        try:
            from utils.async_db import db_count
            total = await db_count(user_collection, {})
        except Exception:
            total = None

        users = docs
        for user in users:
            if user.get('_id'):
                del user['_id']
            if user.get('password'):
                del user['password']
            for key, value in user.items():
                if isinstance(value, bytes):
                    user[key] = value.decode('utf-8')
        logger.info(f'{request_id} | User retrieval successful')
        return ResponseModel(
            status_code=200,
            response={
                'users': users,
                'page': page,
                'page_size': page_size,
                'has_next': has_next,
                **({'total': total} if total is not None else {}),
            },
        ).dict()
