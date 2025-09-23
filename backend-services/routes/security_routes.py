"""
Routes for managing security settings.
"""

from fastapi import APIRouter, Request
import uuid
import time
import logging

from models.response_model import ResponseModel
from models.security_settings_model import SecuritySettingsModel
from utils.response_util import process_response
from utils.auth_util import auth_required
from utils.role_util import platform_role_required_bool
from utils.security_settings_util import load_settings, save_settings

security_router = APIRouter()
logger = logging.getLogger("doorman.gateway")


@security_router.get("/security/settings",
    description="Get security settings",
    response_model=ResponseModel,
)
async def get_security_settings(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_security'):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={"request_id": request_id},
                error_code="SEC001",
                error_message="You do not have permission to view security settings"
            ).dict(), "rest")
        settings = await load_settings()
        # Include memory-only mode to let UI present correct controls
        settings_with_mode = dict(settings)
        try:
            from utils.database import database
            settings_with_mode['memory_only'] = bool(database.memory_only)
        except Exception:
            settings_with_mode['memory_only'] = False
        return process_response(ResponseModel(
            status_code=200,
            response_headers={"request_id": request_id},
            response=settings_with_mode
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


@security_router.put("/security/settings",
    description="Update security settings",
    response_model=ResponseModel,
)
async def update_security_settings(request: Request, body: SecuritySettingsModel):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if not await platform_role_required_bool(username, 'manage_security'):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={"request_id": request_id},
                error_code="SEC002",
                error_message="You do not have permission to update security settings"
            ).dict(), "rest")
        new_settings = await save_settings(body.dict(exclude_none=True))
        # Echo memory-only mode in response for UI convenience
        settings_with_mode = dict(new_settings)
        try:
            from utils.database import database
            settings_with_mode['memory_only'] = bool(database.memory_only)
        except Exception:
            settings_with_mode['memory_only'] = False
        return process_response(ResponseModel(
            status_code=200,
            response_headers={"request_id": request_id},
            message="Security settings updated",
            response=settings_with_mode
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
