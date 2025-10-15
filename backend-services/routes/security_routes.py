"""
Routes for managing security settings.
"""

from fastapi import APIRouter, Request
from typing import Optional
import os
import sys
import subprocess
import uuid
import time
import logging

from models.response_model import ResponseModel
from models.security_settings_model import SecuritySettingsModel
from utils.response_util import process_response
from utils.auth_util import auth_required
from utils.role_util import platform_role_required_bool
from utils.security_settings_util import load_settings, save_settings
from utils.audit_util import audit

security_router = APIRouter()
logger = logging.getLogger('doorman.gateway')

"""
Endpoint

Request:
{}
Response:
{}
"""

@security_router.get('/security/settings',
    description='Get security settings',
    response_model=ResponseModel,
)

async def get_security_settings(request: Request):
    request_id = getattr(request.state, 'request_id', None) or request.headers.get('X-Request-ID') or str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, 'manage_security'):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='SEC001',
                error_message='You do not have permission to view security settings'
            ).dict(), 'rest')
        settings = await load_settings()
        try:
            client_ip = request.client.host if request.client else None
            xff = request.headers.get('x-forwarded-for') or request.headers.get('X-Forwarded-For')
            client_ip_xff = xff.split(',')[0].strip() if xff else None
        except Exception:
            client_ip = None
            client_ip_xff = None

        settings_with_mode = dict(settings)
        try:
            from utils.database import database
            settings_with_mode['memory_only'] = bool(database.memory_only)
        except Exception:
            settings_with_mode['memory_only'] = False
        try:
            import os
            env_val = os.getenv('LOCAL_HOST_IP_BYPASS')
            locked = isinstance(env_val, str) and env_val.strip() != ''
            if locked:
                settings_with_mode['allow_localhost_bypass'] = (env_val.lower() == 'true')
            settings_with_mode['allow_localhost_bypass_locked'] = locked
        except Exception:
            settings_with_mode['allow_localhost_bypass_locked'] = False
        try:
            warnings = []
            if settings_with_mode.get('trust_x_forwarded_for') and not (settings_with_mode.get('xff_trusted_proxies') or []):
                warnings.append('Trust X-Forwarded-For is enabled, but no trusted proxies are configured. Set xff_trusted_proxies to avoid header spoofing.')
            settings_with_mode['security_warnings'] = warnings
        except Exception:
            pass
        settings_with_mode['client_ip'] = client_ip
        settings_with_mode['client_ip_xff'] = client_ip_xff
        return process_response(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            response=settings_with_mode
        ).dict(), 'rest')
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='GTW999',
            error_message='An unexpected error occurred'
        ).dict(), 'rest')
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

@security_router.put('/security/settings',
    description='Update security settings',
    response_model=ResponseModel,
)
async def update_security_settings(request: Request, body: Optional[SecuritySettingsModel] = None):
    request_id = getattr(request.state, 'request_id', None) or request.headers.get('X-Request-ID') or str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, 'manage_security'):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='SEC002',
                error_message='You do not have permission to update security settings'
            ).dict(), 'rest')
        payload_dict = {}
        try:
            payload_dict = (body.dict(exclude_none=True) if body is not None else {})
        except Exception:
            payload_dict = {}
        new_settings = await save_settings(payload_dict)
        audit(request, actor=username, action='security.update_settings', target='security_settings', status='success', details={k: new_settings.get(k) for k in ('enable_auto_save','auto_save_frequency_seconds','dump_path')}, request_id=request_id)

        settings_with_mode = dict(new_settings)
        try:
            from utils.database import database
            settings_with_mode['memory_only'] = bool(database.memory_only)
        except Exception:
            settings_with_mode['memory_only'] = False
        return process_response(ResponseModel(
            status_code=200,
            response_headers={'request_id': request_id},
            message='Security settings updated',
            response=settings_with_mode
        ).dict(), 'rest')
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='GTW999',
            error_message='An unexpected error occurred'
        ).dict(), 'rest')
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

@security_router.post('/security/restart',
    description='Schedule a safe gateway restart (PID-based)',
    response_model=ResponseModel,
)

async def restart_gateway(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get('sub')
        logger.info(f'{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}')
        logger.info(f'{request_id} | Endpoint: {request.method} {str(request.url.path)}')
        if not await platform_role_required_bool(username, 'manage_security'):
            return process_response(ResponseModel(
                status_code=403,
                response_headers={'request_id': request_id},
                error_code='SEC003',
                error_message='You do not have permission to restart the gateway'
            ).dict(), 'rest')

        pid_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'doorman.pid')
        pid_file = os.path.abspath(pid_file)
        if not os.path.exists(pid_file):
            return process_response(ResponseModel(
                status_code=409,
                response_headers={'request_id': request_id},
                error_code='SEC004',
                error_message="Restart not supported: no PID file found (run using 'doorman start' or contact your admin)"
            ).dict(), 'rest')

        doorman_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'doorman.py'))
        try:
            if os.name == 'nt':
                subprocess.Popen([sys.executable, doorman_path, 'restart'],
                                 creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen([sys.executable, doorman_path, 'restart'],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 preexec_fn=os.setsid)
        except Exception as e:
            logger.error(f'{request_id} | Failed to spawn restarter: {e}')
            return process_response(ResponseModel(
                status_code=500,
                response_headers={'request_id': request_id},
                error_code='SEC005',
                error_message='Failed to schedule restart'
            ).dict(), 'rest')
        audit(request, actor=username, action='security.restart', target='gateway', status='scheduled', details=None, request_id=request_id)
        return process_response(ResponseModel(
            status_code=202,
            response_headers={'request_id': request_id},
            message='Restart scheduled'
        ).dict(), 'rest')
    except Exception as e:
        logger.critical(f'{request_id} | Unexpected error: {str(e)}', exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={'request_id': request_id},
            error_code='GTW999',
            error_message='An unexpected error occurred'
        ).dict(), 'rest')
    finally:
        end_time = time.time() * 1000
        logger.info(f'{request_id} | Total time: {str(end_time - start_time)}ms')
