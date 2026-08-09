"""
Lightweight in-memory log storage and handler.

Purpose: In environments where file logging is disabled (e.g., certain AWS
deployments), our logging UI should still be able to surface recent logs. This
module provides a shared ring buffer and a logging.Handler that records
structured log entries compatible with the existing log parser.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Deque, List, Optional


class _MemoryLogStore:
    def __init__(self, maxlen: int = 50000) -> None:
        self._buf: Deque[str] = deque(maxlen=maxlen)
        self._lock = threading.RLock()

    def add(self, entry: str) -> None:
        with self._lock:
            self._buf.append(entry)

    def snapshot(self) -> List[str]:
        with self._lock:
            # return a copy to avoid holding the lock while processing
            return list(self._buf)


_STORE = _MemoryLogStore()


def memory_log_snapshot() -> List[str]:
    return _STORE.snapshot()


class MemoryLogHandler(logging.Handler):
    """A handler that stores structured log records in an in-memory buffer.

    Emits compact JSON lines so the existing LoggingService parser can parse
    without depending on a file formatter.
    """

    def __init__(self, level: int = logging.INFO) -> None:
        super().__init__(level)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload = {
                # Align keys with JSONFormatter in doorman.py
                "time": datetime.fromtimestamp(record.created, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                "name": record.name,
                "level": record.levelname,
                "message": self.format(record) if self.formatter else record.getMessage(),
            }
            _STORE.add(json.dumps(payload, ensure_ascii=False))
        except Exception:
            # Never raise from logging
            pass

