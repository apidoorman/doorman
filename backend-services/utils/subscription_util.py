"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

import logging
import os

from fastapi import HTTPException, Request
from jose import JWTError
from utils.role_util import is_admin_user

from utils.async_db import db_find_one
from utils.auth_util import auth_required
from utils.database_async import subscriptions_collection
from utils.doorman_cache_util import doorman_cache

logger = logging.getLogger('doorman.gateway')


async def subscription_required(request: Request):
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        if not username:
            raise HTTPException(status_code=401, detail='Invalid token')
        
        # Admin user bypasses subscription requirements
        try:
            if await is_admin_user(username):
                logger.info(f'Admin user {username} bypassing subscription check')
                return payload
        except Exception:
            pass
        full_path = request.url.path
        if full_path.startswith('/api/rest/'):
            prefix = '/api/rest/'
            path = full_path[len(prefix) :]
            api_and_version = '/'.join(path.split('/')[:2])
        elif full_path.startswith('/api/soap/'):
            prefix = '/api/soap/'
            path = full_path[len(prefix) :]
            api_and_version = '/'.join(path.split('/')[:2])
        elif full_path.startswith('/api/graphql/'):
            api_name = full_path.replace('/api/graphql/', '')
            api_version = request.headers.get('X-API-Version', 'v1')
            api_and_version = f'{api_name}/{api_version}'
        elif full_path.startswith('/api/grpc/'):
            api_name = full_path.replace('/api/grpc/', '').split('/')[0]
            api_version = request.headers.get('X-API-Version', 'v1')
            api_and_version = f'{api_name}/{api_version}'
        else:
            p = full_path.lstrip('/')
            segs = p.split('/')
            if segs and segs[0] == 'api' and len(segs) >= 4:
                api_and_version = '/'.join(segs[2:4])
            else:
                api_and_version = '/'.join(segs[:2])
        user_subscriptions = doorman_cache.get_cache(
            'user_subscription_cache', username
        ) or await db_find_one(subscriptions_collection, {'username': username})
        subscriptions = (
            user_subscriptions.get('apis')
            if user_subscriptions and 'apis' in user_subscriptions
            else None
        )
        if not subscriptions or api_and_version not in subscriptions:
            logger.info(f'User {username} attempted access to {api_and_version}')
            raise HTTPException(status_code=403, detail='You are not subscribed to this resource')
    except JWTError:
        logger.error('Invalid token')
        raise HTTPException(status_code=401, detail='Invalid token')
    except HTTPException as e:
        logger.error(f'Unexpected error: {e}')
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        logger.error(f'Unexpected error: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')
    return payload
