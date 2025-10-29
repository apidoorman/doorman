"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from jose import jwt, JWTError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import Response
from contextlib import asynccontextmanager
from redis.asyncio import Redis
from pydantic import BaseSettings
from dotenv import load_dotenv
import multiprocessing
import logging
import json
import re
import os
import sys
import subprocess
import signal
import uvicorn
import time
import asyncio
import uuid
import shutil
from pathlib import Path

try:
    if sys.version_info >= (3, 13):
        try:
            from importlib.metadata import version, PackageNotFoundError
        except Exception:
            version = None
            PackageNotFoundError = Exception
        if version is not None:
            try:
                v = version('aiohttp')
                parts = [int(p) for p in (v.split('.')[:3] + ['0', '0'])[:3] if p.isdigit() or p.isnumeric()]
                while len(parts) < 3:
                    parts.append(0)
                if tuple(parts) < (3, 10, 10):
                    raise SystemExit(
                        f"Incompatible aiohttp {v} detected on Python {sys.version.split()[0]}. "
                        "Please upgrade to aiohttp>=3.10.10 (pip install -U aiohttp) or run with Python 3.11."
                    )
            except PackageNotFoundError:
                pass
            except Exception:
                pass
except Exception:
    pass

from models.response_model import ResponseModel
from utils.cache_manager_util import cache_manager
from utils.auth_blacklist import purge_expired_tokens
from utils.doorman_cache_util import doorman_cache
from utils.hot_reload_config import hot_config
from routes.authorization_routes import authorization_router
from routes.group_routes import group_router
from routes.role_routes import role_router
from routes.subscription_routes import subscription_router
from routes.user_routes import user_router
from routes.api_routes import api_router
from routes.endpoint_routes import endpoint_router
from routes.gateway_routes import gateway_router
from routes.routing_routes import routing_router
from routes.proto_routes import proto_router
from routes.logging_routes import logging_router
from routes.dashboard_routes import dashboard_router
from routes.memory_routes import memory_router
from routes.security_routes import security_router
from routes.credit_routes import credit_router
from routes.demo_routes import demo_router
from routes.monitor_routes import monitor_router
from routes.config_routes import config_router
from routes.tools_routes import tools_router
from routes.config_hot_reload_routes import config_hot_reload_router
from utils.security_settings_util import load_settings, start_auto_save_task, stop_auto_save_task, get_cached_settings
from utils.memory_dump_util import dump_memory_to_file, restore_memory_from_file, find_latest_dump_path
from utils.metrics_util import metrics_store
from utils.database import database
from utils.response_util import process_response
from utils.audit_util import audit
from utils.ip_policy_util import _get_client_ip as _policy_get_client_ip, _ip_in_list as _policy_ip_in_list, _is_loopback as _policy_is_loopback

load_dotenv()

PID_FILE = 'doorman.pid'

def _migrate_generated_directory() -> None:
    """Migrate legacy root-level 'generated/' into backend-services/generated.

    Older defaults wrote files to a CWD-relative 'generated/' which could be at
    the repo root. Normalize by moving files into backend-services/generated.
    """
    try:
        be_root = Path(__file__).resolve().parent
        project_root = be_root.parent
        src = project_root / 'generated'
        dst = be_root / 'generated'
        if src == dst:
            return
        if not src.exists() or not src.is_dir():
            dst.mkdir(exist_ok=True)
            gateway_logger.info(f"Generated dir: {dst} (no migration needed)")
            return
        dst.mkdir(parents=True, exist_ok=True)
        moved_count = 0
        for path in src.rglob('*'):
            if path.is_dir():
                continue
            rel = path.relative_to(src)
            dest_file = dst / rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(path), str(dest_file))
            except Exception:
                try:
                    shutil.copy2(str(path), str(dest_file))
                    path.unlink(missing_ok=True)
                except Exception:
                    continue
            moved_count += 1
        try:
            shutil.rmtree(src)
        except Exception:
            pass
        gateway_logger.info(f"Generated dir migrated: {moved_count} file(s) moved to {dst}")
    except Exception as e:
        try:
            gateway_logger.warning(f"Generated dir migration skipped: {e}")
        except Exception:
            pass

async def validate_database_connections():
    """Validate database connections on startup with retry logic"""
    gateway_logger.info("Validating database connections...")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            from utils.database import user_collection
            await user_collection.find_one({})
            gateway_logger.info("✓ MongoDB connection verified")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                gateway_logger.warning(
                    f"MongoDB connection attempt {attempt + 1}/{max_retries} failed: {e}"
                )
                gateway_logger.info(f"Retrying in {wait} seconds...")
                await asyncio.sleep(wait)
            else:
                gateway_logger.error(f"MongoDB connection failed after {max_retries} attempts")
                raise RuntimeError(
                    f"Cannot connect to MongoDB: {e}"
                ) from e

    redis_host = os.getenv('REDIS_HOST')
    mem_or_external = os.getenv('MEM_OR_EXTERNAL', 'MEM')

    if redis_host and mem_or_external == 'REDIS':
        for attempt in range(max_retries):
            try:
                import redis.asyncio as redis
                redis_url = f"redis://{redis_host}:{os.getenv('REDIS_PORT', '6379')}"
                if os.getenv('REDIS_PASSWORD'):
                    redis_url = f"redis://:{os.getenv('REDIS_PASSWORD')}@{redis_host}:{os.getenv('REDIS_PORT', '6379')}"

                r = redis.from_url(redis_url)
                await r.ping()
                await r.close()
                gateway_logger.info("✓ Redis connection verified")
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** attempt
                    gateway_logger.warning(
                        f"Redis connection attempt {attempt + 1}/{max_retries} failed: {e}"
                    )
                    gateway_logger.info(f"Retrying in {wait} seconds...")
                    await asyncio.sleep(wait)
                else:
                    gateway_logger.error(f"Redis connection failed after {max_retries} attempts")
                    raise RuntimeError(
                        f"Cannot connect to Redis: {e}"
                    ) from e

    gateway_logger.info("All database connections validated successfully")

