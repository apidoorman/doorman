"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from utils.database import db
from utils.cache import cache_manager
from services.cache import pygate_cache
from services.api_service import ApiService

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

class SubscriptionService:
    subscriptions_collection = db.subscriptions
    api_collection = db.apis

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def api_exists(api_name, api_version):
        """
        Check if an API exists.
        """
        api = pygate_cache.get_cache('api_cache', f"{api_name}/{api_version}") or ApiService.api_collection.find_one({'api_name': api_name, 'api_version': api_version})
        if api and '_id' in api:
            del api['_id']
        return api

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def get_user_subscriptions(username):
        """
        Get user subscriptions.
        """
        subscriptions = pygate_cache.get_cache('user_subscription_cache', username) or SubscriptionService.subscriptions_collection.find_one({'username': username})
        if not subscriptions:
            raise ValueError('No subscriptions found for user')
        if '_id' in subscriptions:
            del subscriptions['_id']
        return subscriptions

    @staticmethod
    async def subscribe(data):
        """
        Subscribe to an API.
        """
        if not SubscriptionService.api_exists(data.api_name, data.api_version):
            raise ValueError("API does not exist")
        user_subscriptions = pygate_cache.get_cache('user_subscription_cache', data.username) or SubscriptionService.subscriptions_collection.find_one({'username': data.username})
        if user_subscriptions is None:
            user_subscriptions = {
                'username': data.username,
                'apis': [f"{data.api_name}/{data.api_version}"]
            }
            SubscriptionService.subscriptions_collection.insert_one(user_subscriptions)
        elif 'apis' in user_subscriptions and f"{data.api_name}/{data.api_version}" in user_subscriptions['apis']:
            raise ValueError("User is already subscribed to the API")
        else:
            SubscriptionService.subscriptions_collection.update_one(
                {'username': data.username},
                {'$push': {'apis': f"{data.api_name}/{data.api_version}"}}
            )
        user_subscriptions = SubscriptionService.subscriptions_collection.find_one({'username': data.username})
        if user_subscriptions and '_id' in user_subscriptions:
            del user_subscriptions['_id']
        pygate_cache.set_cache('user_subscription_cache', data.username, user_subscriptions)
        
    @staticmethod
    async def unsubscribe(data):
        """
        Unsubscribe from an API.
        """
        if not await SubscriptionService.api_exists(data.api_name, data.api_version):
            raise ValueError("API does not exist")
        user_subscriptions = pygate_cache.get_cache('user_subscription_cache', data.username) or SubscriptionService.subscriptions_collection.find_one({'username': data.username})
        if not user_subscriptions or f"{data.api_name}/{data.api_version}" not in user_subscriptions.get('apis', []):
            raise ValueError("User is not subscribed to the API")
        user_subscriptions['apis'].remove(f"{data.api_name}/{data.api_version}")
        update_result = SubscriptionService.subscriptions_collection.update_one(
            {'username': data.username},
            {'$set': {'apis': user_subscriptions.get('apis', [])}}
        )
        user_subscriptions = SubscriptionService.subscriptions_collection.find_one({'username': data.username})
        if user_subscriptions and '_id' in user_subscriptions:
            del user_subscriptions['_id']
        pygate_cache.set_cache('user_subscription_cache', data.username, user_subscriptions)