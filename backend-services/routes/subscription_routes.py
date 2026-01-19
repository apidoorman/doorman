"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Request

from models.response_model import ResponseModel
from models.subscribe_model import SubscribeModel
from services.subscription_service import SubscriptionService
from utils.audit_util import audit
from utils.auth_util import auth_required
from utils.database import api_collection
from utils.group_util import group_required
from utils.response_util import respond_rest
from utils.role_util import platform_role_required_bool

subscription_router = APIRouter()

logger = logging.getLogger('doorman.gateway')

"""
Subscribe to API

Request:
{}
Response:
{}
"""


@subscription_router.post(
    '/subscribe',
    description='Subscribe to API',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {'example': {'message': 'Subscription created successfully'}}
            },
        }
    },
)
async def subscribe_api(api_data: SubscribeModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')

        # If targeting a different user, require manage_subscriptions permission
        if api_data.username and api_data.username != username:
            if not await platform_role_required_bool(username, 'manage_subscriptions'):
                return respond_rest(
                    ResponseModel(
                        status_code=403,
                        response_headers={'request_id': request_id},
                        error_code='SUB009',
                        error_message='You do not have permission to subscribe another user',
                    )
                )

        if not await group_required(
            request, api_data.api_name + '/' + api_data.api_version, api_data.username
        ):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={'request_id': request_id},
                    error_code='SUB007',
                    error_message='You do not have the correct group access',
                )
            )

        target_user = api_data.username or username
        logger.info(
            f'{request_id} | Actor: {username} | Action: subscribe | Target: {target_user} | API: {api_data.api_name}/{api_data.api_version}'
        )
        result = await SubscriptionService.subscribe(api_data, request_id)
        actor_user = username
        target_user = api_data.username or username
        audit(
            request,
            actor=actor_user,
            action='subscription.subscribe',
            target=f'{target_user}:{api_data.api_name}/{api_data.api_version}',
            status=result.get('status_code'),
            details=None,
            request_id=request_id,
        )
        return respond_rest(result)
    except HTTPException as e:
        return respond_rest(
            ResponseModel(
                status_code=e.status_code,
                response_headers={'request_id': request_id},
                error_code='GEN001',
                error_message=e.detail,
            )
        )
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')


"""
Unsubscribe from API

Request:
{}
Response:
{}
"""


@subscription_router.post(
    '/unsubscribe',
    description='Unsubscribe from API',
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {
                'application/json': {'example': {'message': 'Subscription deleted successfully'}}
            },
        }
    },
)
async def unsubscribe_api(api_data: SubscribeModel, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')

        # If targeting a different user, require manage_subscriptions permission
        if api_data.username and api_data.username != username:
            if not await platform_role_required_bool(username, 'manage_subscriptions'):
                return respond_rest(
                    ResponseModel(
                        status_code=403,
                        response_headers={'request_id': request_id},
                        error_code='SUB010',
                        error_message='You do not have permission to unsubscribe another user',
                    )
                )

        if not await group_required(
            request, api_data.api_name + '/' + api_data.api_version, api_data.username
        ):
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    response_headers={'request_id': request_id},
                    error_code='SUB008',
                    error_message='You do not have the correct group access',
                )
            )

        target_user = api_data.username or username
        logger.info(
            f'{request_id} | Actor: {username} | Action: unsubscribe | Target: {target_user} | API: {api_data.api_name}/{api_data.api_version}'
        )
        result = await SubscriptionService.unsubscribe(api_data, request_id)
        actor_user = username
        target_user = api_data.username or username
        audit(
            request,
            actor=actor_user,
            action='subscription.unsubscribe',
            target=f'{target_user}:{api_data.api_name}/{api_data.api_version}',
            status=result.get('status_code'),
            details=None,
            request_id=request_id,
        )
        return respond_rest(result)
    except HTTPException as e:
        return respond_rest(
            ResponseModel(
                status_code=e.status_code,
                response_headers={'request_id': request_id},
                error_code='GEN002',
                error_message=e.detail,
            )
        )
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')


"""
Get current user's subscriptions

Request:
{}
Response:
{}
"""


@subscription_router.get(
    '/subscriptions',
    description="Get current user's subscriptions",
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {'application/json': {'example': {'apis': ['customer/v1', 'orders/v1']}}},
        }
    },
)
async def subscriptions_for_current_user(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        return respond_rest(await SubscriptionService.get_user_subscriptions(username, request_id))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')


"""
Get user's subscriptions

Request:
{}
Response:
{}
"""


@subscription_router.get(
    '/subscriptions/{user_id}',
    description="Get user's subscriptions",
    response_model=ResponseModel,
    responses={
        200: {
            'description': 'Successful Response',
            'content': {'application/json': {'example': {'apis': ['customer/v1', 'orders/v1']}}},
        }
    },
)
async def subscriptions_for_user_by_id(user_id: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        return respond_rest(await SubscriptionService.get_user_subscriptions(user_id, request_id))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')


"""
Endpoint

Request:
{}
Response:
{}
"""


@subscription_router.get(
    '/available-apis/{username}',
    description='List available APIs for subscription based on permissions and groups',
    response_model=ResponseModel,
)
async def available_apis(username: str, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        actor = payload.get('sub')
        logger.info(
            f'{request_id} | Username: {actor} | From: {request.client.host}:{request.client.port}'
        )
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')

        accesses = (payload or {}).get('accesses') or {}
        can_manage = bool(accesses.get('manage_subscriptions'))
        if not can_manage:
            can_manage = await platform_role_required_bool(actor, 'manage_subscriptions')

        cursor = api_collection.find().sort('api_name', 1)
        apis = list(cursor)
        for a in apis:
            if a.get('_id'):
                del a['_id']
        if can_manage:
            data = [
                {
                    'api_name': a.get('api_name'),
                    'api_version': a.get('api_version'),
                    'api_description': a.get('api_description'),
                }
                for a in apis
            ]
            return respond_rest(ResponseModel(status_code=200, response={'apis': data}))

        if username != actor:
            return respond_rest(
                ResponseModel(
                    status_code=403,
                    error_code='SUB009',
                    error_message='You do not have permission to view available APIs for this user',
                )
            )
        try:
            from services.user_service import UserService

            user = await UserService.get_user_by_username_helper(actor)
            user_groups = set(user.get('groups') or [])
        except Exception:
            user_groups = set()
        allowed = []
        for a in apis:
            api_groups = set(a.get('api_allowed_groups') or [])
            if user_groups.intersection(api_groups):
                allowed.append(
                    {
                        'api_name': a.get('api_name'),
                        'api_version': a.get('api_version'),
                        'api_description': a.get('api_description'),
                    }
                )
        return respond_rest(ResponseModel(status_code=200, response={'apis': allowed}))
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(
            ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='GTW999',
                error_message='An unexpected error occurred',
            )
        )
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')
