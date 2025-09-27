import logging
import json
import re

_logger = logging.getLogger("doorman.audit")

SENSITIVE_KEYS = {"password", "api_key", "user_api_key", "token", "authorization", "access_token", "refresh_token"}

def _sanitize(obj):
    try:
        if isinstance(obj, dict):
            clean = {}
            for k, v in obj.items():
                lk = str(k).lower()
                if lk in SENSITIVE_KEYS:
                    clean[k] = "[REDACTED]"
                else:
                    clean[k] = _sanitize(v)
            return clean
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        return obj
    except Exception:
        return None

def audit(request=None, actor=None, action=None, target=None, status=None, details=None, request_id=None):
    event = {
        "actor": actor,
        "action": action,
        "target": target,
        "status": status,
        "details": _sanitize(details) if details is not None else None,
    }
    try:
        if request is not None:
            event["ip"] = getattr(getattr(request, 'client', None), 'host', None)
            event["path"] = str(getattr(getattr(request, 'url', None), 'path', None))
        if request_id:
            event["request_id"] = request_id
        _logger.info(json.dumps(event, separators=(",", ":")))
    except Exception:
        # Best-effort only; never raise
        pass

