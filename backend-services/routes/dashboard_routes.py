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
        
        # Get monthly usage data (mock data for now)
        current_month = datetime.now().strftime("%b")
        monthly_usage = {
            "Jan": 1250,
            "Feb": 1380,
            "Mar": 1420,
            "Apr": 1580,
            "May": 1620,
            "Jun": 1750,
            "Jul": 1820,
            "Aug": 1950,
            "Sep": 2100,
            "Oct": 2250,
            "Nov": 2400,
            "Dec": 2600
        }
        
        # Get active users list (mock data for now)
        active_users_list = [
            {"username": "admin", "requests": "1,250", "subscribers": 5},
            {"username": "user1", "requests": "890", "subscribers": 3},
            {"username": "user2", "requests": "650", "subscribers": 2},
            {"username": "user3", "requests": "420", "subscribers": 1}
        ]
        
        # Get popular APIs (mock data for now)
        popular_apis = [
            {"name": "User API", "requests": "2,500", "subscribers": 15},
            {"name": "Payment API", "requests": "1,800", "subscribers": 8},
            {"name": "Notification API", "requests": "1,200", "subscribers": 12},
            {"name": "Analytics API", "requests": "950", "subscribers": 6}
        ]
        
        dashboard_data = {
            "totalRequests": sum(monthly_usage.values()),
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