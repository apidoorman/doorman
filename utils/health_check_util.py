"""
The contents of this file are property of doorman.so
Review the Apache License 2.0 for valid authorization of use
See https://github.com/pypeople-dev/doorman for more information
"""

import psutil
import time
import logging
from datetime import timedelta
from utils.database import mongodb_client
from redis.asyncio import Redis
import os

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger("doorman.gateway")

START_TIME = time.time()

async def check_mongodb():
    try:
        mongodb_client.admin.command('ping')
        return True
    except Exception as e:
        logger.error(f"MongoDB health check failed: {str(e)}")
        return False

async def check_redis():
    try:
        redis = Redis.from_url(
            f'redis://{os.getenv("REDIS_HOST")}:{os.getenv("REDIS_PORT")}/{os.getenv("REDIS_DB")}',
            decode_responses=True
        )
        redis.ping()
        return True
    except Exception as e:
        logger.error(f"Redis health check failed: {str(e)}")
        return False

def get_memory_usage():
    try:
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        total_memory = psutil.virtual_memory().total
        memory_percent = (memory_info.rss / total_memory) * 100
        return f"{memory_percent:.1f}%"
    except Exception as e:
        logger.error(f"Memory usage check failed: {str(e)}")
        return "unknown"

def get_active_connections():
    try:
        process = psutil.Process(os.getpid())
        connections = process.connections()
        return len(connections)
    except Exception as e:
        logger.error(f"Active connections check failed: {str(e)}")
        return 0

def get_uptime():
    try:
        uptime_seconds = time.time() - START_TIME
        uptime = timedelta(seconds=int(uptime_seconds))
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m {seconds}s"
    except Exception as e:
        logger.error(f"Uptime check failed: {str(e)}")
        return "unknown" 