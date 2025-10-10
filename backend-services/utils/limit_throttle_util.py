# External imports
from fastapi import Request, HTTPException
import asyncio
import time
import logging
import os

# Internal imports
from utils.auth_util import auth_required
from utils.database import user_collection
from utils.doorman_cache_util import doorman_cache
from utils.ip_policy_util import _get_client_ip

logger = logging.getLogger('doorman.gateway')

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
    # Rate limiting (enabled if explicitly set true, or legacy values exist)
    rate_enabled = (user.get('rate_limit_enabled') is True) or bool(user.get('rate_limit_duration'))
    if rate_enabled:
        # Use user-set values; if explicitly enabled but missing values, fall back to sensible defaults
        rate = int(user.get('rate_limit_duration') or 60)
        duration = user.get('rate_limit_duration_type') or 'minute'
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

    # Throttling (enabled if explicitly set true, or legacy values exist)
    throttle_enabled = (user.get('throttle_enabled') is True) or bool(user.get('throttle_duration'))
    if throttle_enabled:
        throttle_limit = int(user.get('throttle_duration') or 10)
        throttle_duration = user.get('throttle_duration_type') or 'second'
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

async def limit_by_ip(request: Request, limit: int = 10, window: int = 60):
    """
    IP-based rate limiting for endpoints that don't require authentication.

    Prevents brute force attacks by limiting requests per IP address.

    Args:
        request: FastAPI Request object
        limit: Maximum number of requests allowed in window (default: 10)
        window: Time window in seconds (default: 60)

    Raises:
        HTTPException: 429 if rate limit exceeded

    Returns:
        Dict with rate limit info for response headers

    Example:
        # Limit login to 5 attempts per 5 minutes per IP
        await limit_by_ip(request, limit=5, window=300)
    """
    try:
        if os.getenv('LOGIN_IP_RATE_DISABLED', 'false').lower() == 'true':
            now = int(time.time())
            return {
                'limit': limit,
                'remaining': limit,
                'reset': now + window,
                'window': window
            }
        client_ip = _get_client_ip(request, trust_xff=True)
        if not client_ip:
            logger.warning('Unable to determine client IP for rate limiting, allowing request')
            return {
                'limit': limit,
                'remaining': limit,
                'reset': int(time.time()) + window,
                'window': window
            }

        now = int(time.time())
        bucket = now // window
        key = f'ip_rate_limit:{client_ip}:{bucket}'

        redis_client = getattr(request.app.state, 'redis', None)
        client = redis_client or _fallback_counter

        try:
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, window)
        except Exception as e:
            logger.warning(f'Redis failure in IP rate limiting, using fallback: {str(e)}')
            count = await _fallback_counter.incr(key)
            if count == 1:
                await _fallback_counter.expire(key, window)

        remaining = max(0, limit - count)
        reset_time = (bucket + 1) * window
        retry_after = window - (now % window)

        rate_limit_info = {
            'limit': limit,
            'remaining': remaining,
            'reset': reset_time,
            'window': window
        }

        if count > limit:
            logger.warning(f'IP rate limit exceeded for {client_ip}: {count}/{limit} in {window}s')
            raise HTTPException(
                status_code=429,
                detail={
                    'error_code': 'RATE_LIMIT_EXCEEDED',
                    'message': f'Too many requests from your IP. Limit: {limit} per {window} seconds.',
                    'retry_after': retry_after
                },
                headers={
                    'Retry-After': str(retry_after),
                    'X-RateLimit-Limit': str(limit),
                    'X-RateLimit-Remaining': '0',
                    'X-RateLimit-Reset': str(reset_time)
                }
            )

        if count > (limit * 0.8):
            logger.info(f'IP {client_ip} approaching rate limit: {count}/{limit}')

        return rate_limit_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'IP rate limiting error: {str(e)}', exc_info=True)
        return {
            'limit': limit,
            'remaining': limit,
            'reset': int(time.time()) + window,
            'window': window
        }
