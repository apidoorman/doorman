"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

# External imports
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from jose import jwt, JWTError
from fastapi.middleware.cors import CORSMiddleware
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

# Compatibility guard: ensure aiohttp is a Python 3.13–compatible version before
# downstream modules import it (e.g., gateway_service). This avoids a cryptic
# regex error inside older aiohttp builds on 3.13.
try:
    if sys.version_info >= (3, 13):
        try:
            from importlib.metadata import version, PackageNotFoundError  # type: ignore
        except Exception:  # pragma: no cover
            version = None  # type: ignore
            PackageNotFoundError = Exception  # type: ignore
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

# Internal imports
from models.response_model import ResponseModel
from utils.cache_manager_util import cache_manager
from utils.auth_blacklist import purge_expired_tokens
from utils.doorman_cache_util import doorman_cache
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
from utils.security_settings_util import load_settings, start_auto_save_task, stop_auto_save_task, get_cached_settings
from utils.memory_dump_util import dump_memory_to_file, restore_memory_from_file, find_latest_dump_path
from utils.metrics_util import metrics_store
from utils.database import database
from utils.response_util import process_response
from utils.audit_util import audit
from utils.ip_policy_util import _get_client_ip as _policy_get_client_ip, _ip_in_list as _policy_ip_in_list

load_dotenv()

PID_FILE = 'doorman.pid'

@asynccontextmanager
async def app_lifespan(app: FastAPI):

    if not os.getenv('JWT_SECRET_KEY'):
        raise RuntimeError('JWT_SECRET_KEY is not configured. Set it before starting the server.')

    # Production environment validation
    try:
        if os.getenv('ENV', '').lower() == 'production':
            # Validate HTTPS
            https_only = os.getenv('HTTPS_ONLY', 'false').lower() == 'true'
            https_enabled = os.getenv('HTTPS_ENABLED', 'false').lower() == 'true'
            if not (https_only or https_enabled):
                raise RuntimeError(
                    'In production (ENV=production), you must enable HTTPS_ONLY or HTTPS_ENABLED to enforce Secure cookies.'
                )

            # Validate JWT secret is not default
            jwt_secret = os.getenv('JWT_SECRET_KEY', '')
            if jwt_secret in ('please-change-me', 'test-secret-key', 'test-secret-key-please-change', ''):
                raise RuntimeError(
                    'In production (ENV=production), JWT_SECRET_KEY must be changed from default value. '
                    'Generate a strong random secret (32+ characters).'
                )

            # Validate Redis for HA deployments (shared token revocation and rate limiting)
            mem_or_external = os.getenv('MEM_OR_EXTERNAL', 'MEM').upper()
            if mem_or_external == 'MEM':
                gateway_logger.warning(
                    'Production deployment with MEM_OR_EXTERNAL=MEM detected. '
                    'Token revocation and rate limiting will NOT be shared across nodes. '
                    'For HA deployments, set MEM_OR_EXTERNAL=REDIS or EXTERNAL with valid REDIS_HOST. '
                    'Current setup is only suitable for single-node deployments.'
                )
            else:
                # Verify Redis is actually configured
                redis_host = os.getenv('REDIS_HOST')
                if not redis_host:
                    raise RuntimeError(
                        'In production with MEM_OR_EXTERNAL=REDIS/EXTERNAL, REDIS_HOST is required. '
                        'Redis is essential for shared token revocation and rate limiting in HA deployments.'
                    )

            # Validate CORS security
            if os.getenv('CORS_STRICT', 'false').lower() != 'true':
                gateway_logger.warning(
                    'Production deployment without CORS_STRICT=true. '
                    'This allows wildcard origins with credentials, which is a security risk.'
                )

            allowed_origins = os.getenv('ALLOWED_ORIGINS', '')
            if '*' in allowed_origins:
                raise RuntimeError(
                    'In production (ENV=production), wildcard CORS origins (*) are not allowed. '
                    'Set ALLOWED_ORIGINS to specific domain(s): https://yourdomain.com'
                )

            # Validate encryption keys if memory dumps are used
            if mem_or_external == 'MEM':
                mem_encryption_key = os.getenv('MEM_ENCRYPTION_KEY', '')
                if not mem_encryption_key or len(mem_encryption_key) < 32:
                    gateway_logger.error(
                        'Production memory-only mode requires MEM_ENCRYPTION_KEY (32+ characters) for secure dumps. '
                        'Without this, memory dumps will be unencrypted on disk.'
                    )
    except Exception as e:
        # Re-raise all RuntimeErrors (validation failures should stop startup)
        raise
    app.state.redis = Redis.from_url(
        f'redis://{os.getenv("REDIS_HOST")}:{os.getenv("REDIS_PORT")}/{os.getenv("REDIS_DB")}',
        decode_responses=True
    )

    app.state._purger_task = asyncio.create_task(automatic_purger(1800))

    # Restore persisted metrics (if available)
    METRICS_FILE = os.path.join(LOGS_DIR, 'metrics.json')
    try:
        metrics_store.load_from_file(METRICS_FILE)
    except Exception as e:
        gateway_logger.debug(f'Metrics restore skipped: {e}')

    # Start periodic metrics saver
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
    except Exception as e:
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
        yield
    finally:

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

        # Persist metrics on shutdown
        try:
            METRICS_FILE = os.path.join(LOGS_DIR, 'metrics.json')
            metrics_store.save_to_file(METRICS_FILE)
        except Exception:
            pass
        # Stop autosave task
        try:
            t = getattr(app.state, '_metrics_save_task', None)
            if t:
                t.cancel()
        except Exception:
            pass

        # Close shared HTTP client pool if enabled
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

