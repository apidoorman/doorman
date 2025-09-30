"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

# External imports
from fastapi import APIRouter, Request
from typing import Dict, List
import uuid
import time
import logging
from datetime import datetime, timedelta

# Internal imports
from models.response_model import ResponseModel
from utils.auth_util import auth_required
from utils.response_util import respond_rest
from utils.database import user_collection, api_collection, subscriptions_collection
from utils.metrics_util import metrics_store

dashboard_router = APIRouter()
logger = logging.getLogger('doorman.gateway')

"""
Endpoint

Request:
{}
Response:
{}
"""


@dashboard_router.get('',
    description='Get dashboard data',
    response_model=ResponseModel
)

async def get_dashboard_data(request: Request):
    """Get dashboard statistics and data"""
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')

        total_users = user_collection.count_documents({'active': True})
        total_apis = api_collection.count_documents({})

        snap = metrics_store.snapshot('30d')
        monthly_usage: Dict[str, int] = {}
        for pt in snap.get('series', []):
            try:
                ts = datetime.fromtimestamp(pt['timestamp'])
                key = ts.strftime('%b')
                monthly_usage[key] = monthly_usage.get(key, 0) + int(pt.get('count', 0))
            except Exception:
                continue

        active_users_list = []
        for username, reqs in snap.get('top_users', [])[:5]:
            subs = subscriptions_collection.find_one({'username': username}) or {}
            subscribers = len(subs.get('apis', [])) if isinstance(subs.get('apis'), list) else 0
            active_users_list.append({
                'username': username,
                'requests': f'{int(reqs):,}',
                'subscribers': subscribers
            })

        popular_apis = []
        for api_key, reqs in snap.get('top_apis', [])[:10]:

            try:
                name = api_key

                count = 0
                try:
                    for doc in subscriptions_collection.find():
                        apis = doc.get('apis', [])
                        if any(str(api_key).split(':')[-1] in str(a) for a in (apis or [])):
                            count += 1
                except Exception:
                    count = 0
                popular_apis.append({
                    'name': name,
                    'requests': f'{int(reqs):,}',
                    'subscribers': count
                })
            except Exception:
                continue

        dashboard_data = {
            'totalRequests': int(sum(monthly_usage.values()) or snap.get('total_requests', 0)),
            'activeUsers': total_users,
            'newApis': total_apis,
            'monthlyUsage': monthly_usage,
            'activeUsersList': active_users_list,
            'popularApis': popular_apis
        }

        return respond_rest(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            response=dashboard_data
        ))

    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return respond_rest(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='GTW999',
            error_message='An unexpected error occurred'
        ))
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')
