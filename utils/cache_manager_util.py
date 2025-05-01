"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

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
        app.state.cache = self
        return self
    
    def cached(self, ttl=300, key=None):
        return cached(ttl=ttl, key=key, cache=Cache.REDIS)

cache_manager = CacheManager()