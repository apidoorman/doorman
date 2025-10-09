"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import re
import html
from typing import Optional


def sanitize_html(text: str, allow_tags: bool = False) -> str:
    """
    Sanitize HTML input to prevent XSS attacks.

    This function removes or escapes HTML tags and dangerous patterns
    to prevent cross-site scripting vulnerabilities.

    Args:
        text: Input text that may contain HTML
        allow_tags: If False (default), all HTML tags are stripped.
                   If True, tags are HTML-encoded instead.

    Returns:
        Sanitized text safe for display

    Examples:
        >>> sanitize_html("<script>alert('xss')</script>")
        "alert('xss')"

        >>> sanitize_html("<b>Hello</b>", allow_tags=True)
        "&lt;b&gt;Hello&lt;/b&gt;"
    """
    if not text or not isinstance(text, str):
        return text

    # Strip or encode HTML tags
    if allow_tags:
        # HTML encode special characters
        return html.escape(text)
    else:
        # Remove all HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Also encode remaining special chars as defense in depth
        return html.escape(text)


def sanitize_input(text: str, max_length: Optional[int] = None) -> str:
    """
    Comprehensive input sanitization for user-provided text.

    Removes HTML tags, encodes special characters, and optionally
    enforces length limits.

    Args:
        text: User input to sanitize
        max_length: Optional maximum length to enforce

    Returns:
        Sanitized text

    Examples:
        >>> sanitize_input("<script>alert(1)</script>")
        "alert(1)"

        >>> sanitize_input("Hello & goodbye", max_length=10)
        "Hello &amp; go"
    """
    if not text or not isinstance(text, str):
        return text

    # Remove HTML tags
    sanitized = sanitize_html(text, allow_tags=False)

    # Remove null bytes (security risk)
    sanitized = sanitized.replace('\x00', '')

    # Normalize whitespace
    sanitized = ' '.join(sanitized.split())

    # Enforce max length if specified
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]

    return sanitized


def sanitize_url(url: str) -> str:
    """
    Sanitize URL to prevent javascript: and data: URL attacks.

    Args:
        url: URL to sanitize

    Returns:
        Sanitized URL or empty string if dangerous

    Examples:
        >>> sanitize_url("https://example.com")
        "https://example.com"

        >>> sanitize_url("javascript:alert(1)")
        ""
    """
    if not url or not isinstance(url, str):
        return ""

    url = url.strip()

    # Block dangerous URL schemes
    dangerous_schemes = [
        'javascript:',
        'data:',
        'vbscript:',
        'file:',
        'about:'
    ]

    url_lower = url.lower()
    for scheme in dangerous_schemes:
        if url_lower.startswith(scheme):
            return ""

    return url


def strip_control_characters(text: str) -> str:
    """
    Remove control characters that might cause issues.

    Args:
        text: Input text

    Returns:
        Text with control characters removed
    """
    if not text or not isinstance(text, str):
        return text

    # Remove control characters except newline, carriage return, tab
    return ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')


def sanitize_username(username: str) -> str:
    """
    Sanitize username to only allow safe characters.

    Args:
        username: Username to sanitize

    Returns:
        Sanitized username
    """
    if not username or not isinstance(username, str):
        return username

    # Allow only alphanumeric, underscore, dash, dot, @
    # Remove HTML first
    username = sanitize_html(username, allow_tags=False)

    # Keep only safe characters
    safe_pattern = re.compile(r'[^a-zA-Z0-9_\-\.@]')
    return safe_pattern.sub('', username)


def sanitize_api_name(name: str) -> str:
    """
    Sanitize API name to prevent injection attacks.

    Args:
        name: API name to sanitize

    Returns:
        Sanitized API name
    """
    if not name or not isinstance(name, str):
        return name

    # Remove HTML
    name = sanitize_html(name, allow_tags=False)

    # Allow only alphanumeric, underscore, dash
    safe_pattern = re.compile(r'[^a-zA-Z0-9_\-]')
    return safe_pattern.sub('', name)
