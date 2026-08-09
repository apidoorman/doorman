"""
Latency Injection Middleware

Simulates network latency for chaos testing.
Controlled via X-Doorman-Latency header.
Only active if ENABLE_LATENCY_INJECTION env var is set.
"""

import asyncio
import logging
import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger('doorman.gateway')


class LatencyInjectionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.enabled = os.getenv('ENABLE_LATENCY_INJECTION', 'false').lower() == 'true'

    async def dispatch(self, request: Request, call_next):
        if self.enabled:
            latency_ms = request.headers.get('x-doorman-latency')
            if latency_ms:
                try:
                    delay = int(latency_ms)
                    # Cap at 5 seconds for safety
                    delay = min(max(0, delay), 5000)
                    if delay > 0:
                        logger.warning(f'Injecting {delay}ms latency for {request.url.path}')
                        await asyncio.sleep(delay / 1000.0)
                except ValueError:
                    pass
        
        return await call_next(request)
