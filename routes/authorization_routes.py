"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""


from fastapi import APIRouter, Request, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException

from models.response_model import ResponseModel
from services.user_service import UserService
from utils.token_util import create_access_token
from utils.auth_util import auth_required
from utils.auth_blacklist import TimedHeap, jwt_blacklist

import uuid
import time
import logging

authorization_router = APIRouter()

import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("pygate.gateway")

@authorization_router.post("/authorization",
    description="Create authorization token",
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "******************"
                    }
                }
            }
        }
    }
)
async def authorization(request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
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
                status_code=400,
                detail="Invalid email or password"
            )
        access_token = create_access_token({"sub": user["username"], "role": user["role"]}, Authorize, False)
        response = JSONResponse(content={"access_token": access_token}, media_type="application/json")
        response.delete_cookie("access_token_cookie")
        response.set_cookie("access_token_cookie", access_token, httponly=True)
        Authorize.set_access_cookies(access_token, response)
        return response
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")
    
@authorization_router.post("/authorization/refresh",
    description="Create authorization refresh token",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "refresh_token": "******************"
                    }
                }
            }
        }
    }
)
async def extended_authorization(request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        username = Authorize.get_jwt_subject()
        user = await UserService.get_user_by_username_helper(username)
        refresh_token = create_access_token({"sub": username, "role": user["role"]}, Authorize, True)
        response = JSONResponse(content={"refresh_token": refresh_token}, media_type="application/json")
        response.delete_cookie("access_token_cookie")
        Authorize.set_access_cookies(refresh_token, response)
        return response
    except AuthJWTException as e:
        logging.error(f"Token refresh failed: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": "An error occurred during token refresh"})
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@authorization_router.get("/authorization/status",
    description="Get authorization token status",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "status": "authorized"
                    }
                }
            }
        }
    }
)
async def authorization_status(request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return JSONResponse(content={"status": "authorized"}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")
    
@authorization_router.post("/authorization/invalidate",
    description="Invalidate authorization token",
    dependencies=[
        Depends(auth_required)
    ],
    response_model=ResponseModel,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Your token has been invalidated"
                    }
                }
            }
        }
    }
)
async def authorization_invalidate(response: Response, request: Request, Authorize: AuthJWT = Depends()):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | Username: {Authorize.get_jwt_subject()} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        Authorize.jwt_required()
        user = Authorize.get_jwt_subject()
        jti = Authorize.get_raw_jwt()["jti"]
        if user not in jwt_blacklist:
            jwt_blacklist[user] = TimedHeap()
        await jwt_blacklist[user].push(jti)
        response = JSONResponse(content={"message": "Your token has been invalidated"}, status_code=200)
        response.delete_cookie("access_token_cookie")
        response.delete_cookie("refresh_token_cookie")
        response.delete_cookie("csrf_access_token")
        return response
    except AuthJWTException as e:
        logging.error(f"Logout failed: {str(e)}")
        return JSONResponse(status_code=500, content={"detail": "An error occurred during logout"})
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": "An unexpected error occurred"}, status_code=500)
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")