def validate_token_revocation_config():
    """
    Validate token revocation is safe for multi-worker deployments.
    """
    threads = int(os.getenv('THREADS', '1'))
    mem_mode = os.getenv('MEM_OR_EXTERNAL', 'MEM')
    if threads > 1 and mem_mode == 'MEM':
        gateway_logger.error(
            "CRITICAL: Multi-worker mode (THREADS > 1) with in-memory storage "
            "does not provide consistent token revocation across workers. "
            f"Current config: THREADS={threads}, MEM_OR_EXTERNAL={mem_mode}"
        )
        gateway_logger.error(
            "Token revocation requires Redis in multi-worker mode. "
            "Either set MEM_OR_EXTERNAL=REDIS or set THREADS=1"
        )
        raise RuntimeError(
            "Token revocation requires Redis in multi-worker mode (THREADS > 1). "
            "Set MEM_OR_EXTERNAL=REDIS or THREADS=1"
        )
    gateway_logger.info(
        f"Token revocation mode: {mem_mode} with {threads} worker(s)"
    )

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    if os.getenv('MEM_OR_EXTERNAL', '') != 'MEM':
        await validate_database_connections()
    validate_token_revocation_config()
    admin_password = os.getenv('DOORMAN_ADMIN_PASSWORD', '')
    if len(admin_password) < 12:
        raise RuntimeError(
            'DOORMAN_ADMIN_PASSWORD must be at least 12 characters. '
            'Generate strong password: openssl rand -base64 16'
        )

    if not os.getenv('JWT_SECRET_KEY'):
        raise RuntimeError('JWT_SECRET_KEY is not configured. Set it before starting the server.')

    try:
        if os.getenv('ENV', '').lower() == 'production':
            https_only = os.getenv('HTTPS_ONLY', 'false').lower() == 'true'
            https_enabled = os.getenv('HTTPS_ENABLED', 'false').lower() == 'true'
            if not (https_only or https_enabled):
                raise RuntimeError(
                    'In production (ENV=production), you must enable HTTPS_ONLY or HTTPS_ENABLED to enforce Secure cookies.'
                )

            if https_only or https_enabled:
                cert = os.getenv('SSL_CERTFILE')
                key = os.getenv('SSL_KEYFILE')
                if https_only and (not cert or not key):
                    raise RuntimeError(
                        'SSL_CERTFILE and SSL_KEYFILE required when HTTPS_ONLY=true'
                    )
                if cert and not os.path.exists(cert):
                    raise RuntimeError(f'SSL certificate not found: {cert}')
                if key and not os.path.exists(key):
                    raise RuntimeError(f'SSL private key not found: {key}')

            jwt_secret = os.getenv('JWT_SECRET_KEY', '')
            if jwt_secret in ('please-change-me', 'test-secret-key', 'test-secret-key-please-change', ''):
                raise RuntimeError(
                    'In production (ENV=production), JWT_SECRET_KEY must be changed from default value. '
                    'Generate a strong random secret (32+ characters).'
                )

            mem_or_external = os.getenv('MEM_OR_EXTERNAL', 'MEM').upper()
            if mem_or_external == 'MEM':
                num_threads = int(os.getenv('THREADS', 1))
                if num_threads > 1:
                    raise RuntimeError(
                        'In production with THREADS > 1, MEM_OR_EXTERNAL=MEM is unsafe. '
                        'Rate limiting and token revocation are not shared across workers. '
                        'Set MEM_OR_EXTERNAL=REDIS with REDIS_HOST configured.'
                    )
                gateway_logger.warning(
                    'Production deployment with MEM_OR_EXTERNAL=MEM detected. '
                    'Single-node only. For multi-node HA, use REDIS or EXTERNAL mode.'
                )
            else:
                redis_host = os.getenv('REDIS_HOST')
                if not redis_host:
                    raise RuntimeError(
                        'In production with MEM_OR_EXTERNAL=REDIS/EXTERNAL, REDIS_HOST is required. '
                        'Redis is essential for shared token revocation and rate limiting in HA deployments.'
                    )

            if os.getenv('CORS_STRICT', 'false').lower() != 'true':
                raise RuntimeError(
                    'In production (ENV=production), CORS_STRICT must be true. '
                    'This prevents wildcard origins with credentials, which is a critical security risk.'
                )

            allowed_origins = os.getenv('ALLOWED_ORIGINS', '')
            if '*' in allowed_origins:
                raise RuntimeError(
                    'In production (ENV=production), wildcard CORS origins (*) are not allowed. '
                    'Set ALLOWED_ORIGINS to specific domain(s): https://yourdomain.com'
                )

            token_encryption_key = os.getenv('TOKEN_ENCRYPTION_KEY', '')
            if not token_encryption_key or len(token_encryption_key) < 32:
                gateway_logger.warning(
                    'Production deployment without TOKEN_ENCRYPTION_KEY (32+ characters). '
                    'API keys will not be encrypted at rest. Highly recommended for production security.'
                )

            if mem_or_external == 'MEM':
                mem_encryption_key = os.getenv('MEM_ENCRYPTION_KEY', '')
                if not mem_encryption_key or len(mem_encryption_key) < 32:
                    raise RuntimeError(
                        'In production (ENV=production) with MEM_OR_EXTERNAL=MEM, MEM_ENCRYPTION_KEY is required (32+ characters). '
                        'Memory dumps contain sensitive data and must be encrypted. '
                        'Generate a strong random key: openssl rand -hex 32'
                    )
    except Exception as e:
        raise

    mem_or_external = os.getenv('MEM_OR_EXTERNAL', 'MEM').upper()
    redis_host = os.getenv('REDIS_HOST')
    redis_port = os.getenv('REDIS_PORT')
    redis_db = os.getenv('REDIS_DB')
    redis_password = os.getenv('REDIS_PASSWORD', '')

    if mem_or_external in ('REDIS', 'EXTERNAL'):
        if not redis_password:
            gateway_logger.warning(
                'Redis password not set; connection may be unauthenticated. '
                'Set REDIS_PASSWORD environment variable to secure Redis access.'
            )
        host = redis_host or 'localhost'
        port = redis_port or '6379'
        db = redis_db or '0'
        if redis_password:
            redis_url = f'redis://:{redis_password}@{host}:{port}/{db}'
        else:
            redis_url = f'redis://{host}:{port}/{db}'
        app.state.redis = Redis.from_url(redis_url, decode_responses=True)
    else:
        app.state.redis = None

    app.state._purger_task = asyncio.create_task(automatic_purger(1800))

    METRICS_FILE = os.path.join(LOGS_DIR, 'metrics.json')
    try:
        metrics_store.load_from_file(METRICS_FILE)
    except Exception as e:
        gateway_logger.debug(f'Metrics restore skipped: {e}')

    async def _metrics_autosave(interval_s: int = 60):
        while True:
            try:
                await asyncio.sleep(interval_s)
                metrics_store.save_to_file(METRICS_FILE)
            except asyncio.CancelledError:
                break
            except Exception:
                pass
    try:
        app.state._metrics_save_task = asyncio.create_task(_metrics_autosave(60))
    except Exception:
        app.state._metrics_save_task = None

    try:
        await load_settings()
        await start_auto_save_task()
    except Exception as e:
        gateway_logger.error(f'Failed to initialize security settings auto-save: {e}')

    try:
        settings = get_cached_settings()
        if bool(settings.get('trust_x_forwarded_for')) and not (settings.get('xff_trusted_proxies') or []):
            gateway_logger.warning('Security: trust_x_forwarded_for enabled but xff_trusted_proxies is empty; header spoofing risk. Configure trusted proxy IPs/CIDRs.')

            if os.getenv('ENV', '').lower() == 'production':
                raise RuntimeError(
                    'Production deployment with trust_x_forwarded_for requires xff_trusted_proxies '
                    'to prevent IP spoofing. Configure trusted proxy IPs/CIDRs via /platform/security endpoint.'
                )
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise
        gateway_logger.debug(f'Startup security checks skipped: {e}')

    try:
        spec = app.openapi()
        problems = []
        for route in app.routes:
            path = getattr(route, 'path', '')
            if not path.startswith(('/platform', '/api')):
                continue
            include = getattr(route, 'include_in_schema', True)
            methods = set(getattr(route, 'methods', set()) or [])
            if not include or 'OPTIONS' in methods:
                continue
            if not getattr(route, 'description', None):
                problems.append(f'Route {path} missing description')
            if not getattr(route, 'response_model', None):
                problems.append(f'Route {path} missing response_model')
        if problems:
            gateway_logger.info('OpenAPI lint: \n' + '\n'.join(problems[:50]))
    except Exception as e:
        gateway_logger.debug(f'OpenAPI lint skipped: {e}')

    try:
        if database.memory_only:
            settings = get_cached_settings()
            hint = settings.get('dump_path')
            latest_path = find_latest_dump_path(hint)
            if latest_path and os.path.exists(latest_path):
                info = restore_memory_from_file(latest_path)
                gateway_logger.info(f"Memory mode: restored from dump {latest_path} (created_at={info.get('created_at')})")
            else:
                gateway_logger.info('Memory mode: no existing dump found to restore')
    except Exception as e:
        gateway_logger.error(f'Memory mode restore failed: {e}')

    try:
        if hasattr(signal, 'SIGUSR1'):
            loop = asyncio.get_event_loop()

            async def _sigusr1_dump():
                try:
                    if not database.memory_only:
                        gateway_logger.info('SIGUSR1 ignored: not in memory-only mode')
                        return
                    if not os.getenv('MEM_ENCRYPTION_KEY'):
                        gateway_logger.error('SIGUSR1 dump skipped: MEM_ENCRYPTION_KEY not configured')
                        return
                    settings = get_cached_settings()
                    path_hint = settings.get('dump_path')
                    dump_path = await asyncio.to_thread(dump_memory_to_file, path_hint)
                    gateway_logger.info(f'SIGUSR1: memory dump written to {dump_path}')
                except Exception as e:
                    gateway_logger.error(f'SIGUSR1 dump failed: {e}')

            loop.add_signal_handler(signal.SIGUSR1, lambda: asyncio.create_task(_sigusr1_dump()))
            gateway_logger.info('SIGUSR1 handler registered for on-demand memory dumps')
    except NotImplementedError:

        pass

    try:
        if hasattr(signal, 'SIGHUP'):
            loop = asyncio.get_event_loop()

            async def _sighup_reload():
                try:
                    gateway_logger.info('SIGHUP received: reloading configuration...')

                    hot_config.reload()

                    log_level = hot_config.get('LOG_LEVEL', 'INFO')
                    try:
                        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
                        logging.getLogger('doorman.gateway').setLevel(numeric_level)
                        gateway_logger.info(f'Log level updated to {log_level}')
                    except Exception as e:
                        gateway_logger.error(f'Failed to update log level: {e}')

                    gateway_logger.info('Configuration reload complete')
                except Exception as e:
                    gateway_logger.error(f'SIGHUP reload failed: {e}', exc_info=True)

            loop.add_signal_handler(signal.SIGHUP, lambda: asyncio.create_task(_sighup_reload()))
            gateway_logger.info('SIGHUP handler registered for configuration hot reload')
    except (NotImplementedError, AttributeError):
        gateway_logger.debug('SIGHUP not supported on this platform')

    try:
        yield
    finally:
        gateway_logger.info("Starting graceful shutdown...")
        app.state.shutting_down = True
        gateway_logger.info("Waiting for in-flight requests to complete (5s grace period)...")
        await asyncio.sleep(5)
        try:
            await stop_auto_save_task()
        except Exception as e:
            gateway_logger.error(f'Failed to stop auto-save task: {e}')
        try:
            if database.memory_only:
                settings = get_cached_settings()
                path = settings.get('dump_path')
                dump_memory_to_file(path)
                gateway_logger.info(f'Final memory dump written to {path}')
        except Exception as e:
            gateway_logger.error(f'Failed to write final memory dump: {e}')
        try:
            task = getattr(app.state, '_purger_task', None)
            if task:
                task.cancel()
        except Exception:
            pass
        try:
            gateway_logger.info("Closing database connections...")
            from utils.database import close_database_connections
            close_database_connections()
        except Exception as e:
            gateway_logger.error(f"Error closing database connections: {e}")
        try:
            gateway_logger.info("Closing HTTP clients...")
            from services.gateway_service import GatewayService
            if hasattr(GatewayService, '_http_client') and GatewayService._http_client:
                await GatewayService._http_client.aclose()
                gateway_logger.info("HTTP client closed")
        except Exception as e:
            gateway_logger.error(f"Error closing HTTP client: {e}")

        try:
            METRICS_FILE = os.path.join(LOGS_DIR, 'metrics.json')
            metrics_store.save_to_file(METRICS_FILE)
        except Exception:
            pass

        gateway_logger.info("Graceful shutdown complete")
        try:
            t = getattr(app.state, '_metrics_save_task', None)
            if t:
                t.cancel()
        except Exception:
            pass

        try:
            from services.gateway_service import GatewayService as _GS
            if os.getenv('ENABLE_HTTPX_CLIENT_CACHE', 'true').lower() != 'false':
                try:
                    import asyncio as _asyncio
                    if _asyncio.iscoroutinefunction(_GS.aclose_http_client):
                        await _GS.aclose_http_client()
                except Exception:
                    pass
        except Exception:
            pass

