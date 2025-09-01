"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from fastapi import APIRouter, Request
from typing import Dict, List

from models.response_model import ResponseModel
from utils.auth_util import auth_required
from utils.response_util import process_response
from utils.database import user_collection, api_collection, subscriptions_collection
from utils.metrics_util import metrics_store

import uuid
import time
import logging
from datetime import datetime, timedelta

dashboard_router = APIRouter()
logger = logging.getLogger("doorman.gateway")

@dashboard_router.get("",
    description="Get dashboard data",
    response_model=ResponseModel
)
async def get_dashboard_data(request: Request):
    """Get dashboard statistics and data"""
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        
        # Get basic statistics
        total_users = user_collection.count_documents({"active": True})
        total_apis = api_collection.count_documents({})
        
        # Build monthly usage from metrics (aggregate per calendar month from available series)
        snap = metrics_store.snapshot('30d')
        monthly_usage: Dict[str, int] = {}
        for pt in snap.get('series', []):
            try:
                ts = datetime.fromtimestamp(pt['timestamp'])
                key = ts.strftime('%b')
                monthly_usage[key] = monthly_usage.get(key, 0) + int(pt.get('count', 0))
            except Exception:
                continue

        # Active users list from top_users in metrics; enrich with subscribers (count of apis in subscriptions)
        active_users_list = []
        for username, reqs in snap.get('top_users', [])[:10]:
            subs = subscriptions_collection.find_one({'username': username}) or {}
            subscribers = len(subs.get('apis', [])) if isinstance(subs.get('apis'), list) else 0
            active_users_list.append({
                'username': username,
                'requests': f"{int(reqs):,}",
                'subscribers': subscribers
            })

        # Popular APIs from metrics top_apis; subscribers are approximate (number of users subscribed to that api token path)
        popular_apis = []
        for api_key, reqs in snap.get('top_apis', [])[:10]:
            # Estimate subscribers across all users who have this api in their subscriptions
            try:
                name = api_key
                # Count subscribers
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
                    'requests': f"{int(reqs):,}",
                    'subscribers': count
                })
            except Exception:
                continue
        
        dashboard_data = {
            "totalRequests": int(sum(monthly_usage.values()) or snap.get('total_requests', 0)),
            "activeUsers": total_users,
            "newApis": total_apis,
            "monthlyUsage": monthly_usage,
            "activeUsersList": active_users_list,
            "popularApis": popular_apis
        }
        
        return process_response(ResponseModel(
            status_code=200,
            response_headers={"request_id": request_id},
            response=dashboard_data
        ).dict(), "rest")
        
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={"request_id": request_id},
            error_code="GTW999",
            error_message="An unexpected error occurred"
        ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms") 
