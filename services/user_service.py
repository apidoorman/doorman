"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from utils import password_util
from utils.database import db
from services.cache import pygate_cache
from models.create_user_model import CreateUserModel

class UserService:
    user_collection = db.users
    subscriptions_collection = db.subscriptions
    api_collection = db.apis

    @staticmethod
    async def get_user_by_username(username):
        """
        Retrieve a user by username.
        """
        try:
            user = pygate_cache.get_cache('user_cache', username)
            if not user:
                user = UserService.user_collection.find_one({'username': username})
                if not user:
                    raise ValueError("User not found in database")
                if user.get('_id'): del user['_id']
                if user.get('password'): del user['password']
                pygate_cache.set_cache('user_cache', username, user)
            if '_id' in user:
                del user['_id']
            if 'password' in user:
                del user['password']
            if not user:
                raise ValueError("User not found")
            return user
        except Exception as e:
            raise ValueError("User not found error" + str(e))

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
        if non_null_update_data.get('role'):
            await UserService.purge_apis_after_role_change(username)
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

    @staticmethod
    async def purge_apis_after_role_change(username):
        """
        Remove subscriptions after role change.
        """
        user_subscriptions = pygate_cache.get_cache('user_subscription_cache', username) or UserService.subscriptions_collection.find_one({'username': username})
        for subscription in user_subscriptions.get('apis'):
            api_name, api_version = subscription.split('/')
            user = pygate_cache.get_cache('user_cache', username) or UserService.user_collection.find_one({'username': username})
            api = pygate_cache.get_cache('api_cache', f"{api_name}/{api_version}") or UserService.api_collection.find_one({'api_name': api_name, 'api_version': api_version})
            if api and api.get('role') and user.get('role') not in api.get('role'):
                user_subscriptions['apis'].remove(subscription)
        UserService.subscriptions_collection.update_one(
            {'username': username},
            {'$set': {'apis': user_subscriptions.get('apis', [])}}
        )
        pygate_cache.set_cache('user_subscription_cache', username, user_subscriptions)