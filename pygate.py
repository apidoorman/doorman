"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException
from fastapi.middleware.cors import CORSMiddleware

from redis.asyncio import Redis

from pydantic import BaseSettings
from dotenv import load_dotenv

from models.response_model import ResponseModel
from utils.cache_manager_util import cache_manager
from utils.auth_blacklist import purge_expired_tokens

from routes.authorization_routes import authorization_router
from routes.group_routes import group_router
from routes.role_routes import role_router
from routes.subscription_routes import subscription_router
from routes.user_routes import user_router
from routes.api_routes import api_router
from routes.endpoint_routes import endpoint_router
from routes.gateway_routes import gateway_router
from routes.routing_routes import routing_router

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

PID_FILE = "pygate.pid"

pygate = FastAPI(
    title="pygate",
    description="A lightweight API gateway for AI, REST, SOAP, GraphQL, gRPC, and WebSocket APIs — fully managed with built-in RESTful APIs for configuration and control. This is your application’s gateway to the world.",  # Optional: Add a description
    version="1.0.0"
)

origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
credentials = os.getenv("ALLOW_CREDENTIALS", "true").lower() == "true"
methods = os.getenv("ALLOW_METHODS", "GET, POST, PUT, DELETE").split(",")
headers = os.getenv("ALLOW_HEADERS", "*").split(",")
https_only = os.getenv("HTTPS_ONLY", "false").lower() == "true"
domain = os.getenv("COOKIE_DOMAIN", "localhost")

pygate.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=credentials,
    allow_methods=methods,
    allow_headers=headers,
)

os.makedirs("logs", exist_ok=True)
log_file_handler = TimedRotatingFileHandler(
    filename="logs/pygate-logs-{start_time}.log".format(
        start_time="{:%Y-%m-%d_%H-%M}".format(datetime.now())
    ),
    when="H",
    interval=6,
    backupCount=999,
    encoding="utf-8"
)
log_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(log_file_handler)
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    mongo_db_uri: str = os.getenv("MONGO_DB_URI")

    authjwt_secret_key: str = os.getenv("JWT_SECRET_KEY")
    authjwt_token_location: set = {"cookies"}
    authjwt_cookie_secure: bool = https_only
    authjwt_cookie_domain: str = domain
    authjwt_cookie_path: str = "/"
    authjwt_cookie_samesite: str = 'lax'
    authjwt_cookie_csrf_protect: bool = https_only
    authjwt_refresh_cookie_path: str = "/refresh"

    authjwt_access_token_expires: timedelta = timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRES_MINUTES", 15)))
    authjwt_refresh_token_expires: timedelta = timedelta(days=int(os.getenv("REFRESH_TOKEN_EXPIRES_DAYS", 30)))

@AuthJWT.load_config
def get_config():
    return Settings()

async def automatic_purger(interval_seconds):
    while True:
        await asyncio.sleep(interval_seconds)
        await purge_expired_tokens()
        logging.info("Expired JWTs purged from blacklist.")

@pygate.on_event("startup")
async def startup_event():
    pygate.state.redis = Redis.from_url(
        f'redis://{os.getenv("REDIS_HOST")}:{os.getenv("REDIS_PORT")}/{os.getenv("REDIS_DB")}',
        decode_responses=True
    )
    asyncio.create_task(automatic_purger(1800))

@pygate.exception_handler(AuthJWTException)
async def authjwt_exception_handler(exc: AuthJWTException):
    return process_response(ResponseModel(
        status_code=exc.status_code,
        error_code="JWT001",
        error_message=exc.message
    ).dict())

@pygate.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    return process_response(ResponseModel(
        status_code=500,
        error_code="ISE001",
        error_message="Internal Server Error"
    ).dict())

@pygate.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return process_response(ResponseModel(
        status_code=422,
        error_code="VAL001",
        error_message="Validation Error"
    ).dict())

cache_manager.init_app(pygate)

pygate.include_router(gateway_router, prefix="/api", tags=["Gateway"])
pygate.include_router(authorization_router, prefix="/platform", tags=["Authorization"])
pygate.include_router(user_router, prefix="/platform/user", tags=["User"])
pygate.include_router(api_router, prefix="/platform/api", tags=["API"])
pygate.include_router(endpoint_router, prefix="/platform/endpoint", tags=["Endpoint"])
pygate.include_router(group_router, prefix="/platform/group", tags=["Group"])
pygate.include_router(role_router, prefix="/platform/role", tags=["Role"])
pygate.include_router(subscription_router, prefix="/platform/subscription", tags=["Subscription"])
pygate.include_router(routing_router, prefix="/platform/routing", tags=["Routing"])

def start():
    if os.path.exists(PID_FILE):
        print("pygate is already running!")
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
    logger.info(f"Starting pygate with PID {process.pid}.")


def stop():
    if not os.path.exists(PID_FILE):
        logger.info("No running instance found")
        return

    with open(PID_FILE, "r") as f:
        pid = int(f.read())
    
    try:
        if os.name == "nt":
            subprocess.call(["taskkill", "/F", "/PID", str(pid)])
        else:
            os.killpg(pid, signal.SIGTERM)
        print(f"Stopping pygate with PID {pid}")
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
    logger.info(f"Started pygate with {num_threads} threads on port {server_port}")
    uvicorn.run(
        "pygate:pygate",
        host="0.0.0.0",
        port=server_port,
        reload=os.getenv("DEV_RELOAD", "false").lower() == "true",
        reload_excludes=["venv", "logs"],
        workers=num_threads,
        log_level="critical",
        ssl_certfile=os.getenv("SSL_CERTFILE") if os.getenv("HTTPS_ONLY", "false").lower() == "true" else None,
        ssl_keyfile=os.getenv("SSL_KEYFILE") if os.getenv("HTTPS_ONLY", "false").lower() == "true" else None
    )

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        stop()
    elif len(sys.argv) > 1 and sys.argv[1] == "start":
        start()
    elif len(sys.argv) > 1 and sys.argv[1] == "run":
        run()
    else:
        print("Invalid command. Use 'start' or 'stop'.")