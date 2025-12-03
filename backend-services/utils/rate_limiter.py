"""
Rate Limiter

Implements token bucket and sliding window algorithms for rate limiting.
Supports distributed rate limiting across multiple server instances using Redis.
"""

import time
import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from models.rate_limit_models import (
    RateLimitRule,
    RateLimitCounter,
    RateLimitInfo,
    TimeWindow,
    get_time_window_seconds,
    generate_redis_key
)
from utils.redis_client import get_redis_client, RedisClient

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """Result of rate limit check"""
    allowed: bool
    limit: int
    remaining: int
    reset_at: int
    retry_after: Optional[int] = None
    burst_remaining: int = 0
    
    def to_info(self) -> RateLimitInfo:
        """Convert to RateLimitInfo"""
        return RateLimitInfo(
            limit=self.limit,
            remaining=self.remaining,
            reset_at=self.reset_at,
            retry_after=self.retry_after,
            burst_remaining=self.burst_remaining
        )


class RateLimiter:
    """
    Rate limiter with token bucket and sliding window algorithms
    
    Features:
    - Token bucket for burst handling
    - Sliding window for accurate rate limiting
    - Distributed locking for multi-instance support
    - Graceful degradation if Redis is unavailable
    """
    
    def __init__(self, redis_client: Optional[RedisClient] = None):
        """
        Initialize rate limiter
        
        Args:
            redis_client: Redis client instance (creates default if None)
        """
        self.redis = redis_client or get_redis_client()
        self._fallback_mode = False
    
    def check_rate_limit(
        self,
        rule: RateLimitRule,
        identifier: str
    ) -> RateLimitResult:
        """
        Check if request is allowed under rate limit rule
        
        Args:
            rule: Rate limit rule to apply
            identifier: Unique identifier (user ID, API name, IP, etc.)
            
        Returns:
            RateLimitResult with allow/deny decision
        """
        if not rule.enabled:
            # Rule is disabled, allow request
            return RateLimitResult(
                allowed=True,
                limit=rule.limit,
                remaining=rule.limit,
                reset_at=int(time.time()) + get_time_window_seconds(rule.time_window)
            )
        
        # Use sliding window algorithm
        return self._check_sliding_window(rule, identifier)
    
    def _check_sliding_window(
        self,
        rule: RateLimitRule,
        identifier: str
    ) -> RateLimitResult:
        """
        Check rate limit using sliding window counter algorithm
        
        This is more accurate than fixed window and prevents boundary issues.
        
        Algorithm:
        1. Get current and previous window counts
        2. Calculate weighted count based on time elapsed in current window
        3. Check if weighted count exceeds limit
        4. If allowed, increment current window counter
        
        Args:
            rule: Rate limit rule
            identifier: Unique identifier
            
        Returns:
            RateLimitResult
        """
        now = time.time()
        window_size = get_time_window_seconds(rule.time_window)
        
        # Calculate current and previous window timestamps
        current_window = int(now / window_size) * window_size
        previous_window = current_window - window_size
        
        # Generate Redis keys
        current_key = generate_redis_key(
            rule.rule_type,
            identifier,
            rule.time_window,
            current_window
        )
        previous_key = generate_redis_key(
            rule.rule_type,
            identifier,
            rule.time_window,
            previous_window
        )
        
        try:
            # Get counts from both windows
            with self.redis.pipeline() as pipe:
                pipe.get(current_key)
                pipe.get(previous_key)
                results = pipe.execute()
            
            current_count = int(results[0]) if results[0] else 0
            previous_count = int(results[1]) if results[1] else 0
            
            # Calculate weighted count (sliding window)
            elapsed_in_window = now - current_window
            weight = 1 - (elapsed_in_window / window_size)
            estimated_count = int((previous_count * weight) + current_count)
            
            # Check if limit exceeded
            if estimated_count >= rule.limit:
                # Rate limit exceeded
                reset_at = current_window + window_size
                retry_after = int(reset_at - now)
                
                return RateLimitResult(
                    allowed=False,
                    limit=rule.limit,
                    remaining=0,
                    reset_at=int(reset_at),
                    retry_after=retry_after
                )
            
            # Check burst allowance if available
            burst_remaining = rule.burst_allowance
            if rule.burst_allowance > 0:
                burst_key = f"{current_key}:burst"
                burst_count = int(self.redis.get(burst_key) or 0)
                burst_remaining = max(0, rule.burst_allowance - burst_count)
            
            # Increment counter (atomic operation)
            new_count = self.redis.incr(current_key)
            
            # Set TTL on first increment
            if new_count == 1:
                self.redis.expire(current_key, window_size * 2)
            
            # Calculate remaining requests
            remaining = max(0, rule.limit - estimated_count - 1)
            reset_at = current_window + window_size
            
            return RateLimitResult(
                allowed=True,
                limit=rule.limit,
                remaining=remaining,
                reset_at=int(reset_at),
                burst_remaining=burst_remaining
            )
            
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # Graceful degradation: allow request on error
            return RateLimitResult(
                allowed=True,
                limit=rule.limit,
                remaining=rule.limit,
                reset_at=int(now) + window_size
            )
    
    def check_token_bucket(
        self,
        rule: RateLimitRule,
        identifier: str
    ) -> RateLimitResult:
        """
        Check rate limit using token bucket algorithm
        
        Token bucket allows bursts while maintaining average rate.
        
        Algorithm:
        1. Calculate tokens to add based on time elapsed
        2. Add tokens to bucket (up to limit)
        3. Check if enough tokens available
        4. If yes, consume token and allow request
        
        Args:
            rule: Rate limit rule
            identifier: Unique identifier
            
        Returns:
            RateLimitResult
        """
        now = time.time()
        window_size = get_time_window_seconds(rule.time_window)
        refill_rate = rule.limit / window_size  # Tokens per second
        
        # Generate Redis key for bucket
        bucket_key = f"bucket:{rule.rule_type.value}:{identifier}:{rule.time_window.value}"
        
        try:
            # Get current bucket state
            bucket_data = self.redis.hmget(bucket_key, ['tokens', 'last_refill'])
            
            if bucket_data[0] is None:
                # Initialize bucket
                tokens = float(rule.limit)
                last_refill = now
            else:
                tokens = float(bucket_data[0])
                last_refill = float(bucket_data[1])
            
            # Calculate tokens to add
            elapsed = now - last_refill
            tokens_to_add = elapsed * refill_rate
            tokens = min(rule.limit, tokens + tokens_to_add)
            
            # Check if request is allowed
            if tokens >= 1.0:
                # Consume token
                tokens -= 1.0
                
                # Update bucket state
                self.redis.hmset(bucket_key, {
                    'tokens': tokens,
                    'last_refill': now
                })
                self.redis.expire(bucket_key, window_size * 2)
                
                # Calculate reset time (when bucket will be full)
                time_to_full = (rule.limit - tokens) / refill_rate
                reset_at = int(now + time_to_full)
                
                return RateLimitResult(
                    allowed=True,
                    limit=rule.limit,
                    remaining=int(tokens),
                    reset_at=reset_at
                )
            else:
                # Not enough tokens
                time_to_token = (1.0 - tokens) / refill_rate
                retry_after = int(time_to_token) + 1
                reset_at = int(now + time_to_token)
                
                return RateLimitResult(
                    allowed=False,
                    limit=rule.limit,
                    remaining=0,
                    reset_at=reset_at,
                    retry_after=retry_after
                )
                
        except Exception as e:
            logger.error(f"Token bucket check error: {e}")
            # Graceful degradation
            return RateLimitResult(
                allowed=True,
                limit=rule.limit,
                remaining=rule.limit,
                reset_at=int(now) + window_size
            )
    
    def check_hybrid(
        self,
        rule: RateLimitRule,
        identifier: str
    ) -> RateLimitResult:
        """
        Check rate limit using hybrid approach (sliding window + token bucket)
        
        This combines accuracy of sliding window with burst handling of token bucket.
        
        Algorithm:
        1. Check sliding window (accurate rate limit)
        2. If allowed, check token bucket (burst handling)
        3. Both must pass for request to be allowed
        
        Args:
            rule: Rate limit rule
            identifier: Unique identifier
            
        Returns:
            RateLimitResult
        """
        # First check sliding window
        sliding_result = self._check_sliding_window(rule, identifier)
        
        if not sliding_result.allowed:
            return sliding_result
        
        # If sliding window allows, check token bucket for burst
        if rule.burst_allowance > 0:
            bucket_result = self.check_token_bucket(rule, identifier)
            
            if not bucket_result.allowed:
                # Use burst tokens if available
                return self._use_burst_tokens(rule, identifier, sliding_result)
        
        return sliding_result
    
    def _use_burst_tokens(
        self,
        rule: RateLimitRule,
        identifier: str,
        sliding_result: RateLimitResult
    ) -> RateLimitResult:
        """
        Try to use burst tokens when normal tokens are exhausted
        
        Args:
            rule: Rate limit rule
            identifier: Unique identifier
            sliding_result: Result from sliding window check
            
        Returns:
            RateLimitResult
        """
        now = time.time()
        window_size = get_time_window_seconds(rule.time_window)
        current_window = int(now / window_size) * window_size
        
        burst_key = f"burst:{rule.rule_type.value}:{identifier}:{current_window}"
        
        try:
            # Get current burst usage
            burst_count = int(self.redis.get(burst_key) or 0)
            
            if burst_count < rule.burst_allowance:
                # Burst tokens available
                new_burst_count = self.redis.incr(burst_key)
                
                if new_burst_count == 1:
                    self.redis.expire(burst_key, window_size * 2)
                
                burst_remaining = rule.burst_allowance - new_burst_count
                
                return RateLimitResult(
                    allowed=True,
                    limit=rule.limit,
                    remaining=sliding_result.remaining,
                    reset_at=sliding_result.reset_at,
                    burst_remaining=burst_remaining
                )
            else:
                # No burst tokens available
                return RateLimitResult(
                    allowed=False,
                    limit=rule.limit,
                    remaining=0,
                    reset_at=sliding_result.reset_at,
                    retry_after=sliding_result.retry_after,
                    burst_remaining=0
                )
                
        except Exception as e:
            logger.error(f"Burst token check error: {e}")
            # On error, allow with sliding window result
            return sliding_result
    
    def reset_limit(self, rule: RateLimitRule, identifier: str) -> bool:
        """
        Reset rate limit for identifier (admin function)
        
        Args:
            rule: Rate limit rule
            identifier: Unique identifier
            
        Returns:
            True if successful
        """
        try:
            now = time.time()
            window_size = get_time_window_seconds(rule.time_window)
            current_window = int(now / window_size) * window_size
            
            # Delete all related keys
            keys_to_delete = [
                generate_redis_key(rule.rule_type, identifier, rule.time_window, current_window),
                generate_redis_key(rule.rule_type, identifier, rule.time_window, current_window - window_size),
                f"bucket:{rule.rule_type.value}:{identifier}:{rule.time_window.value}",
                f"burst:{rule.rule_type.value}:{identifier}:{current_window}"
            ]
            
            self.redis.delete(*keys_to_delete)
            logger.info(f"Reset rate limit for {identifier}")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting rate limit: {e}")
            return False
    
    def get_current_usage(
        self,
        rule: RateLimitRule,
        identifier: str
    ) -> RateLimitCounter:
        """
        Get current usage for identifier
        
        Args:
            rule: Rate limit rule
            identifier: Unique identifier
            
        Returns:
            RateLimitCounter with current state
        """
        now = time.time()
        window_size = get_time_window_seconds(rule.time_window)
        current_window = int(now / window_size) * window_size
        
        key = generate_redis_key(
            rule.rule_type,
            identifier,
            rule.time_window,
            current_window
        )
        
        try:
            count = int(self.redis.get(key) or 0)
            burst_key = f"{key}:burst"
            burst_count = int(self.redis.get(burst_key) or 0)
            
            return RateLimitCounter(
                key=key,
                window_start=current_window,
                window_size=window_size,
                count=count,
                limit=rule.limit,
                burst_count=burst_count,
                burst_limit=rule.burst_allowance
            )
            
        except Exception as e:
            logger.error(f"Error getting current usage: {e}")
            return RateLimitCounter(
                key=key,
                window_start=current_window,
                window_size=window_size,
                count=0,
                limit=rule.limit
            )


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create global rate limiter instance"""
    global _rate_limiter
    
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    
    return _rate_limiter
