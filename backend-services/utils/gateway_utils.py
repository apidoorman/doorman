import re
from typing import Dict, List

from fastapi import Request


def sanitize_headers(value: str):
    value = value.replace('\n', '').replace('\r', '')
    value = re.sub(r'<[^>]+>', '', value)
    return value

async def get_headers(request: Request, allowed_headers: List[str]):
    safe_headers = {}
    for key, value in request.headers.items():
        if key in allowed_headers:
            safe_headers[key] = sanitize_headers(value)
    return safe_headers