# Replace global CORSMiddleware with path-aware CORS handling:
# - Platform routes (/platform/*): preserve env-based behavior for now
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

@doorman.middleware('http')
async def platform_cors(request: Request, call_next):

    resp = None
    if str(request.url.path).startswith('/platform/'):
        cfg = _env_cors_config()
        origin = request.headers.get('origin') or request.headers.get('Origin')
        origin_allowed = origin in cfg['safe_origins'] or ('*' in cfg['origins'] and not os.getenv('CORS_STRICT', 'false').lower() == 'true')

        if request.method.upper() == 'OPTIONS':
            headers = {}
            if origin and origin_allowed:
                headers['Access-Control-Allow-Origin'] = origin
                headers['Vary'] = 'Origin'
            headers['Access-Control-Allow-Methods'] = ', '.join(cfg['methods'])
            headers['Access-Control-Allow-Headers'] = ', '.join(cfg['headers'])
            headers['Access-Control-Allow-Credentials'] = 'true' if cfg['credentials'] else 'false'
            headers['request_id'] = request.headers.get('X-Request-ID') or str(uuid.uuid4())
            from fastapi.responses import Response as StarletteResponse
            return StarletteResponse(status_code=204, headers=headers)
        resp = await call_next(request)
        try:
            if origin and origin_allowed:
                resp.headers.setdefault('Access-Control-Allow-Origin', origin)
                resp.headers.setdefault('Vary', 'Origin')
            resp.headers.setdefault('Access-Control-Allow-Credentials', 'true' if cfg['credentials'] else 'false')
        except Exception:
            pass
        return resp

    return await call_next(request)

# Body size limit middleware (Content-Length based)
MAX_BODY_SIZE = int(os.getenv('MAX_BODY_SIZE_BYTES', 1_048_576))

def _get_max_body_size() -> int:
    try:
        v = os.getenv('MAX_BODY_SIZE_BYTES')
        if v is None or str(v).strip() == '':
            return MAX_BODY_SIZE
        return int(v)
    except Exception:
        return MAX_BODY_SIZE

@doorman.middleware('http')
async def body_size_limit(request: Request, call_next):
    """Enforce request body size limits to prevent DoS attacks.

    Default limit: 1MB (configurable via MAX_BODY_SIZE_BYTES)
    Per-API overrides: MAX_BODY_SIZE_BYTES_<API_TYPE> (e.g., MAX_BODY_SIZE_BYTES_SOAP)

    Protected paths:
    - /platform/authorization: Strict enforcement (prevent auth DoS)
    - /api/rest/*: Enforce on all requests with Content-Length
    - /api/soap/*: Enforce on XML/SOAP bodies
    - /api/graphql/*: Enforce on GraphQL queries
    - /api/grpc/*: Enforce on gRPC JSON payloads
    """
    try:
        path = str(request.url.path)
        cl = request.headers.get('content-length')

        # Skip requests without Content-Length header (GET, HEAD, etc.)
        if not cl or str(cl).strip() == '':
            return await call_next(request)

        try:
            content_length = int(cl)
        except (ValueError, TypeError):
            # Invalid Content-Length header - let it through and fail later
            return await call_next(request)

        # Determine if this path should be protected
        should_enforce = False
        default_limit = _get_max_body_size()
        limit = default_limit

        # Strictly enforce on auth route (prevent auth DoS)
        if path.startswith('/platform/authorization'):
            should_enforce = True
        # Enforce on all /api/* routes with per-type overrides
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
            # Catch-all for other /api/* routes
            should_enforce = True

        # Skip if this path is not protected
        if not should_enforce:
            return await call_next(request)

        # Enforce limit
        if content_length > limit:
            # Log for security monitoring
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
                        'content_type': request.headers.get('content-type')
                    }
                )
            except Exception:
                pass

            return process_response(ResponseModel(
                status_code=413,
                error_code='REQ001',
                error_message=f'Request entity too large (max: {limit} bytes)'
            ).dict(), 'rest')

        return await call_next(request)
    except Exception:
        pass
    return await call_next(request)

