from __future__ import annotations

import time

from fastapi import HTTPException, Request

from utils.database import user_collection
from utils.doorman_cache_util import doorman_cache


def _window_to_seconds(win: str | None) -> int:
    mapping = {
        'second': 1,
        'minute': 60,
        'hour': 3600,
        'day': 86400,
        'week': 604800,
        'month': 2592000,
    }
    if not win:
        return 86400
    w = win.lower().rstrip('s')
    return mapping.get(w, 86400)


def _bucket_key(username: str, window: str, now: int | None = None) -> tuple[str, int]:
    sec = _window_to_seconds(window)
    now = now or int(time.time())
    bucket = (now // sec) * sec
    key = f'bandwidth_usage:{username}:{sec}:{bucket}'
    return key, sec


def _get_user(username: str) -> dict | None:
    user = doorman_cache.get_cache('user_cache', username)
    if not user:
        user = user_collection.find_one({'username': username})
        if user and user.get('_id'):
            del user['_id']
    return user


def _get_client():
    return doorman_cache.cache if getattr(doorman_cache, 'is_redis', False) else None


def get_current_usage(username: str, window: str | None) -> int:
    win = window or 'day'
    key, ttl = _bucket_key(username, win)
    client = _get_client()
    if client is not None:
        val = client.get(key)
        try:
            return int(val) if val is not None else 0
        except Exception:
            return 0
    val = doorman_cache.cache.get(key)
    try:
        return int(val) if isinstance(val, int) else int(val or 0)
    except Exception:
        return 0


def add_usage(username: str, delta_bytes: int, window: str | None) -> None:
    if not delta_bytes:
        return
    win = window or 'day'
    key, ttl = _bucket_key(username, win)
    client = _get_client()
    if client is not None:
        try:
            new_val = client.incrby(key, int(delta_bytes))
            client.expire(key, ttl)
            return
        except Exception:
            pass
    cur = get_current_usage(username, win)
    new_val = cur + int(delta_bytes)
    try:
        doorman_cache.cache.setex(key, ttl, str(new_val))
    except Exception:
        pass


async def enforce_pre_request_limit(request: Request, username: str | None) -> None:
    if not username:
        return
    user = _get_user(username)
    if not user:
        return
    if user.get('bandwidth_limit_enabled') is False:
        return
    limit = user.get('bandwidth_limit_bytes')
    if not limit or int(limit) <= 0:
        return
    window = user.get('bandwidth_limit_window') or 'day'
    used = get_current_usage(username, window)
    clen = 0
    try:
        clen = int(request.headers.get('content-length') or 0)
    except Exception:
        clen = 0
    if used >= int(limit) or used + clen > int(limit):
        raise HTTPException(status_code=429, detail='Bandwidth limit exceeded')
