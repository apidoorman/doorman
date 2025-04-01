"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import HTTPException, Depends, Request
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import MissingTokenError
from services.cache import pygate_cache
from services.subscription_service import SubscriptionService

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

def subscription_required(request: Request, Authorize: AuthJWT = Depends()):
    try:
        username = Authorize.get_jwt_subject()
        full_path = request.url.path
        prefix = "/api/rest/"
        if full_path.startswith(prefix):
            path = full_path[len(prefix):]
        else:
            path = full_path
        api_and_version = '/'.join(path.split('/')[:2])
        user_subscriptions = pygate_cache.get_cache('user_subscription_cache', username) or SubscriptionService.subscriptions_collection.find_one({'username': username})
        subscriptions = user_subscriptions.get('apis') if user_subscriptions and 'apis' in user_subscriptions else None
        if not subscriptions or api_and_version not in subscriptions:
            logger.info(f"User {username} attempted access to {api_and_version}")
            raise HTTPException(status_code=403, detail="You are not subscribed to this resource")
    except MissingTokenError:
        raise HTTPException(status_code=401, detail="Missing token")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    return Authorize