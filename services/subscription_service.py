"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from models.response_model import ResponseModel
from utils.database import db
from utils.cache import cache_manager
from services.cache import pygate_cache

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

class SubscriptionService:
    subscriptions_collection = db.subscriptions
    api_collection = db.apis
    user_collection = db.users

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def api_exists(api_name, api_version):
        """
        Check if an API exists.
        """
        api = pygate_cache.get_cache('api_cache', f"{api_name}/{api_version}")
        if not api:
            api = SubscriptionService.api_collection.find_one({'api_name': api_name, 'api_version': api_version})
            if not api:
                return ResponseModel(
                    status_code=404,
                    error_code='SUB001',
                    error_message='API does not exist for the requested name and version'
                ).dict()
            if api.get('_id'):
                del api['_id']
            pygate_cache.set_cache('api_cache', f"{api_name}/{api_version}", api)
        if api and '_id' in api:
            del api['_id']
        return api

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_user_subscriptions(username):
        """
        Get user subscriptions.
        """
        subscriptions = pygate_cache.get_cache('user_subscription_cache', username)
        if not subscriptions:
            subscriptions = SubscriptionService.subscriptions_collection.find_one({'username': username})
            if not subscriptions:
                return ResponseModel(
                    status_code=404,
                    error_code='SUB002',
                    error_message='User does not exist'
                ).dict()
            if subscriptions.get('_id'): del subscriptions['_id']
            pygate_cache.set_cache('user_subscription_cache', username, subscriptions)
        if '_id' in subscriptions:
            del subscriptions['_id']
        return ResponseModel(
            status_code=200,
            response={'subscriptions': subscriptions}
        ).dict()

    @staticmethod
    async def subscribe(data):
        """
        Subscribe to an API.
        """
        if not await SubscriptionService.api_exists(data.api_name, data.api_version):
            return ResponseModel(
                status_code=404,
                error_code='SUB003',
                error_message='API does not exist for the requested name and version'
            ).dict()
        user_subscriptions = pygate_cache.get_cache('user_subscription_cache', data.username)
        if not user_subscriptions:
            user_subscriptions = SubscriptionService.subscriptions_collection.find_one({'username': data.username})
            if user_subscriptions and '_id' in user_subscriptions: del user_subscriptions['_id']
            pygate_cache.set_cache('user_subscription_cache', data.username, user_subscriptions)
        if user_subscriptions is None:
            user_subscriptions = {
                'username': data.username,
                'apis': [f"{data.api_name}/{data.api_version}"]
            }
            SubscriptionService.subscriptions_collection.insert_one(user_subscriptions)
        elif 'apis' in user_subscriptions and f"{data.api_name}/{data.api_version}" in user_subscriptions['apis']:
            return ResponseModel(
                status_code=400,
                error_code='SUB004',
                error_message='User is already subscribed to the API'
            ).dict()
        else:
            SubscriptionService.subscriptions_collection.update_one(
                {'username': data.username},
                {'$push': {'apis': f"{data.api_name}/{data.api_version}"}}
            )
        user_subscriptions = SubscriptionService.subscriptions_collection.find_one({'username': data.username})
        if user_subscriptions and '_id' in user_subscriptions:
            del user_subscriptions['_id']
        pygate_cache.set_cache('user_subscription_cache', data.username, user_subscriptions)
        return ResponseModel(
            status_code=200,
            response={'message': 'Successfully subscribed to the API'}
        ).dict()
        
    @staticmethod
    async def unsubscribe(data):
        """
        Unsubscribe from an API.
        """
        if not await SubscriptionService.api_exists(data.api_name, data.api_version):
            return ResponseModel(
                status_code=404,
                error_code='SUB005',
                error_message='API does not exist for the requested name and version'
            ).dict()
        user_subscriptions = pygate_cache.get_cache('user_subscription_cache', data.username)
        if not user_subscriptions:
            user_subscriptions = SubscriptionService.subscriptions_collection.find_one({'username': data.username})
            if user_subscriptions and '_id' in user_subscriptions: del user_subscriptions['_id']
            pygate_cache.set_cache('user_subscription_cache', data.username, user_subscriptions)
        if not user_subscriptions or f"{data.api_name}/{data.api_version}" not in user_subscriptions.get('apis', []):
            return ResponseModel(
                status_code=400,
                error_code='SUB006',
                error_message='User is not subscribed to the API'
            ).dict()
        user_subscriptions['apis'].remove(f"{data.api_name}/{data.api_version}")
        SubscriptionService.subscriptions_collection.update_one(
            {'username': data.username},
            {'$set': {'apis': user_subscriptions.get('apis', [])}}
        )
        user_subscriptions = SubscriptionService.subscriptions_collection.find_one({'username': data.username})
        if user_subscriptions and '_id' in user_subscriptions:
            del user_subscriptions['_id']
        pygate_cache.set_cache('user_subscription_cache', data.username, user_subscriptions)
        return ResponseModel(
            status_code=200,
            response={'message': 'Successfully unsubscribed from the API'}
        ).dict()