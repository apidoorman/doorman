"""
Async cache wrapper using redis.asyncio for non-blocking I/O operations.

The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

import json
import logging
import os
from typing import Any

import redis.asyncio as aioredis

from utils.doorman_cache_util import MemoryCache

logger = logging.getLogger('doorman.gateway')


class AsyncDoormanCacheManager:
    """Async cache manager supporting both Redis (async) and in-memory modes."""

    def __init__(self):
        cache_flag = os.getenv('MEM_OR_EXTERNAL')
        if cache_flag is None:
            cache_flag = os.getenv('MEM_OR_REDIS', 'MEM')
        self.cache_type = str(cache_flag).upper()

        if self.cache_type == 'MEM':
            maxsize = int(os.getenv('CACHE_MAX_SIZE', 10000))
            self.cache = MemoryCache(maxsize=maxsize)
            self.is_redis = False
            self._redis_pool = None
        else:
            self.cache = None
            self.is_redis = True
            self._redis_pool = None
            self._init_lock = False

        self.prefixes = {
            'api_cache': 'api_cache:',
            'api_endpoint_cache': 'api_endpoint_cache:',
            'api_id_cache': 'api_id_cache:',
            'endpoint_cache': 'endpoint_cache:',
            'endpoint_validation_cache': 'endpoint_validation_cache:',
            'group_cache': 'group_cache:',
            'role_cache': 'role_cache:',
            'user_subscription_cache': 'user_subscription_cache:',
            'user_cache': 'user_cache:',
            'user_group_cache': 'user_group_cache:',
            'user_role_cache': 'user_role_cache:',
            'endpoint_load_balancer': 'endpoint_load_balancer:',
            'endpoint_server_cache': 'endpoint_server_cache:',
            'client_routing_cache': 'client_routing_cache:',
            'token_def_cache': 'token_def_cache:',
            'credit_def_cache': 'credit_def_cache:',
        }

        self.default_ttls = {
            'api_cache': 86400,
            'api_endpoint_cache': 86400,
            'api_id_cache': 86400,
            'endpoint_cache': 86400,
            'group_cache': 86400,
            'role_cache': 86400,
            'user_subscription_cache': 86400,
            'user_cache': 86400,
            'user_group_cache': 86400,
            'user_role_cache': 86400,
            'endpoint_load_balancer': 86400,
            'endpoint_server_cache': 86400,
            'client_routing_cache': 86400,
            'token_def_cache': 86400,
            'credit_def_cache': 86400,
        }

    def _to_json_serializable(self, value):
        """Recursively convert bytes and non-JSON types into serializable forms.

        Mirrors the sync cache utility behavior so cached values are portable.
        """
        try:
            if isinstance(value, bytes):
                try:
                    return value.decode('utf-8')
                except Exception:
                    return value.decode('latin-1', errors='ignore')
            if isinstance(value, dict):
                return {k: self._to_json_serializable(v) for k, v in value.items()}
            if isinstance(value, list):
                return [self._to_json_serializable(v) for v in value]
            return value
        except Exception:
            return value

    async def _ensure_redis_connection(self):
        """Lazy initialize Redis connection (async)."""
        if not self.is_redis or self.cache is not None:
            return

        if self._init_lock:
            import asyncio

            while self._init_lock:
                await asyncio.sleep(0.01)
            return

        self._init_lock = True
        try:
            redis_host = os.getenv('REDIS_HOST', 'localhost')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            redis_db = int(os.getenv('REDIS_DB', 0))

            self._redis_pool = aioredis.ConnectionPool(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                decode_responses=True,
                max_connections=100,
            )
            self.cache = aioredis.Redis(connection_pool=self._redis_pool)

            await self.cache.ping()
            logger.info(f'Async Redis connected: {redis_host}:{redis_port}')

        except Exception as e:
            logger.warning(f'Async Redis connection failed, falling back to memory cache: {e}')
            maxsize = int(os.getenv('CACHE_MAX_SIZE', 10000))
            self.cache = MemoryCache(maxsize=maxsize)
            self.is_redis = False
            self.cache_type = 'MEM'
        finally:
            self._init_lock = False

    def _get_key(self, cache_name: str, key: str) -> str:
        """Get prefixed cache key."""
        return f'{self.prefixes[cache_name]}{key}'

    async def set_cache(self, cache_name: str, key: str, value: Any):
        """Set cache value with TTL (async)."""
        if self.is_redis:
            await self._ensure_redis_connection()

        ttl = self.default_ttls.get(cache_name, 86400)
        cache_key = self._get_key(cache_name, key)

        payload = json.dumps(self._to_json_serializable(value))
        if self.is_redis:
            await self.cache.setex(cache_key, ttl, payload)
        else:
            self.cache.setex(cache_key, ttl, payload)

    async def get_cache(self, cache_name: str, key: str) -> Any | None:
        """Get cache value (async)."""
        if self.is_redis:
            await self._ensure_redis_connection()

        cache_key = self._get_key(cache_name, key)

        if self.is_redis:
            value = await self.cache.get(cache_key)
        else:
            value = self.cache.get(cache_key)

        if value:
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return None

    async def delete_cache(self, cache_name: str, key: str):
        """Delete cache key (async)."""
        if self.is_redis:
            await self._ensure_redis_connection()

        cache_key = self._get_key(cache_name, key)

        if self.is_redis:
            await self.cache.delete(cache_key)
        else:
            self.cache.delete(cache_key)

    async def clear_cache(self, cache_name: str):
        """Clear all keys with given prefix (async)."""
        if self.is_redis:
            await self._ensure_redis_connection()

        pattern = f'{self.prefixes[cache_name]}*'

        if self.is_redis:
            keys = await self.cache.keys(pattern)
            if keys:
                await self.cache.delete(*keys)
        else:
            keys = self.cache.keys(pattern)
            if keys:
                self.cache.delete(*keys)

    async def clear_all_caches(self):
        """Clear all cache prefixes (async)."""
        for cache_name in self.prefixes.keys():
            await self.clear_cache(cache_name)

    async def get_cache_info(self) -> dict[str, Any]:
        """Get cache information (async)."""
        info = {
            'type': self.cache_type,
            'is_redis': self.is_redis,
            'prefixes': list(self.prefixes.keys()),
            'default_ttl': self.default_ttls,
        }

        if not self.is_redis and hasattr(self.cache, 'get_cache_stats'):
            info['memory_stats'] = self.cache.get_cache_stats()

        return info

    async def cleanup_expired_entries(self):
        """Cleanup expired entries (async, only for memory cache)."""
        if not self.is_redis and hasattr(self.cache, '_cleanup_expired'):
            self.cache._cleanup_expired()

    async def is_operational(self) -> bool:
        """Test if cache is operational (async)."""
        try:
            test_key = 'health_check_test'
            test_value = 'test'
            await self.set_cache('api_cache', test_key, test_value)
            retrieved_value = await self.get_cache('api_cache', test_key)
            await self.delete_cache('api_cache', test_key)
            return retrieved_value == test_value
        except Exception:
            return False

    async def invalidate_on_db_failure(self, cache_name: str, key: str, operation):
        """
        Cache invalidation wrapper for async database operations.

        Invalidates cache on:
        1. Database exceptions (to force fresh read on next access)
        2. Successful updates (to prevent stale cache)

        Does NOT invalidate if:
        - No matching document found (modified_count == 0 but no exception)

        Usage:
            try:
                result = await user_collection.update_one({'username': username}, {'$set': updates})
                await async_doorman_cache.invalidate_on_db_failure('user_cache', username, lambda: result)
            except Exception as e:
                await async_doorman_cache.delete_cache('user_cache', username)
                raise

        Args:
            cache_name: Cache type (user_cache, role_cache, etc.)
            key: Cache key to invalidate
            operation: Lambda returning db operation result or coroutine
        """
        try:
            import inspect

            if inspect.iscoroutine(operation):
                result = await operation
            else:
                result = operation()

            if hasattr(result, 'modified_count') and result.modified_count > 0:
                await self.delete_cache(cache_name, key)
            elif hasattr(result, 'deleted_count') and result.deleted_count > 0:
                await self.delete_cache(cache_name, key)

            return result
        except Exception:
            await self.delete_cache(cache_name, key)
            raise

    async def close(self):
        """Close Redis connections gracefully (async)."""
        if self.is_redis and self.cache:
            await self.cache.close()
            if self._redis_pool:
                await self._redis_pool.disconnect()
            logger.info('Async Redis connections closed')


async_doorman_cache = AsyncDoormanCacheManager()


async def close_async_cache_connections():
    """Close all async cache connections for graceful shutdown."""
    await async_doorman_cache.close()
