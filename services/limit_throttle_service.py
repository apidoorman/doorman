from fastapi import Request, HTTPException
from fastapi_jwt_auth import AuthJWT
from services.cache import pygate_cache
from services.user_service import UserService

import asyncio
import time

def duration_to_seconds(duration: str) -> int:
    mapping = {
        "second": 1,
        "minute": 60,
        "hour": 3600,
        "day": 86400,
        "week": 604800,
        "month": 2592000,
        "year": 31536000
    }
    if not duration:
        return 60
    if duration.endswith("s"):
        duration = duration[:-1]
    return mapping.get(duration.lower(), 60)

async def limit_and_throttle(Authorize: AuthJWT, request: Request):
    username = Authorize.get_jwt_subject()
    redis_client = request.app.state.redis
    user = pygate_cache.get_cache("user_cache", username)
    if not user:
        user = await UserService.user_collection.find_one({"username": username})
    rate = int(user.get("rate_limit", 1))
    duration = user.get("rate_limit_duration", "minute")
    window = duration_to_seconds(duration)
    now = int(time.time())
    key = f"rate_limit:{username}:{now // window}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, window)
    if count > rate:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    throttle_limit = int(user.get("throttle_soft_limit", 5))
    throttle_duration = user.get("throttle_duration", "second")
    throttle_window = duration_to_seconds(throttle_duration)
    throttle_key = f"throttle_limit:{username}:{now // throttle_window}"
    throttle_count = await redis_client.incr(throttle_key)
    if throttle_count == 1:
        await redis_client.expire(throttle_key, throttle_window)
    throttle_queue_limit = int(user.get("throttle_queue_limit", 10))
    if throttle_count > throttle_queue_limit:
        raise HTTPException(status_code=429, detail="Throttle queue limit exceeded")
    if throttle_count > throttle_limit:
        throttle_wait = float(user.get("throttle_wait", 0.5) or 0.5)
        throttle_wait_duration = user.get("throttle_wait_duration", "second")
        if throttle_wait_duration != "second":
            throttle_wait *= duration_to_seconds(throttle_wait_duration)
        dynamic_wait = throttle_wait * (throttle_count - throttle_limit)
        await asyncio.sleep(dynamic_wait)