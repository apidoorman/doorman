"""
The contents of this file are property of Doorman Dev, LLC
Review the Apache License 2.0 for valid authorization of use
See https://github.com/apidoorman/doorman for more information
"""

import html
import re


def sanitize_html(text: str, allow_tags: bool = False) -> str:
    """
    Sanitize HTML input to prevent XSS attacks.
    """
    if not text or not isinstance(text, str):
        return text
    if allow_tags:
        return html.escape(text)
    else:
        text = re.sub(r'<[^>]+>', '', text)
        return html.escape(text)


def sanitize_input(text: str, max_length: int | None = None) -> str:
    """
    Comprehensive input sanitization for user-provided text.
    """
    if not text or not isinstance(text, str):
        return text
    sanitized = sanitize_html(text, allow_tags=False)
    sanitized = sanitized.replace('\x00', '')
    sanitized = ' '.join(sanitized.split())
    if max_length and len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    return sanitized


def sanitize_url(url: str) -> str:
    """
    Sanitize URL to prevent javascript: and data: URL attacks.
    """
    if not url or not isinstance(url, str):
        return ''
    url = url.strip()
    dangerous_schemes = ['javascript:', 'data:', 'vbscript:', 'file:', 'about:']
    url_lower = url.lower()
    for scheme in dangerous_schemes:
        if url_lower.startswith(scheme):
            return ''
    return url


def strip_control_characters(text: str) -> str:
    """
    Remove control characters that might cause issues.
    """
    if not text or not isinstance(text, str):
        return text
    return ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')


def sanitize_username(username: str) -> str:
    """
    Sanitize username to only allow safe characters.
    """
    if not username or not isinstance(username, str):
        return username
    username = sanitize_html(username, allow_tags=False)
    safe_pattern = re.compile(r'[^a-zA-Z0-9_\-\.@]')
    return safe_pattern.sub('', username)


def sanitize_api_name(name: str) -> str:
    """
    Sanitize API name to prevent injection attacks.
    """
    if not name or not isinstance(name, str):
        return name
    name = sanitize_html(name, allow_tags=False)
    safe_pattern = re.compile(r'[^a-zA-Z0-9_\-]')
    return safe_pattern.sub('', name)
