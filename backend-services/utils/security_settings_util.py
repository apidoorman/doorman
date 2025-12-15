"""
Utilities to manage security-related settings and schedule auto-save of memory dumps.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from .database import database, db
from .memory_dump_util import dump_memory_to_file

logger = logging.getLogger('doorman.gateway')

_CACHE: dict[str, Any] = {}
_AUTO_TASK: asyncio.Task | None = None
_STOP_EVENT: asyncio.Event | None = None

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_GEN_DIR = _PROJECT_ROOT / 'generated'

def _env_bool(name: str, default: bool) -> bool:
    try:
        raw = os.getenv(name)
        if raw is None:
            return default
        return str(raw).strip().lower() in ('1', 'true', 'yes', 'on')
    except Exception:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        raw = os.getenv(name)
        if raw is None:
            return default
        v = int(str(raw).strip())
        return v if v > 0 else default
    except Exception:
        return default


DEFAULTS = {
    'type': 'security_settings',
    # Allow env overrides so deployments can enable autosave without API calls
    'enable_auto_save': _env_bool('MEM_AUTO_SAVE_ENABLED', False),
    'auto_save_frequency_seconds': _env_int('MEM_AUTO_SAVE_FREQ', 900),
    'dump_path': os.getenv('MEM_DUMP_PATH', str(_GEN_DIR / 'memory_dump.bin')),
    'ip_whitelist': [],
    'ip_blacklist': [],
    'trust_x_forwarded_for': False,
    'xff_trusted_proxies': [],
    'allow_localhost_bypass': (os.getenv('LOCAL_HOST_IP_BYPASS', 'false').lower() == 'true'),
}

SETTINGS_FILE = os.getenv('SECURITY_SETTINGS_FILE', str(_GEN_DIR / 'security_settings.json'))


def _get_collection():
    return db.settings if not database.memory_only else database.db.settings


def _merge_settings(doc: dict[str, Any]) -> dict[str, Any]:
    merged = DEFAULTS.copy()
    if doc:
        merged.update({k: v for k, v in doc.items() if v is not None})
    return merged


def get_cached_settings() -> dict[str, Any]:
    global _CACHE
    if not _CACHE:
        _CACHE = DEFAULTS.copy()
    return _CACHE


def _load_from_file() -> dict[str, Any] | None:
    try:
        if not os.path.exists(SETTINGS_FILE):
            return None
        with open(SETTINGS_FILE, encoding='utf-8') as f:
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


def _save_to_file(settings: dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE) or '.', exist_ok=True)
        import json

        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            f.write(json.dumps(settings, separators=(',', ':')))
    except Exception as e:
        logger.error('Failed to write settings file %s: %s', SETTINGS_FILE, e)


async def load_settings() -> dict[str, Any]:
    coll = _get_collection()
    doc = coll.find_one({'type': 'security_settings'})

    if not doc and database.memory_only:
        file_obj = _load_from_file()
        if file_obj:
            try:
                to_set = _merge_settings(file_obj)
                coll.update_one({'type': 'security_settings'}, {'$set': to_set}, upsert=True)
                doc = to_set
            except Exception:
                doc = file_obj
    
    # If still no doc, initialize with defaults (including env vars)
    if not doc:
        settings = _merge_settings({})
        try:
            coll.insert_one(settings)
            logger.info('Initialized security settings from environment variables and defaults')
        except Exception as e:
            logger.warning(f'Failed to persist initial security settings: {e}')
        _CACHE.update(settings)
        _save_to_file(settings)
        return settings
    
    settings = _merge_settings(doc)
    _CACHE.update(settings)
    return settings


async def save_settings(partial: dict[str, Any]) -> dict[str, Any]:
    coll = _get_collection()
    current = _merge_settings(coll.find_one({'type': 'security_settings'}) or {})
    current.update({k: v for k, v in partial.items() if v is not None})
    result = coll.update_one({'type': 'security_settings'}, {'$set': current})

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
        except TimeoutError:
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
