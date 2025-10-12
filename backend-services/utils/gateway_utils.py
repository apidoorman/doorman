# External imports
import re
from typing import Dict, List
from fastapi import Request
import logging

_logger = logging.getLogger('doorman.gateway')

# Sensitive headers that should NEVER be logged (even if sanitized)
SENSITIVE_HEADERS = {
    'authorization',
    'proxy-authorization',
    'www-authenticate',
    'x-api-key',
    'api-key',
    'cookie',
    'set-cookie',
    'x-csrf-token',
    'csrf-token',
}

def sanitize_headers(value: str):
    """Sanitize header values to prevent injection attacks.

    Removes:
    - Newline characters (CRLF injection)
    - HTML tags (XSS prevention)
    - Null bytes
    """
    try:
        # Remove control characters and newlines
        value = value.replace('\n', '').replace('\r', '').replace('\0', '')

        # Remove HTML tags
        value = re.sub(r'<[^>]+>', '', value)

        # Truncate extremely long values (potential DoS)
        if len(value) > 8192:
            value = value[:8192] + '...[TRUNCATED]'

        return value
    except Exception:
        return ''

def redact_sensitive_header(header_name: str, header_value: str) -> str:
    """Redact sensitive header values for logging purposes.

    Args:
        header_name: Header name (case-insensitive)
        header_value: Header value to potentially redact

    Returns:
        Redacted value if sensitive, original value otherwise
    """
    try:
        header_lower = header_name.lower().replace('-', '_')

        # Check if header is in sensitive list
        if header_lower in SENSITIVE_HEADERS:
            return '[REDACTED]'

        # Redact bearer tokens
        if 'bearer' in header_value.lower()[:10]:
            return 'Bearer [REDACTED]'

        # Redact basic auth
        if header_value.startswith('Basic '):
            return 'Basic [REDACTED]'

        # Redact JWT tokens (eyJ... pattern)
        if re.match(r'^eyJ[a-zA-Z0-9_\-]+\.', header_value):
            return '[REDACTED_JWT]'

        # Redact API keys (common patterns)
        if re.match(r'^[a-zA-Z0-9_\-]{32,}$', header_value):
            return '[REDACTED_API_KEY]'

        return header_value
    except Exception:
        return '[REDACTION_ERROR]'

def log_headers_safely(request: Request, allowed_headers: List[str] = None, redact: bool = True):
    """Log request headers safely with redaction.

    Args:
        request: FastAPI Request object
        allowed_headers: List of headers to log (None = log all non-sensitive)
        redact: If True, redact sensitive values; if False, skip sensitive headers entirely

    Example:
        log_headers_safely(request, allowed_headers=['content-type', 'user-agent'])
    """
    try:
        headers_to_log = {}
        allowed_lower = {h.lower() for h in (allowed_headers or [])} if allowed_headers else None

        for key, value in request.headers.items():
            key_lower = key.lower()

            # Skip if not in allowed list (when specified)
            if allowed_lower and key_lower not in allowed_lower:
                continue

            # Skip sensitive headers entirely if not redacting
            if not redact and key_lower in SENSITIVE_HEADERS:
                continue

            # Sanitize and optionally redact
            sanitized = sanitize_headers(value)
            if redact:
                sanitized = redact_sensitive_header(key, sanitized)

            headers_to_log[key] = sanitized

        if headers_to_log:
            _logger.debug(f"Request headers: {headers_to_log}")

    except Exception as e:
        _logger.debug(f"Failed to log headers safely: {e}")

async def get_headers(request: Request, allowed_headers: List[str]):
    """Extract and sanitize allowed headers from request.

    This function is used for forwarding headers to upstream services.
    Sensitive headers are never forwarded (even if in allowed list).

    Args:
        request: FastAPI Request object
        allowed_headers: List of headers allowed to be forwarded

    Returns:
        Dict of sanitized headers safe to forward
    """
    safe_headers = {}
    allowed_lower = {h.lower() for h in (allowed_headers or [])}

    for key, value in request.headers.items():
        key_lower = key.lower()

        # Skip sensitive headers (never forward, even if "allowed")
        if key_lower in SENSITIVE_HEADERS:
            continue

        # Only include if in allowed list
        if key_lower in allowed_lower:
            safe_headers[key] = sanitize_headers(value)

    return safe_headers
