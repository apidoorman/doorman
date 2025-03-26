"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from utils import password_util
from utils.database import db
from services.cache import pygate_cache
from models.create_user_model import CreateUserModel

import logging

class UserService:
    user_collection = db.users

    @staticmethod
    async def get_user_by_username(username):
        """
        Retrieve a user by username.
        """
        try:
            user = pygate_cache.get_cache('user_cache', username) or await UserService.user_collection.find_one({'username': username})
            if '_id' in user:
                del user['_id']
            if 'password' in user:
                del user['password']
            if not user:
                raise ValueError("User not found")
            return user
        except Exception as e:
            raise ValueError("User not found")

    @staticmethod
    async def get_user_by_email(email):
        """
        Retrieve a user by email.
        """
        try:
            user = UserService.user_collection.find_one({'email': email})
            if '_id' in user:
                del user['_id']
            if 'password' in user:
                del user['password']
            if not user:
                raise ValueError("User not found")
            return user
        except Exception as e:
            raise ValueError("User not found")
        
    @staticmethod
    async def get_user_by_email_with_password(email):
        """
        Retrieve a user by email.
        """
        try:
            user = UserService.user_collection.find_one({'email': email})
            if '_id' in user:
                del user['_id']
            if not user:
                raise ValueError("User not found")
            return user
        except Exception as e:
            raise ValueError("User not found")

    @staticmethod
    async def create_user(data: CreateUserModel):
        """
        Create a new user.
        """
        if UserService.user_collection.find_one({'username': data.username}):
            raise ValueError("Username already exists")
        
        if UserService.user_collection.find_one({'email': data.email}):
            raise ValueError("Email already exists")

        data.password = password_util.hash_password(data.password)

        data_dict = data.dict()
        UserService.user_collection.insert_one(data_dict)
        if '_id' in data_dict:
            del data_dict['_id']
        if 'password' in data_dict:
            del data_dict['password']
        pygate_cache.set_cache('user_cache', data.username, data_dict)

    @staticmethod
    async def check_password_return_user(email, password):
        """
        Verify password and return user if valid.
        """
        try:
            user = await UserService.get_user_by_email_with_password(email)
            
            if not password_util.verify_password(password, user.get('password')):
                raise ValueError("Invalid email or password")
            
            return user
            
        except Exception as e:
            logging.error(f"Error in check_password_return_user: {str(e)}")
            raise ValueError("Authentication failed")

    @staticmethod
    async def update_user(username, update_data):
        """
        Update user information.
        """
        update_data_dict = update_data.dict()
        non_null_update_data = {key: value for key, value in update_data_dict.items() if value is not None}
        if non_null_update_data:
            UserService.user_collection.update_one({'username': username}, {'$set': non_null_update_data})
        user = UserService.user_collection.find_one({'username': username})
        if '_id' in user:
            del user['_id']
        if 'password' in user:
            del user['password']
        pygate_cache.set_cache('user_cache', username, user)

    @staticmethod
    async def update_password(username, update_data):
        """
        Update user information.
        """
        hashed_password = password_util.hash_password(update_data.new_password)
        UserService.user_collection.update_one({'username': username}, {'$set': {'password': hashed_password}})
        user = UserService.user_collection.find_one({'username': username})
        if '_id' in user:
            del user['_id']
        if 'password' in user:
            del user['password']
        pygate_cache.set_cache('user_cache', username, user)