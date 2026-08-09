"""
Test endpoints to demonstrate and verify async database/cache operations.

The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
"""

import asyncio
import time
from typing import Any

from fastapi import APIRouter, HTTPException

from utils.database import api_collection as sync_api_collection
from utils.database import user_collection as sync_user_collection
from utils.database_async import api_collection as async_api_collection
from utils.database_async import async_database
from utils.database_async import user_collection as async_user_collection
from utils.doorman_cache_async import async_doorman_cache
from utils.doorman_cache_util import doorman_cache

router = APIRouter(prefix='/test/async', tags=['Async Testing'])


@router.get('/health')
async def async_health_check() -> dict[str, Any]:
    """Test async database and cache health."""
    try:
        if async_database.is_memory_only():
            db_status = 'memory_only'
        else:
            await async_user_collection.find_one({'username': 'admin'})
            db_status = 'connected'

        cache_operational = await async_doorman_cache.is_operational()
        cache_info = await async_doorman_cache.get_cache_info()

        return {
            'status': 'healthy',
            'database': {'status': db_status, 'mode': async_database.get_mode_info()},
            'cache': {'operational': cache_operational, 'info': cache_info},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Health check failed: {str(e)}')


@router.get('/performance/sync')
async def test_sync_performance() -> dict[str, Any]:
    """Test SYNC (blocking) database operations - SLOW under load."""
    start_time = time.time()

    try:
        user = sync_user_collection.find_one({'username': 'admin'})
        apis = list(sync_api_collection.find({}).limit(10))

        cached_user = doorman_cache.get_cache('user_cache', 'admin')
        if not cached_user:
            doorman_cache.set_cache('user_cache', 'admin', user)

        elapsed = time.time() - start_time

        return {
            'method': 'sync (blocking)',
            'elapsed_ms': round(elapsed * 1000, 2),
            'user_found': user is not None,
            'apis_count': len(apis),
            'warning': 'This endpoint blocks the event loop and causes poor performance under load',
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Sync test failed: {str(e)}')


@router.get('/performance/async')
async def test_async_performance() -> dict[str, Any]:
    """Test ASYNC (non-blocking) database operations - FAST under load."""
    start_time = time.time()

    try:
        user = await async_user_collection.find_one({'username': 'admin'})

        if async_database.is_memory_only():
            apis = async_api_collection.find({}).limit(10)
            apis = list(apis)
        else:
            apis = await async_api_collection.find({}).limit(10).to_list(length=10)

        cached_user = await async_doorman_cache.get_cache('user_cache', 'admin')
        if not cached_user:
            await async_doorman_cache.set_cache('user_cache', 'admin', user)

        elapsed = time.time() - start_time

        return {
            'method': 'async (non-blocking)',
            'elapsed_ms': round(elapsed * 1000, 2),
            'user_found': user is not None,
            'apis_count': len(apis),
            'note': 'This endpoint does NOT block the event loop and performs well under load',
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Async test failed: {str(e)}')


@router.get('/performance/parallel')
async def test_parallel_performance() -> dict[str, Any]:
    """Test PARALLEL async operations - Maximum performance."""
    start_time = time.time()

    try:
        user_task = async_user_collection.find_one({'username': 'admin'})

        if async_database.is_memory_only():
            apis_task = asyncio.to_thread(lambda: list(async_api_collection.find({}).limit(10)))
        else:
            apis_task = async_api_collection.find({}).limit(10).to_list(length=10)

        cache_task = async_doorman_cache.get_cache('user_cache', 'admin')

        user, apis, cached_user = await asyncio.gather(user_task, apis_task, cache_task)

        if not cached_user and user:
            await async_doorman_cache.set_cache('user_cache', 'admin', user)

        elapsed = time.time() - start_time

        return {
            'method': 'async parallel (non-blocking + concurrent)',
            'elapsed_ms': round(elapsed * 1000, 2),
            'user_found': user is not None,
            'apis_count': len(apis) if apis else 0,
            'note': 'Operations executed in parallel for maximum performance',
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Parallel test failed: {str(e)}')


@router.get('/cache/test')
async def test_cache_operations() -> dict[str, Any]:
    """Test async cache operations."""
    try:
        test_key = 'test_user_123'
        test_value = {'username': 'test_user_123', 'email': 'test@example.com', 'role': 'user'}

        await async_doorman_cache.set_cache('user_cache', test_key, test_value)

        retrieved = await async_doorman_cache.get_cache('user_cache', test_key)

        await async_doorman_cache.delete_cache('user_cache', test_key)

        after_delete = await async_doorman_cache.get_cache('user_cache', test_key)

        return {
            'set': 'success',
            'get': 'success' if retrieved == test_value else 'failed',
            'delete': 'success' if after_delete is None else 'failed',
            'cache_info': await async_doorman_cache.get_cache_info(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Cache test failed: {str(e)}')


@router.get('/load-test-compare')
async def load_test_comparison() -> dict[str, Any]:
    """
    Compare sync vs async performance under simulated load.

    This endpoint simulates 10 concurrent database queries.
    """
    try:
        sync_start = time.time()
        sync_results = []
        for _i in range(10):
            user = sync_user_collection.find_one({'username': 'admin'})
            sync_results.append(user is not None)
        sync_elapsed = time.time() - sync_start

        async_start = time.time()
        async_tasks = [async_user_collection.find_one({'username': 'admin'}) for i in range(10)]
        await asyncio.gather(*async_tasks)
        async_elapsed = time.time() - async_start

        speedup = sync_elapsed / async_elapsed if async_elapsed > 0 else 0

        return {
            'test': '10 concurrent user lookups',
            'sync': {
                'elapsed_ms': round(sync_elapsed * 1000, 2),
                'queries_per_second': round(10 / sync_elapsed, 2),
            },
            'async': {
                'elapsed_ms': round(async_elapsed * 1000, 2),
                'queries_per_second': round(10 / async_elapsed, 2),
            },
            'speedup': f'{round(speedup, 2)}x faster',
            'note': 'Async shows significant improvement with concurrent operations',
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Load test failed: {str(e)}')
