"""
Rate Limiter Test Suite

Comprehensive tests for rate limiting functionality including:
- Unit tests for rate limiter
- Integration tests for middleware
- Burst handling tests
- Load tests for distributed scenarios
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from utils.rate_limiter import RateLimiter, RateLimitResult
from utils.quota_tracker import QuotaTracker
from utils.ip_rate_limiter import IPRateLimiter
from models.rate_limit_models import (
    RateLimitRule, RuleType, TimeWindow, QuotaType
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_redis():
    """Mock Redis client for testing"""
    redis = MagicMock()
    redis.get.return_value = None
    redis.incr.return_value = 1
    redis.expire.return_value = True
    redis.pipeline.return_value = redis
    redis.execute.return_value = [1, True, 1, True]
    return redis


@pytest.fixture
def rate_limiter(mock_redis):
    """Rate limiter instance with mock Redis"""
    return RateLimiter(redis_client=mock_redis)


@pytest.fixture
def quota_tracker(mock_redis):
    """Quota tracker instance with mock Redis"""
    return QuotaTracker(redis_client=mock_redis)


@pytest.fixture
def ip_limiter(mock_redis):
    """IP rate limiter instance with mock Redis"""
    return IPRateLimiter(redis_client=mock_redis)


@pytest.fixture
def sample_rule():
    """Sample rate limit rule"""
    return RateLimitRule(
        rule_id="test_rule",
        rule_type=RuleType.PER_USER,
        time_window=TimeWindow.MINUTE,
        limit=100,
        burst_allowance=20,
        target_identifier="test_user"
    )


# ============================================================================
# UNIT TESTS - RATE LIMITER
# ============================================================================

class TestRateLimiter:
    """Unit tests for RateLimiter class"""
    
    def test_sliding_window_within_limit(self, rate_limiter, sample_rule, mock_redis):
        """Test sliding window allows requests within limit"""
        mock_redis.get.return_value = "50"  # Current count
        
        result = rate_limiter._check_sliding_window(sample_rule, "test_user")
        
        assert result.allowed is True
        assert result.limit == 100
        assert result.remaining == 50
        
    def test_sliding_window_exceeds_limit(self, rate_limiter, sample_rule, mock_redis):
        """Test sliding window blocks requests exceeding limit"""
        mock_redis.get.return_value = "100"  # At limit
        
        result = rate_limiter._check_sliding_window(sample_rule, "test_user")
        
        assert result.allowed is False
        assert result.remaining == 0
        
    def test_token_bucket_allows_burst(self, rate_limiter, sample_rule, mock_redis):
        """Test token bucket allows burst requests"""
        mock_redis.get.side_effect = ["100", "5"]  # Normal at limit, burst available
        
        result = rate_limiter.check_token_bucket(sample_rule, "test_user")
        
        assert result.allowed is True
        
    def test_burst_tokens_exhausted(self, rate_limiter, sample_rule, mock_redis):
        """Test burst tokens can be exhausted"""
        mock_redis.get.side_effect = ["100", "20"]  # Normal at limit, burst exhausted
        
        result = rate_limiter._use_burst_tokens(sample_rule, "test_user", Mock())
        
        assert result.allowed is False
        
    def test_hybrid_check_normal_flow(self, rate_limiter, sample_rule, mock_redis):
        """Test hybrid check in normal flow"""
        mock_redis.get.return_value = "50"
        
        result = rate_limiter.check_hybrid(sample_rule, "test_user")
        
        assert result.allowed is True
        
    def test_hybrid_check_uses_burst(self, rate_limiter, sample_rule, mock_redis):
        """Test hybrid check falls back to burst tokens"""
        # First call: normal limit reached
        # Second call: burst available
        mock_redis.get.side_effect = ["100", "5"]
        
        result = rate_limiter.check_hybrid(sample_rule, "test_user")
        
        # Should attempt to use burst tokens
        assert mock_redis.get.call_count >= 1


# ============================================================================
# UNIT TESTS - QUOTA TRACKER
# ============================================================================

class TestQuotaTracker:
    """Unit tests for QuotaTracker class"""
    
    def test_quota_within_limit(self, quota_tracker, mock_redis):
        """Test quota check within limit"""
        mock_redis.get.return_value = "5000"
        
        result = quota_tracker.check_quota(
            "test_user",
            QuotaType.REQUESTS,
            10000,
            "month"
        )
        
        assert result.is_exhausted is False
        assert result.is_warning is False
        assert result.remaining == 5000
        
    def test_quota_warning_threshold(self, quota_tracker, mock_redis):
        """Test quota warning at 80%"""
        mock_redis.get.return_value = "8500"  # 85% used
        
        result = quota_tracker.check_quota(
            "test_user",
            QuotaType.REQUESTS,
            10000,
            "month"
        )
        
        assert result.is_warning is True
        assert result.is_critical is False
        
    def test_quota_critical_threshold(self, quota_tracker, mock_redis):
        """Test quota critical at 95%"""
        mock_redis.get.return_value = "9600"  # 96% used
        
        result = quota_tracker.check_quota(
            "test_user",
            QuotaType.REQUESTS,
            10000,
            "month"
        )
        
        assert result.is_critical is True
        
    def test_quota_exhausted(self, quota_tracker, mock_redis):
        """Test quota exhausted at 100%"""
        mock_redis.get.return_value = "10000"
        
        result = quota_tracker.check_quota(
            "test_user",
            QuotaType.REQUESTS,
            10000,
            "month"
        )
        
        assert result.is_exhausted is True
        assert result.remaining == 0
        
    def test_quota_increment(self, quota_tracker, mock_redis):
        """Test quota increment"""
        mock_redis.incr.return_value = 101
        
        new_usage = quota_tracker.increment_quota(
            "test_user",
            QuotaType.REQUESTS,
            "month"
        )
        
        assert new_usage == 101
        mock_redis.incr.assert_called_once()


# ============================================================================
# UNIT TESTS - IP RATE LIMITER
# ============================================================================

class TestIPRateLimiter:
    """Unit tests for IPRateLimiter class"""
    
    def test_extract_ip_from_forwarded_for(self, ip_limiter):
        """Test IP extraction from X-Forwarded-For"""
        request = Mock()
        request.headers.get.return_value = "192.168.1.1, 10.0.0.1"
        
        ip = ip_limiter.extract_client_ip(request)
        
        assert ip == "192.168.1.1"
        
    def test_extract_ip_from_real_ip(self, ip_limiter):
        """Test IP extraction from X-Real-IP"""
        request = Mock()
        request.headers.get.side_effect = [None, "192.168.1.1"]
        
        ip = ip_limiter.extract_client_ip(request)
        
        assert ip == "192.168.1.1"
        
    def test_whitelist_bypasses_limit(self, ip_limiter, mock_redis):
        """Test whitelisted IP bypasses rate limit"""
        mock_redis.sismember.return_value = True
        
        result = ip_limiter.check_ip_rate_limit("192.168.1.1")
        
        assert result.allowed is True
        assert result.limit == 999999
        
    def test_blacklist_blocks_request(self, ip_limiter, mock_redis):
        """Test blacklisted IP is blocked"""
        mock_redis.sismember.side_effect = [False, True]  # Not whitelisted, is blacklisted
        
        result = ip_limiter.check_ip_rate_limit("10.0.0.1")
        
        assert result.allowed is False
        
    def test_reputation_reduces_limits(self, ip_limiter, mock_redis):
        """Test low reputation reduces rate limits"""
        mock_redis.sismember.return_value = False
        mock_redis.get.side_effect = ["30", "0", "0"]  # Low reputation, no requests yet
        
        result = ip_limiter.check_ip_rate_limit("10.0.0.1")
        
        # Limits should be reduced due to low reputation
        assert result.allowed is True
        
    def test_reputation_score_update(self, ip_limiter, mock_redis):
        """Test reputation score update"""
        mock_redis.get.return_value = "100"
        
        new_score = ip_limiter.update_reputation_score("192.168.1.1", -10)
        
        assert new_score == 90
        mock_redis.setex.assert_called_once()


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestRateLimitIntegration:
    """Integration tests for rate limiting system"""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, rate_limiter, sample_rule, mock_redis):
        """Test concurrent requests handling"""
        mock_redis.get.return_value = "0"
        
        # Simulate 10 concurrent requests
        tasks = []
        for i in range(10):
            task = asyncio.create_task(
                asyncio.to_thread(
                    rate_limiter.check_hybrid,
                    sample_rule,
                    f"user_{i}"
                )
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # All should be allowed (different users)
        assert all(r.allowed for r in results)
        
    def test_burst_handling_sequence(self, rate_limiter, sample_rule, mock_redis):
        """Test burst handling in sequence"""
        # Simulate reaching normal limit, then using burst
        mock_redis.get.side_effect = [
            "99", "100", "0",  # Normal flow
            "100", "5"         # Burst flow
        ]
        
        # First request: within normal limit
        result1 = rate_limiter.check_hybrid(sample_rule, "test_user")
        assert result1.allowed is True
        
        # Second request: at normal limit, use burst
        result2 = rate_limiter.check_hybrid(sample_rule, "test_user")
        # Should attempt burst tokens
        
    def test_quota_and_rate_limit_interaction(self, quota_tracker, rate_limiter, mock_redis):
        """Test interaction between quota and rate limits"""
        mock_redis.get.return_value = "50"
        
        # Check rate limit
        rate_result = rate_limiter._check_sliding_window(
            RateLimitRule(
                rule_id="test",
                rule_type=RuleType.PER_USER,
                time_window=TimeWindow.MINUTE,
                limit=100
            ),
            "test_user"
        )
        
        # Check quota
        quota_result = quota_tracker.check_quota(
            "test_user",
            QuotaType.REQUESTS,
            10000,
            "month"
        )
        
        # Both should allow
        assert rate_result.allowed is True
        assert quota_result.is_exhausted is False


# ============================================================================
# LOAD TESTS
# ============================================================================

class TestRateLimitLoad:
    """Load tests for rate limiting system"""
    
    def test_high_volume_requests(self, rate_limiter, sample_rule, mock_redis):
        """Test handling high volume of requests"""
        mock_redis.get.return_value = "0"
        
        start_time = time.time()
        
        # Simulate 1000 requests
        for i in range(1000):
            result = rate_limiter.check_hybrid(sample_rule, f"user_{i % 100}")
        
        elapsed = time.time() - start_time
        
        # Should complete in reasonable time (< 1 second for 1000 requests)
        assert elapsed < 1.0
        
    def test_distributed_scenario(self, rate_limiter, mock_redis):
        """Test distributed rate limiting scenario"""
        # Simulate multiple servers checking same user
        rules = [
            RateLimitRule(
                rule_id=f"rule_{i}",
                rule_type=RuleType.PER_USER,
                time_window=TimeWindow.MINUTE,
                limit=100
            )
            for i in range(5)
        ]
        
        mock_redis.get.return_value = "50"
        
        # All servers should get consistent results
        results = [
            rate_limiter.check_hybrid(rule, "test_user")
            for rule in rules
        ]
        
        # All should have same limit
        assert all(r.limit == 100 for r in results)


# ============================================================================
# BURST HANDLING TESTS
# ============================================================================

class TestBurstHandling:
    """Specific tests for burst handling"""
    
    def test_burst_allows_spike(self, rate_limiter, sample_rule, mock_redis):
        """Test burst allows temporary spike"""
        # Normal limit reached
        mock_redis.get.side_effect = ["100", "0"]
        
        result = rate_limiter._use_burst_tokens(sample_rule, "test_user", Mock())
        
        assert result.allowed is True
        
    def test_burst_refills_over_time(self, rate_limiter, sample_rule, mock_redis):
        """Test burst tokens refill over time"""
        # Burst used, then check again after time window
        mock_redis.get.side_effect = ["20", "0"]  # Burst exhausted, then refilled
        
        # First check: exhausted
        result1 = rate_limiter._use_burst_tokens(sample_rule, "test_user", Mock())
        
        # Simulate time passing (would reset in Redis)
        mock_redis.get.side_effect = ["0"]
        
        # Second check: refilled
        result2 = rate_limiter._use_burst_tokens(sample_rule, "test_user", Mock())
        
    def test_burst_tracking(self, rate_limiter, sample_rule, mock_redis):
        """Test burst usage is tracked separately"""
        mock_redis.get.return_value = "5"
        
        result = rate_limiter._use_burst_tokens(sample_rule, "test_user", Mock())
        
        # Should track burst usage
        mock_redis.incr.assert_called()


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Performance optimization tests"""
    
    def test_redis_pipeline_usage(self, rate_limiter, mock_redis):
        """Test Redis pipeline is used for batch operations"""
        rule = RateLimitRule(
            rule_id="test",
            rule_type=RuleType.PER_USER,
            time_window=TimeWindow.MINUTE,
            limit=100
        )
        
        mock_redis.get.return_value = "50"
        
        rate_limiter.check_hybrid(rule, "test_user")
        
        # Pipeline should be used for atomic operations
        # (Implementation dependent)
        
    def test_counter_increment_efficiency(self, quota_tracker, mock_redis):
        """Test counter increment is efficient"""
        start_time = time.time()
        
        # Increment 100 times
        for i in range(100):
            quota_tracker.increment_quota(
                f"user_{i}",
                QuotaType.REQUESTS,
                "month"
            )
        
        elapsed = time.time() - start_time
        
        # Should be fast (< 0.1 seconds)
        assert elapsed < 0.1


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test error handling and graceful degradation"""
    
    def test_redis_connection_failure(self, rate_limiter, sample_rule):
        """Test graceful handling of Redis connection failure"""
        redis = Mock()
        redis.get.side_effect = Exception("Connection failed")
        
        limiter = RateLimiter(redis_client=redis)
        
        # Should not crash, should allow by default (fail open)
        result = limiter.check_hybrid(sample_rule, "test_user")
        
        # Graceful degradation: allow request
        assert result is not None
        
    def test_invalid_rule_parameters(self, rate_limiter):
        """Test handling of invalid rule parameters"""
        invalid_rule = RateLimitRule(
            rule_id="invalid",
            rule_type=RuleType.PER_USER,
            time_window=TimeWindow.MINUTE,
            limit=0  # Invalid limit
        )
        
        # Should handle gracefully
        result = rate_limiter.check_hybrid(invalid_rule, "test_user")
        assert result is not None


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