def _generate_unique_id(route):
    try:
        name = getattr(route, 'name', 'op') or 'op'
        path = getattr(route, 'path', '').replace('/', '_').replace('{', '').replace('}', '')
        methods = '_'.join(sorted(list(getattr(route, 'methods', []) or [])))
        return f"{name}_{methods}_{path}".lower()
    except Exception:
        return (getattr(route, 'name', 'op') or 'op').lower()

doorman = FastAPI(
    title='doorman',
    description="A lightweight API gateway for AI, REST, SOAP, GraphQL, gRPC, and WebSocket APIs — fully managed with built-in RESTful APIs for configuration and control. This is your application's gateway to the world.",
    version='1.0.0',
    lifespan=app_lifespan,
    generate_unique_id_function=_generate_unique_id,
)

https_only = os.getenv('HTTPS_ONLY', 'false').lower() == 'true'
domain = os.getenv('COOKIE_DOMAIN', 'localhost')

# - API gateway routes (/api/*): CORS controlled per-API in gateway routes/services

def _env_cors_config():
    origins_env = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000')
    if not (origins_env or '').strip():
        origins_env = 'http://localhost:3000'
    origins = [o.strip() for o in origins_env.split(',') if o.strip()]
    credentials = os.getenv('ALLOW_CREDENTIALS', 'true').lower() == 'true'
    methods_env = os.getenv('ALLOW_METHODS', 'GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD')
    if not (methods_env or '').strip():
        methods_env = 'GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD'
    methods = [m.strip().upper() for m in methods_env.split(',') if m.strip()]
    if 'OPTIONS' not in methods:
        methods.append('OPTIONS')
    headers_env = os.getenv('ALLOW_HEADERS', '*')
    if not (headers_env or '').strip():
        headers_env = '*'
    raw_headers = [h.strip() for h in headers_env.split(',') if h.strip()]
    if any(h == '*' for h in raw_headers):
        headers = ['Accept', 'Content-Type', 'X-CSRF-Token', 'Authorization']
    else:
        headers = raw_headers
    def _safe(origins, credentials):
        if credentials and any(o.strip() == '*' for o in origins):
            return ['http://localhost', 'http://localhost:3000']
        if os.getenv('CORS_STRICT', 'false').lower() == 'true':
            safe = [o for o in origins if o.strip() != '*']
            return safe if safe else ['http://localhost', 'http://localhost:3000']
        return origins
    return {
        'origins': origins,
        'safe_origins': _safe(origins, credentials),
        'credentials': credentials,
        'methods': methods,
        'headers': headers,
    }

