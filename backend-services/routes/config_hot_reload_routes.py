"""
Configuration Hot Reload Routes

API endpoints for configuration management and hot reload.
"""

from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
import logging

from utils.auth_util import auth_required
from utils.hot_reload_config import hot_config
from models.response_model import ResponseModel

logger = logging.getLogger('doorman.gateway')

config_hot_reload_router = APIRouter(
    prefix='/config',
    tags=['Configuration Hot Reload']
)

@config_hot_reload_router.get(
    '/current',
    summary='Get Current Configuration',
    description='Retrieve current hot-reloadable configuration values',
    response_model=Dict[str, Any],
)
async def get_current_config(
    payload: dict = Depends(auth_required)
):
    """Get current configuration (admin only)"""
    try:
        accesses = payload.get('accesses', {})
        if not accesses.get('manage_gateway'):
            raise HTTPException(
                status_code=403,
                detail='Insufficient permissions: manage_gateway required'
            )

        config = hot_config.dump()

        return ResponseModel(
            status_code=200,
            data={
                'config': config,
                'source': 'Environment variables override config file values',
                'reload_command': 'kill -HUP $(cat doorman.pid)'
            },
            error_code=None,
            error_message=None
        ).dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Failed to retrieve configuration: {e}', exc_info=True)
        raise HTTPException(
            status_code=500,
            detail='Failed to retrieve configuration'
        )

@config_hot_reload_router.post(
    '/reload',
    summary='Trigger Configuration Reload',
    description='Manually trigger configuration reload (same as SIGHUP)',
    response_model=Dict[str, Any],
)
async def trigger_config_reload(
    payload: dict = Depends(auth_required)
):
    """Trigger configuration reload (admin only)"""
    try:
        accesses = payload.get('accesses', {})
        if not accesses.get('manage_gateway'):
            raise HTTPException(
                status_code=403,
                detail='Insufficient permissions: manage_gateway required'
            )

        hot_config.reload()

        return ResponseModel(
            status_code=200,
            data={
                'message': 'Configuration reloaded successfully',
                'config': hot_config.dump()
            },
            error_code=None,
            error_message=None
        ).dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Failed to reload configuration: {e}', exc_info=True)
        raise HTTPException(
            status_code=500,
            detail='Failed to reload configuration'
        )

@config_hot_reload_router.get(
    '/reloadable-keys',
    summary='List Reloadable Configuration Keys',
    description='Get list of configuration keys that support hot reload',
    response_model=Dict[str, Any],
)
async def get_reloadable_keys(
    payload: dict = Depends(auth_required)
):
    """Get list of reloadable configuration keys"""
    try:
        reloadable_keys = [
            {'key': 'LOG_LEVEL', 'description': 'Log level (DEBUG, INFO, WARNING, ERROR)', 'example': 'INFO'},
            {'key': 'LOG_FORMAT', 'description': 'Log format (json, text)', 'example': 'json'},
            {'key': 'LOG_FILE', 'description': 'Log file path', 'example': 'logs/doorman.log'},

            {'key': 'GATEWAY_TIMEOUT', 'description': 'Gateway timeout in seconds', 'example': '30'},
            {'key': 'UPSTREAM_TIMEOUT', 'description': 'Upstream timeout in seconds', 'example': '30'},
            {'key': 'CONNECTION_TIMEOUT', 'description': 'Connection timeout in seconds', 'example': '10'},

            {'key': 'RATE_LIMIT_ENABLED', 'description': 'Enable rate limiting', 'example': 'true'},
            {'key': 'RATE_LIMIT_REQUESTS', 'description': 'Requests per window', 'example': '100'},
            {'key': 'RATE_LIMIT_WINDOW', 'description': 'Window size in seconds', 'example': '60'},

            {'key': 'CACHE_TTL', 'description': 'Cache TTL in seconds', 'example': '300'},
            {'key': 'CACHE_MAX_SIZE', 'description': 'Maximum cache entries', 'example': '1000'},

            {'key': 'CIRCUIT_BREAKER_ENABLED', 'description': 'Enable circuit breaker', 'example': 'true'},
            {'key': 'CIRCUIT_BREAKER_THRESHOLD', 'description': 'Failures before opening', 'example': '5'},
            {'key': 'CIRCUIT_BREAKER_TIMEOUT', 'description': 'Timeout before retry (seconds)', 'example': '60'},

            {'key': 'RETRY_ENABLED', 'description': 'Enable retry logic', 'example': 'true'},
            {'key': 'RETRY_MAX_ATTEMPTS', 'description': 'Maximum retry attempts', 'example': '3'},
            {'key': 'RETRY_BACKOFF', 'description': 'Backoff multiplier', 'example': '1.0'},

            {'key': 'METRICS_ENABLED', 'description': 'Enable metrics collection', 'example': 'true'},
            {'key': 'METRICS_INTERVAL', 'description': 'Metrics interval (seconds)', 'example': '60'},

            {'key': 'FEATURE_REQUEST_REPLAY', 'description': 'Enable request replay', 'example': 'false'},
            {'key': 'FEATURE_AB_TESTING', 'description': 'Enable A/B testing', 'example': 'false'},
            {'key': 'FEATURE_COST_ANALYTICS', 'description': 'Enable cost analytics', 'example': 'false'},
        ]

        return ResponseModel(
            status_code=200,
            data={
                'reloadable_keys': reloadable_keys,
                'total': len(reloadable_keys),
                'notes': [
                    'Environment variables always override config file values',
                    'Changes take effect immediately after reload',
                    'Reload via: kill -HUP $(cat doorman.pid)',
                    'Or use: POST /config/reload'
                ]
            },
            error_code=None,
            error_message=None
        ).dict()

    except Exception as e:
        logger.error(f'Failed to retrieve reloadable keys: {e}', exc_info=True)
        raise HTTPException(
            status_code=500,
            detail='Failed to retrieve reloadable keys'
        )
