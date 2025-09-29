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
from fastapi.responses import Response
from contextlib import asynccontextmanager

from redis.asyncio import Redis

from pydantic import BaseSettings
from dotenv import load_dotenv

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

from utils.response_util import process_response

load_dotenv()

PID_FILE = "doorman.pid"

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    # Startup
    # Security: JWT secret must be configured
    if not os.getenv("JWT_SECRET_KEY"):
        raise RuntimeError("JWT_SECRET_KEY is not configured. Set it before starting the server.")
    # Production guard: require secure cookies via HTTPS
    try:
        if os.getenv("ENV", "").lower() == "production":
            https_only = os.getenv("HTTPS_ONLY", "false").lower() == "true"
            https_enabled = os.getenv("HTTPS_ENABLED", "false").lower() == "true"
            if not (https_only or https_enabled):
                raise RuntimeError(
                    "In production (ENV=production), you must enable HTTPS_ONLY or HTTPS_ENABLED to enforce Secure cookies."
                )
    except Exception as e:
        # If misconfigured, fail early with a clear message
        raise
    app.state.redis = Redis.from_url(
        f'redis://{os.getenv("REDIS_HOST")}:{os.getenv("REDIS_PORT")}/{os.getenv("REDIS_DB")}',
        decode_responses=True
    )
    # Background purger task
    app.state._purger_task = asyncio.create_task(automatic_purger(1800))
    # Load security settings and start auto-save loop (non-blocking)
    try:
        await load_settings()
        await start_auto_save_task()
    except Exception as e:
        gateway_logger.error(f"Failed to initialize security settings auto-save: {e}")
    # Minimal OpenAPI linting pass
    try:
        spec = app.openapi()
        problems = []
        for route in app.routes:
            path = getattr(route, 'path', '')
            if not path.startswith(('/platform', '/api')):
                continue
            if not getattr(route, 'description', None):
                problems.append(f"Route {path} missing description")
            # Response model presence (best effort)
            if not getattr(route, 'response_model', None):
                # Many routes return JSONResponse; warn to encourage consistency
                problems.append(f"Route {path} missing response_model")
        if problems:
            gateway_logger.info("OpenAPI lint: \n" + "\n".join(problems[:50]))
    except Exception as e:
        gateway_logger.debug(f"OpenAPI lint skipped: {e}")
    # If running in memory-only mode, try to restore from the most recent encrypted dump
    try:
        if database.memory_only:
            settings = get_cached_settings()
            hint = settings.get("dump_path")
            latest_path = find_latest_dump_path(hint)
            if latest_path and os.path.exists(latest_path):
                info = restore_memory_from_file(latest_path)
                gateway_logger.info(f"Memory mode: restored from dump {latest_path} (created_at={info.get('created_at')})")
            else:
                gateway_logger.info("Memory mode: no existing dump found to restore")
    except Exception as e:
        gateway_logger.error(f"Memory mode restore failed: {e}")

    # Register SIGUSR1 handler to force a memory dump (Unix only)
    try:
        if hasattr(signal, "SIGUSR1"):
            loop = asyncio.get_event_loop()

            async def _sigusr1_dump():
                try:
                    if not database.memory_only:
                        gateway_logger.info("SIGUSR1 ignored: not in memory-only mode")
                        return
                    if not os.getenv("MEM_ENCRYPTION_KEY"):
                        gateway_logger.error("SIGUSR1 dump skipped: MEM_ENCRYPTION_KEY not configured")
                        return
                    settings = get_cached_settings()
                    path_hint = settings.get("dump_path")
                    dump_path = await asyncio.to_thread(dump_memory_to_file, path_hint)
                    gateway_logger.info(f"SIGUSR1: memory dump written to {dump_path}")
                except Exception as e:
                    gateway_logger.error(f"SIGUSR1 dump failed: {e}")

            loop.add_signal_handler(signal.SIGUSR1, lambda: asyncio.create_task(_sigusr1_dump()))
            gateway_logger.info("SIGUSR1 handler registered for on-demand memory dumps")
    except NotImplementedError:
        # add_signal_handler not supported on this platform/event loop
        pass

    # Yield to run the application
    try:
        yield
    finally:
        # Shutdown
        # Stop auto-save task cleanly
        try:
            await stop_auto_save_task()
        except Exception as e:
            gateway_logger.error(f"Failed to stop auto-save task: {e}")
        # Always write a final encrypted memory dump when in memory-only mode
        try:
            if database.memory_only:
                settings = get_cached_settings()
                path = settings.get("dump_path")
                dump_memory_to_file(path)
                gateway_logger.info(f"Final memory dump written to {path}")
        except Exception as e:
            gateway_logger.error(f"Failed to write final memory dump: {e}")
        # Cancel background purger task
        try:
            task = getattr(app.state, "_purger_task", None)
            if task:
                task.cancel()
        except Exception:
            pass


