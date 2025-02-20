"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

# Start of file

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseSettings
from dotenv import load_dotenv
import uvicorn
import asyncio

from utils.cache import cache_manager
from utils.auth_util import jwt_blacklist
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

# Initialize FastAPI application
pygate = FastAPI()
origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

# Middleware
pygate.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Update this with allowed origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# JWT Configuration
class Settings(BaseSettings):
    mongo_db_uri: str = os.getenv("MONGO_DB_URI")

    authjwt_secret_key: str = os.getenv("JWT_SECRET_KEY")
    authjwt_token_location: set = {"cookies"}
    authjwt_cookie_secure: bool = False   # Only send cookies over HTTPS
    authjwt_cookie_domain: str = "localhost"  # Adjust based on your deployment
    authjwt_cookie_path: str = "/"
    authjwt_cookie_samesite: str = 'lax'  # Or 'none' if your requirements dictate

    class Config:
        env_file = ".env"

# AuthJWT requires a configuration function that returns a class with settings
@AuthJWT.load_config
def get_config():
    return Settings()

#jwt blacklist purger
async def automatic_purger(interval_seconds):
    while True:
        await asyncio.sleep(interval_seconds)
        # Assuming `jwt_blacklist` has a method to purge expired tokens
        purge_expired_tokens()
        logging.info("Expired JWTs purged from blacklist.")

@pygate.on_event("startup")
async def startup_event():
    asyncio.create_task(automatic_purger(1800))

# Exception handling for authentication errors
@pygate.exception_handler(AuthJWTException)
async def authjwt_exception_handler(request: Request, exc: AuthJWTException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"details": exc.message}
    )

# Initialize cache manager
cache_manager.init_app(pygate)

# Register routes
pygate.include_router(gateway_router, prefix="/api", tags=["Gateway"])
pygate.include_router(authorization_router, prefix="/platform", tags=["Authorization"])
pygate.include_router(user_router, prefix="/platform/user", tags=["User"])
pygate.include_router(api_router, prefix="/platform/api", tags=["API"])
pygate.include_router(endpoint_router, prefix="/platform/endpoint", tags=["Endpoint"])
pygate.include_router(group_router, prefix="/platform/group", tags=["Group"])
pygate.include_router(role_router, prefix="/platform/role", tags=["Role"])
pygate.include_router(subscription_router, prefix="/platform/subscription", tags=["Subscription"])

# Error handling
@pygate.exception_handler(500)
async def internal_server_error_handler(request, exc):
    return {
        "error": "Internal Server Error",
        "message": "An unexpected error occurred. Please try again later.",
    }

def start():
    if os.path.exists(PID_FILE):
        print("pygate is already running!")
        sys.exit(0)

    # Run process in the background
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

    # Save the PID to a file
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
        reload=True
    )

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        run()
    elif len(sys.argv) > 1 and sys.argv[1] == "stop":
        stop()
    elif len(sys.argv) > 1 and sys.argv[1] == "start":
        start()
    else:
        print("Invalid command. Use 'start', 'stop', or 'run'.")

# End of file