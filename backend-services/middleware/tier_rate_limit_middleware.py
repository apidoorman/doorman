"""
Tier-Based Rate Limit Middleware

Enforces rate limiting and throttling based on user tier configuration.
Works alongside existing per-user rate limiting.
"""

import asyncio
import logging
import time
from typing import Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from models.rate_limit_models import TierLimits
from services.tier_service import TierService, get_tier_service
from utils.database_async import async_database

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
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self._request_counts = {}  # Simple in-memory counter (use Redis in production)
        self._request_queue = {}  # Queue for throttling
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request through tier-based rate limiting
        """
        # Skip rate limiting for certain paths
        if self._should_skip(request):
            return await call_next(request)
        
        # Extract user ID
        user_id = self._get_user_id(request)
        
        if not user_id:
            # No user ID, skip tier-based limiting
            return await call_next(request)
        
        # Get user's tier limits
        tier_service = get_tier_service(async_database.db)
        limits = await tier_service.get_user_limits(user_id)
        
        if not limits:
            # No tier limits configured, allow request
            return await call_next(request)
        
        # Check rate limits
        rate_limit_result = await self._check_rate_limits(user_id, limits)
        
        if not rate_limit_result['allowed']:
            # Check if throttling is enabled
            if limits.enable_throttling:
                # Try to queue the request
                queued = await self._try_queue_request(
                    user_id, 
                    limits.max_queue_time_ms
                )
                
                if not queued:
                    # Queue full or timeout, return 429
                    return self._create_rate_limit_response(
                        rate_limit_result,
                        limits
                    )
                
                # Request was queued and processed, continue
            else:
                # Throttling disabled, hard reject
                return self._create_rate_limit_response(
                    rate_limit_result,
                    limits
                )
        
        # Increment counters
        self._increment_counters(user_id, limits)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        self._add_rate_limit_headers(response, user_id, limits)
        
        return response
    
    async def _check_rate_limits(
        self, 
        user_id: str, 
        limits: TierLimits
    ) -> dict:
        """
        Check if user has exceeded any rate limits
        
        Returns:
            dict with 'allowed' (bool) and 'limit_type' (str)
        """
        now = int(time.time())
        
        # Check requests per minute
        if limits.requests_per_minute and limits.requests_per_minute < 999999:
            key = f"{user_id}:minute:{now // 60}"
            count = self._request_counts.get(key, 0)
            
            if count >= limits.requests_per_minute:
                return {
                    'allowed': False,
                    'limit_type': 'minute',
                    'limit': limits.requests_per_minute,
                    'current': count,
                    'reset_at': ((now // 60) + 1) * 60
                }
        
        # Check requests per hour
        if limits.requests_per_hour and limits.requests_per_hour < 999999:
            key = f"{user_id}:hour:{now // 3600}"
            count = self._request_counts.get(key, 0)
            
            if count >= limits.requests_per_hour:
                return {
                    'allowed': False,
                    'limit_type': 'hour',
                    'limit': limits.requests_per_hour,
                    'current': count,
                    'reset_at': ((now // 3600) + 1) * 3600
                }
        
        # Check requests per day
        if limits.requests_per_day and limits.requests_per_day < 999999:
            key = f"{user_id}:day:{now // 86400}"
            count = self._request_counts.get(key, 0)
            
            if count >= limits.requests_per_day:
                return {
                    'allowed': False,
                    'limit_type': 'day',
                    'limit': limits.requests_per_day,
                    'current': count,
                    'reset_at': ((now // 86400) + 1) * 86400
                }
        
        return {'allowed': True}
    
    def _increment_counters(self, user_id: str, limits: TierLimits):
        """Increment request counters for all time windows"""
        now = int(time.time())
        
        if limits.requests_per_minute:
            key = f"{user_id}:minute:{now // 60}"
            self._request_counts[key] = self._request_counts.get(key, 0) + 1
        
        if limits.requests_per_hour:
            key = f"{user_id}:hour:{now // 3600}"
            self._request_counts[key] = self._request_counts.get(key, 0) + 1
        
        if limits.requests_per_day:
            key = f"{user_id}:day:{now // 86400}"
            self._request_counts[key] = self._request_counts.get(key, 0) + 1
    
    async def _try_queue_request(
        self, 
        user_id: str, 
        max_wait_ms: int
    ) -> bool:
        """
        Try to queue request with throttling
        
        Returns:
            True if request was processed, False if timeout/rejected
        """
        queue_key = f"{user_id}:queue"
        start_time = time.time() * 1000  # milliseconds
        
        # Initialize queue if needed
        if queue_key not in self._request_queue:
            self._request_queue[queue_key] = asyncio.Queue(maxsize=100)
        
        queue = self._request_queue[queue_key]
        
        try:
            # Add to queue with timeout
            await asyncio.wait_for(
                queue.put(1),
                timeout=max_wait_ms / 1000.0
            )
            
            # Wait for rate limit to reset
            while True:
                elapsed = (time.time() * 1000) - start_time
                
                if elapsed >= max_wait_ms:
                    # Timeout exceeded
                    await queue.get()  # Remove from queue
                    return False
                
                # Check if we can proceed
                # In a real implementation, check actual rate limit status
                await asyncio.sleep(0.1)  # Small delay
                
                # For now, assume we can proceed after a short wait
                if elapsed >= 100:  # 100ms min throttle delay
                    await queue.get()  # Remove from queue
                    return True
                    
        except asyncio.TimeoutError:
            return False
    
    def _create_rate_limit_response(
        self, 
        result: dict, 
        limits: TierLimits
    ) -> JSONResponse:
        """Create 429 Too Many Requests response"""
        retry_after = result.get('reset_at', 0) - int(time.time())
        
        return JSONResponse(
            status_code=429,
            content={
                'error': 'Rate limit exceeded',
                'error_code': 'RATE_LIMIT_EXCEEDED',
                'message': f"Rate limit exceeded: {result.get('current', 0)}/{result.get('limit', 0)} requests per {result.get('limit_type', 'period')}",
                'limit_type': result.get('limit_type'),
                'limit': result.get('limit'),
                'current': result.get('current'),
                'reset_at': result.get('reset_at'),
                'retry_after': max(0, retry_after),
                'throttling_enabled': limits.enable_throttling
            },
            headers={
                'Retry-After': str(max(0, retry_after)),
                'X-RateLimit-Limit': str(result.get('limit', 0)),
                'X-RateLimit-Remaining': '0',
                'X-RateLimit-Reset': str(result.get('reset_at', 0))
            }
        )
    
    def _add_rate_limit_headers(
        self, 
        response: Response, 
        user_id: str, 
        limits: TierLimits
    ):
        """Add rate limit headers to response"""
        now = int(time.time())
        
        # Add headers for minute limit (most relevant)
        if limits.requests_per_minute:
            key = f"{user_id}:minute:{now // 60}"
            current = self._request_counts.get(key, 0)
            remaining = max(0, limits.requests_per_minute - current)
            reset_at = ((now // 60) + 1) * 60
            
            response.headers['X-RateLimit-Limit'] = str(limits.requests_per_minute)
            response.headers['X-RateLimit-Remaining'] = str(remaining)
            response.headers['X-RateLimit-Reset'] = str(reset_at)
    
    def _should_skip(self, request: Request) -> bool:
        """Check if rate limiting should be skipped"""
        skip_paths = [
            '/health', 
            '/metrics', 
            '/docs', 
            '/redoc', 
            '/openapi.json',
            '/platform/authorization'  # Skip auth endpoints
        ]
        
        return any(request.url.path.startswith(path) for path in skip_paths)
    
    def _get_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request"""
        # Try to get from request state (set by auth middleware)
        if hasattr(request.state, 'user'):
            user = request.state.user
            if hasattr(user, 'username'):
                return user.username
            elif isinstance(user, dict):
                return user.get('username') or user.get('sub')
        
        # Try to get from JWT payload in state
        if hasattr(request.state, 'jwt_payload'):
            return request.state.jwt_payload.get('sub')
        
        return None
