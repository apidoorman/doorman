"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from jose import jwt, JWTError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

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
from routes.monitor_routes import monitor_router
from utils.security_settings_util import load_settings, start_auto_save_task, stop_auto_save_task, get_cached_settings
from utils.memory_dump_util import dump_memory_to_file, restore_memory_from_file, find_latest_dump_path
from utils.metrics_util import metrics_store
from utils.database import database

import multiprocessing
import logging
import os
import sys
import subprocess
import signal
import uvicorn
import asyncio

from utils.response_util import process_response

load_dotenv()

PID_FILE = "doorman.pid"

doorman = FastAPI(
    title="doorman",
    description="A lightweight API gateway for AI, REST, SOAP, GraphQL, gRPC, and WebSocket APIs — fully managed with built-in RESTful APIs for configuration and control. This is your application's gateway to the world.",  # Optional: Add a description
    version="0.0.1"
)

origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
credentials = os.getenv("ALLOW_CREDENTIALS", "true").lower() == "true"
methods = os.getenv("ALLOW_METHODS", "GET, POST, PUT, DELETE").split(",")
headers = os.getenv("ALLOW_HEADERS", "*").split(",")
https_only = os.getenv("HTTPS_ONLY", "false").lower() == "true"
domain = os.getenv("COOKIE_DOMAIN", "localhost")

doorman.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=credentials,
    allow_methods=methods,
    allow_headers=headers,
)

os.makedirs("logs", exist_ok=True)
log_file_handler = RotatingFileHandler(
    filename="logs/doorman.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8"
)
log_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Configure all doorman loggers to use the same handler and prevent propagation
def configure_logger(logger_name):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Prevent propagation to root logger
    # Remove any existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    logger.addHandler(log_file_handler)
    return logger

# Configure main loggers
gateway_logger = configure_logger("doorman.gateway")
logging_logger = configure_logger("doorman.logging")

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

@doorman.on_event("startup")
async def startup_event():
    doorman.state.redis = Redis.from_url(
        f'redis://{os.getenv("REDIS_HOST")}:{os.getenv("REDIS_PORT")}/{os.getenv("REDIS_DB")}',
        decode_responses=True
    )
    asyncio.create_task(automatic_purger(1800))
    # Load security settings and start auto-save loop (non-blocking)
    try:
        await load_settings()
        await start_auto_save_task()
    except Exception as e:
        gateway_logger.error(f"Failed to initialize security settings auto-save: {e}")
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

@doorman.on_event("shutdown")
async def shutdown_event():
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
    if doorman_cache.cache_type == "MEM":
        doorman_cache.force_save_cache()
        doorman_cache.stop_cache_persistence()
    if not os.path.exists(PID_FILE):
        gateway_logger.info("No running instance found")
        return
    with open(PID_FILE, "r") as f:
        pid = int(f.read())
    try:
        if os.name == "nt":
            subprocess.call(["taskkill", "/F", "/PID", str(pid)])
        else:
            os.killpg(pid, signal.SIGTERM)
        print(f"Stopping doorman with PID {pid}")
    except ProcessLookupError:
        print("Process already terminated")
    finally:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)

def run():
    server_port = int(os.getenv('PORT', 5001))
    max_threads = multiprocessing.cpu_count()
    env_threads = int(os.getenv("THREADS", max_threads))
    num_threads = min(env_threads, max_threads)
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
    elif len(sys.argv) > 1 and sys.argv[1] == "run":
        run()
    else:
        main()
