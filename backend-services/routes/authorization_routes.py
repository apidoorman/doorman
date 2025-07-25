"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

from fastapi import APIRouter, Request, Depends, HTTPException, Response
from jose import JWTError

from models.response_model import ResponseModel
from services.user_service import UserService
from utils.response_util import process_response
from utils.auth_util import auth_required, create_access_token
from utils.auth_blacklist import TimedHeap, jwt_blacklist

import uuid
import time
import logging

authorization_router = APIRouter()

logger = logging.getLogger("doorman.gateway")

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
async def authorization(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        logger.info(f"{request_id} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        data = await request.json()
        email = data.get('email')
        password = data.get('password')
        if not email or not password:
            return process_response(ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code="AUTH001",
                error_message="Missing email or password"
            ))
        user = await UserService.check_password_return_user(email, password)
        if not user:
            return process_response(ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code="AUTH002",
                error_message="Invalid email or password"
            ))
        if not user["active"]:
            return process_response(ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code="AUTH007",
                error_message="User is not active"
            ))
        access_token = create_access_token({"sub": user["username"], "role": user["role"]}, False)
        response = process_response(ResponseModel(
            status_code=200,
            response_headers={
                "request_id": request_id
            },
            response={"access_token": access_token}
        ).dict(), "rest")
        response.delete_cookie("access_token_cookie")
        response.set_cookie(
            key="access_token_cookie",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="Lax"
        )
        return response
    except HTTPException as e:
        return process_response(ResponseModel(
            status_code=401,
            response_headers={
                "request_id": request_id
            },
            error_code="AUTH003",
            error_message="Unable to validate credentials"
            ).dict(), "rest")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")
    
@authorization_router.post("/authorization/refresh",
    description="Create authorization refresh token",
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
async def extended_authorization(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        user = await UserService.get_user_by_username_helper(username)
        if not user["active"]:
            return process_response(ResponseModel(
                status_code=400,
                response_headers={
                    "request_id": request_id
                },
                error_code="AUTH007",
                error_message="User is not active"
            ).dict(), "rest")
        refresh_token = create_access_token({"sub": username, "role": user["role"]}, True)
        response = process_response(ResponseModel(
            status_code=200,
            response_headers={
                "request_id": request_id
            },
            response={"refresh_token": refresh_token}
        ).dict(), "rest")
        response.set_cookie(
            key="access_token_cookie",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="Lax"
        )
        return response
    except HTTPException as e:
        return process_response(ResponseModel(
            status_code=401,
            response_headers={
                "request_id": request_id
            },
            error_code="AUTH003",
            error_message="Unable to validate credentials"
            ).dict(), "rest")
    except JWTError as e:
        logging.error(f"Token refresh failed: {str(e)}")
        return process_response(ResponseModel(
            status_code=401,
            response_headers={
                "request_id": request_id
            },
            error_code="AUTH004",
            error_message="Token refresh failed"
            ).dict(), "rest")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")

@authorization_router.get("/authorization/status",
    description="Get authorization token status",
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
async def authorization_status(request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        return process_response(ResponseModel(
            status_code=200,
            response_headers={
                "request_id": request_id
            },
            message="Token is valid"
            ).dict(), "rest")
    except JWTError:
        return process_response(ResponseModel(
            status_code=401,
            response_headers={
                "request_id": request_id
            },
            error_code="AUTH005",
            error_message="Token is invalid"
            ).dict(), "rest")
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")
    
@authorization_router.post("/authorization/invalidate",
    description="Invalidate authorization token",
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
async def authorization_invalidate(response: Response, request: Request):
    request_id = str(uuid.uuid4())
    start_time = time.time() * 1000
    try:
        payload = await auth_required(request)
        username = payload.get("sub")
        logger.info(f"{request_id} | Username: {username} | From: {request.client.host}:{request.client.port}")
        logger.info(f"{request_id} | Endpoint: {request.method} {str(request.url.path)}")
        if username not in jwt_blacklist:
            jwt_blacklist[username] = TimedHeap()
        jwt_blacklist[username].push(payload.get("jti"))
        response = process_response(ResponseModel(
            status_code=200,
            response_headers={
                "request_id": request_id
            },
            message="Your token has been invalidated"
            ).dict(), "rest")
        response.delete_cookie("access_token_cookie")
        return response
    except Exception as e:
        logger.critical(f"{request_id} | Unexpected error: {str(e)}", exc_info=True)
        return process_response(ResponseModel(
            status_code=500,
            response_headers={
                "request_id": request_id
            },
            error_code="GTW999",
            error_message="An unexpected error occurred"
            ).dict(), "rest")
    finally:
        end_time = time.time() * 1000
        logger.info(f"{request_id} | Total time: {str(end_time - start_time)}ms")