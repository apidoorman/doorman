"""
Durable token revocation utilities.

**IMPORTANT: Process-local fallback - NOT safe for multi-worker deployments**

**Backend Priority:**
1. Redis (sync client) - REQUIRED for multi-worker/multi-node deployments
2. Memory-only MongoDB (revocations_collection) - Single-process only
3. In-memory fallback (jwt_blacklist, revoked_all_users) - Single-process only

**Behavior:**
- If Redis is configured (MEM_OR_EXTERNAL=REDIS) and connection succeeds:
  Revocations are persisted in Redis (sync client) and survive restarts.
  Shared across all workers/nodes in distributed deployments.

- If database.memory_only is True and revocations_collection exists:
  Revocations stored in memory-only MongoDB for single-process persistence.
  Included in memory dumps but NOT shared across workers.

- Otherwise:
  Falls back to in-memory Python structures (jwt_blacklist, revoked_all_users).
  Process-local only - NOT shared across workers.

**Multi-Worker Safety:**
Production deployments with THREADS>1 MUST configure Redis (MEM_OR_EXTERNAL=REDIS).
The in-memory and memory-only DB fallbacks are NOT safe for multi-worker setups
and will allow revoked tokens to remain valid on other workers.

**Note on Redis Client:**
This module uses a synchronous Redis client (_redis_client) because token
revocation checks occur in synchronous code paths. For async rate limiting,
see limit_throttle_util.py which uses the async Redis client (app.state.redis).

**Public API (backward-compatible):**
- `TimedHeap` (in-memory helper)
- `jwt_blacklist` (in-memory map for fallback)
- `revoke_all_for_user`, `unrevoke_all_for_user`, `is_user_revoked`
- `purge_expired_tokens` (no-op when using Redis)
- `add_revoked_jti(username, jti, ttl_seconds)`
- `is_jti_revoked(username, jti)`

**See Also:**
- doorman.py validate_token_revocation_config() for multi-worker validation
- doorman.py app_lifespan() for production Redis requirement enforcement
"""

# External imports
from datetime import datetime, timedelta
import heapq
import os
from typing import Optional
import time

try:
    from utils.database import database, revocations_collection
except Exception:  # pragma: no cover
    database = None  # type: ignore
    revocations_collection = None  # type: ignore

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None  # type: ignore

# In-memory fallback structures (legacy behavior)
jwt_blacklist = {}
revoked_all_users = set()

# Module-level Redis client (sync) for durability
_redis_client = None
_redis_enabled = False

def _init_redis_if_possible():
    global _redis_client, _redis_enabled
    if _redis_client is not None:
        return
    try:
        # Honor unified MEM/REDIS flag (same as database/cache utils)
        flag = os.getenv('MEM_OR_EXTERNAL') or os.getenv('MEM_OR_REDIS', 'MEM')
        if str(flag).upper() == 'MEM':
            _redis_enabled = False
            _redis_client = None
            return
        if redis is None:
            _redis_enabled = False
            _redis_client = None
            return
        host = os.getenv('REDIS_HOST', 'localhost')
        port = int(os.getenv('REDIS_PORT', 6379))
        db = int(os.getenv('REDIS_DB', 0))
        pool = redis.ConnectionPool(host=host, port=port, db=db, decode_responses=True, max_connections=100)
        _redis_client = redis.StrictRedis(connection_pool=pool)
        # cheap ping to verify
        try:
            _redis_client.ping()
            _redis_enabled = True
        except Exception:
            _redis_client = None
            _redis_enabled = False
    except Exception:
        _redis_client = None
        _redis_enabled = False

def _revoked_jti_key(username: str, jti: str) -> str:
    return f'jwt:revoked:{username}:{jti}'

def _revoke_all_key(username: str) -> str:
    return f'jwt:revoke_all:{username}'

def revoke_all_for_user(username: str):
    """Mark all tokens for a user as revoked (durable if Redis is enabled)."""
    _init_redis_if_possible()
    try:
        # Memory-only mode: persist flag into in-memory DB for dumping
        if database is not None and getattr(database, 'memory_only', False) and revocations_collection is not None:
            try:
                existing = revocations_collection.find_one({'type': 'revoke_all', 'username': username})
                if existing:
                    revocations_collection.update_one({'_id': existing.get('_id')}, {'$set': {'revoke_all': True}})
                else:
                    revocations_collection.insert_one({'type': 'revoke_all', 'username': username, 'revoke_all': True})
            except Exception:
                revoked_all_users.add(username)
            return
        if _redis_enabled and _redis_client is not None:
            _redis_client.set(_revoke_all_key(username), '1')  # no TTL – admin will clear explicitly
        else:
            revoked_all_users.add(username)
    except Exception:
        revoked_all_users.add(username)

