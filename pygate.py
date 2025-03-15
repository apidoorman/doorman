"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseSettings
from dotenv import load_dotenv
import uvicorn
import asyncio

from utils.cache import cache_manager
from utils.auth_blacklist import purge_expired_tokens

from routes.authorization_routes import authorization_router
from routes.group_routes import group_router
from routes.role_routes import role_router
from routes.subscription_routes import subscription_router
from routes.user_routes import user_router
from routes.api_routes import api_router
from routes.endpoint_routes import endpoint_router
from routes.gateway_routes import gateway_router

import logging
import os
import sys
import subprocess
import signal

load_dotenv()

PID_FILE = "pygate.pid"

pygate = FastAPI()
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    mongo_db_uri: str = os.getenv("MONGO_DB_URI")

    authjwt_secret_key: str = os.getenv("JWT_SECRET_KEY")
    authjwt_token_location: set = {"cookies"}
    authjwt_cookie_secure: bool = https_only
    authjwt_cookie_domain: str = domain
    authjwt_cookie_path: str = "/"
    authjwt_cookie_samesite: str = 'lax'

    class Config:
        env_file = ".env"

@AuthJWT.load_config
def get_config():
    return Settings()

async def automatic_purger(interval_seconds):
    while True:
        await asyncio.sleep(interval_seconds)
        purge_expired_tokens()
        logging.info("Expired JWTs purged from blacklist.")

@pygate.on_event("startup")
async def startup_event():
    asyncio.create_task(automatic_purger(1800))

@pygate.exception_handler(AuthJWTException)
async def authjwt_exception_handler(exc: AuthJWTException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"details": exc.message}
    )

cache_manager.init_app(pygate)

pygate.include_router(gateway_router, prefix="/api", tags=["Gateway"])
pygate.include_router(authorization_router, prefix="/platform", tags=["Authorization"])
pygate.include_router(user_router, prefix="/platform/user", tags=["User"])
pygate.include_router(api_router, prefix="/platform/api", tags=["API"])
pygate.include_router(endpoint_router, prefix="/platform/endpoint", tags=["Endpoint"])
pygate.include_router(group_router, prefix="/platform/group", tags=["Group"])
pygate.include_router(role_router, prefix="/platform/role", tags=["Role"])
pygate.include_router(subscription_router, prefix="/platform/subscription", tags=["Subscription"])

@pygate.exception_handler(500)
async def internal_server_error_handler():
    return {
        "error": "Internal Server Error",
        "message": "An unexpected error occurred. Please try again later.",
    }

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
    print(f"pygate started with PID {process.pid}.")


def stop():
    if not os.path.exists(PID_FILE):
        print("No running instance found.")
        return

    with open(PID_FILE, "r") as f:
        pid = int(f.read())
    
    try:
        if os.name == "nt":
            subprocess.call(["taskkill", "/F", "/PID", str(pid)])
        else:
            os.killpg(pid, signal.SIGTERM)
        print(f"pygate with PID {pid} has been stopped.")
    except ProcessLookupError:
        print("Process already terminated.")
    finally:
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)

def run():
    server_port = int(os.getenv('PORT', 5001))
    logging.info("pygate server started on port " + str(server_port))

    uvicorn.run(
        "pygate:pygate",
        host="0.0.0.0",
        port=server_port,
        reload=True, 
        reload_excludes="venv"
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