"""
Routes to expose gateway metrics to the web client.
"""

from fastapi import APIRouter, Request
import uuid
import time
import logging

from models.response_model import ResponseModel
from utils.response_util import process_response
from utils.metrics_util import metrics_store
from utils.auth_util import auth_required
from utils.role_util import platform_role_required_bool
from utils.health_check_util import check_mongodb, check_redis

monitor_router = APIRouter()
logger = logging.getLogger("doorman.gateway")


@monitor_router.get("/monitor/metrics",
    description="Get aggregated gateway metrics",
    response_model=ResponseModel,
)
async def get_metrics(request: Request, range: str = "24h"):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_gateway'):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={"request_id": request_id},
                error_code="MON001",
                error_message="You do not have permission to view monitor metrics"
            ).dict(), "rest")
        snap = metrics_store.snapshot(range)
        return process_response(ResponseModel(
            status_code=200,
            response_headers={"request_id": request_id},
            response=snap
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


@monitor_router.get("/monitor/liveness",
    description="Kubernetes liveness probe endpoint (no auth)")
async def liveness():
    return {"status": "alive"}


@monitor_router.get("/monitor/readiness",
    description="Kubernetes readiness probe endpoint (no auth)")
async def readiness():
    try:
        mongo_ok = await check_mongodb()
        redis_ok = await check_redis()
        ready = mongo_ok and redis_ok
        return {
            "status": "ready" if ready else "degraded",
            "mongodb": mongo_ok,
            "redis": redis_ok
        }
    except Exception:
        return {"status": "degraded"}
