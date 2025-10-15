import logging
import json
import re

_logger = logging.getLogger('doorman.audit')

SENSITIVE_KEYS = {
    'password', 'passwd', 'pwd',
    'token', 'access_token', 'refresh_token', 'bearer_token', 'auth_token',
    'authorization', 'auth', 'bearer',

    'api_key', 'apikey', 'api-key',
    'user_api_key', 'user-api-key',
    'secret', 'client_secret', 'client-secret', 'api_secret', 'api-secret',
    'private_key', 'private-key', 'privatekey',

    'session', 'session_id', 'session-id', 'sessionid',
    'csrf_token', 'csrf-token', 'csrftoken',
    'x-csrf-token', 'xsrf_token', 'xsrf-token',

    'cookie', 'set-cookie', 'set_cookie',
    'access_token_cookie', 'refresh_token_cookie',

    'connection_string', 'connection-string', 'connectionstring',
    'database_password', 'db_password', 'db_passwd',
    'mongo_password', 'redis_password',

    'id_token', 'id-token',
    'jwt', 'jwt_token',
    'oauth_token', 'oauth-token',
    'code_verifier', 'code-verifier',

    'encryption_key', 'encryption-key',
    'signing_key', 'signing-key',
    'key', 'private', 'secret_key',
}

SENSITIVE_VALUE_PATTERNS = [
    re.compile(r'^eyJ[a-zA-Z0-9_\-]+\.eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+$'),
    re.compile(r'^Bearer\s+', re.IGNORECASE),
    re.compile(r'^Basic\s+[a-zA-Z0-9+/=]+$', re.IGNORECASE),
    re.compile(r'^sk-[a-zA-Z0-9]{32,}$'),
    re.compile(r'^[a-fA-F0-9]{32,}$'),
    re.compile(r'^-----BEGIN[A-Z\s]+PRIVATE KEY-----', re.DOTALL),
]

def _is_sensitive_key(key: str) -> bool:
    """Check if a key name indicates sensitive data."""
    try:
        lk = str(key).lower().replace('-', '_')
        return lk in SENSITIVE_KEYS or any(s in lk for s in ['password', 'secret', 'token', 'key', 'auth'])
    except Exception:
        return False

def _is_sensitive_value(value) -> bool:
    """Check if a value looks like sensitive data (even if key isn't obviously sensitive)."""
    try:
        if not isinstance(value, str):
            return False
        return any(pat.match(value) for pat in SENSITIVE_VALUE_PATTERNS)
    except Exception:
        return False

def _sanitize(obj):
    """Recursively sanitize objects to redact sensitive data.

    Redacts:
    - Keys matching SENSITIVE_KEYS (case-insensitive)
    - Keys containing sensitive terms (password, secret, token, key, auth)
    - Values matching sensitive patterns (JWT, Bearer tokens, etc.)
    """
    try:
        if isinstance(obj, dict):
            clean = {}
            for k, v in obj.items():
                if _is_sensitive_key(k):
                    clean[k] = '[REDACTED]'
                elif isinstance(v, str) and _is_sensitive_value(v):
                    clean[k] = '[REDACTED]'
                else:
                    clean[k] = _sanitize(v)
            return clean
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        if isinstance(obj, str) and _is_sensitive_value(obj):
            return '[REDACTED]'
        return obj
    except Exception:
        return None

def audit(request=None, actor=None, action=None, target=None, status=None, details=None, request_id=None):
    event = {
        'actor': actor,
        'action': action,
        'target': target,
        'status': status,
        'details': _sanitize(details) if details is not None else None,
    }
    try:
        if request is not None:
            event['ip'] = getattr(getattr(request, 'client', None), 'host', None)
            event['path'] = str(getattr(getattr(request, 'url', None), 'path', None))
        if request_id:
            event['request_id'] = request_id
        _logger.info(json.dumps(event, separators=(',', ':')))
    except Exception:

        pass

