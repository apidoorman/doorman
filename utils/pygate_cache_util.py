"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
"""

import redis
import json
import os

class PygateCacheManager:
    def __init__(self):
        redis_host = os.getenv("REDIS_HOST")
        redis_port = int(os.getenv("REDIS_PORT"))
        redis_db = int(os.getenv("REDIS_DB"))

        pool = redis.ConnectionPool(host=redis_host, port=redis_port, db=redis_db, decode_responses=True, max_connections=100)
        self.redis = redis.StrictRedis(connection_pool=pool)

        self.prefixes = {
            'api_cache': 'api_cache:',
            'api_endpoint_cache': 'api_endpoint_cache:',
            'api_id_cache': 'api_id_cache:',
            'endpoint_cache': 'endpoint_cache:',
            'group_cache': 'group_cache:',
            'role_cache': 'role_cache:',
            'user_subscription_cache': 'user_subscription_cache:',
            'user_cache': 'user_cache:',
            'user_group_cache': 'user_group_cache:',
            'user_role_cache': 'user_role_cache:',
            'endpoint_load_balancer': 'endpoint_load_balancer:',
            'endpoint_server_cache': 'endpoint_server_cache:',
            'client_routing_cache': 'client_routing_cache:',
            'token_def_cache': 'token_def_cache'
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
            'token_def_cache': 86400
        }

    def _get_key(self, cache_name, key):
        """Generate a Redis key."""
        return f"{self.prefixes[cache_name]}{key}"

    def set_cache(self, cache_name, key, value):
        """Set a value in the specified cache."""
        ttl = self.default_ttls.get(cache_name)
        redis_key = self._get_key(cache_name, key)
        self.redis.setex(redis_key, ttl, json.dumps(value))

    def get_cache(self, cache_name, key):
        """Get a value from the specified cache."""
        redis_key = self._get_key(cache_name, key)
        value = self.redis.get(redis_key)
        return json.loads(value) if value else None

    def delete_cache(self, cache_name, key):
        """Delete a value from the specified cache."""
        redis_key = self._get_key(cache_name, key)
        self.redis.delete(redis_key)

    def clear_cache(self, cache_name):
        """Clear all values in the specified cache."""
        pattern = f"{self.prefixes[cache_name]}*"
        keys = self.redis.keys(pattern)
        if keys:
            self.redis.delete(*keys)

    def clear_all_caches(self):
        """Clear all caches."""
        for cache_name in self.prefixes.keys():
            self.clear_cache(cache_name)

    @staticmethod
    def is_operational():
        """Check if the cache is operational"""
        try:
            test_key = "health_check_test"
            test_value = "test"
            pygate_cache.set_cache(test_key, test_key, test_value)
            retrieved_value = pygate_cache.get_cache(test_key, test_key)
            pygate_cache.delete_cache(test_key, test_key)
            return retrieved_value == test_value
        except Exception:
            return False

pygate_cache = PygateCacheManager()

"""
# Example usage
pygate_cache = PygateCacheManager()

# Setting values
pygate_cache.set_cache('api_cache', 'api_name/v1', {'data': 'example'})

# Getting values
print(pygate_cache.get_cache('api_cache', 'api_name/v1'))

# Deleting a key
pygate_cache.delete_cache('api_cache', 'api_name/v1')

# Clearing an entire cache
pygate_cache.clear_cache('api_cache')
"""