"""
Tier-Based Rate Limit Middleware

Enforces rate limiting and throttling based on user tier configuration.
Works alongside existing per-user rate limiting.
"""

import asyncio
import logging
import time

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from models.rate_limit_models import TierLimits
from services.tier_service import get_tier_service
from utils.database_async import async_database

try:
    from utils.auth_util import SECRET_KEY, ALGORITHM
except Exception:
    SECRET_KEY = None
    ALGORITHM = 'HS256'

try:
    from jose import jwt as _jwt
except Exception:
    _jwt = None

logger = logging.getLogger(__name__)


class TierRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for tier-based rate limiting and throttling

    Features:
    - Enforces tier-based rate limits (requests per minute/hour/day)
    - Supports throttling (queuing requests) vs hard rejection
    - Respects user-specific limit overrides
    - Adds rate limit headers to responses
    """

    # Class-level helper for usage in tests
    _rate_limiter_override = None

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        # Use simple local queue for throttling, but rate limiting itself is distributed via Redis
        self._request_queue = {}

    async def dispatch(self, request: Request, call_next):
        """
        Process request through tier-based rate limiting
        """
        # Skip rate limiting for certain paths
        if self._should_skip(request):
            return await call_next(request)

        # Extract user ID
        user_id = self._get_user_id(request)
        logger.debug(f'[tier_rl] user_id={user_id} path={request.url.path}')

        if not user_id:
            return await call_next(request)

        # Get user's tier limits
        tier_service = get_tier_service(async_database.db)
        limits = await tier_service.get_user_limits(user_id)

        if not limits:
            return await call_next(request)

        # Using the utility's RateLimiter to check distributed limits
        from utils.rate_limiter import get_rate_limiter
        rate_limiter = self._rate_limiter_override or get_rate_limiter()
        
        # Check all applicable windows
        from models.rate_limit_models import RateLimitRule, RuleType, TimeWindow
        
        # Minute check
        minute_res = None
        if limits.requests_per_minute and limits.requests_per_minute < 999999:
            rule = RateLimitRule(
                rule_id=f'tier_minute_{user_id}',
                rule_type=RuleType.PER_USER,
                time_window=TimeWindow.MINUTE,
                limit=limits.requests_per_minute,
                burst_allowance=limits.burst_per_minute,
            )
            # Use check_hybrid for token bucket burst support + sliding window accuracy
            minute_res = await asyncio.to_thread(rate_limiter.check_hybrid, rule, user_id)
            if not minute_res.allowed:
                return self._handle_limit_exceeded(minute_res, limits, 'minute')

        # Hour check
        hour_res = None
        if limits.requests_per_hour and limits.requests_per_hour < 999999:
            rule = RateLimitRule(
                rule_id=f'tier_hour_{user_id}',
                rule_type=RuleType.PER_USER,
                time_window=TimeWindow.HOUR,
                limit=limits.requests_per_hour,
                burst_allowance=limits.burst_per_hour,
            )
            hour_res = await asyncio.to_thread(rate_limiter.check_hybrid, rule, user_id)
            if not hour_res.allowed:
                return self._handle_limit_exceeded(hour_res, limits, 'hour')

        # Day check
        day_res = None
        if limits.requests_per_day and limits.requests_per_day < 999999:
            rule = RateLimitRule(
                rule_id=f'tier_day_{user_id}',
                rule_type=RuleType.PER_USER,
                time_window=TimeWindow.DAY,
                limit=limits.requests_per_day,
            )
            day_res = await asyncio.to_thread(rate_limiter.check_hybrid, rule, user_id)
            if not day_res.allowed:
                return self._handle_limit_exceeded(day_res, limits, 'day')

        # Allowed. Proceed.
        response = await call_next(request)

        # Add headers (prioritize smallest window)
        res_to_use = minute_res or hour_res or day_res
        if res_to_use:
            self._add_rate_limit_headers(response, res_to_use)

        return response

    def _handle_limit_exceeded(self, result, limits: TierLimits, period: str):
        """Handle rejection or throttling"""
        # Throttling logic could go here, but for complexity reduction in distributed env,
        # we'll default to 429 unless explicitly requested to queue (which is complex to do distributively).
        # For now, standard rejection.
        return self._create_rate_limit_response(result, limits, period)

    def _create_rate_limit_response(self, result, limits: TierLimits, period: str) -> JSONResponse:
        """Create 429 Too Many Requests response"""
        retry_after = max(0, result.retry_after or (result.reset_at - int(time.time())))
        
        info = result.to_info()
        headers = info.to_headers()
        
        return JSONResponse(
            status_code=429,
            content={
                'error': 'Rate limit exceeded',
                'error_code': 'RATE_LIMIT_EXCEEDED',
                'message': f'Rate limit exceeded: quota {result.limit} per {period}',
                'limit': result.limit,
                'remaining': 0,
                'reset_at': result.reset_at,
                'retry_after': retry_after,
            },
            headers=headers,
        )

    def _add_rate_limit_headers(self, response: Response, result):
        """Add X-RateLimit-* headers"""
        try:
            info = result.to_info()
            for key, val in info.to_headers().items():
                response.headers[key] = val
        except Exception:
            pass

    def _should_skip(self, request: Request) -> bool:
        """Check if request should skip rate limiting"""
        import os

        # Skip tier rate limiting when explicitly disabled
        if os.getenv('SKIP_TIER_RATE_LIMIT', '').lower() in ('1', 'true', 'yes'):
            return True

        if request.url.path.startswith('/health') or \
           request.url.path.startswith('/metrics') or \
           request.url.path.startswith('/docs') or \
           request.url.path.startswith('/redoc') or \
           request.url.path.startswith('/openapi.json'):
            return True
            
        # Admin interface usually skipped for user-tier limits
        if request.url.path.startswith('/platform/'):
            return True

        return False

    def _get_user_id(self, request: Request) -> str | None:
        """Extract user ID with support for previously decoded state"""
        # 1) Previously decoded payload
        try:
            if hasattr(request.state, 'jwt_payload') and request.state.jwt_payload:
                 return request.state.jwt_payload.get('sub')
        except Exception:
            pass

        # 2) Cookie/Header decode logic duplicate from auth_util handled by earlier middleware usually,
        # but re-implemented here for safety if middleware order varies.
        try:
            from utils.auth_util import auth_required
            # We don't call auth_required because it raises 401. We just want to peek.
            # Reuse existing methods if possible or simplified peek:
            pass 
        except Exception:
            pass
            
        # Fallback to existing logic if needed, but for now assuming auth middleware ran first
        # or we accept checking cookies directly
        import os
        token = request.cookies.get('access_token_cookie')
        if not token:
            auth = request.headers.get('Authorization') or request.headers.get('authorization')
            if auth and str(auth).lower().startswith('bearer '):
                token = auth.split(' ', 1)[1].strip()
        
        if token and _jwt:
            # Read secret from key_util now
            from utils.key_util import get_verification_key
            try:
                # Unverified decode to find kid
                header = _jwt.get_unverified_header(token)
                kid = header.get('kid')
                key_info = get_verification_key(kid)
                if key_info:
                    payload = _jwt.decode(token, key_info.verification_key, algorithms=[key_info.algorithm])
                    return payload.get('sub')
            except Exception:
                pass
                
        return None
