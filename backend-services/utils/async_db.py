"""
Async DB helpers that transparently handle Motor (async) and in-memory/PyMongo (sync).

These wrappers detect whether a collection method is coroutine-based and either await it
directly (Motor) or run the sync call in a thread (to avoid blocking the event loop).
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any


async def db_find_one(collection: Any, query: dict[str, Any]) -> dict[str, Any] | None:
    fn = collection.find_one
    if inspect.iscoroutinefunction(fn):
        return await fn(query)
    return await asyncio.to_thread(fn, query)


async def db_insert_one(collection: Any, doc: dict[str, Any]) -> Any:
    fn = collection.insert_one
    if inspect.iscoroutinefunction(fn):
        return await fn(doc)
    return await asyncio.to_thread(fn, doc)


async def db_update_one(collection: Any, query: dict[str, Any], update: dict[str, Any]) -> Any:
    fn = collection.update_one
    if inspect.iscoroutinefunction(fn):
        return await fn(query, update)
    return await asyncio.to_thread(fn, query, update)


async def db_delete_one(collection: Any, query: dict[str, Any]) -> Any:
    fn = collection.delete_one
    if inspect.iscoroutinefunction(fn):
        return await fn(query)
    return await asyncio.to_thread(fn, query)


async def db_find_list(collection: Any, query: dict[str, Any]) -> list[dict[str, Any]]:
    find = collection.find
    cursor = find(query)
    to_list = getattr(cursor, 'to_list', None)
    if callable(to_list):
        if inspect.iscoroutinefunction(to_list):
            return await to_list(length=None)
        return await asyncio.to_thread(to_list, None)
    return await asyncio.to_thread(lambda: list(cursor))