doorman = FastAPI(
    title="doorman",
    description="A lightweight API gateway for AI, REST, SOAP, GraphQL, gRPC, and WebSocket APIs — fully managed with built-in RESTful APIs for configuration and control. This is your application's gateway to the world.",
    version="1.0.0",
    lifespan=app_lifespan,
)

https_only = os.getenv("HTTPS_ONLY", "false").lower() == "true"
domain = os.getenv("COOKIE_DOMAIN", "localhost")

# Replace global CORSMiddleware with path-aware CORS handling:
# - Platform routes (/platform/*): preserve env-based behavior for now
# - API gateway routes (/api/*): CORS controlled per-API in gateway routes/services

def _env_cors_config():
    origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
    if not (origins_env or "").strip():
        origins_env = "http://localhost:3000"
    origins = [o.strip() for o in origins_env.split(",") if o.strip()]
    credentials = os.getenv("ALLOW_CREDENTIALS", "true").lower() == "true"
    methods_env = os.getenv("ALLOW_METHODS", "GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD")
    if not (methods_env or "").strip():
        methods_env = "GET,POST,PUT,DELETE,OPTIONS,PATCH,HEAD"
    methods = [m.strip().upper() for m in methods_env.split(",") if m.strip()]
    if "OPTIONS" not in methods:
        methods.append("OPTIONS")
    headers_env = os.getenv("ALLOW_HEADERS", "*")
    if not (headers_env or "").strip():
        headers_env = "*"
    raw_headers = [h.strip() for h in headers_env.split(",") if h.strip()]
    if any(h == "*" for h in raw_headers):
        headers = ["Accept", "Content-Type", "X-CSRF-Token", "Authorization"]
    else:
        headers = raw_headers
    def _safe(origins, credentials):
        if credentials and any(o.strip() == "*" for o in origins):
            return ["http://localhost", "http://localhost:3000"]
        if os.getenv("CORS_STRICT", "false").lower() == "true":
            safe = [o for o in origins if o.strip() != "*"]
            return safe if safe else ["http://localhost", "http://localhost:3000"]
        return origins
    return {
        'origins': origins,
        'safe_origins': _safe(origins, credentials),
        'credentials': credentials,
        'methods': methods,
        'headers': headers,
    }

@doorman.middleware("http")
async def platform_cors(request: Request, call_next):
    # Only apply env-based CORS to /platform/* paths to keep behavior/stability
    resp = None
    if str(request.url.path).startswith('/platform/'):
        cfg = _env_cors_config()
        origin = request.headers.get('origin') or request.headers.get('Origin')
        origin_allowed = origin in cfg['safe_origins'] or ('*' in cfg['origins'] and not os.getenv("CORS_STRICT", "false").lower() == "true")
        # Handle preflight for platform
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
    # Non-platform: let downstream handlers control CORS (per-API)
    return await call_next(request)

# Body size limit middleware (Content-Length based)
MAX_BODY_SIZE = int(os.getenv("MAX_BODY_SIZE_BYTES", 1_048_576))  # 1MB default

@doorman.middleware("http")
async def body_size_limit(request: Request, call_next):
    try:
        cl = request.headers.get("content-length")
        if cl and int(cl) > MAX_BODY_SIZE:
            return process_response(ResponseModel(
                status_code=413,
                error_code="REQ001",
                error_message="Request entity too large"
            ).dict(), "rest")
    except Exception:
        pass
    return await call_next(request)

