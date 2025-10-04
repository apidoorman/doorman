# External imports
from fastapi import Request, HTTPException
import asyncio
import time

# Internal imports
from utils.auth_util import auth_required
from utils.database import user_collection
from utils.doorman_cache_util import doorman_cache

class InMemoryWindowCounter:
    """Simple in-memory counter with TTL semantics to mimic required Redis ops.
    Not distributed; process-local only. Used as fallback when Redis is unavailable.
    """
    def __init__(self):
        self._store = {}

    async def incr(self, key: str) -> int:
        now = int(time.time())
        entry = self._store.get(key)
        if entry and entry['expires_at'] > now:
            entry['count'] += 1
        else:

            entry = {'count': 1, 'expires_at': now + 1}
        self._store[key] = entry
        return entry['count']

    async def expire(self, key: str, ttl_seconds: int) -> None:
        now = int(time.time())
        entry = self._store.get(key)
        if entry:
            entry['expires_at'] = now + int(ttl_seconds)
            self._store[key] = entry

_fallback_counter = InMemoryWindowCounter()

def duration_to_seconds(duration: str) -> int:
    mapping = {
        'second': 1,
        'minute': 60,
        'hour': 3600,
        'day': 86400,
        'week': 604800,
        'month': 2592000,
        'year': 31536000
    }
    if not duration:
        return 60
    if duration.endswith('s'):
        duration = duration[:-1]
    return mapping.get(duration.lower(), 60)

async def limit_and_throttle(request: Request):
    payload = await auth_required(request)
    username = payload.get('sub')
    redis_client = getattr(request.app.state, 'redis', None)
    user = doorman_cache.get_cache('user_cache', username)
    if not user:
        user = user_collection.find_one({'username': username})
    now_ms = int(time.time() * 1000)
    # Rate limiting (skip if explicitly disabled)
    if user.get('rate_limit_enabled') is not False:
        rate = int(user.get('rate_limit_duration') or 1)
        duration = user.get('rate_limit_duration_type', 'minute')
        window = duration_to_seconds(duration)
        key = f'rate_limit:{username}:{now_ms // (window * 1000)}'
        try:
            client = redis_client or _fallback_counter
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, window)
        except Exception:
            count = await _fallback_counter.incr(key)
            if count == 1:
                await _fallback_counter.expire(key, window)
        if count > rate:
            raise HTTPException(status_code=429, detail='Rate limit exceeded')

    # Throttling (skip if explicitly disabled)
    if user.get('throttle_enabled') is not False:
        throttle_limit = int(user.get('throttle_duration') or 5)
        throttle_duration = user.get('throttle_duration_type', 'second')
        throttle_window = duration_to_seconds(throttle_duration)
        throttle_key = f'throttle_limit:{username}:{now_ms // (throttle_window * 1000)}'
        try:
            client = redis_client or _fallback_counter
            throttle_count = await client.incr(throttle_key)
            if throttle_count == 1:
                await client.expire(throttle_key, throttle_window)
        except Exception:
            throttle_count = await _fallback_counter.incr(throttle_key)
            if throttle_count == 1:
                await _fallback_counter.expire(throttle_key, throttle_window)
        throttle_queue_limit = int(user.get('throttle_queue_limit') or 10)
        if throttle_count > throttle_queue_limit:
            raise HTTPException(status_code=429, detail='Throttle queue limit exceeded')
        if throttle_count > throttle_limit:
            throttle_wait = float(user.get('throttle_wait_duration', 0.5) or 0.5)
            throttle_wait_duration = user.get('throttle_wait_duration_type', 'second')
            if throttle_wait_duration != 'second':
                throttle_wait *= duration_to_seconds(throttle_wait_duration)
            dynamic_wait = throttle_wait * (throttle_count - throttle_limit)
            await asyncio.sleep(dynamic_wait)

def reset_counters():
    """Reset in-memory rate/throttle counters (used by tests and cache clears).
    Has no effect when a real Redis client is configured.
    """
    try:
        _fallback_counter._store.clear()
    except Exception:
        pass
