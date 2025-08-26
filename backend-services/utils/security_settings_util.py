"""
Utilities to manage security-related settings and schedule auto-save of memory dumps.
"""

import asyncio
import os
from typing import Optional, Dict, Any
import logging

from .database import database, db
from .memory_dump_util import dump_memory_to_file

logger = logging.getLogger("doorman.gateway")

_CACHE: Dict[str, Any] = {}
_AUTO_TASK: Optional[asyncio.Task] = None
_STOP_EVENT: Optional[asyncio.Event] = None

DEFAULTS = {
    "type": "security_settings",
    "enable_auto_save": False,
    "auto_save_frequency_seconds": 900,  # 15 minutes
    "dump_path": os.getenv("MEM_DUMP_PATH", "generated/memory_dump.bin"),
}


def _get_collection():
    return db.settings if not database.memory_only else database.db.settings


def _merge_settings(doc: Dict[str, Any]) -> Dict[str, Any]:
    merged = DEFAULTS.copy()
    if doc:
        merged.update({k: v for k, v in doc.items() if v is not None})
    return merged


def get_cached_settings() -> Dict[str, Any]:
    global _CACHE
    if not _CACHE:
        # initialize with defaults until load is called
        _CACHE = DEFAULTS.copy()
    return _CACHE


async def load_settings() -> Dict[str, Any]:
    coll = _get_collection()
    doc = coll.find_one({"type": "security_settings"})
    settings = _merge_settings(doc or {})
    _CACHE.update(settings)
    return settings


async def save_settings(partial: Dict[str, Any]) -> Dict[str, Any]:
    coll = _get_collection()
    current = _merge_settings(coll.find_one({"type": "security_settings"}) or {})
    current.update({k: v for k, v in partial.items() if v is not None})
    result = coll.update_one({"type": "security_settings"}, {"$set": current},)
    # If nothing was updated (e.g., first time in memory mode), insert
    try:
        modified = getattr(result, 'modified_count', 0)
    except Exception:
        modified = 0
    if not modified and not coll.find_one({"type": "security_settings"}):
        coll.insert_one(current)
    _CACHE.update(current)
    await restart_auto_save_task()
    return current


async def _auto_save_loop(stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            settings = get_cached_settings()
            # Auto-save is ALWAYS enabled in memory-only mode; only frequency is configurable
            freq = int(settings.get("auto_save_frequency_seconds", 0) or 0)
            if database.memory_only and freq > 0:
                try:
                    dump_memory_to_file(settings.get("dump_path"))
                    logger.info("Auto-saved memory dump to %s", settings.get("dump_path"))
                except Exception as e:
                    logger.error("Auto-save memory dump failed: %s", e)
            # Sleep for at least 60s if misconfigured
            await asyncio.wait_for(stop_event.wait(), timeout=max(freq, 60) if freq > 0 else 60)
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.error("Auto-save loop error: %s", e)
            await asyncio.sleep(60)


async def start_auto_save_task():
    global _AUTO_TASK, _STOP_EVENT
    if _AUTO_TASK and not _AUTO_TASK.done():
        return
    _STOP_EVENT = asyncio.Event()
    _AUTO_TASK = asyncio.create_task(_auto_save_loop(_STOP_EVENT))
    logger.info("Security auto-save task started")


async def stop_auto_save_task():
    global _AUTO_TASK, _STOP_EVENT
    if _STOP_EVENT:
        _STOP_EVENT.set()
    if _AUTO_TASK:
        try:
            await asyncio.wait_for(_AUTO_TASK, timeout=5)
        except Exception:
            pass
    _AUTO_TASK = None
    _STOP_EVENT = None


async def restart_auto_save_task():
    await stop_auto_save_task()
    await start_auto_save_task()
