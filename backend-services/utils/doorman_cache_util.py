"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

import redis
import json
import os
import threading
from typing import Dict, Any, Optional

class MemoryCache:
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
    
    def setex(self, key: str, ttl: int, value: str):
        with self._lock:
            self._cache[key] = {
                'value': value,
                'expires_at': self._get_current_time() + ttl
            }

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            if key in self._cache:
                cache_entry = self._cache[key]
                if self._get_current_time() < cache_entry['expires_at']:
                    return cache_entry['value']
                else:
                    del self._cache[key]
            return None
    
    def delete(self, *keys):
        with self._lock:
            for key in keys:
                if key in self._cache:
                    self._cache.pop(key, None)
    
    def keys(self, pattern: str) -> list:
        with self._lock:
            if pattern.endswith('*'):
                prefix = pattern[:-1]
                return [key for key in self._cache.keys() if key.startswith(prefix)]
            return [key for key in self._cache.keys() if key == pattern]
    
    def _get_current_time(self) -> int:
        import time
        return int(time.time())

    def get_cache_stats(self) -> Dict[str, Any]:
        with self._lock:
            current_time = self._get_current_time()
            total_entries = len(self._cache)
            expired_entries = sum(1 for entry in self._cache.values() 
                                if current_time >= entry['expires_at'])
            active_entries = total_entries - expired_entries
            return {
                'total_entries': total_entries,
                'active_entries': active_entries,
                'expired_entries': expired_entries
            }
    
    def _cleanup_expired(self):
        with self._lock:
            current_time = self._get_current_time()
            expired_keys = [
                key for key, entry in self._cache.items() 
                if current_time >= entry['expires_at']
            ]
            for key in expired_keys:
                del self._cache[key]
            if expired_keys:
                print(f"Cleaned up {len(expired_keys)} expired cache entries")

    # No-op stubs to keep interface compatibility
    def stop_auto_save(self):
        return

class DoormanCacheManager:
    def __init__(self):
        # Unified flag MEM_OR_EXTERNAL with backward-compatible alias MEM_OR_REDIS
        cache_flag = os.getenv("MEM_OR_EXTERNAL")
        if cache_flag is None:
            cache_flag = os.getenv("MEM_OR_REDIS", "MEM")
        self.cache_type = str(cache_flag).upper()
        if self.cache_type == "MEM":
            self.cache = MemoryCache()
            self.is_redis = False
        else:
            try:
                redis_host = os.getenv("REDIS_HOST", "localhost")
                redis_port = int(os.getenv("REDIS_PORT", 6379))
                redis_db = int(os.getenv("REDIS_DB", 0))
                pool = redis.ConnectionPool(
                    host=redis_host, 
                    port=redis_port, 
                    db=redis_db, 
                    decode_responses=True, 
                    max_connections=100
                )
                self.cache = redis.StrictRedis(connection_pool=pool)
                self.is_redis = True
            except Exception as e:
                print(f"Warning: Redis connection failed, falling back to memory cache: {e}")
                self.cache = MemoryCache()
                self.is_redis = False
                self.cache_type = "MEM"
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
            'credit_def_cache': 'credit_def_cache:'
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
            'credit_def_cache': 86400
        }

    def _get_key(self, cache_name, key):
        return f"{self.prefixes[cache_name]}{key}"

    def set_cache(self, cache_name, key, value):
        ttl = self.default_ttls.get(cache_name, 86400)
        cache_key = self._get_key(cache_name, key)
        if self.is_redis:
            self.cache.setex(cache_key, ttl, json.dumps(value))
        else:
            self.cache.setex(cache_key, ttl, json.dumps(value))

    def get_cache(self, cache_name, key):
        cache_key = self._get_key(cache_name, key)
        value = self.cache.get(cache_key)
        if value:
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return None

    def delete_cache(self, cache_name, key):
        cache_key = self._get_key(cache_name, key)
        self.cache.delete(cache_key)

    def clear_cache(self, cache_name):
        pattern = f"{self.prefixes[cache_name]}*"
        keys = self.cache.keys(pattern)
        if keys:
            self.cache.delete(*keys)

    def clear_all_caches(self):
        for cache_name in self.prefixes.keys():
            self.clear_cache(cache_name)

    def get_cache_info(self):
        info = {
            'type': self.cache_type,
            'is_redis': self.is_redis,
            'prefixes': list(self.prefixes.keys()),
            'default_ttl': self.default_ttls
        }
        if not self.is_redis and hasattr(self.cache, 'get_cache_stats'):
            info['memory_stats'] = self.cache.get_cache_stats()
        
        return info

    def cleanup_expired_entries(self):
        if not self.is_redis and hasattr(self.cache, '_cleanup_expired'):
            self.cache._cleanup_expired()

    def force_save_cache(self):
        # No-op: cache persistence removed
        return

    def stop_cache_persistence(self):
        """No-op: cache persistence removed."""
        return

    @staticmethod
    def is_operational():
        try:
            test_key = "health_check_test"
            test_value = "test"
            doorman_cache.set_cache('api_cache', test_key, test_value)
            retrieved_value = doorman_cache.get_cache('api_cache', test_key)
            doorman_cache.delete_cache('api_cache', test_key)
            return retrieved_value == test_value
        except Exception:
            return False

# Initialize the cache manager
doorman_cache = DoormanCacheManager()