def unrevoke_all_for_user(username: str):
    """Clear 'revoke all' for a user (durable if Redis is enabled)."""
    _init_redis_if_possible()
    try:
        if database is not None and getattr(database, 'memory_only', False) and revocations_collection is not None:
            try:
                revocations_collection.delete_one({'type': 'revoke_all', 'username': username})
            except Exception:
                revoked_all_users.discard(username)
            return
        if _redis_enabled and _redis_client is not None:
            _redis_client.delete(_revoke_all_key(username))
        else:
            revoked_all_users.discard(username)
    except Exception:
        revoked_all_users.discard(username)

def is_user_revoked(username: str) -> bool:
    """Return True if user is under 'revoke all' (durable check if Redis enabled)."""
    _init_redis_if_possible()
    try:
        if database is not None and getattr(database, 'memory_only', False) and revocations_collection is not None:
            try:
                doc = revocations_collection.find_one({'type': 'revoke_all', 'username': username})
                return bool(doc and doc.get('revoke_all'))
            except Exception:
                pass
        if _redis_enabled and _redis_client is not None:
            return bool(_redis_client.exists(_revoke_all_key(username)))
        return username in revoked_all_users
    except Exception:
        return username in revoked_all_users

class TimedHeap:
    def __init__(self, purge_after=timedelta(hours=1)):
        self.heap = []
        self.purge_after = purge_after

    def push(self, item):
        expire_time = datetime.now() + self.purge_after
        heapq.heappush(self.heap, (expire_time, item))

    def pop(self):
        self.purge()
        if self.heap:
            return heapq.heappop(self.heap)[1]
        raise IndexError('pop from an empty priority queue')

    def purge(self):
        current_time = datetime.now()
        while self.heap and self.heap[0][0] < current_time:
            heapq.heappop(self.heap)

    def peek(self):
        self.purge()
        if self.heap:
            return self.heap[0][1]
        return None

def add_revoked_jti(username: str, jti: str, ttl_seconds: Optional[int] = None):
    """Add a specific JTI to the revocation list.

    - If Redis is enabled, store key with TTL so it auto-expires.
    - Otherwise push into in-memory TimedHeap (approximate via default purge window when ttl not provided).
    """
    if not username or not jti:
        return
    _init_redis_if_possible()
    try:
        if database is not None and getattr(database, 'memory_only', False) and revocations_collection is not None:
            try:
                exp = int(time.time()) + (max(1, int(ttl_seconds)) if ttl_seconds is not None else 3600)
                existing = revocations_collection.find_one({'type': 'jti', 'username': username, 'jti': jti})
                if existing:
                    revocations_collection.update_one({'_id': existing.get('_id')}, {'$set': {'expires_at': exp}})
                else:
                    revocations_collection.insert_one({'type': 'jti', 'username': username, 'jti': jti, 'expires_at': exp})
                return
            except Exception:
                pass
        if _redis_enabled and _redis_client is not None:
            ttl = max(1, int(ttl_seconds)) if ttl_seconds is not None else 3600
            _redis_client.setex(_revoked_jti_key(username, jti), ttl, '1')
            return
    except Exception:
        pass
    # Fallback to in-memory
    th = jwt_blacklist.get(username)
    if not th:
        th = TimedHeap()
        jwt_blacklist[username] = th
    th.push(jti)

def is_jti_revoked(username: str, jti: str) -> bool:
    """Check whether a specific JTI is revoked (durable if Redis enabled)."""
    if not username or not jti:
        return False
    _init_redis_if_possible()
    try:
        if database is not None and getattr(database, 'memory_only', False) and revocations_collection is not None:
            try:
                doc = revocations_collection.find_one({'type': 'jti', 'username': username, 'jti': jti})
                if not doc:
                    pass
                else:
                    exp = int(doc.get('expires_at') or 0)
                    now = int(time.time())
                    if exp <= now:
                        # expire eagerly
                        revocations_collection.delete_one({'_id': doc.get('_id')})
                        return False
                    return True
            except Exception:
                pass
        if _redis_enabled and _redis_client is not None:
            return bool(_redis_client.exists(_revoked_jti_key(username, jti)))
    except Exception:
        pass
    # Fallback check in-memory
    th = jwt_blacklist.get(username)
    if not th:
        return False
    th.purge()
    for _, token_jti in list(th.heap):
        if token_jti == jti:
            return True
    return False

async def purge_expired_tokens():
    """No-op when Redis-backed; purge DB/in-memory when memory-only."""
    _init_redis_if_possible()
    if _redis_enabled:
        return
    # Purge memory-only DB entries
    try:
        if database is not None and getattr(database, 'memory_only', False) and revocations_collection is not None:
            now = int(time.time())
            # remove all expired jti docs
            to_delete = []
            for d in revocations_collection.find({'type': 'jti'}):
                try:
                    if int(d.get('expires_at') or 0) <= now:
                        to_delete.append(d)
                except Exception:
                    to_delete.append(d)
            for d in to_delete:
                revocations_collection.delete_one({'_id': d.get('_id')})
    except Exception:
        pass
    # Purge in-memory fallback heaps
    for key, timed_heap in list(jwt_blacklist.items()):
        timed_heap.purge()
        if not timed_heap.heap:
            del jwt_blacklist[key]
