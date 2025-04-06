import time
from fastapi import Request, HTTPException
from fastapi_jwt_auth import AuthJWT
from services.cache import pygate_cache
from services.user_service import UserService

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
    if duration.endswith("s"):
        duration = duration[:-1]
    return mapping.get(duration.lower(), 60)

async def rate_limit(Authorize: AuthJWT, request: Request):
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