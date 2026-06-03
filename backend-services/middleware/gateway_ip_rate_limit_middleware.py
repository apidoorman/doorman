"""
Gateway IP Rate Limit Middleware

Rate-limits all gateway requests (both /api/* path-based routes and host-based
transparent routes) by client IP address before authentication runs.  This
protects the gateway from unauthenticated and anonymous traffic floods without
requiring a valid JWT.

Excluded paths:
  /platform/*  — management/admin routes have separate rate limiting

Configuration via environment variables:
  GATEWAY_IP_RATE_LIMIT    - max requests per IP per window (default: 100)
  GATEWAY_IP_RATE_WINDOW   - window size in seconds (default: 60)
  GATEWAY_IP_RATE_DISABLED - set to 'true'/'1'/'yes'/'on' to disable (default: false)
"""

import logging
import os

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger('doorman.gateway')

_DISABLED_VALUES = frozenset(('1', 'true', 'yes', 'on'))


class GatewayIPRateLimitMiddleware(BaseHTTPMiddleware):
    """Pre-authentication IP rate limiter for all gateway traffic.

    Covers both conventional /api/* path-based routing and host-based transparent
    routing (Feature 1), where requests arrive at the root path with no /api/ prefix.
    Platform management routes (/platform/*) are explicitly excluded.

    The existing user-tier rate limiting (TierRateLimitMiddleware) and per-user
    throttling (limit_and_throttle) continue to run independently for authenticated
    traffic.

    Configuration is read once at construction time so that a mis-set env var is
    detected at startup with a log warning rather than silently disabling the limiter
    on every request.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self._limit = self._parse_int('GATEWAY_IP_RATE_LIMIT', 100)
        self._window = self._parse_int('GATEWAY_IP_RATE_WINDOW', 60)

    @staticmethod
    def _parse_int(env_key: str, default: int) -> int:
        raw = os.getenv(env_key, str(default))
        try:
            val = int(raw)
            if val <= 0:
                raise ValueError(f'{env_key} must be a positive integer, got {val!r}')
            return val
        except (ValueError, TypeError) as exc:
            logger.warning(
                f'GatewayIPRateLimitMiddleware: invalid {env_key}={raw!r} — '
                f'using default {default}. Error: {exc}'
            )
            return default

    async def dispatch(self, request: Request, call_next):
        # Platform management routes are excluded from gateway rate limiting.
        # All other paths (including host-routed requests that arrive without
        # an /api/ prefix) are subject to the limit.
        if request.url.path.startswith('/platform/'):
            return await call_next(request)

        # Runtime kill-switch — checked per-request so operators can toggle without
        # a restart.  Document this as the intended behaviour.
        if os.getenv('GATEWAY_IP_RATE_DISABLED', 'false').lower() in _DISABLED_VALUES:
            return await call_next(request)

        # Re-read limit/window per-request so that runtime changes (e.g. via env-var
        # updates without restart) and test monkeypatching both take effect
        # immediately.  _parse_int handles invalid values gracefully via the default.
        limit = self._parse_int('GATEWAY_IP_RATE_LIMIT', 100)
        window = self._parse_int('GATEWAY_IP_RATE_WINDOW', 60)

        try:
            from utils.limit_throttle_util import limit_by_ip
            # bypass_login_disabled_flag=True so that LOGIN_IP_RATE_DISABLED (which
            # tests set globally to suppress login-route throttling) does not also
            # suppress the gateway-level rate limit.  GATEWAY_IP_RATE_DISABLED is
            # the sole kill-switch for this middleware.
            await limit_by_ip(
                request,
                limit=limit,
                window=window,
                bypass_login_disabled_flag=True,
            )
        except Exception as exc:
            # limit_by_ip raises HTTPException(429) on breach — convert to a JSON
            # response.  Any other unexpected error is logged and the request is
            # allowed through so a rate-limiter bug never takes down the gateway.
            from fastapi import HTTPException
            from fastapi.responses import JSONResponse

            if isinstance(exc, HTTPException) and exc.status_code == 429:
                logger.warning(
                    f'Gateway IP rate limit exceeded: path={request.url.path} '
                    f'limit={self._limit}/{self._window}s'
                )
                return JSONResponse(
                    status_code=429,
                    content=(
                        exc.detail
                        if isinstance(exc.detail, dict)
                        else {'message': str(exc.detail)}
                    ),
                    headers=dict(exc.headers) if exc.headers else {},
                )
            logger.error(
                f'Unexpected error in GatewayIPRateLimitMiddleware: {exc}', exc_info=True
            )

        return await call_next(request)