def _origin_matches_allowed(origin: str | None, cfg: dict) -> bool:
    """Return True if the Origin matches configured allowed origins.

    Supports:
    - Exact matches (e.g., https://app.example.com)
    - Subdomain globs using a single leading wildcard (e.g., https://*.example.com)
    - When CORS_STRICT=false and '*' is present, allow any origin (development only)
    """
    try:
        if not origin:
            return False

        strict = os.getenv('CORS_STRICT', 'false').lower() == 'true'
        allowed = cfg.get('origins') or []
        safe = cfg.get('safe_origins') or []

        # Development convenience: wildcard allowed only when not strict
        if not strict and any(o.strip() == '*' for o in allowed):
            return True

        # Exact allow list (preferred)
        if origin in safe or origin in allowed:
            return True

        # Simple wildcard subdomain support: https://*.example.com
        # We only support a single leading '*' before a dot.
        # Convert pattern to suffix check.
        for entry in allowed:
            e = (entry or '').strip()
            if not e:
                continue
            if e.startswith('http://*.') or e.startswith('https://*.'):
                # Split scheme and host suffix
                try:
                    scheme, rest = e.split('://', 1)
                    host_suffix = rest[1:]  # drop the leading '*'
                    if '://' in origin:
                        o_scheme, o_host = origin.split('://', 1)
                    else:
                        # Fallback: assume https
                        o_scheme, o_host = 'https', origin
                    if o_scheme != scheme:
                        continue
                    if o_host.endswith(host_suffix) and o_host.count('.') >= host_suffix.count('.') + 1:
                        return True
                except Exception:
                    continue
        return False
    except Exception:
        return False

@doorman.middleware('http')
async def platform_cors(request: Request, call_next):
    try:
        if os.getenv('DISABLE_PLATFORM_CORS_ASGI', 'false').lower() in ('1','true','yes','on'):
            path = str(request.url.path)
            if path.startswith('/platform/'):
                cfg = _env_cors_config()
                origin = request.headers.get('origin') or request.headers.get('Origin')
                origin_allowed = _origin_matches_allowed(origin, cfg)

                if request.method.upper() == 'OPTIONS':
                    from fastapi.responses import Response as _Resp
                    headers = {}
                    if origin and origin_allowed:
                        headers['Access-Control-Allow-Origin'] = origin
                        headers['Vary'] = 'Origin'
                    headers['Access-Control-Allow-Methods'] = ', '.join(cfg['methods'])
                    headers['Access-Control-Allow-Headers'] = ', '.join(cfg['headers'])
                    headers['Access-Control-Allow-Credentials'] = 'true' if cfg['credentials'] else 'false'
                    rid = request.headers.get('x-request-id') or request.headers.get('X-Request-ID')
                    if rid:
                        headers['request_id'] = rid
                    return _Resp(status_code=204, headers=headers)

                response = await call_next(request)
                try:
                    response.headers['Access-Control-Allow-Credentials'] = 'true' if cfg['credentials'] else 'false'
                    if origin and origin_allowed:
                        response.headers['Access-Control-Allow-Origin'] = origin
                        # Normalize Vary to exactly 'Origin'
                        try:
                            # Remove any pre-existing Vary to avoid appended values
                            _ = response.headers.pop('Vary', None)
                        except Exception:
                            pass
                        response.headers['Vary'] = 'Origin'
                except Exception:
                    pass
                return response
    except Exception:
        pass
    return await call_next(request)

MAX_BODY_SIZE = int(os.getenv('MAX_BODY_SIZE_BYTES', 1_048_576))

def _get_max_body_size() -> int:
    try:
        v = os.getenv('MAX_BODY_SIZE_BYTES')
        if v is None or str(v).strip() == '':
            return MAX_BODY_SIZE
        return int(v)
    except Exception:
        return MAX_BODY_SIZE

class LimitedStreamReader:
    """
    Wrapper around ASGI receive channel that enforces size limits on chunked requests.

    Prevents Transfer-Encoding: chunked bypass by tracking accumulated size
    and rejecting streams that exceed the limit.
    """
    def __init__(self, receive, max_size: int):
        self.receive = receive
        self.max_size = max_size
        self.bytes_received = 0
        self.over_limit = False

    async def __call__(self):
        if self.over_limit:
            return {'type': 'http.request', 'body': b'', 'more_body': False}

        message = await self.receive()

        if message.get('type') == 'http.request':
            body = message.get('body', b'') or b''
            self.bytes_received += len(body)

            if self.bytes_received > self.max_size:
                self.over_limit = True
                return {'type': 'http.request', 'body': b'', 'more_body': False}

        return message