# Request ID middleware: accept incoming X-Request-ID or generate one.
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
            settings = get_cached_settings()
            trust_xff = bool(settings.get('trust_x_forwarded_for'))
            direct_ip = getattr(getattr(request, 'client', None), 'host', None)
            effective_ip = _policy_get_client_ip(request, trust_xff)
            gateway_logger.info(f"{rid} | Entry: client_ip={direct_ip} effective_ip={effective_ip} method={request.method} path={str(request.url.path)}")
        except Exception:
            pass
        response = await call_next(request)

        try:
            if 'X-Request-ID' not in response.headers:
                response.headers['X-Request-ID'] = rid

            if 'request_id' not in response.headers:
                response.headers['request_id'] = rid
        except Exception:
            pass
        return response
    except Exception:

        return await call_next(request)

# Security headers (including HSTS when HTTPS is used)
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

# Resolve logs directory: env override or default next to this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_env_logs_dir = os.getenv('LOGS_DIR')
# Default to backend-services/platform-logs
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

    print(f'Warning: file logging disabled ({_e}); using console logging only')
    _file_handler = None

# Configure all doorman loggers to use the same handler and prevent propagation
def configure_logger(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    class RedactFilter(logging.Filter):

        PATTERNS = [
            re.compile(r'(?i)(authorization\s*[:=]\s*)([^;\r\n]+)'),
            re.compile(r'(?i)(access[_-]?token\s*[\"\']?\s*[:=]\s*[\"\'])([^\"\']+)([\"\'])'),
            re.compile(r'(?i)(refresh[_-]?token\s*[\"\']?\s*[:=]\s*[\"\'])([^\"\']+)([\"\'])'),
            re.compile(r'(?i)(password\s*[\"\']?\s*[:=]\s*[\"\'])([^\"\']+)([\"\'])'),
            re.compile(r'(?i)(cookie\s*[:=]\s*)([^;\r\n]+)'),
            re.compile(r'(?i)(x-csrf-token\s*[:=]\s*)([^\s,;]+)'),
        ]
        def filter(self, record: logging.LogRecord) -> bool:
            try:
                msg = str(record.getMessage())
                red = msg
                for pat in self.PATTERNS:
                    red = pat.sub(lambda m: (m.group(1) + '[REDACTED]' + (m.group(3) if m.lastindex and m.lastindex >=3 else '')), red)
                if red != msg:
                    record.msg = red
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

# Configure main loggers
gateway_logger = configure_logger('doorman.gateway')
logging_logger = configure_logger('doorman.logging')

# Dedicated audit trail logger (separate file handler)
audit_logger = logging.getLogger('doorman.audit')
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False
# Remove existing handlers
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
    audit_logger.addHandler(_audit_file)
except Exception as _e:

    console = logging.StreamHandler(stream=sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(JSONFormatter() if _fmt_is_json else logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
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
        settings = get_cached_settings()
        wl = settings.get('ip_whitelist') or []
        bl = settings.get('ip_blacklist') or []
        trust_xff = bool(settings.get('trust_x_forwarded_for'))
        client_ip = _policy_get_client_ip(request, trust_xff)
        xff_hdr = request.headers.get('x-forwarded-for') or request.headers.get('X-Forwarded-For')

        try:
            import os, ipaddress
            settings = get_cached_settings()
            env_flag = os.getenv('LOCAL_HOST_IP_BYPASS')
            allow_local = (env_flag.lower() == 'true') if isinstance(env_flag, str) and env_flag.strip() != '' else bool(settings.get('allow_localhost_bypass'))
            if allow_local:
                direct_ip = getattr(getattr(request, 'client', None), 'host', None)
                has_forward = any(request.headers.get(h) for h in ('x-forwarded-for','X-Forwarded-For','x-real-ip','X-Real-IP','cf-connecting-ip','CF-Connecting-IP','forwarded','Forwarded'))
                if direct_ip and ipaddress.ip_address(direct_ip).is_loopback and not has_forward:
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
                    clen = _parse_len(getattr(response, 'headers', {}).get('content-length'))
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
                        # Track usage when limit is set unless explicitly disabled
                        if u and u.get('bandwidth_limit_bytes') and u.get('bandwidth_limit_enabled') is not False:
                            add_usage(username, int(bytes_in) + int(clen), u.get('bandwidth_limit_window') or 'day')
                except Exception:
                    pass
        except Exception:

            pass

async def automatic_purger(interval_seconds):
    while True:
        await asyncio.sleep(interval_seconds)
        await purge_expired_tokens()
        gateway_logger.info('Expired JWTs purged from blacklist.')

## Startup/shutdown handled by lifespan above

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
# Expose token management under both legacy and new prefixes
doorman.include_router(credit_router, prefix='/platform/credit', tags=['Credit'])
doorman.include_router(demo_router, prefix='/platform/demo', tags=['Demo'])
doorman.include_router(config_router, prefix='/platform', tags=['Config'])
doorman.include_router(tools_router, prefix='/platform/tools', tags=['Tools'])

def start():
    if os.path.exists(PID_FILE):
        print('doorman is already running!')
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
        print(f'Stopping doorman with PID {pid}')
    except ProcessLookupError:
        print('Process already terminated')
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
    try:
        if database.memory_only and num_threads != 1:
            gateway_logger.info('Memory-only mode detected; forcing single worker to avoid divergent state')
            num_threads = 1
    except Exception:
        pass
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
