"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

# Internal imports
from utils.database import db
from utils.cache import cache_manager
from services.cache import pygate_cache
from services.api_service import ApiService

class SubscriptionService:
    subscriptions_collection = db.subscriptions

    @staticmethod
    @cache_manager.cached(ttl=300)
    async def api_exists(api_name, api_version):
        """
        Check if an API exists.
        """
        return pygate_cache.get_cache('api_cache', f"{api_name}/{api_version}") or ApiService.api_collection.find_one({'api_name': api_name, 'api_version': api_version})

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
        username = data.get('username')
        api_name = data.get('api_name')
        api_version = data.get('api_version')
        
        if not await SubscriptionService.api_exists(api_name, api_version):
            raise ValueError("API does not exist")
            
        user_subscriptions = pygate_cache.get_cache('user_subscription_cache', username) or SubscriptionService.subscriptions_collection.find_one({'username': username})
        if user_subscriptions is None:
            user_subscriptions = {
                'username': username,
                'apis': []
            }
            SubscriptionService.subscriptions_collection.insert_one(user_subscriptions)
        elif 'apis' in user_subscriptions and f"{api_name}/{api_version}" in user_subscriptions['apis']:
            raise ValueError("User is already subscribed to the API")
            
        updated_subscriptions = SubscriptionService.subscriptions_collection.update_one(
            {'username': username},
            {'$push': {'apis': f"{api_name}/{api_version}"}}
        )
        pygate_cache.set_cache('user_subscription_cache', username, updated_subscriptions)

    @staticmethod
    async def unsubscribe(data):
        """
        Unsubscribe from an API.
        """
        username = data.get('username')
        api_name = data.get('api_name')
        api_version = data.get('api_version')
        if not SubscriptionService.api_exists(api_name, api_version):
            raise ValueError("API does not exist")
        user_subscriptions = pygate_cache.get_cache('user_subscription_cache', username) or SubscriptionService.subscriptions_collection.find_one({'username': username})
        if not user_subscriptions.contains(
                f"""{api_name}/{api_version}"""):
            raise ValueError("User is already not subscribed to the API")
        updated_subscriptions = SubscriptionService.subscriptions_collection.update_one(
            {'username': username},
            {'$pull': {'apis': f"""{api_name}/{api_version}"""}})
        pygate_cache.get_cache('user_subscription_cache', username, updated_subscriptions)