# Request ID middleware: accept incoming X-Request-ID or generate one.
@doorman.middleware("http")
async def request_id_middleware(request: Request, call_next):
    try:
        rid = (
            request.headers.get("x-request-id")
            or request.headers.get("request-id")
            or request.headers.get("x-request-id".title())
        )
        if not rid:
            rid = str(uuid.uuid4())
        # Expose on request.state for route handlers that want to use it
        try:
            request.state.request_id = rid
        except Exception:
            pass
        response = await call_next(request)
        # Ensure response carries standard header (and legacy for compatibility)
        try:
            if "X-Request-ID" not in response.headers:
                response.headers["X-Request-ID"] = rid
            # Maintain existing convention for clients expecting request_id
            if "request_id" not in response.headers:
                response.headers["request_id"] = rid
        except Exception:
            pass
        return response
    except Exception:
        # Do not break the request if request-id handling fails
        return await call_next(request)

# Security headers (including HSTS when HTTPS is used)
@doorman.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    try:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        # Content Security Policy: configurable via CONTENT_SECURITY_POLICY; strong default if unset
        try:
            csp = os.getenv("CONTENT_SECURITY_POLICY")
            if csp is None or not csp.strip():
                # Strict default for API responses; UI is served by Next.js separately
                csp = \
                    "default-src 'none'; " \
                    "frame-ancestors 'none'; " \
                    "base-uri 'none'; " \
                    "form-action 'self'; " \
                    "img-src 'self' data:; " \
                    "connect-src 'self';"
            response.headers.setdefault("Content-Security-Policy", csp)
        except Exception:
            pass
        if os.getenv("HTTPS_ONLY", "false").lower() == "true":
            # 6 months HSTS with subdomains and preload
            response.headers.setdefault("Strict-Transport-Security", "max-age=15552000; includeSubDomains; preload")
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
_env_logs_dir = os.getenv("LOGS_DIR")
# Default to backend-services/platform-logs
LOGS_DIR = os.path.abspath(_env_logs_dir) if _env_logs_dir else os.path.join(BASE_DIR, "platform-logs")

# Build formatters
class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "name": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }
        try:
            return json.dumps(payload, ensure_ascii=False)
        except Exception:
            return f"{payload}"

