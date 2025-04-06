"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""


from fastapi import APIRouter, Request, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException

from services.user_service import UserService
from utils.token import create_access_token
from utils.auth_util import auth_required
from utils.auth_blacklist import TimedHeap, jwt_blacklist

import uuid
import time
import logging

authorization_router = APIRouter()

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

"""
Login endpoint
"""
@authorization_router.post("/authorization")
async def login(request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {str(request.url.path)}")
        data = await request.json()
        email = data.get('email')
        password = data.get('password')
        if not email or not password:
            logger.error(f"{request_id} | Missing email or password")
            raise HTTPException(
                status_code=400,
                detail="Missing email or password"
            )
        user = await UserService.check_password_return_user(email, password)
        if not user:
            logger.error(f"{request_id} | Invalid email or password")
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )
        access_token = create_access_token({"sub": user["username"], "role": user["role"]}, Authorize, False)
        response = JSONResponse(content={"access_token": access_token}, media_type="application/json")
        Authorize.set_access_cookies(access_token, response)
        return response
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")
    
"""
Refresh token endpoint
"""
@authorization_router.post("/authorization/refresh",
    dependencies=[
        Depends(auth_required)
    ])
async def extended_login(request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {str(request.url.path)}")
        username = Authorize.get_jwt_subject()
        user = await UserService.get_user_by_username_helper(username)
        refresh_token = create_access_token({"sub": username, "role": user["role"]}, Authorize, True)
        response = JSONResponse(content={"refresh_token": refresh_token}, media_type="application/json")
        Authorize.set_access_cookies(refresh_token, response)
        return response
    except AuthJWTException as e:
        logging.error(f"Token refresh failed: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": "An error occurred during token refresh"})
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

"""
Status endpoint
"""
@authorization_router.get("/authorization/status",
    dependencies=[
        Depends(auth_required)
    ])
async def status(request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {str(request.url.path)}")
        return JSONResponse(content={"status": "authorized"}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")
    
"""
Logout endpoint
"""
@authorization_router.post("/authorization/invalidate",
    dependencies=[
        Depends(auth_required)
    ])
async def logout(response: Response, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {str(request.url.path)}")
        jwt_id = Authorize.get_raw_jwt()['jti']
        user = Authorize.get_jwt_subject()
        Authorize.unset_jwt_cookies(response)
        if user not in jwt_blacklist:
            jwt_blacklist[user] = TimedHeap()
        jwt_blacklist[user].push(jwt_id)
        return JSONResponse(content={"message": "Your token has been invalidated"}, status_code=200)
    except AuthJWTException as e:
        logging.error(f"Logout failed: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": "An error occurred during logout"})
    except ValueError as e:
        return JSONResponse(content={"error": "Unable to process request"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")
    
@authorization_router.api_route("/status", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def rest_gateway():
    return JSONResponse(content={"message": "Gateway is online"}, status_code=200)