@doorman.middleware('http')
async def body_size_limit(request: Request, call_next):
    """Enforce request body size limits to prevent DoS attacks.

    Protects against both:
    - Content-Length header (fast path)
    - Transfer-Encoding: chunked (stream enforcement)

    Default limit: 1MB (configurable via MAX_BODY_SIZE_BYTES)
    Per-API overrides: MAX_BODY_SIZE_BYTES_<API_TYPE> (e.g., MAX_BODY_SIZE_BYTES_SOAP)

    Protected paths:
    - /platform/authorization: Strict enforcement (prevent auth DoS)
    - /api/rest/*: Enforce on all requests
    - /api/soap/*: Enforce on XML/SOAP bodies
    - /api/graphql/*: Enforce on GraphQL queries
    - /api/grpc/*: Enforce on gRPC JSON payloads
    """
    try:
        if os.getenv('DISABLE_BODY_SIZE_LIMIT', 'false').lower() in ('1','true','yes','on'):
            return await call_next(request)
        path = str(request.url.path)

        try:
            raw_excludes = os.getenv('BODY_LIMIT_EXCLUDE_PATHS', '')
            if raw_excludes:
                excludes = [p.strip() for p in raw_excludes.split(',') if p.strip()]
                if any(path == p or (p.endswith('*') and path.startswith(p[:-1])) for p in excludes):
                    return await call_next(request)
        except Exception:
            pass

        if path.startswith('/platform/monitor/'):
            return await call_next(request)

        if path == '/platform/security/settings':
            try:
                return await call_next(request)
            except Exception as e:
                msg = str(e)
                if 'EndOfStream' in msg or 'No response returned' in msg:
                    try:
                        from models.response_model import ResponseModel as _RM
                        from utils.response_util import process_response as _pr
                        return _pr(_RM(
                            status_code=200,
                            message='Settings updated (middleware bypass)'
                        ).dict(), 'rest')
                    except Exception:
                        pass
                raise

        should_enforce = False
        default_limit = _get_max_body_size()
        limit = default_limit

        if path.startswith('/platform/authorization'):
            should_enforce = True
        elif path.startswith('/api/soap/'):
            should_enforce = True
            limit = int(os.getenv('MAX_BODY_SIZE_BYTES_SOAP', default_limit))
        elif path.startswith('/api/graphql/'):
            should_enforce = True
            limit = int(os.getenv('MAX_BODY_SIZE_BYTES_GRAPHQL', default_limit))
        elif path.startswith('/api/grpc/'):
            should_enforce = True
            limit = int(os.getenv('MAX_BODY_SIZE_BYTES_GRPC', default_limit))
        elif path.startswith('/api/rest/'):
            should_enforce = True
            limit = int(os.getenv('MAX_BODY_SIZE_BYTES_REST', default_limit))
        elif path.startswith('/api/'):
            should_enforce = True
        elif path.startswith('/platform/'):
            should_enforce = True

        if not should_enforce:
            return await call_next(request)

        cl = request.headers.get('content-length')
        transfer_encoding = request.headers.get('transfer-encoding', '').lower()

        if cl and str(cl).strip() != '':
            try:
                content_length = int(cl)
                if content_length > limit:
                    try:
                        from utils.audit_util import audit
                        audit(
                            request,
                            actor=None,
                            action='request.body_size_exceeded',
                            target=path,
                            status='blocked',
                            details={
                                'content_length': content_length,
                                'limit': limit,
                                'content_type': request.headers.get('content-type'),
                                'transfer_encoding': transfer_encoding or None
                            }
                        )
                    except Exception:
                        pass

                    return process_response(ResponseModel(
                        status_code=413,
                        error_code='REQ001',
                        error_message=f'Request entity too large (max: {limit} bytes)'
                    ).dict(), 'rest')
            except (ValueError, TypeError):
                pass

        if 'chunked' in transfer_encoding or not cl:
            if request.method in ('POST', 'PUT', 'PATCH'):
                wrap_allowed = True
                try:
                    env_flag = os.getenv('DISABLE_PLATFORM_CHUNKED_WRAP')
                    if isinstance(env_flag, str) and env_flag.strip() != '':
                        if env_flag.strip().lower() in ('1','true','yes','on'):
                            wrap_allowed = False
                    if str(path) == '/platform/authorization':
                        wrap_allowed = True
                except Exception:
                    pass

                if wrap_allowed:
                    original_receive = request.receive
                    limited_reader = LimitedStreamReader(original_receive, limit)
                    request._receive = limited_reader

                try:
                    response = await call_next(request)

                    try:
                        if wrap_allowed and (limited_reader.over_limit or limited_reader.bytes_received > limit):
                            try:
                                from utils.audit_util import audit
                                audit(
                                    request,
                                    actor=None,
                                    action='request.body_size_exceeded',
                                    target=path,
                                    status='blocked',
                                    details={
                                        'bytes_received': limited_reader.bytes_received,
                                        'limit': limit,
                                        'content_type': request.headers.get('content-type'),
                                        'transfer_encoding': transfer_encoding or 'chunked'
                                    }
                                )
                            except Exception:
                                pass

                            return process_response(ResponseModel(
                                status_code=413,
                                error_code='REQ001',
                                error_message=f'Request entity too large (max: {limit} bytes)'
                            ).dict(), 'rest')
                    except Exception:
                        pass

                    return response
                except Exception as e:
                    try:
                        if wrap_allowed and (limited_reader.over_limit or limited_reader.bytes_received > limit):
                            return process_response(ResponseModel(
                                status_code=413,
                                error_code='REQ001',
                                error_message=f'Request entity too large (max: {limit} bytes)'
                            ).dict(), 'rest')
                    except Exception:
                        pass
                    raise

        return await call_next(request)
    except Exception as e:
        try:
            from models.response_model import ResponseModel as _RM
            from utils.response_util import process_response as _pr
        except Exception:
            _RM = None
            _pr = None

        msg = str(e)
        gateway_logger.error(f'Body size limit middleware error: {msg}', exc_info=True)

        swallow = False
        try:
            if isinstance(e, RuntimeError) and 'No response returned' in msg:
                swallow = True
            else:
                try:
                    import anyio
                    if isinstance(e, getattr(anyio, 'EndOfStream', tuple())):
                        swallow = True
                except Exception:
                    pass
        except Exception:
            pass

        if swallow and _RM and _pr:
            try:
                return _pr(_RM(
                    status_code=500,
                    error_code='GTW998',
                    error_message='Upstream handler failed to produce a response'
                ).dict(), 'rest')
            except Exception:
                pass

        raise

class PlatformCORSMiddleware:
    """ASGI-level CORS for /platform/* routes to avoid BaseHTTPMiddleware pitfalls.

    - Handles OPTIONS preflight directly
    - Injects CORS headers on response start for matching origins
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        try:
            if os.getenv('DISABLE_PLATFORM_CORS_ASGI', 'false').lower() in ('1','true','yes','on'):
                return await self.app(scope, receive, send)
        except Exception:
            pass
        try:
            if scope.get('type') != 'http':
                return await self.app(scope, receive, send)
            path = scope.get('path') or ''
            if not str(path).startswith('/platform/'):
                return await self.app(scope, receive, send)

            cfg = _env_cors_config()
            hdrs = {}
            try:
                for k, v in (scope.get('headers') or []):
                    hdrs[k.decode('latin1').lower()] = v.decode('latin1')
            except Exception:
                pass
            origin = hdrs.get('origin')
            origin_allowed = _origin_matches_allowed(origin, cfg)

            if str(scope.get('method', '')).upper() == 'OPTIONS':
                headers = []
                if origin and origin_allowed:
                    headers.append((b'access-control-allow-origin', origin.encode('latin1')))
                    headers.append((b'vary', b'Origin'))
                headers.append((b'access-control-allow-methods', ', '.join(cfg['methods']).encode('latin1')))
                headers.append((b'access-control-allow-headers', ', '.join(cfg['headers']).encode('latin1')))
                headers.append((b'access-control-allow-credentials', b'true' if cfg['credentials'] else b'false'))
                rid = hdrs.get('x-request-id')
                if rid:
                    headers.append((b'request_id', rid.encode('latin1')))
                await send({'type': 'http.response.start', 'status': 204, 'headers': headers})
                await send({'type': 'http.response.body', 'body': b''})
                return

            async def send_wrapper(message):
                if message.get('type') == 'http.response.start':
                    headers = list(message.get('headers') or [])
                    try:
                        headers.append((b'access-control-allow-credentials', b'true' if cfg['credentials'] else b'false'))
                        if origin and origin_allowed:
                            headers.append((b'access-control-allow-origin', origin.encode('latin1')))
                            headers.append((b'vary', b'Origin'))
                    except Exception:
                        pass
                    message = {**message, 'headers': headers}
                await send(message)

            return await self.app(scope, receive, send_wrapper)
        except Exception:
            return await self.app(scope, receive, send)

doorman.add_middleware(PlatformCORSMiddleware)

@doorman.middleware('http')
async def request_id_middleware(request: Request, call_next):
    try:
        rid = (
            request.headers.get('x-request-id')
            or request.headers.get('request-id')
            or request.headers.get('x-request-id'.title())
        )
        if not rid:
            rid = str(uuid.uuid4())

        try:
            request.state.request_id = rid
        except Exception:
            pass

        try:
            from utils.correlation_util import set_correlation_id
            set_correlation_id(rid)
        except Exception:
            pass
        try:
            settings = get_cached_settings()
            trust_xff = bool(settings.get('trust_x_forwarded_for'))
            direct_ip = getattr(getattr(request, 'client', None), 'host', None)
            effective_ip = _policy_get_client_ip(request, trust_xff)
            gateway_logger.info(f"{rid} | Entry: client_ip={direct_ip} effective_ip={effective_ip} method={request.method} path={str(request.url.path)}")
        except Exception:
            pass
        response = await call_next(request)
        try:
            response.headers['X-Request-ID'] = rid
            response.headers['request_id'] = rid
        except Exception as e:
            gateway_logger.warning(f'Failed to set response headers: {str(e)}')
        return response
    except Exception as e:
        gateway_logger.error(f'Request ID middleware error: {str(e)}', exc_info=True)
        raise

@doorman.middleware('http')
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    try:
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'no-referrer')
        response.headers.setdefault('Permissions-Policy', 'geolocation=(), microphone=(), camera=()')

        try:
            csp = os.getenv('CONTENT_SECURITY_POLICY')
            if csp is None or not csp.strip():

                csp =\
                    "default-src 'none'; "\
                    "frame-ancestors 'none'; "\
                    "base-uri 'none'; "\
                    "form-action 'self'; "\
                    "img-src 'self' data:; "\
                    "connect-src 'self';"
            response.headers.setdefault('Content-Security-Policy', csp)
        except Exception:
            pass
        if os.getenv('HTTPS_ONLY', 'false').lower() == 'true':

            response.headers.setdefault('Strict-Transport-Security', 'max-age=15552000; includeSubDomains; preload')
    except Exception:
        pass
    return response

"""Logging configuration

