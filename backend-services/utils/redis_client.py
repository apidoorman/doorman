"""
Redis Client Wrapper

Provides a robust Redis client with connection pooling, error handling,
and graceful degradation for rate limiting operations.
"""

import logging
from contextlib import contextmanager
from typing import Any

import redis

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Redis client wrapper with connection pooling and error handling

    Features:
    - Connection pooling for performance
    - Automatic reconnection on failure
    - Graceful degradation (returns None on errors)
    - Pipeline support for batch operations
    """

    def __init__(
        self,
        host: str = 'localhost',
        port: int = 6379,
        password: str | None = None,
        db: int = 0,
        max_connections: int = 50,
        socket_timeout: int = 5,
        socket_connect_timeout: int = 5,
        decode_responses: bool = True,
    ):
        """
        Initialize Redis client

        Args:
            host: Redis server host
            port: Redis server port
            password: Redis password (if required)
            db: Redis database number
            max_connections: Maximum connections in pool
            socket_timeout: Socket timeout in seconds
            socket_connect_timeout: Connection timeout in seconds
            decode_responses: Decode byte responses to strings
        """
        self.host = host
        self.port = port
        self.password = password
        self.db = db

        # Create connection pool
        self.pool = redis.ConnectionPool(
            host=host,
            port=port,
            password=password,
            db=db,
            max_connections=max_connections,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            decode_responses=decode_responses,
        )

        # Create Redis client
        self.client = redis.Redis(connection_pool=self.pool)

        # Test connection
        self._test_connection()

    def _test_connection(self) -> bool:
        """Test Redis connection"""
        try:
            self.client.ping()
            logger.info(f'Redis connection successful: {self.host}:{self.port}')
            return True
        except redis.ConnectionError as e:
            logger.error(f'Redis connection failed: {e}')
            return False
        except Exception as e:
            logger.error(f'Unexpected Redis error: {e}')
            return False

    def get(self, key: str) -> str | None:
        """
        Get value by key

        Args:
            key: Redis key

        Returns:
            Value or None if not found or error
        """
        try:
            return self.client.get(key)
        except Exception as e:
            logger.error(f'Redis GET error for key {key}: {e}')
            return None

    def set(
        self,
        key: str,
        value: Any,
        ex: int | None = None,
        px: int | None = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool:
        """
        Set key-value pair

        Args:
            key: Redis key
            value: Value to store
            ex: Expiration time in seconds
            px: Expiration time in milliseconds
            nx: Only set if key doesn't exist
            xx: Only set if key exists

        Returns:
            True if successful, False otherwise
        """
        try:
            result = self.client.set(key, value, ex=ex, px=px, nx=nx, xx=xx)
            return bool(result)
        except Exception as e:
            logger.error(f'Redis SET error for key {key}: {e}')
            return False

    def incr(self, key: str, amount: int = 1) -> int | None:
        """
        Increment counter atomically

        Args:
            key: Redis key
            amount: Amount to increment

        Returns:
            New value or None on error
        """
        try:
            return self.client.incr(key, amount)
        except Exception as e:
            logger.error(f'Redis INCR error for key {key}: {e}')
            return None

    def decr(self, key: str, amount: int = 1) -> int | None:
        """
        Decrement counter atomically

        Args:
            key: Redis key
            amount: Amount to decrement

        Returns:
            New value or None on error
        """
        try:
            return self.client.decr(key, amount)
        except Exception as e:
            logger.error(f'Redis DECR error for key {key}: {e}')
            return None

    def expire(self, key: str, seconds: int) -> bool:
        """
        Set expiration time for key

        Args:
            key: Redis key
            seconds: Expiration time in seconds

        Returns:
            True if successful, False otherwise
        """
        try:
            return bool(self.client.expire(key, seconds))
        except Exception as e:
            logger.error(f'Redis EXPIRE error for key {key}: {e}')
            return False

    def ttl(self, key: str) -> int | None:
        """
        Get time to live for key

        Args:
            key: Redis key

        Returns:
            TTL in seconds, -1 if no expiry, -2 if key doesn't exist, None on error
        """
        try:
            return self.client.ttl(key)
        except Exception as e:
            logger.error(f'Redis TTL error for key {key}: {e}')
            return None

    def delete(self, *keys: str) -> int:
        """
        Delete one or more keys

        Args:
            keys: Keys to delete

        Returns:
            Number of keys deleted
        """
        try:
            return self.client.delete(*keys)
        except Exception as e:
            logger.error(f'Redis DELETE error: {e}')
            return 0

    def exists(self, *keys: str) -> int:
        """
        Check if keys exist

        Args:
            keys: Keys to check

        Returns:
            Number of existing keys
        """
        try:
            return self.client.exists(*keys)
        except Exception as e:
            logger.error(f'Redis EXISTS error: {e}')
            return 0

    def hget(self, name: str, key: str) -> str | None:
        """
        Get hash field value

        Args:
            name: Hash name
            key: Field key

        Returns:
            Field value or None
        """
        try:
            return self.client.hget(name, key)
        except Exception as e:
            logger.error(f'Redis HGET error for {name}:{key}: {e}')
            return None

    def hset(self, name: str, key: str, value: Any) -> bool:
        """
        Set hash field value

        Args:
            name: Hash name
            key: Field key
            value: Field value

        Returns:
            True if successful
        """
        try:
            self.client.hset(name, key, value)
            return True
        except Exception as e:
            logger.error(f'Redis HSET error for {name}:{key}: {e}')
            return False

    def hmget(self, name: str, keys: list) -> list | None:
        """
        Get multiple hash field values

        Args:
            name: Hash name
            keys: List of field keys

        Returns:
            List of values or None
        """
        try:
            return self.client.hmget(name, keys)
        except Exception as e:
            logger.error(f'Redis HMGET error for {name}: {e}')
            return None

    def hmset(self, name: str, mapping: dict[str, Any]) -> bool:
        """
        Set multiple hash field values

        Args:
            name: Hash name
            mapping: Dictionary of field:value pairs

        Returns:
            True if successful
        """
        try:
            self.client.hset(name, mapping=mapping)
            return True
        except Exception as e:
            logger.error(f'Redis HMSET error for {name}: {e}')
            return False

    @contextmanager
    def pipeline(self, transaction: bool = True):
        """
        Context manager for Redis pipeline

        Args:
            transaction: Use MULTI/EXEC transaction

        Yields:
            Pipeline object

        Example:
            with redis_client.pipeline() as pipe:
                pipe.incr('key1')
                pipe.incr('key2')
                pipe.execute()
        """
        pipe = self.client.pipeline(transaction=transaction)
        try:
            yield pipe
        except Exception as e:
            logger.error(f'Redis pipeline error: {e}')
            raise
        finally:
            pipe.reset()

    def zadd(self, name: str, mapping: dict[str, float]) -> int:
        """
        Add members to sorted set

        Args:
            name: Sorted set name
            mapping: Dictionary of member:score pairs

        Returns:
            Number of members added
        """
        try:
            return self.client.zadd(name, mapping)
        except Exception as e:
            logger.error(f'Redis ZADD error for {name}: {e}')
            return 0

    def zremrangebyscore(self, name: str, min_score: float, max_score: float) -> int:
        """
        Remove members from sorted set by score range

        Args:
            name: Sorted set name
            min_score: Minimum score
            max_score: Maximum score

        Returns:
            Number of members removed
        """
        try:
            return self.client.zremrangebyscore(name, min_score, max_score)
        except Exception as e:
            logger.error(f'Redis ZREMRANGEBYSCORE error for {name}: {e}')
            return 0

    def zcount(self, name: str, min_score: float, max_score: float) -> int:
        """
        Count members in sorted set by score range

        Args:
            name: Sorted set name
            min_score: Minimum score
            max_score: Maximum score

        Returns:
            Number of members in range
        """
        try:
            return self.client.zcount(name, min_score, max_score)
        except Exception as e:
            logger.error(f'Redis ZCOUNT error for {name}: {e}')
            return 0

    def close(self):
        """Close Redis connection pool"""
        try:
            self.pool.disconnect()
            logger.info('Redis connection pool closed')
        except Exception as e:
            logger.error(f'Error closing Redis pool: {e}')


# Global Redis client instance
_redis_client: RedisClient | None = None


def get_redis_client(
    host: str = 'localhost', port: int = 6379, password: str | None = None, db: int = 0
) -> RedisClient:
    """
    Get or create global Redis client instance

    Args:
        host: Redis server host
        port: Redis server port
        password: Redis password
        db: Redis database number

    Returns:
        RedisClient instance
    """
    global _redis_client

    if _redis_client is None:
        _redis_client = RedisClient(host=host, port=port, password=password, db=db)

    return _redis_client


def close_redis_client():
    """Close global Redis client"""
    global _redis_client

    if _redis_client is not None:
        _redis_client.close()
        _redis_client = None
