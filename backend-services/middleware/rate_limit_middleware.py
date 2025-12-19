"""
Rate Limit Middleware

FastAPI middleware that applies rate limiting to incoming requests.
Checks rate limits and quotas, adds headers, and returns 429 when exceeded.
"""

import logging
from collections.abc import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from models.rate_limit_models import RateLimitRule, RuleType, TierLimits, TimeWindow
from utils.quota_tracker import QuotaTracker, QuotaType, get_quota_tracker
from utils.rate_limiter import RateLimiter, get_rate_limiter

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for rate limiting requests

    Features:
    - Applies rate limit rules based on user, API, endpoint, IP
    - Checks quotas (monthly, daily)
    - Adds rate limit headers to responses
    - Returns 429 Too Many Requests when limits exceeded
    - Supports tier-based limits
    """

    def __init__(
        self,
        app: ASGIApp,
        rate_limiter: RateLimiter | None = None,
        quota_tracker: QuotaTracker | None = None,
        get_rules_func: Callable | None = None,
        get_user_tier_func: Callable | None = None,
    ):
        """
        Initialize rate limit middleware

        Args:
            app: FastAPI application
            rate_limiter: Rate limiter instance
            quota_tracker: Quota tracker instance
            get_rules_func: Function to get applicable rules for request
            get_user_tier_func: Function to get user's tier
        """
        super().__init__(app)
        self.rate_limiter = rate_limiter or get_rate_limiter()
        self.quota_tracker = quota_tracker or get_quota_tracker()
        self.get_rules_func = get_rules_func or self._default_get_rules
        self.get_user_tier_func = get_user_tier_func or self._default_get_user_tier

    async def dispatch(self, request: Request, call_next):
        """
        Process request through rate limiting

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response (possibly 429 if rate limited)
        """
        # Skip rate limiting for certain paths
        if self._should_skip(request):
            return await call_next(request)

        # Extract identifiers
        user_id = self._get_user_id(request)
        api_name = self._get_api_name(request)
        endpoint_uri = str(request.url.path)
        ip_address = self._get_client_ip(request)

        # Get applicable rules
        rules = await self.get_rules_func(request, user_id, api_name, endpoint_uri, ip_address)

        # Check rate limits
        for rule in rules:
            identifier = self._get_identifier(rule, user_id, api_name, endpoint_uri, ip_address)

            if identifier:
                result = self.rate_limiter.check_rate_limit(rule, identifier)

                if not result.allowed:
                    # Rate limit exceeded
                    return self._create_rate_limit_response(result, rule)

        # Check quotas if user identified
        if user_id:
            tier_limits = await self.get_user_tier_func(user_id)

            if tier_limits:
                quota_result = await self._check_quotas(user_id, tier_limits)

                if not quota_result.allowed:
                    return self._create_quota_exceeded_response(quota_result)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        if rules:
            # Use first rule for headers (highest priority)
            rule = rules[0]
            identifier = self._get_identifier(rule, user_id, api_name, endpoint_uri, ip_address)

            if identifier:
                usage = self.rate_limiter.get_current_usage(rule, identifier)
                self._add_rate_limit_headers(response, usage.limit, usage.remaining, usage.reset_at)

        # Increment quota (async, don't block response)
        if user_id:
            try:
                self.quota_tracker.increment_quota(user_id, QuotaType.REQUESTS, 1, 'month')
            except Exception as e:
                logger.error(f'Error incrementing quota: {e}')

        return response

    def _should_skip(self, request: Request) -> bool:
        """
        Check if rate limiting should be skipped for this request

        Args:
            request: Incoming request

        Returns:
            True if should skip
        """
        # Skip health checks, metrics, etc.
        skip_paths = ['/health', '/metrics', '/docs', '/redoc', '/openapi.json']

        return any(request.url.path.startswith(path) for path in skip_paths)

    def _get_user_id(self, request: Request) -> str | None:
        """
        Extract user ID from request

        Args:
            request: Incoming request

        Returns:
            User ID or None
        """
        # Try to get from request state (set by auth middleware)
        if hasattr(request.state, 'user'):
            return getattr(request.state.user, 'username', None)

        # Try to get from headers
        return request.headers.get('X-User-ID')

    def _get_api_name(self, request: Request) -> str | None:
        """
        Extract API name from request

        Args:
            request: Incoming request

        Returns:
            API name or None
        """
        # Try to get from request state (set by routing)
        if hasattr(request.state, 'api_name'):
            return request.state.api_name

        # Try to extract from path
        path_parts = request.url.path.strip('/').split('/')
        if len(path_parts) > 0:
            return path_parts[0]

        return None

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request

        Args:
            request: Incoming request

        Returns:
            IP address
        """
        # Check X-Forwarded-For header (proxy/load balancer)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            # Take first IP (original client)
            return forwarded_for.split(',')[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip

        # Fall back to direct connection
        if request.client:
            return request.client.host

        return 'unknown'

    def _get_identifier(
        self,
        rule: RateLimitRule,
        user_id: str | None,
        api_name: str | None,
        endpoint_uri: str,
        ip_address: str,
    ) -> str | None:
        """
        Get identifier for rate limit rule

        Args:
            rule: Rate limit rule
            user_id: User ID
            api_name: API name
            endpoint_uri: Endpoint URI
            ip_address: IP address

        Returns:
            Identifier string or None
        """
        if rule.rule_type == RuleType.PER_USER:
            return user_id
        elif rule.rule_type == RuleType.PER_API:
            return api_name or rule.target_identifier
        elif rule.rule_type == RuleType.PER_ENDPOINT:
            return endpoint_uri
        elif rule.rule_type == RuleType.PER_IP:
            return ip_address
        elif rule.rule_type == RuleType.PER_USER_API:
            return f'{user_id}:{api_name}' if user_id and api_name else None
        elif rule.rule_type == RuleType.PER_USER_ENDPOINT:
            return f'{user_id}:{endpoint_uri}' if user_id else None
        elif rule.rule_type == RuleType.GLOBAL:
            return 'global'

        return None

    async def _default_get_rules(
        self, request: Request, user_id: str | None, api_name: str | None, endpoint_uri: str, ip_address: str
    ) -> list[RateLimitRule]:
        """
        Default implementation to get applicable rules

        Args:
            request: Request object
            user_id: User identifier
            api_name: API name
            endpoint_uri: Endpoint URI
            ip_address: IP address

        Returns:
            List of applicable rules
        """
        # TODO: Query MongoDB for rules
        # For now, return default rules

        rules = []

        # Check if user has a tier assigned
        user_tier = None
        if user_id:
            user_tier = await self.get_user_tier_func(user_id)

        if user_tier:
            # User has tier → Use tier limits ONLY (priority)
            # Convert tier limits to rate limit rules
            if user_tier.requests_per_minute:
                rules.append(
                    RateLimitRule(
                        rule_id=f'tier_{user_id}',
                        rule_type=RuleType.PER_USER,
                        time_window=TimeWindow.MINUTE,
                        limit=user_tier.requests_per_minute,
                        burst_allowance=user_tier.burst_allowance or 0,
                        priority=100,  # Highest priority
                        enabled=True,
                        description=f'Tier-based limit for {user_id}',
                    )
                )
        else:
            # User has NO tier → Use per-user rate limit rules
            if user_id:
                # TODO: Query MongoDB for per-user rules
                # For now, use default per-user rule
                rules.append(
                    RateLimitRule(
                        rule_id='default_per_user',
                        rule_type=RuleType.PER_USER,
                        time_window=TimeWindow.MINUTE,
                        limit=100,
                        burst_allowance=20,
                        priority=10,
                        enabled=True,
                        description='Default per-user limit',
                    )
                )

        # Add global rule as fallback if no rules were loaded
        if not rules:
            rules.append(
                RateLimitRule(
                    rule_id='default_global',
                    rule_type=RuleType.GLOBAL,
                    time_window=TimeWindow.MINUTE,
                    limit=1000,
                    priority=0,
                    enabled=True,
                    description='Global rate limit',
                )
            )

        return rules

    async def _default_get_user_tier(self, user_id: str) -> TierLimits | None:
        """
        Get user's tier limits from TierService

        Args:
            user_id: User ID

        Returns:
            TierLimits or None
        """
        try:
            from services.tier_service import get_tier_service
            from utils.database_async import async_database

            tier_service = get_tier_service(async_database.db)
            limits = await tier_service.get_user_limits(user_id)

            return limits
        except Exception as e:
            logger.error(f'Error fetching user tier limits: {e}')
            return None

    async def _check_quotas(self, user_id: str, tier_limits: TierLimits) -> 'QuotaCheckResult':
        """
        Check user's quotas

        Args:
            user_id: User ID
            tier_limits: User's tier limits

        Returns:
            QuotaCheckResult
        """
        # Check monthly quota
        if tier_limits.monthly_request_quota:
            result = self.quota_tracker.check_quota(
                user_id, QuotaType.REQUESTS, tier_limits.monthly_request_quota, 'month'
            )

            if not result.allowed:
                return result

        # Check daily quota
        if tier_limits.daily_request_quota:
            result = self.quota_tracker.check_quota(
                user_id, QuotaType.REQUESTS, tier_limits.daily_request_quota, 'day'
            )

            if not result.allowed:
                return result

        # All quotas OK
        from utils.quota_tracker import QuotaCheckResult

        return QuotaCheckResult(
            allowed=True,
            current_usage=0,
            limit=tier_limits.monthly_request_quota or 0,
            remaining=tier_limits.monthly_request_quota or 0,
            reset_at=self.quota_tracker._get_next_reset('month'),
            percentage_used=0.0,
        )

    def _create_rate_limit_response(
        self, result: 'RateLimitResult', rule: RateLimitRule
    ) -> JSONResponse:
        """
        Create 429 response for rate limit exceeded

        Args:
            result: Rate limit result
            rule: Rule that was exceeded

        Returns:
            JSONResponse with 429 status
        """
        info = result.to_info()

        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                'error': 'Rate limit exceeded',
                'message': f'You have exceeded the rate limit of {result.limit} requests per {rule.time_window.value}',
                'limit': result.limit,
                'remaining': result.remaining,
                'reset_at': result.reset_at,
                'retry_after': result.retry_after,
            },
            headers=info.to_headers(),
        )

    def _create_quota_exceeded_response(self, result: 'QuotaCheckResult') -> JSONResponse:
        """
        Create 429 response for quota exceeded

        Args:
            result: Quota check result

        Returns:
            JSONResponse with 429 status
        """
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                'error': 'Quota exceeded',
                'message': f'You have exceeded your quota of {result.limit} requests',
                'current_usage': result.current_usage,
                'limit': result.limit,
                'remaining': result.remaining,
                'reset_at': result.reset_at.isoformat(),
                'percentage_used': result.percentage_used,
            },
            headers={
                'X-RateLimit-Limit': str(result.limit),
                'X-RateLimit-Remaining': str(result.remaining),
                'X-RateLimit-Reset': str(int(result.reset_at.timestamp())),
                'Retry-After': str(int((result.reset_at - datetime.now()).total_seconds())),
            },
        )

    def _add_rate_limit_headers(
        self, response: Response, limit: int, remaining: int, reset_at: int
    ):
        """
        Add rate limit headers to response

        Args:
            response: Response object
            limit: Rate limit
            remaining: Remaining requests
            reset_at: Reset timestamp
        """
        response.headers['X-RateLimit-Limit'] = str(limit)
        response.headers['X-RateLimit-Remaining'] = str(remaining)
        response.headers['X-RateLimit-Reset'] = str(reset_at)


# Import datetime for response creation
from datetime import datetime
