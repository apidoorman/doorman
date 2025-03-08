"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from fastapi_jwt_auth import AuthJWT

from services.subscription_service import SubscriptionService
from utils.auth_util import auth_required
from utils.whitelist_util import whitelist_check
from utils.role_util import role_required

subscription_router = APIRouter()

"""
Subscribe to API *platform endpoint.
Request:
{
    "username": "<string>",
    "api_name": "<string>",
    "api_version": "<string>"
}
Response:
{
    "message": "Successfully subscribed to the API"
}
"""
@subscription_router.post("/subscribe")
@auth_required()
@whitelist_check()
@role_required(("admin", "dev", "platform"))
async def subscribe_api(request: Request):
    try:
        data = await request.json()
        SubscriptionService.subscribe(data)
        return JSONResponse(content={'message': 'Successfully subscribed to the API'}, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


"""
Unsubscribe from API *platform endpoint.
Request:
{
    "username": "<string>",
    "api_name": "<string>",
    "api_version": "<string>"
}
Response:
{
    "message": "Successfully unsubscribed from the API"
}
"""
@subscription_router.post("/unsubscribe")
@auth_required()
@whitelist_check()
@role_required(("admin", "dev", "platform"))
async def unsubscribe_api(request: Request):
    try:
        data = await request.json()
        SubscriptionService.unsubscribe(data)
        return JSONResponse(content={'message': 'Successfully unsubscribed from the API'}, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


"""
Get API Subscriptions for user by id *platform endpoint.
Request:
{
}
Response:
{
    "subscriptions": []
}
"""
@subscription_router.get("/subscriptions/{user_id}")
@auth_required()
@whitelist_check()
@role_required(("admin", "dev", "platform"))
async def subscriptions_for_user_by_id(user_id: str):
    try:
        subscriptions = SubscriptionService.get_user_subscriptions(user_id)
        return JSONResponse(content={'subscriptions': subscriptions}, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

"""
Get API Subscriptions for active user *platform endpoint.
Request:
{
}
Response:
{
    "subscriptions": []
}
"""
@subscription_router.get("/subscriptions")
@auth_required()
async def subscriptions_for_current_user(Authorize: AuthJWT = Depends()):
    try:
        username = Authorize.get_jwt_subject()
        subscriptions = SubscriptionService.get_user_subscriptions(username)
        return JSONResponse(content={'subscriptions': subscriptions}, status_code=200)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))