"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from typing import List
from fastapi import HTTPException
from models.response_model import ResponseModel
from utils import password_util
from utils.database import user_collection, subscriptions_collection, api_collection
from utils.doorman_cache_util import doorman_cache
from models.create_user_model import CreateUserModel

import logging

from utils.role_util import platform_role_required_bool

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("doorman.gateway")

class UserService:

    @staticmethod
    async def get_user_by_email_with_password_helper(email):
        """
        Retrieve a user by email.
        """
        user = user_collection.find_one({'email': email})
        if user.get('_id'): del user['_id']
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    @staticmethod
    async def get_user_by_username_helper(username):
        """
        Retrieve a user by username.
        """
        try:
            user = doorman_cache.get_cache('user_cache', username)
            if not user:
                user = user_collection.find_one({'username': username})
                if not user:
                    raise HTTPException(status_code=404, detail="User not found")
                if user.get('_id'): del user['_id']
                if user.get('password'): del user['password']
                doorman_cache.set_cache('user_cache', username, user)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            return user
        except Exception as e:
            raise HTTPException(status_code=404, detail="User not found")
        
    @staticmethod
    async def get_user_by_username(username, request_id):
        """
        Retrieve a user by username.
        """
        logger.info(f"{request_id} | Getting user: {username}")
        user = doorman_cache.get_cache('user_cache', username)
        if not user:
            user = user_collection.find_one({'username': username})
            if not user:
                logger.error(f"{request_id} | User retrieval failed with code USR002")
                return ResponseModel(
                    status_code=404,
                    error_code='USR002',
                    error_message='User not found'
                ).dict()
            if user.get('_id'): del user['_id']
            if user.get('password'): del user['password']
            doorman_cache.set_cache('user_cache', username, user)
        if not user:
            logger.error(f"{request_id} | User retrieval failed with code USR002")
            return ResponseModel(
                status_code=404,
                response_headers={
                    "request_id": request_id
                },
                error_code='USR002',
                error_message='User not found'
            ).dict()
        logger.info(f"{request_id} | User retrieval successful")
        return ResponseModel(
            status_code=200,
            response=user
        ).dict()

    @staticmethod
    async def get_user_by_email(active_username, email, request_id):
        """
        Retrieve a user by email.
        """
        logger.info(f"{request_id} | Getting user by email: {email}")
        user = user_collection.find_one({'email': email})
        if '_id' in user:
            del user['_id']
        if 'password' in user:
            del user['password']
        if not user:
            logger.error(f"{request_id} | User retrieval failed with code USR002")
            return ResponseModel(
                status_code=404,
                response_headers={
                    "request_id": request_id
                },
                error_code='USR002',
                error_message='User not found'
            ).dict()
        logger.info(f"{request_id} | User retrieval successful")
        if not active_username == user.get('username') and not await platform_role_required_bool(active_username, 'manage_users'):
            logger.error(f"{request_id} | User retrieval failed with code USR008")
            return ResponseModel(
                    status_code=403,
                    error_code="USR008",
                    error_message="Unable to retrieve information for user",
                ).dict()
        return ResponseModel(
            status_code=200,
            response=user
        ).dict()

    @staticmethod
    async def create_user(data: CreateUserModel, request_id):
        """
        Create a new user.
        """
        logger.info(f"{request_id} | Creating user: {data.username}")
        if user_collection.find_one({'username': data.username}):
            logger.error(f"{request_id} | User creation failed with code USR001")
            return ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code='USR001',
                error_message='Username already exists'
            ).dict()
        if user_collection.find_one({'email': data.email}):
            logger.error(f"{request_id} | User creation failed with code USR001")
            return ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code='USR001',
                error_message='Email already exists'
            ).dict()
        if not password_util.is_secure_password(data.password):
            logger.error(f"{request_id} | User creation failed with code USR005")
            return ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code='USR005',
                error_message='Password must include at least 16 characters, one uppercase letter, one lowercase letter, one digit, and one special character'
            ).dict()
        data.password = password_util.hash_password(data.password)
        data_dict = data.dict()
        user_collection.insert_one(data_dict)
        if '_id' in data_dict:
            del data_dict['_id']
        if 'password' in data_dict:
            del data_dict['password']
        doorman_cache.set_cache('user_cache', data.username, data_dict)
        logger.info(f"{request_id} | User creation successful")
        return ResponseModel(
            status_code=201,
            response_headers={
                "request_id": request_id
            },
            message='User created successfully'
        ).dict()

    @staticmethod
    async def check_password_return_user(email, password):
        """
        Verify password and return user if valid.
        """
        try:
            user = await UserService.get_user_by_email_with_password_helper(email)
            if not password_util.verify_password(password, user.get('password')):
                raise HTTPException(status_code=400, detail="Invalid email or password")
            return user
        except Exception as e:
            raise HTTPException(status_code=400, detail="Invalid email or password")

    @staticmethod
    async def update_user(username, update_data, request_id):
        """
        Update user information.
        """
        logger.info(f"{request_id} | Updating user: {username}")
        user = doorman_cache.get_cache('user_cache', username)
        if not user:
            user = user_collection.find_one({'username': username})
            if not user:
                logger.error(f"{request_id} | User update failed with code USR002")
                return ResponseModel(
                    status_code=404,
                    error_code='USR002',
                    error_message='User not found'
                ).dict()
        else:
            doorman_cache.delete_cache('user_cache', username)
        non_null_update_data = {k: v for k, v in update_data.dict().items() if v is not None}
        if non_null_update_data:
            update_result = user_collection.update_one({'username': username}, {'$set': non_null_update_data})
            if not update_result.acknowledged or update_result.modified_count == 0:
                logger.error(f"{request_id} | User update failed with code USR003")
                return ResponseModel(
                    status_code=400,
                    error_code='USR004',
                    error_message='Unable to update user'
                ).dict()
        if non_null_update_data.get('role'):
            await UserService.purge_apis_after_role_change(username, request_id)
        logger.info(f"{request_id} | User update successful")
        return ResponseModel(
            status_code=200,
            response_headers={
                "request_id": request_id
            },
            message='User updated successfully'
        ).dict()
    
    @staticmethod
    async def delete_user(username, request_id):
        """
        Delete a user.
        """
        logger.info(f"{request_id} | Deleting user: {username}")
        user = doorman_cache.get_cache('user_cache', username)
        if not user:
            user = user_collection.find_one({'username': username})
            if not user:
                logger.error(f"{request_id} | User deletion failed with code USR002")
                return ResponseModel(
                    status_code=404,
                    error_code='USR002',
                    error_message='User not found'
                ).dict()
        delete_result = user_collection.delete_one({'username': username})
        if not delete_result.acknowledged or delete_result.deleted_count == 0:
            logger.error(f"{request_id} | User deletion failed with code USR003")
            return ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code='USR003',
                error_message='Unable to delete user'
            ).dict()
        doorman_cache.delete_cache('user_cache', username)
        doorman_cache.delete_cache('user_subscription_cache', username)
        logger.info(f"{request_id} | User deletion successful")
        return ResponseModel(
            status_code=200,
            response_headers={
                "request_id": request_id
            },
            message='User deleted successfully'
        ).dict()

    @staticmethod
    async def update_password(username, update_data, request_id):
        """
        Update user information.
        """
        logger.info(f"{request_id} | Updating password for user: {username}")
        if not password_util.is_secure_password(update_data.new_password):
            logger.error(f"{request_id} | User password update failed with code USR005")
            return ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code='USR005',
                error_message='Password must include at least 16 characters, one uppercase letter, one lowercase letter, one digit, and one special character'
            ).dict()
        hashed_password = password_util.hash_password(update_data.new_password)
        user_collection.update_one({'username': username}, {'$set': {'password': hashed_password}})
        user = user_collection.find_one({'username': username})
        if not user:
            logger.error(f"{request_id} | User password update failed with code USR002")
            return ResponseModel(
                status_code=404,
                response_headers={
                    "request_id": request_id
                },
                error_code='USR002',
                error_message='User not found'
            ).dict()
        if '_id' in user:
            del user['_id']
        if 'password' in user:
            del user['password']
        doorman_cache.set_cache('user_cache', username, user)
        logger.info(f"{request_id} | User password update successful")
        return ResponseModel(
            status_code=200,
            response_headers={
                "request_id": request_id
            },
            message='User updated successfully'
        ).dict()

    @staticmethod
    async def purge_apis_after_role_change(username, request_id):
        """
        Remove subscriptions after role change.
        """
        logger.info(f"{request_id} | Purging APIs for user: {username}")
        user_subscriptions = doorman_cache.get_cache('user_subscription_cache', username) or subscriptions_collection.find_one({'username': username})
        if user_subscriptions:
            for subscription in user_subscriptions.get('apis'):
                api_name, api_version = subscription.split('/')
                user = doorman_cache.get_cache('user_cache', username) or user_collection.find_one({'username': username})
                api = doorman_cache.get_cache('api_cache', f"{api_name}/{api_version}") or api_collection.find_one({'api_name': api_name, 'api_version': api_version})
                if api and api.get('role') and user.get('role') not in api.get('role'):
                    user_subscriptions['apis'].remove(subscription)
            subscriptions_collection.update_one(
                {'username': username},
                {'$set': {'apis': user_subscriptions.get('apis', [])}}
            )
            doorman_cache.set_cache('user_subscription_cache', username, user_subscriptions)
        logger.info(f"{request_id} | Purge successful")


    @staticmethod
    async def get_all_users(page, page_size, request_id):
        """
        Get all users.
        """
        logger.info(f"{request_id} | Getting all users: Page={page} Page Size={page_size}")
        skip = (page - 1) * page_size
        cursor = user_collection.find().sort('username', 1).skip(skip).limit(page_size)
        users = cursor.to_list(length=None)
        for user in users:
            if user.get('_id'): del user['_id']
            if user.get('password'): del user['password']
            for key, value in user.items():
                if isinstance(value, bytes):
                    user[key] = value.decode('utf-8')
        logger.info(f"{request_id} | User retrieval successful")
        return ResponseModel(
            status_code=200,
            response={'users': users}
        ).dict()