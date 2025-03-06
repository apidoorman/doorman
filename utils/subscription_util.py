"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from functools import wraps
from fastapi import HTTPException, Depends, Request
from fastapi_jwt_auth import AuthJWT
from services.cache import pygate_cache

from services.subscription_service import SubscriptionService

def subscription_required():
    def decorator(f):
        @wraps(f)
        async def decorated_function(*args, request: Request, Authorize: AuthJWT = Depends(), **kwargs):
            Authorize.jwt_required('cookies')
            username = Authorize.get_jwt_subject()
            subscriptions = await pygate_cache.get_cache('user_subscription_cache', username) or SubscriptionService.subscriptions_collection.find_one({'username': username})
            path = kwargs.get('path', '')
            if not subscriptions or not subscriptions.get('apis') or path not in subscriptions.get('apis'):
                raise HTTPException(status_code=403, detail="You are not subscribed to this resource")
            return await f(*args, **kwargs)
        return decorated_function
    return decorator