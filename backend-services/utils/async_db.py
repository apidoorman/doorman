"""
Async DB helpers that transparently handle Motor (async) and in-memory/PyMongo (sync).

These wrappers detect whether a collection method is coroutine-based and either await it
directly (Motor) or run the sync call in a thread (to avoid blocking the event loop).
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any


async def _call_collection_method(fn: Any, *args: Any) -> Any:
    """Call a Motor or synchronous collection method without blocking.

    Motor collection methods are regular functions that return Futures, so
    ``iscoroutinefunction`` alone cannot distinguish them from PyMongo calls.
    """
    if inspect.iscoroutinefunction(fn):
        return await fn(*args)

    owner = getattr(fn, '__self__', None)
    owner_module = type(owner).__module__ if owner is not None else ''
    if owner_module.startswith('motor.'):
        result = fn(*args)
        if inspect.isawaitable(result):
            return await result
        return result

    return await asyncio.to_thread(fn, *args)


async def _cursor_to_list(cursor: Any, length: int | None) -> list[dict[str, Any]]:
    # Motor exposes a regular method that returns an awaitable; in-memory
    # facades may return a list directly.
    to_list = getattr(cursor, 'to_list', None)
    if not callable(to_list):
        return await asyncio.to_thread(lambda: list(cursor))
    try:
        result = to_list(length=length)
    except TypeError:
        result = to_list(length)
    if inspect.isawaitable(result):
        result = await result
    return list(result)


async def db_find_one(collection: Any, query: dict[str, Any]) -> dict[str, Any] | None:
    return await _call_collection_method(collection.find_one, query)


async def db_insert_one(collection: Any, doc: dict[str, Any]) -> Any:
    return await _call_collection_method(collection.insert_one, doc)


async def db_update_one(collection: Any, query: dict[str, Any], update: dict[str, Any]) -> Any:
    return await _call_collection_method(collection.update_one, query, update)


async def db_delete_one(collection: Any, query: dict[str, Any]) -> Any:
    return await _call_collection_method(collection.delete_one, query)


async def db_find_list(
    collection: Any, query: dict[str, Any], sort: list[tuple[str, int]] | None = None
) -> list[dict[str, Any]]:
    find = collection.find
    cursor = find(query)
    if sort:
        # Some drivers use .sort([(field, dir)]), others .sort(field, dir)
        try:
            cursor = cursor.sort(sort)
        except Exception:
            for fld, direction in sort:
                cursor = cursor.sort(fld, direction)

    return await _cursor_to_list(cursor, None)


async def db_aggregate_list(collection: Any, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run an aggregation pipeline and return a list of docs.

    Works with both Motor (async) and PyMongo (sync) drivers.
    """
    agg = collection.aggregate(pipeline)
    return await _cursor_to_list(agg, None)


async def db_find_paginated(
    collection: Any,
    query: dict[str, Any],
    *,
    skip: int = 0,
    limit: int = 10,
    sort: list[tuple[str, int]] | tuple[str, int] | None = None,
) -> list[dict[str, Any]]:
    """Find with optional sort/skip/limit using async Motor or sync PyMongo.

    - sort: list of (field, direction) where direction is 1 (asc) or -1 (desc)
    """
    def _build_cursor():
        c = collection.find(query)
        if sort:
            # Motor/PyMongo accept list/tuple sorts directly; our in-memory
            # cursor expects .sort(field, direction). Support both.
            try:
                if isinstance(sort, (list, tuple)) and sort and isinstance(sort[0], (list, tuple)):
                    # Likely a list of (field, direction)
                    for fld, direction in sort:
                        c = c.sort(fld, direction)
                else:
                    c = c.sort(sort)  # type: ignore[arg-type]
            except TypeError:
                # Fallback: iterate pairs
                if isinstance(sort, (list, tuple)):
                    for item in sort:
                        if isinstance(item, (list, tuple)) and len(item) == 2:
                            c = c.sort(item[0], item[1])
        if skip:
            c = c.skip(int(skip))
        if limit is not None:
            c = c.limit(int(limit))
        return c

    cursor = _build_cursor()
    return await _cursor_to_list(cursor, limit)


async def db_count(collection: Any, query: dict[str, Any]) -> int:
    """Count documents matching query using Motor/PyMongo.
    Falls back to running in a thread for sync drivers.
    """
    fn = getattr(collection, 'count_documents', None)
    if fn is None:
        # Last resort: iterate (should not happen on Mongo)
        docs = await db_find_list(collection, query)
        return len(docs)
    return await _call_collection_method(fn, query)


async def db_delete_many(collection: Any, query: dict[str, Any]) -> Any:
    return await _call_collection_method(collection.delete_many, query)


async def db_insert_many(collection: Any, docs: list[dict[str, Any]]) -> Any:
    return await _call_collection_method(collection.insert_many, docs)