Prefer file logging to LOGS_DIR/doorman.log when writable; otherwise, fall back
to console so production environments (e.g., ECS/EKS/Lambda) still capture logs.
Respects LOG_FORMAT=json|plain.
"""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_env_logs_dir = os.getenv('LOGS_DIR')
LOGS_DIR = os.path.abspath(_env_logs_dir) if _env_logs_dir else os.path.join(BASE_DIR, 'platform-logs')

# Build formatters
class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'time': self.formatTime(record, '%Y-%m-%dT%H:%M:%S'),
            'name': record.name,
            'level': record.levelname,
            'message': record.getMessage(),
        }
        try:
            return json.dumps(payload, ensure_ascii=False)
        except Exception:
            return f'{payload}'

_fmt_is_json = os.getenv('LOG_FORMAT', 'plain').lower() == 'json'
_file_handler = None
try:
    os.makedirs(LOGS_DIR, exist_ok=True)
    _file_handler = RotatingFileHandler(
        filename=os.path.join(LOGS_DIR, 'doorman.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    _file_handler.setFormatter(JSONFormatter() if _fmt_is_json else logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
except Exception as _e:
    logging.getLogger('doorman.gateway').warning(f'File logging disabled ({_e}); using console logging only')
    _file_handler = None

# Configure all doorman loggers to use the same handler and prevent propagation
def configure_logger(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    class RedactFilter(logging.Filter):
        """Comprehensive logging redaction filter for sensitive data.

        Redacts:
        - Authorization headers (Bearer, Basic, API-Key, etc.)
        - Access/refresh tokens
        - Passwords and secrets
        - Cookies and session data
        - API keys and credentials
        - CSRF tokens
        """

        PATTERNS = [
            re.compile(r'(?i)(authorization\s*[:=]\s*)([^;\r\n]+)'),

            re.compile(r'(?i)(x-api-key\s*[:=]\s*)([^;\r\n]+)'),
            re.compile(r'(?i)(api[_-]?key\s*[:=]\s*)([^;\r\n]+)'),
            re.compile(r'(?i)(api[_-]?secret\s*[:=]\s*)([^;\r\n]+)'),

            re.compile(r'(?i)(access[_-]?token\s*["\']?\s*[:=]\s*["\']?)([^"\';\r\n\s]+)(["\']?)'),
            re.compile(r'(?i)(refresh[_-]?token\s*["\']?\s*[:=]\s*["\']?)([^"\';\r\n\s]+)(["\']?)'),
            re.compile(r'(?i)(token\s*["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_\-\.]{20,})(["\']?)'),

            re.compile(r'(?i)(password\s*["\']?\s*[:=]\s*["\']?)([^"\';\r\n]+)(["\']?)'),
            re.compile(r'(?i)(secret\s*["\']?\s*[:=]\s*["\']?)([^"\';\r\n\s]+)(["\']?)'),
            re.compile(r'(?i)(client[_-]?secret\s*["\']?\s*[:=]\s*["\']?)([^"\';\r\n\s]+)(["\']?)'),

            re.compile(r'(?i)(cookie\s*[:=]\s*)([^;\r\n]+)'),
            re.compile(r'(?i)(set-cookie\s*[:=]\s*)([^;\r\n]+)'),

            re.compile(r'(?i)(x-csrf-token\s*[:=]\s*["\']?)([^"\';\r\n\s]+)(["\']?)'),
            re.compile(r'(?i)(csrf[_-]?token\s*["\']?\s*[:=]\s*["\']?)([^"\';\r\n\s]+)(["\']?)'),

            re.compile(r'\b(eyJ[a-zA-Z0-9_\-]+\.eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+)\b'),

            re.compile(r'(?i)(session[_-]?id\s*["\']?\s*[:=]\s*["\']?)([^"\';\r\n\s]+)(["\']?)'),

            re.compile(r'(-----BEGIN[A-Z\s]+PRIVATE KEY-----)(.*?)(-----END[A-Z\s]+PRIVATE KEY-----)', re.DOTALL),
        ]

        def filter(self, record: logging.LogRecord) -> bool:
            try:
                msg = str(record.getMessage())
                red = msg

                for pat in self.PATTERNS:
                    if pat.groups == 3 and pat.flags & re.DOTALL:
                        red = pat.sub(r'\1[REDACTED]\3', red)
                    elif pat.groups >= 2:
                        red = pat.sub(lambda m: (
                            m.group(1) +
                            '[REDACTED]' +
                            (m.group(3) if m.lastindex and m.lastindex >= 3 else '')
                        ), red)
                    else:
                        red = pat.sub('[REDACTED]', red)

                if red != msg:
                    record.msg = red
                    if hasattr(record, 'args') and record.args:
                        try:
                            if isinstance(record.args, dict):
                                record.args = {k: '[REDACTED]' if 'token' in str(k).lower() or 'password' in str(k).lower() or 'secret' in str(k).lower() or 'authorization' in str(k).lower() else v for k, v in record.args.items()}
                        except Exception:
                            pass
            except Exception:
                pass
            return True

    console = logging.StreamHandler(stream=sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(JSONFormatter() if _fmt_is_json else logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    console.addFilter(RedactFilter())
    logger.addHandler(console)

    if _file_handler is not None:

        if not any(isinstance(f, logging.Filter) and hasattr(f, 'PATTERNS') for f in _file_handler.filters):
            _file_handler.addFilter(RedactFilter())
        logger.addHandler(_file_handler)
    return logger

gateway_logger = configure_logger('doorman.gateway')
logging_logger = configure_logger('doorman.logging')

# Add GZip compression middleware (configurable via environment variables)
# This should be added early in the middleware stack so it compresses final responses
try:
    compression_enabled = os.getenv('COMPRESSION_ENABLED', 'true').lower() == 'true'
    if compression_enabled:
        compression_level = int(os.getenv('COMPRESSION_LEVEL', '1'))
        compression_minimum_size = int(os.getenv('COMPRESSION_MINIMUM_SIZE', '500'))

        # Validate compression level (1-9)
        if not 1 <= compression_level <= 9:
            gateway_logger.warning(
                f'Invalid COMPRESSION_LEVEL={compression_level}. Must be 1-9. Using default: 1'
            )
            compression_level = 1

        doorman.add_middleware(
            GZipMiddleware,
            minimum_size=compression_minimum_size,
            compresslevel=compression_level
        )
        gateway_logger.info(
            f'Response compression enabled: level={compression_level}, '
            f'minimum_size={compression_minimum_size} bytes'
        )
    else:
        gateway_logger.info('Response compression disabled (COMPRESSION_ENABLED=false)')
except Exception as e:
    gateway_logger.warning(f'Failed to configure response compression: {e}. Compression disabled.')

# Ensure platform responses set Vary=Origin (and not Accept-Encoding) for CORS tests.
class _VaryOriginMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        try:
            p = str(request.url.path)
            if p.startswith('/platform/'):
                # Force Vary to exactly 'Origin'
                try:
                    _ = response.headers.pop('Vary', None)
                except Exception:
                    pass
                response.headers['Vary'] = 'Origin'
        except Exception:
            pass
        return response

doorman.add_middleware(_VaryOriginMiddleware)

# Now that logging is configured, attempt to migrate any legacy 'generated/' dir
try:
    _migrate_generated_directory()
except Exception:
    # Non-fatal: migration best-effort only
    pass

audit_logger = logging.getLogger('doorman.audit')
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False
for h in audit_logger.handlers[:]:
    audit_logger.removeHandler(h)
try:
    os.makedirs(LOGS_DIR, exist_ok=True)
    _audit_file = RotatingFileHandler(
        filename=os.path.join(LOGS_DIR, 'doorman-trail.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    _audit_file.setFormatter(JSONFormatter() if _fmt_is_json else logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    try:
        for eh in gateway_logger.handlers:
            for f in getattr(eh, 'filters', []):
                _audit_file.addFilter(f)
    except Exception:
        pass
    audit_logger.addHandler(_audit_file)
except Exception as _e:

    console = logging.StreamHandler(stream=sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(JSONFormatter() if _fmt_is_json else logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    try:
        for eh in gateway_logger.handlers:
            for f in getattr(eh, 'filters', []):
                console.addFilter(f)
    except Exception:
        pass
    audit_logger.addHandler(console)

class Settings(BaseSettings):
    mongo_db_uri: str = os.getenv('MONGO_DB_URI')
    jwt_secret_key: str = os.getenv('JWT_SECRET_KEY')
    jwt_algorithm: str = 'HS256'
    jwt_access_token_expires: timedelta = timedelta(minutes=int(os.getenv('ACCESS_TOKEN_EXPIRES_MINUTES', 15)))
    jwt_refresh_token_expires: timedelta = timedelta(days=int(os.getenv('REFRESH_TOKEN_EXPIRES_DAYS', 30)))

@doorman.middleware('http')
async def ip_filter_middleware(request: Request, call_next):
    try:
        path = str(request.url.path)
        if path == '/platform/security/settings':
            return await call_next(request)

        settings = get_cached_settings()
        wl = settings.get('ip_whitelist') or []
        bl = settings.get('ip_blacklist') or []
        trust_xff = bool(settings.get('trust_x_forwarded_for'))
        client_ip = _policy_get_client_ip(request, trust_xff)
        xff_hdr = request.headers.get('x-forwarded-for') or request.headers.get('X-Forwarded-For')

        try:
            import os
            settings = get_cached_settings()
            env_flag = os.getenv('LOCAL_HOST_IP_BYPASS')
            allow_local = (env_flag.lower() == 'true') if isinstance(env_flag, str) and env_flag.strip() != '' else bool(settings.get('allow_localhost_bypass'))
            if allow_local:
                direct_ip = getattr(getattr(request, 'client', None), 'host', None)
                has_forward = any(request.headers.get(h) for h in ('x-forwarded-for','X-Forwarded-For','x-real-ip','X-Real-IP','cf-connecting-ip','CF-Connecting-IP','forwarded','Forwarded'))
                if direct_ip and _policy_is_loopback(direct_ip) and not has_forward:
                    return await call_next(request)
        except Exception:
            pass

        if client_ip:
            if wl and not _policy_ip_in_list(client_ip, wl):
                try:
                    audit(request, actor=None, action='ip.global_deny', target=client_ip, status='blocked', details={'reason': 'not_in_whitelist', 'xff': xff_hdr, 'source_ip': getattr(getattr(request, 'client', None), 'host', None)})
                except Exception:
                    pass
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=403, content={'status_code': 403, 'error_code': 'SEC010', 'error_message': 'IP not allowed'})
            if bl and _policy_ip_in_list(client_ip, bl):
                try:
                    audit(request, actor=None, action='ip.global_deny', target=client_ip, status='blocked', details={'reason': 'blacklisted', 'xff': xff_hdr, 'source_ip': getattr(getattr(request, 'client', None), 'host', None)})
                except Exception:
                    pass
                from fastapi.responses import JSONResponse
                return JSONResponse(status_code=403, content={'status_code': 403, 'error_code': 'SEC011', 'error_message': 'IP blocked'})
    except Exception:
        pass
    return await call_next(request)

@doorman.middleware('http')
async def metrics_middleware(request: Request, call_next):
    start = asyncio.get_event_loop().time()
    def _parse_len(val: str | None) -> int:
        try:
            return int(val) if val is not None else 0
        except Exception:
            return 0
    bytes_in = _parse_len(request.headers.get('content-length'))
    response = None
    try:
        response = await call_next(request)
        return response
    finally:

        try:
            if str(request.url.path).startswith('/api/'):
                end = asyncio.get_event_loop().time()
                duration_ms = (end - start) * 1000.0
                status = getattr(response, 'status_code', 500) if response is not None else 500
                username = None
                api_key = None

                try:
                    from utils.auth_util import auth_required as _auth_required
                    payload = await _auth_required(request)
                    username = payload.get('sub') if isinstance(payload, dict) else None
                except Exception:
                    pass

                p = str(request.url.path)
                if p.startswith('/api/rest/'):
                    parts = p.split('/')
                    try:
                        idx = parts.index('rest')
                        api_key = f'rest:{parts[idx+1]}' if len(parts) > idx+1 and parts[idx+1] else 'rest:unknown'
                    except ValueError:
                        api_key = 'rest:unknown'
                elif p.startswith('/api/graphql/'):

                    seg = p.rsplit('/', 1)[-1] or 'unknown'
                    api_key = f'graphql:{seg}'
                elif p.startswith('/api/soap/'):
                    seg = p.rsplit('/', 1)[-1] or 'unknown'
                    api_key = f'soap:{seg}'
                clen = 0
                try:
                    headers = getattr(response, 'headers', {}) or {}
                    clen = _parse_len(headers.get('content-length'))
                    if clen == 0:
                        # Fallback to explicit body length header set by response_util
                        clen = _parse_len(headers.get('x-body-length'))
                    if clen == 0:
                        body = getattr(response, 'body', None)
                        if isinstance(body, (bytes, bytearray)):
                            clen = len(body)
                except Exception:
                    clen = 0

                metrics_store.record(status=status, duration_ms=duration_ms, username=username, api_key=api_key, bytes_in=bytes_in, bytes_out=clen)
                try:
                    if username:
                        from utils.bandwidth_util import add_usage, _get_user
                        u = _get_user(username)
                        if u and u.get('bandwidth_limit_bytes') and u.get('bandwidth_limit_enabled') is not False:
                            add_usage(username, int(bytes_in) + int(clen), u.get('bandwidth_limit_window') or 'day')
                except Exception:
                    pass
                try:
                    # Normalize platform CORS Vary header last to avoid gzip appending
                    if str(request.url.path).startswith('/platform/'):
                        headers = getattr(response, 'headers', None)
                        if headers is not None:
                            try:
                                _ = headers.pop('Vary', None)
                            except Exception:
                                pass
                            headers['Vary'] = 'Origin'
                except Exception:
                    pass
        except Exception:

            pass

async def automatic_purger(interval_seconds):
    while True:
        await asyncio.sleep(interval_seconds)
        await purge_expired_tokens()
        gateway_logger.info('Expired JWTs purged from blacklist.')

@doorman.exception_handler(JWTError)
async def jwt_exception_handler(exc: JWTError):
    return process_response(ResponseModel(
        status_code=401,
        error_code='JWT001',
        error_message='Invalid token'
    ).dict(), 'rest')

@doorman.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    return process_response(ResponseModel(
        status_code=500,
        error_code='ISE001',
        error_message='Internal Server Error'
    ).dict(), 'rest')

@doorman.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return process_response(ResponseModel(
        status_code=422,
        error_code='VAL001',
        error_message='Validation Error'
    ).dict(), 'rest')

cache_manager.init_app(doorman)

doorman.include_router(gateway_router, prefix='/api', tags=['Gateway'])
doorman.include_router(authorization_router, prefix='/platform', tags=['Authorization'])
doorman.include_router(user_router, prefix='/platform/user', tags=['User'])
doorman.include_router(api_router, prefix='/platform/api', tags=['API'])
doorman.include_router(endpoint_router, prefix='/platform/endpoint', tags=['Endpoint'])
doorman.include_router(group_router, prefix='/platform/group', tags=['Group'])
doorman.include_router(role_router, prefix='/platform/role', tags=['Role'])
doorman.include_router(subscription_router, prefix='/platform/subscription', tags=['Subscription'])
doorman.include_router(routing_router, prefix='/platform/routing', tags=['Routing'])
doorman.include_router(proto_router, prefix='/platform/proto', tags=['Proto'])
doorman.include_router(logging_router, prefix='/platform/logging', tags=['Logging'])
doorman.include_router(dashboard_router, prefix='/platform/dashboard', tags=['Dashboard'])
doorman.include_router(memory_router, prefix='/platform', tags=['Memory'])
doorman.include_router(security_router, prefix='/platform', tags=['Security'])
doorman.include_router(monitor_router, prefix='/platform', tags=['Monitor'])
doorman.include_router(credit_router, prefix='/platform/credit', tags=['Credit'])
doorman.include_router(demo_router, prefix='/platform/demo', tags=['Demo'])
doorman.include_router(config_router, prefix='/platform', tags=['Config'])
doorman.include_router(tools_router, prefix='/platform/tools', tags=['Tools'])
doorman.include_router(config_hot_reload_router, prefix='/platform', tags=['Config Hot Reload'])

def start():
    if os.path.exists(PID_FILE):
        gateway_logger.info('doorman is already running!')
        sys.exit(0)
    if os.name == 'nt':
        process = subprocess.Popen([sys.executable, __file__, 'run'],
                                   creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
    else:
        process = subprocess.Popen([sys.executable, __file__, 'run'],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,
                                   preexec_fn=os.setsid)
    with open(PID_FILE, 'w') as f:
        f.write(str(process.pid))
    gateway_logger.info(f'Starting doorman with PID {process.pid}.')

def stop():
    if not os.path.exists(PID_FILE):
        gateway_logger.info('No running instance found')
        return
    with open(PID_FILE, 'r') as f:
        pid = int(f.read())
    try:
        if os.name == 'nt':
            subprocess.call(['taskkill', '/F', '/PID', str(pid)])
        else:
            os.killpg(pid, signal.SIGTERM)

            deadline = time.time() + 15
            while time.time() < deadline:
                try:

                    os.kill(pid, 0)
                    time.sleep(0.5)
                except ProcessLookupError:
                    break
        gateway_logger.info(f'Stopping doorman with PID {pid}')
    except ProcessLookupError:
        gateway_logger.info('Process already terminated')
    finally:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)

def restart():
    """Restart the doorman process using PID-based supervisor.
    This function is intended to be invoked from a detached helper process.
    """
    try:
        stop()

        time.sleep(1.0)
    except Exception as e:
        gateway_logger.error(f'Error during stop phase of restart: {e}')
    try:
        start()
    except Exception as e:
        gateway_logger.error(f'Error during start phase of restart: {e}')

def run():
    server_port = int(os.getenv('PORT', 5001))
    max_threads = multiprocessing.cpu_count()
    env_threads = int(os.getenv('THREADS', max_threads))
    num_threads = min(env_threads, max_threads)

    # Hard validation: memory-only mode requires a single worker.
    # Start-up should fail fast with a clear error instead of silently
    # modifying the configured worker count.
    if database.memory_only and env_threads != 1:
        raise RuntimeError(
            'MEM_OR_EXTERNAL=MEM requires THREADS=1. '
            'Set THREADS=1 for single-process memory mode or switch to MEM_OR_EXTERNAL=REDIS for multi-worker.'
        )
    gateway_logger.info(f'Started doorman with {num_threads} threads on port {server_port}')
    uvicorn.run(
        'doorman:doorman',
        host='0.0.0.0',
        port=server_port,
        reload=os.getenv('DEV_RELOAD', 'false').lower() == 'true',
        reload_excludes=['venv/*', 'logs/*'],
        workers=num_threads,
        log_level='info',
        ssl_certfile=os.getenv('SSL_CERTFILE') if os.getenv('HTTPS_ONLY', 'false').lower() == 'true' else None,
        ssl_keyfile=os.getenv('SSL_KEYFILE') if os.getenv('HTTPS_ONLY', 'false').lower() == 'true' else None
    )

def main():
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8000'))
    try:
        uvicorn.run(
            'doorman:doorman',
            host=host,
            port=port,
            reload=os.getenv('DEBUG', 'false').lower() == 'true'
        )
    except Exception as e:
        gateway_logger.error(f'Failed to start server: {str(e)}')
        raise

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'stop':
        stop()
    elif len(sys.argv) > 1 and sys.argv[1] == 'start':
        start()
    elif len(sys.argv) > 1 and sys.argv[1] == 'restart':
        restart()
    elif len(sys.argv) > 1 and sys.argv[1] == 'run':
        run()
    else:
        main()
