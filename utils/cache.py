"""
The contents of this file are property of pygate.org
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/pygate for more information
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
        self.cache_config = {
            'default': {
                'cache': "aiocache.RedisCache",
                'endpoint': os.getenv("REDIS_HOST"),
                'port': int(os.getenv("REDIS_PORT")),
                'db': int(os.getenv("REDIS_DB")),
                'timeout': 300
            }
        }
        caches.set_config(self.cache_config)

    def init_app(self, app: FastAPI):
        """Initialize cache with FastAPI application"""
        app.state.cache = self
        return self
    
    def cached(self, ttl=300, key=None):
        """Wrapper around aiocache.cached with default configuration"""
        return cached(ttl=ttl, key=key, cache=Cache.REDIS)

cache_manager = CacheManager()