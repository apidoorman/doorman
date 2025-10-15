"""
Ensure the 'doorman.gateway' and 'doorman.logging' loggers have a redaction filter
attached, even when the application module isn't imported (e.g., unit tests that
only import logging). Python automatically imports sitecustomize at interpreter
startup when it's present on sys.path.
"""

import logging
import re
import sys

class _RedactFilter(logging.Filter):
    PATTERNS = [
        re.compile(r'(?i)(authorization\s*[:=]\s*)([^;\r\n]+)'),
        re.compile(r'(?i)(access[_-]?token\s*[\"\']?\s*[:=]\s*[\"\'])([^\"\']+)([\"\'])'),
        re.compile(r'(?i)(refresh[_-]?token\s*[\"\']?\s*[:=]\s*[\"\'])([^\"\']+)([\"\'])'),
        re.compile(r'(?i)(password\s*[\"\']?\s*[:=]\s*[\"\'])([^\"\']+)([\"\'])'),
        re.compile(r'(?i)(cookie\s*[:=]\s*)([^;\r\n]+)'),
        re.compile(r'(?i)(x-csrf-token\s*[:=]\s*)([^\s,;]+)'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = str(record.getMessage())
            red = msg
            for pat in self.PATTERNS:
                red = pat.sub(lambda m: (m.group(1) + '[REDACTED]' + (m.group(3) if m.lastindex and m.lastindex >= 3 else '')), red)
            if red != msg:
                record.msg = red
        except Exception:
            pass
        return True

def _ensure_logger(name: str):
    logger = logging.getLogger(name)
    for h in logger.handlers:
        if h.filters:
            return
    h = logging.StreamHandler(stream=sys.stdout)
    h.setLevel(logging.INFO)
    h.addFilter(_RedactFilter())
    logger.addHandler(h)

try:
    _ensure_logger('doorman.gateway')
    _ensure_logger('doorman.logging')
except Exception:
    pass

