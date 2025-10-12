"""
Async DB helpers that transparently handle Motor (async) and in-memory/PyMongo (sync).

These wrappers detect whether a collection method is coroutine-based and either await it
directly (Motor) or run the sync call in a thread (to avoid blocking the event loop).
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Dict, List, Optional


async def db_find_one(collection: Any, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fn = getattr(collection, 'find_one')
    if inspect.iscoroutinefunction(fn):
        return await fn(query)
    return await asyncio.to_thread(fn, query)


async def db_insert_one(collection: Any, doc: Dict[str, Any]) -> Any:
    fn = getattr(collection, 'insert_one')
    if inspect.iscoroutinefunction(fn):
        return await fn(doc)
    return await asyncio.to_thread(fn, doc)


async def db_update_one(collection: Any, query: Dict[str, Any], update: Dict[str, Any]) -> Any:
    fn = getattr(collection, 'update_one')
    if inspect.iscoroutinefunction(fn):
        return await fn(query, update)
    return await asyncio.to_thread(fn, query, update)


async def db_delete_one(collection: Any, query: Dict[str, Any]) -> Any:
    fn = getattr(collection, 'delete_one')
    if inspect.iscoroutinefunction(fn):
        return await fn(query)
    return await asyncio.to_thread(fn, query)


async def db_find_list(collection: Any, query: Dict[str, Any]) -> List[Dict[str, Any]]:
    find = getattr(collection, 'find')
    cursor = find(query)
    to_list = getattr(cursor, 'to_list', None)
    if callable(to_list):
        # Motor async cursor has to_list as coroutine
        if inspect.iscoroutinefunction(to_list):
            return await to_list(length=None)
        # In-memory cursor has to_list as sync method
        return await asyncio.to_thread(to_list, None)
    # PyMongo or in-memory iterator
    return await asyncio.to_thread(lambda: list(cursor))

