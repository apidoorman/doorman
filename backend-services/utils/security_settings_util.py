"""
Utilities to manage security-related settings and schedule auto-save of memory dumps.
"""

# External imports
import asyncio
import os
from typing import Optional, Dict, Any
import logging

# Internal imports
from .database import database, db
from .memory_dump_util import dump_memory_to_file

logger = logging.getLogger('doorman.gateway')

_CACHE: Dict[str, Any] = {}
_AUTO_TASK: Optional[asyncio.Task] = None
_STOP_EVENT: Optional[asyncio.Event] = None

DEFAULTS = {
    'type': 'security_settings',
    'enable_auto_save': False,
    'auto_save_frequency_seconds': 900,
    'dump_path': os.getenv('MEM_DUMP_PATH', 'generated/memory_dump.bin'),
    'ip_whitelist': [],
    'ip_blacklist': [],
    'trust_x_forwarded_for': False,
    # Optional: when set, only requests coming from these proxies (IPs/CIDRs)
    # will have their X-Forwarded-For / X-Real-IP / CF-Connecting-IP trusted.
    # Empty list preserves legacy behavior (trust all proxies when enabled).
    'xff_trusted_proxies': [],
    # Never lock out localhost (direct requests only; ignored if forwarded headers present)
    # Defaults from env LOCAL_HOST_IP_BYPASS (true/false), falling back to False.
    'allow_localhost_bypass': (os.getenv('LOCAL_HOST_IP_BYPASS', 'false').lower() == 'true'),
}

# Persist settings to a small JSON file so memory-only mode
# can restore across restarts (before any DB state exists).
SETTINGS_FILE = os.getenv('SECURITY_SETTINGS_FILE', 'generated/security_settings.json')

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

        _CACHE = DEFAULTS.copy()
    return _CACHE

def _load_from_file() -> Optional[Dict[str, Any]]:
    try:
        if not os.path.exists(SETTINGS_FILE):
            return None
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = f.read().strip()
            if not data:
                return None
            import json
            obj = json.loads(data)

            if isinstance(obj, dict):
                return obj
    except Exception as e:
        logger.error('Failed to read settings file %s: %s', SETTINGS_FILE, e)
    return None

def _save_to_file(settings: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE) or '.', exist_ok=True)
        import json
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            f.write(json.dumps(settings, separators=(',', ':')))
    except Exception as e:
        logger.error('Failed to write settings file %s: %s', SETTINGS_FILE, e)

async def load_settings() -> Dict[str, Any]:
    coll = _get_collection()
    doc = coll.find_one({'type': 'security_settings'})

    if not doc and database.memory_only:
        file_obj = _load_from_file()
        if file_obj:

            try:
                to_set = _merge_settings(file_obj)
                coll.update_one({'type': 'security_settings'}, {'$set': to_set})
                doc = to_set
            except Exception:

                doc = file_obj
    settings = _merge_settings(doc or {})
    _CACHE.update(settings)
    return settings

async def save_settings(partial: Dict[str, Any]) -> Dict[str, Any]:
    coll = _get_collection()
    current = _merge_settings(coll.find_one({'type': 'security_settings'}) or {})
    current.update({k: v for k, v in partial.items() if v is not None})
    result = coll.update_one({'type': 'security_settings'}, {'$set': current},)

    try:
        modified = getattr(result, 'modified_count', 0)
    except Exception:
        modified = 0
    if not modified and not coll.find_one({'type': 'security_settings'}):
        coll.insert_one(current)
    _CACHE.update(current)

    _save_to_file(_CACHE)
    await restart_auto_save_task()
    return current

async def _auto_save_loop(stop_event: asyncio.Event):
    while not stop_event.is_set():
        try:
            settings = get_cached_settings()

            freq = int(settings.get('auto_save_frequency_seconds', 0) or 0)
            if database.memory_only and freq > 0:
                try:
                    dump_memory_to_file(settings.get('dump_path'))
                    logger.info('Auto-saved memory dump to %s', settings.get('dump_path'))
                except Exception as e:
                    logger.error('Auto-save memory dump failed: %s', e)

            await asyncio.wait_for(stop_event.wait(), timeout=max(freq, 60) if freq > 0 else 60)
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.error('Auto-save loop error: %s', e)
            await asyncio.sleep(60)

async def start_auto_save_task():
    global _AUTO_TASK, _STOP_EVENT
    if _AUTO_TASK and not _AUTO_TASK.done():
        return
    _STOP_EVENT = asyncio.Event()
    _AUTO_TASK = asyncio.create_task(_auto_save_loop(_STOP_EVENT))
    logger.info('Security auto-save task started')

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
