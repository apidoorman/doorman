"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

import redis
import json
import os
import threading
from typing import Dict, Any, Optional
import pickle
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

class MemoryCache:
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._dump_file = os.getenv("CACHE_DUMP_FILE", "cache_dump.enc")
        self._encryption_key = self._get_encryption_key()
        self._auto_save_thread = None
        self._stop_auto_save = threading.Event()
        self._dump_interval = int(os.getenv("CACHE_DUMP_INTERVAL", "300"))
        self._min_dump_interval = int(os.getenv("CACHE_MIN_DUMP_INTERVAL", "60"))
        self._last_dump_time = 0
        self._cache_modified = False
        self._last_cache_size = 0
        self._load_cache()
        self._start_auto_save()
    
    def setex(self, key: str, ttl: int, value: str):
        with self._lock:
            self._cache[key] = {
                'value': value,
                'expires_at': self._get_current_time() + ttl
            }
            self._cache_modified = True
    
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
                    self._cache_modified = True
    
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
                'expired_entries': expired_entries,
                'dump_file': self._dump_file,
                'auto_save_active': not self._stop_auto_save.is_set()
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

    def _get_encryption_key(self) -> bytes:
        env_key = os.getenv("MEM_ENCRYPTION_KEY")
        if not env_key:
            raise ValueError("MEM_ENCRYPTION_KEY environment variable is required for memory cache")
        salt = b'pygate_cache_salt'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(env_key.encode()))
        return key
    
    def _encrypt_data(self, data: bytes) -> bytes:
        f = Fernet(self._encryption_key)
        return f.encrypt(data)
    
    def _decrypt_data(self, encrypted_data: bytes) -> bytes:
        f = Fernet(self._encryption_key)
        return f.decrypt(encrypted_data)
    
    def _save_cache(self):
        try:
            with self._lock:
                cache_data = {}
                current_time = self._get_current_time()
                for key, entry in self._cache.items():
                    if current_time < entry['expires_at']:
                        cache_data[key] = entry
                serialized_data = pickle.dumps(cache_data)
                encrypted_data = self._encrypt_data(serialized_data)
                temp_file = f"{self._dump_file}.tmp"
                dump_dir = os.path.dirname(self._dump_file)
                if dump_dir:
                    os.makedirs(dump_dir, exist_ok=True)
                with open(temp_file, 'wb') as f:
                    f.write(encrypted_data)
                os.replace(temp_file, self._dump_file)
        except Exception as e:
            print(f"Warning: Failed to save cache to {self._dump_file}: {e}")
    
    def _load_cache(self):
        try:
            if os.path.exists(self._dump_file):
                with open(self._dump_file, 'rb') as f:
                    encrypted_data = f.read()
                decrypted_data = self._decrypt_data(encrypted_data)
                loaded_cache = pickle.loads(decrypted_data)
                current_time = self._get_current_time()
                with self._lock:
                    for key, entry in loaded_cache.items():
                        if current_time < entry['expires_at']:
                            self._cache[key] = entry
                print(f"Loaded {len(self._cache)} cache entries from {self._dump_file}")
        except Exception as e:
            print(f"Warning: Failed to load cache from {self._dump_file}: {e}")

    def _start_auto_save(self):
        def auto_save_worker():
            while not self._stop_auto_save.wait(self._min_dump_interval):
                current_time = self._get_current_time()
                if (self._cache_modified and 
                    current_time - self._last_dump_time >= self._dump_interval and
                    abs(len(self._cache) - self._last_cache_size) > 0):
                    self._save_cache()
                    self._last_dump_time = current_time
                    self._cache_modified = False
                    self._last_cache_size = len(self._cache)
        self._auto_save_thread = threading.Thread(target=auto_save_worker, daemon=True)
        self._auto_save_thread.start()

    def stop_auto_save(self):
        """Stop the auto-save thread and perform final save."""
        self._stop_auto_save.set()
        if self._auto_save_thread:
            self._auto_save_thread.join(timeout=5)
        self._save_cache()

class DoormanCacheManager:
    def __init__(self):
        self.cache_type = os.getenv("MEM_OR_EXTERNAL", "MEM").upper()
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
            'token_def_cache': 'token_def_cache:'
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
        if not self.is_redis and hasattr(self.cache, '_save_cache'):
            self.cache._save_cache()

    def stop_cache_persistence(self):
        """Stop the auto-save thread (memory cache only)."""
        if not self.is_redis and hasattr(self.cache, 'stop_auto_save'):
            self.cache.stop_auto_save()

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
