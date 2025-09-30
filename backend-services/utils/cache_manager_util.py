"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

# External imports
from fastapi import FastAPI
from aiocache import Cache, caches
from aiocache.decorators import cached
from dotenv import load_dotenv
import os

load_dotenv()

class CacheManager:
    def __init__(self):

        redis_host = os.getenv('REDIS_HOST')
        redis_port = os.getenv('REDIS_PORT')
        redis_db = os.getenv('REDIS_DB')
        if redis_host and redis_port and redis_db:
            try:
                port = int(redis_port)
                db = int(redis_db)
                self.cache_backend = Cache.REDIS
                self.cache_config = {
                    'default': {
                        'cache': 'aiocache.RedisCache',
                        'endpoint': redis_host,
                        'port': port,
                        'db': db,
                        'timeout': 300
                    }
                }
            except Exception:

                self.cache_backend = Cache.MEMORY
                self.cache_config = {
                    'default': {
                        'cache': 'aiocache.SimpleMemoryCache',
                        'timeout': 300
                    }
                }
        else:
            self.cache_backend = Cache.MEMORY
            self.cache_config = {
                'default': {
                    'cache': 'aiocache.SimpleMemoryCache',
                    'timeout': 300
                }
            }
        caches.set_config(self.cache_config)

    def init_app(self, app: FastAPI):
        app.state.cache = self
        return self

    def cached(self, ttl=300, key=None):
        return cached(ttl=ttl, key=key, cache=self.cache_backend)

cache_manager = CacheManager()
