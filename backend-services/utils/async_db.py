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


async def db_aggregate_list(collection: Any, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run an aggregation pipeline and return a list of docs.

    Works with both Motor (async) and PyMongo (sync) drivers.
    """
    agg = collection.aggregate(pipeline)
    to_list = getattr(agg, 'to_list', None)
    if callable(to_list):
        # Motor aggregation cursor
        if inspect.iscoroutinefunction(to_list):
            return await to_list(length=None)
        return await asyncio.to_thread(to_list, None)
    # Sync aggregate cursor
    return await asyncio.to_thread(lambda: list(agg))


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
    to_list = getattr(cursor, 'to_list', None)
    if callable(to_list):
        # Motor cursor
        if inspect.iscoroutinefunction(to_list):
            return await to_list(length=limit)
        return await asyncio.to_thread(to_list, limit)
    # Sync cursor
    return await asyncio.to_thread(lambda: list(cursor))


async def db_count(collection: Any, query: dict[str, Any]) -> int:
    """Count documents matching query using Motor/PyMongo.
    Falls back to running in a thread for sync drivers.
    """
    fn = getattr(collection, 'count_documents', None)
    if fn is None:
        # Last resort: iterate (should not happen on Mongo)
        docs = await db_find_list(collection, query)
        return len(docs)
    if inspect.iscoroutinefunction(fn):
        return await fn(query)
    return await asyncio.to_thread(fn, query)