_fmt_is_json = os.getenv("LOG_FORMAT", "plain").lower() == "json"
_file_handler = None
try:
    os.makedirs(LOGS_DIR, exist_ok=True)
    _file_handler = RotatingFileHandler(
        filename=os.path.join(LOGS_DIR, "doorman.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    _file_handler.setFormatter(JSONFormatter() if _fmt_is_json else logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
except Exception as _e:
    # Fall back to console-only logging if file handler cannot be initialized
    print(f"Warning: file logging disabled ({_e}); using console logging only")
    _file_handler = None

# Configure all doorman loggers to use the same handler and prevent propagation
def configure_logger(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Prevent propagation to root logger
    # Remove any existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    class RedactFilter(logging.Filter):
        # Redact common credential/header value patterns
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
                    red = pat.sub(lambda m: (m.group(1) + "[REDACTED]" + (m.group(3) if m.lastindex and m.lastindex >=3 else "")), red)
                if red != msg:
                    record.msg = red
            except Exception:
                pass
            return True
    # Console handler (always attach)
    console = logging.StreamHandler(stream=sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(JSONFormatter() if _fmt_is_json else logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    console.addFilter(RedactFilter())
    logger.addHandler(console)
    # File handler (attach if available)
    if _file_handler is not None:
        # Avoid stacking multiple redact filters on the shared handler
        if not any(isinstance(f, logging.Filter) and hasattr(f, 'PATTERNS') for f in _file_handler.filters):
            _file_handler.addFilter(RedactFilter())
        logger.addHandler(_file_handler)
    return logger

# Configure main loggers
gateway_logger = configure_logger("doorman.gateway")
logging_logger = configure_logger("doorman.logging")

# Dedicated audit trail logger (separate file handler)
audit_logger = logging.getLogger("doorman.audit")
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False
# Remove existing handlers
for h in audit_logger.handlers[:]:
    audit_logger.removeHandler(h)
try:
    os.makedirs(LOGS_DIR, exist_ok=True)
    _audit_file = RotatingFileHandler(
        filename=os.path.join(LOGS_DIR, "doorman-trail.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    _audit_file.setFormatter(JSONFormatter() if _fmt_is_json else logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    audit_logger.addHandler(_audit_file)
except Exception as _e:
    # Fall back to console
    console = logging.StreamHandler(stream=sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(JSONFormatter() if _fmt_is_json else logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    audit_logger.addHandler(console)

class Settings(BaseSettings):
    mongo_db_uri: str = os.getenv("MONGO_DB_URI")
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expires: timedelta = timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRES_MINUTES", 15)))
    jwt_refresh_token_expires: timedelta = timedelta(days=int(os.getenv("REFRESH_TOKEN_EXPIRES_DAYS", 30)))


@doorman.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = asyncio.get_event_loop().time()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        # Record metrics for gateway requests only (under /api/*)
        try:
            if str(request.url.path).startswith("/api/"):
                end = asyncio.get_event_loop().time()
                duration_ms = (end - start) * 1000.0
                status = getattr(response, 'status_code', 500) if response is not None else 500
                username = None
                api_key = None
                # Try to extract username via auth payload
                try:
                    from utils.auth_util import auth_required as _auth_required
                    payload = await _auth_required(request)
                    username = payload.get('sub') if isinstance(payload, dict) else None
                except Exception:
                    pass
                # Derive a coarse api_key from path
                p = str(request.url.path)
                if p.startswith('/api/rest/'):
                    parts = p.split('/')
                    try:
                        idx = parts.index('rest')
                        api_key = f"rest:{parts[idx+1]}" if len(parts) > idx+1 and parts[idx+1] else 'rest:unknown'
                    except ValueError:
                        api_key = 'rest:unknown'
                elif p.startswith('/api/graphql/'):
                    # Use last segment as name
                    seg = p.rsplit('/', 1)[-1] or 'unknown'
                    api_key = f"graphql:{seg}"
                elif p.startswith('/api/soap/'):
                    seg = p.rsplit('/', 1)[-1] or 'unknown'
                    api_key = f"soap:{seg}"
                metrics_store.record(status=status, duration_ms=duration_ms, username=username, api_key=api_key)
        except Exception:
            # Never break the request flow due to metrics errors
            pass

async def automatic_purger(interval_seconds):
    while True:
        await asyncio.sleep(interval_seconds)
        await purge_expired_tokens()
        gateway_logger.info("Expired JWTs purged from blacklist.")

## Startup/shutdown handled by lifespan above

@doorman.exception_handler(JWTError)
async def jwt_exception_handler(exc: JWTError):
    return process_response(ResponseModel(
        status_code=401,
        error_code="JWT001",
        error_message="Invalid token"
    ).dict(), "rest")

@doorman.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    return process_response(ResponseModel(
        status_code=500,
        error_code="ISE001",
        error_message="Internal Server Error"
    ).dict(), "rest")

@doorman.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return process_response(ResponseModel(
        status_code=422,
        error_code="VAL001",
        error_message="Validation Error"
    ).dict(), "rest")

cache_manager.init_app(doorman)

doorman.include_router(gateway_router, prefix="/api", tags=["Gateway"])
doorman.include_router(authorization_router, prefix="/platform", tags=["Authorization"])
doorman.include_router(user_router, prefix="/platform/user", tags=["User"])
doorman.include_router(api_router, prefix="/platform/api", tags=["API"])
doorman.include_router(endpoint_router, prefix="/platform/endpoint", tags=["Endpoint"])
doorman.include_router(group_router, prefix="/platform/group", tags=["Group"])
doorman.include_router(role_router, prefix="/platform/role", tags=["Role"])
doorman.include_router(subscription_router, prefix="/platform/subscription", tags=["Subscription"])
doorman.include_router(routing_router, prefix="/platform/routing", tags=["Routing"])
doorman.include_router(proto_router, prefix="/platform/proto", tags=["Proto"])
doorman.include_router(logging_router, prefix="/platform/logging", tags=["Logging"])
doorman.include_router(dashboard_router, prefix="/platform/dashboard", tags=["Dashboard"])
doorman.include_router(memory_router, prefix="/platform", tags=["Memory"])
doorman.include_router(security_router, prefix="/platform", tags=["Security"])
doorman.include_router(monitor_router, prefix="/platform", tags=["Monitor"])
# Expose token management under both legacy and new prefixes
doorman.include_router(credit_router, prefix="/platform/credit", tags=["Credit"])
doorman.include_router(demo_router, prefix="/platform/demo", tags=["Demo"])
doorman.include_router(config_router, prefix="/platform", tags=["Config"])
doorman.include_router(tools_router, prefix="/platform/tools", tags=["Tools"])

def start():
    if os.path.exists(PID_FILE):
        print("doorman is already running!")
        sys.exit(0)
    if os.name == "nt":
        process = subprocess.Popen([sys.executable, __file__, "run"],
                                   creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
    else:
        process = subprocess.Popen([sys.executable, __file__, "run"],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,
                                   preexec_fn=os.setsid)
    with open(PID_FILE, "w") as f:
        f.write(str(process.pid))
    gateway_logger.info(f"Starting doorman with PID {process.pid}.")

def stop():
    if not os.path.exists(PID_FILE):
        gateway_logger.info("No running instance found")
        return
    with open(PID_FILE, "r") as f:
        pid = int(f.read())
    try:
        if os.name == "nt":
            subprocess.call(["taskkill", "/F", "/PID", str(pid)])
        else:
            # Send SIGTERM to allow graceful shutdown; FastAPI shutdown event
            # writes a final encrypted memory dump in memory-only mode.
            os.killpg(pid, signal.SIGTERM)
            # Wait briefly for graceful shutdown so the dump can complete
            deadline = time.time() + 15
            while time.time() < deadline:
                try:
                    # Check if process group leader still exists
                    os.kill(pid, 0)
                    time.sleep(0.5)
                except ProcessLookupError:
                    break
        print(f"Stopping doorman with PID {pid}")
    except ProcessLookupError:
        print("Process already terminated")
    finally:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)

def restart():
    """Restart the doorman process using PID-based supervisor.
    This function is intended to be invoked from a detached helper process.
    """
    try:
        stop()
        # Small delay to ensure ports/files released before start
        time.sleep(1.0)
    except Exception as e:
        gateway_logger.error(f"Error during stop phase of restart: {e}")
    try:
        start()
    except Exception as e:
        gateway_logger.error(f"Error during start phase of restart: {e}")

def run():
    server_port = int(os.getenv('PORT', 5001))
    max_threads = multiprocessing.cpu_count()
    env_threads = int(os.getenv("THREADS", max_threads))
    num_threads = min(env_threads, max_threads)
    try:
        if database.memory_only and num_threads != 1:
            gateway_logger.info("Memory-only mode detected; forcing single worker to avoid divergent state")
            num_threads = 1
    except Exception:
        pass
    gateway_logger.info(f"Started doorman with {num_threads} threads on port {server_port}")
    uvicorn.run(
        "doorman:doorman",
        host="0.0.0.0",
        port=server_port,
        reload=os.getenv("DEV_RELOAD", "false").lower() == "true",
        reload_excludes=["venv/*", "logs/*"],
        workers=num_threads,
        log_level="info",
        ssl_certfile=os.getenv("SSL_CERTFILE") if os.getenv("HTTPS_ONLY", "false").lower() == "true" else None,
        ssl_keyfile=os.getenv("SSL_KEYFILE") if os.getenv("HTTPS_ONLY", "false").lower() == "true" else None
    )

def main():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    try:
        uvicorn.run(
            "doorman:doorman",
            host=host,
            port=port,
            reload=os.getenv("DEBUG", "false").lower() == "true"
        )
    except Exception as e:
        gateway_logger.error(f"Failed to start server: {str(e)}")
        raise

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        stop()
    elif len(sys.argv) > 1 and sys.argv[1] == "start":
        start()
    elif len(sys.argv) > 1 and sys.argv[1] == "restart":
        restart()
    elif len(sys.argv) > 1 and sys.argv[1] == "run":
        run()
    else:
        main()
